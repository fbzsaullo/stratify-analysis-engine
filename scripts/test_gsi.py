import json
import http.client
import time
import os

def test_gsi_connection():
    payload = {
        "provider": {"name": "Counter-Strike 2", "appid": 730},
        "map": {"name": "de_dust2", "mode": "competitive"},
        "player": {
            "steamid": "76561198000000001",
            "name": "QA_Tester",
            "state": {"health": 100, "armor": 100},
            "weapons": {
                "weapon_0": {"name": "weapon_ak47", "state": "reloading"}
            }
        }
    }

    # Internal Docker target or external localhost
    bridge_host = os.environ.get("GSI_BRIDGE_HOST", "localhost")
    bridge_port = int(os.environ.get("GSI_BRIDGE_PORT", 3000))

    print("🧪 Starting GSI Connectivity Test...")
    print(f"Connecting to GSI Bridge at {bridge_host}:{bridge_port}...")
    
    try:
        conn = http.client.HTTPConnection(bridge_host, bridge_port, timeout=5)
        headers = {'Content-type': 'application/json'}
        json_data = json.dumps(payload)
        
        start_time = time.time()
        conn.request("POST", "/gsi", json_data, headers)
        response = conn.getresponse()
        elapsed = time.time() - start_time
        
        if response.status == 200:
            print(f"✅ SUCCESS! Bridge responded in {elapsed:.3f}s")
            print("Check the 'GSI Bridge Logs' in stratify.sh to see the processed event.")
        else:
            print(f"❌ FAILED: Bridge returned status {response.status}")
            
        conn.close()
    except Exception as e:
        print(f"❌ ERROR: Could not connect to Bridge. Is it running?")
        print(f"Details: {e}")

if __name__ == "__main__":
    test_gsi_connection()
