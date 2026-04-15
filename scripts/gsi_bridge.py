import os
import json
import time
import redis
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6381/0")
STREAM_KEY = "stratify:events"
PORT = 3000

class GSIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))

        print(f"Received GSI data from: {payload.get('provider', {}).get('name', 'Unknown')}")

        # Map GSI to Stratify Events
        events = self.map_gsi_to_stratify(payload)
        
        for event in events:
            self.publish_to_redis(event)

        self.send_response(200)
        self.end_headers()

    def map_gsi_to_stratify(self, data):
        """Simple mapping logic for the Bridge MVP."""
        events = []
        match_id = data.get('map', {}).get('name', 'real_match') # Simplified
        player_id = data.get('player', {}).get('steamid', 'real_player')

        # Example: CrosshairMoved simulation (GSI doesn't give raw mouse movement directly, 
        # but we can map player state changes as events)
        if 'player' in data and 'state' in data['player']:
            events.append({
                "event_type": "CrosshairMoved",
                "occurred_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "match_id": match_id,
                "player_id": player_id,
                "payload": {
                    "crosshair_offset_degrees": 0.0, # Placeholder
                    "nearest_enemy_distance": 500.0,  # Placeholder
                }
            })

        # Example: Map reload starts
        weapons = data.get('player', {}).get('weapons', {})
        for w in weapons.values():
            if w.get('state') == 'reloading':
                events.append({
                    "event_type": "PlayerReloadStarted",
                    "occurred_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    "match_id": match_id,
                    "player_id": player_id,
                    "payload": {
                        "weapon": w.get('name'),
                        "nearest_enemy_distance": 200.0, # Reality check placeholder
                        "is_in_combat": True
                    }
                })

        return events

    def publish_to_redis(self, event):
        try:
            r = redis.from_url(REDIS_URL)
            r.xadd(STREAM_KEY, {"data": json.dumps(event)})
            print(f" [OK] Published {event['event_type']} to Redis")
        except Exception as e:
            print(f" [ERROR] Redis sync failed: {e}")

    def log_message(self, format, *args):
        return # Silence logs to keep console clean

def run(server_class=HTTPServer, handler_class=GSIHandler):
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    print(f"🚀 Stratify GSI Bridge running on port {PORT}...")
    print(f"Listening for CS2 events and bridging to Redis at {REDIS_URL}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    run()
