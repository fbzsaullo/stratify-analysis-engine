#!/usr/bin/env python3
"""
seed_events.py — Publica eventos simulados de uma partida de CS2 no Redis.

Uso:
    pip install redis
    python scripts/seed_events.py [--redis-url redis://localhost:6379/0]

Este script simula uma partida completa no Redis Streams para validar
o pipeline ponta a ponta localmeente sem precisar de uma demo real.
"""
import json
import uuid
import argparse
import random
from datetime import datetime, timezone, timedelta

import redis
import os

STREAM_KEY = "stratify:events"

MAPS = ["de_dust2", "de_mirage", "de_inferno", "de_nuke", "de_overpass"]
WEAPONS = ["ak47", "m4a1", "m4a1_silencer", "awp", "deagle", "usp_s"]
RIFLE_WEAPONS = ["ak47", "m4a1", "m4a1_silencer", "sg556", "aug"]


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_event(event_type: str, match_id: str, player_id: str, payload: dict) -> dict:
    return {
        "event_type": event_type,
        "schema_version": "1.0",
        "occurred_at": ts(),
        "match_id": match_id,
        "player_id": player_id,
        "game": "cs2",
        "payload": payload,
    }


def publish(r: redis.Redis, event: dict):
    r.xadd(STREAM_KEY, {"data": json.dumps(event)})
    print(f"  → Published: {event['event_type']}")


def simulate_match(r: redis.Redis, match_id: str, player_id: str, num_rounds: int = 12):
    selected_map = random.choice(MAPS)
    print(f"\n🎮 Simulating match {match_id[:8]}... on {selected_map} ({num_rounds} rounds)")

    # MatchStarted
    publish(r, base_event("MatchStarted", match_id, player_id, {
        "map": selected_map,
        "mode": "competitive",
        "max_rounds": 24,
        "team_ct": [player_id],
        "team_t": [str(uuid.uuid4())],
    }))

    for round_num in range(1, num_rounds + 1):
        ct_score = (round_num - 1) // 2
        t_score = round_num - 1 - ct_score

        # RoundStarted
        publish(r, base_event("RoundStarted", match_id, player_id, {
            "round_number": round_num,
            "ct_score": ct_score,
            "t_score": t_score,
            "team_economy": {"ct_money": random.randint(3700, 16000), "t_money": random.randint(1000, 12000)},
        }))

        # CrosshairMoved events (simula 30 amostras por round)
        for _ in range(30):
            # Simula jogador com mira às vezes baixa (offset negativo)
            offset = random.gauss(-3.0, 8.0)
            publish(r, base_event("CrosshairMoved", match_id, player_id, {
                "tick": random.randint(10000, 50000),
                "crosshair_offset_degrees": round(offset, 2),
                "crosshair_pitch": round(random.uniform(-10, 10), 2),
                "crosshair_yaw": round(random.uniform(0, 360), 2),
                "nearest_enemy_distance": round(random.uniform(100, 1200), 1),
                "movement_speed": round(random.uniform(0, 250), 1),
            }))

        # PlayerReloadStarted — às vezes em zona de perigo
        if random.random() > 0.5:
            dangerous = random.random() > 0.4
            publish(r, base_event("PlayerReloadStarted", match_id, player_id, {
                "weapon": random.choice(RIFLE_WEAPONS),
                "ammo_remaining": random.randint(0, 10),
                "nearest_enemy_distance": round(random.uniform(50, 250) if dangerous else random.uniform(400, 1500), 1),
                "is_in_combat": dangerous,
                "player_position": {"x": random.uniform(-2000, 2000), "y": random.uniform(-2000, 2000), "z": 0},
            }))

        # PlayerKilled events (1-2 kills per round, sometimes with grenades)
        num_kills = random.randint(0, 2)
        for _ in range(num_kills):
            weapon = random.choice(WEAPONS)
            distance = random.uniform(100, 1200)
            grenades = random.randint(0, 3) if random.random() > 0.6 else 0

            publish(r, base_event("PlayerKilled", match_id, player_id, {
                "victim_id": str(uuid.uuid4()),
                "killer_id": player_id,
                "weapon": weapon,
                "distance_units": round(distance, 1),
                "is_headshot": random.random() > 0.6,
                "grenades_remaining": grenades,
            }))

        # RoundEnded
        winner = random.choice(["ct", "t"])
        publish(r, base_event("RoundEnded", match_id, player_id, {
            "round_number": round_num,
            "winner": winner,
            "reason": random.choice(["elimination", "bomb_exploded", "bomb_defused"]),
            "ct_score": ct_score + (1 if winner == "ct" else 0),
            "t_score": t_score + (1 if winner == "t" else 0),
            "duration_seconds": round(random.uniform(30, 115), 1),
        }))

    # MatchEnded — triggers end-of-match analysis
    publish(r, base_event("MatchEnded", match_id, player_id, {
        "final_score": {"ct": 13, "t": num_rounds - 13},
        "duration_seconds": num_rounds * 90,
        "map": selected_map,
    }))

    print(f"  ✅ Match simulation complete: {num_rounds} rounds published.")


def main():
    parser = argparse.ArgumentParser(description="Stratify Seed Events Publisher")
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6381/0"))
    parser.add_argument("--matches", type=int, default=3, help="Number of matches to simulate")
    parser.add_argument("--rounds", type=int, default=12, help="Rounds per match")
    args = parser.parse_args()

    r = redis.from_url(args.redis_url, decode_responses=True)
    player_id = "demo_player_76561198000000001"

    print(f"🚀 Stratify Seed Events Publisher")
    print(f"   Redis: {args.redis_url}")
    print(f"   Matches: {args.matches} | Rounds each: {args.rounds}")

    for i in range(args.matches):
        match_id = str(uuid.uuid4())
        simulate_match(r, match_id, player_id, num_rounds=args.rounds)

    print(f"\n🎯 Done! Published {args.matches} simulated matches.")
    print(f"   The Analysis Engine workers should now generate FeedbackGenerated events.")
    print(f"   The Core Backend consumer will ingest them into PostgreSQL.")


if __name__ == "__main__":
    main()
