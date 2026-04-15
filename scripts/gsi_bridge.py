import os
import json
import time
import redis
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6381/0")
STREAM_KEY = "stratify:events"
PORT = 3000

last_log_time = 0

class GSIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global last_log_time
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))

        # Log Throttling: Envia log apenas 1 vez por segundo
        current_time = time.time()
        if current_time - last_log_time > 1.0:
            player_name = payload.get('player', {}).get('name', 'Unknown')
            map_name = payload.get('map', {}).get('name', 'Menu/None')
            print(f"📥 [GSI] Listening: {player_name} @ {map_name}")
            last_log_time = current_time

        # Map GSI to Stratify Events
        events = self.map_gsi_to_stratify(payload)
        
        for event in events:
            self.publish_to_redis(event)

        self.send_response(200)
        self.end_headers()

    def map_gsi_to_stratify(self, data):
        """Simple mapping logic for the Bridge MVP."""
        events = []
        match_id = data.get('map', {}).get('name', 'real_match')
        player_id = data.get('player', {}).get('steamid', 'real_player')

        if 'player' in data and 'state' in data['player']:
            state = data['player']['state']
            
            # Exemplo: Detecção de Recarga (Reload)
            # No GSI real, olharíamos para o estado da arma.
            # Aqui fazemos um mapeamento simples para fins de demonstração.
            events.append({
                "event_id": str(time.time()),
                "event_type": "GameStateUpdate",
                "match_id": match_id,
                "player_id": player_id,
                "payload": state
            })

        return events

    def publish_to_redis(self, event):
        try:
            r = redis.Redis.from_url(REDIS_URL)
            r.xadd(STREAM_KEY, {"data": json.dumps(event)})
        except Exception as e:
            print(f" [ERROR] Redis sync failed: {e}")

    def log_message(self, format, *args):
        # Silenciando os logs padrão de HTTP 200
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
