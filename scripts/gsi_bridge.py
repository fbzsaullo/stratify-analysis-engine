import os
import json
import time
import redis
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6381/0")
STREAM_KEY = "stratify:events"
PORT = 3000

# Cache para detectar mudanças de estado
last_log_time = 0
player_state_cache = {}

class GSIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global last_log_time
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))

        # Log Throttling (1Hz)
        current_time = time.time()
        if current_time - last_log_time > 1.0:
            player_name = payload.get('player', {}).get('name', 'Unknown')
            map_name = payload.get('map', {}).get('name', 'Menu/None')
            print(f"📥 [GSI] Listening: {player_name} @ {map_name}")
            last_log_time = current_time

        # Processar Eventos Inteligentes
        events = self.map_gsi_to_stratify(payload)
        
        for event in events:
            self.publish_to_redis(event)

        self.send_response(200)
        self.end_headers()

    def map_gsi_to_stratify(self, data):
        """Converte dados brutos do GSI em eventos semânticos para o Stratify."""
        events = []
        player = data.get('player', {})
        steamid = player.get('steamid', 'real_player')
        map_name = data.get('map', {}).get('name', 'real_match')
        
        # 1. Registro de Mudança de Estado (GameStateUpdate básico)
        if 'state' in player:
            events.append({
                "event_id": f"gsu_{time.time()}",
                "event_type": "GameStateUpdate",
                "match_id": map_name,
                "player_id": steamid,
                "payload": player['state']
            })

        # 2. Detecção de Recarga (Reload)
        # Verificamos se alguma arma entrou no estado 'reloading'
        weapons = player.get('weapons', {})
        is_reloading = any(w.get('state') == 'reloading' for w in weapons.values())
        
        prev_state = player_state_cache.get(steamid, {})
        was_reloading = prev_state.get('is_reloading', False)

        if is_reloading and not was_reloading:
            print(f" 🔥 [EVENT] Player {steamid} started reloading!")
            events.append({
                "event_id": f"rel_{time.time()}",
                "event_type": "PlayerReloadStarted",
                "match_id": map_name,
                "player_id": steamid,
                "payload": {
                    "nearest_enemy_distance": 250, # Mock por enquanto, precisa de mais dados da engine
                    "is_in_combat": True
                }
            })

        # 3. Detecção de Morte (PlayerKilled)
        if player.get('state', {}).get('health') == 0 and prev_state.get('health', 100) > 0:
            print(f" 💀 [EVENT] Player {steamid} killed!")
            events.append({
                "event_id": f"kill_{time.time()}",
                "event_type": "PlayerKilled",
                "match_id": map_name,
                "player_id": steamid,
                "payload": {
                    "killer_id": "enemy",
                    "weapon": "ak47",
                    "distance_units": 450
                }
            })

        # Atualizar Cache
        player_state_cache[steamid] = {
            "is_reloading": is_reloading,
            "health": player.get('state', {}).get('health', 100)
        }

        return events

    def publish_to_redis(self, event):
        try:
            r = redis.Redis.from_url(REDIS_URL)
            r.xadd(STREAM_KEY, {"data": json.dumps(event)})
        except Exception as e:
            print(f" [ERROR] Redis sync failed: {e}")

    def log_message(self, format, *args):
        return

def run(server_class=HTTPServer, handler_class=GSIHandler):
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    print(f"🚀 [GSI Bridge] Listening on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GSI Bridge...")
        httpd.server_close()

if __name__ == "__main__":
    run()
