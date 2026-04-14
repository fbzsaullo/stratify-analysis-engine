"""Anti-Noob Detector — detecta padrões recorrentes de baixa proficiência."""
from analyzers.base_analyzer import BaseAnalyzer

SPRAY_DISTANCE_THRESHOLD = 750.0  # unidades do CS2
SPRAY_RATE_THRESHOLD = 0.60       # 60% das mortes em spray longo


class AntiNoobDetectorAnalyzer(BaseAnalyzer):
    name = "anti-noob-detector"
    subscribed_events = ["PlayerKilled", "MatchEnded"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kill_log: dict[str, list[dict]] = {}

    async def analyze(self, event: dict) -> dict | None:
        if event["event_type"] == "PlayerKilled":
            return await self._log_kill(event)
        if event["event_type"] == "MatchEnded":
            return await self._detect_spray_noob(event)
        return None

    async def _log_kill(self, event: dict) -> dict | None:
        payload = event.get("payload", {})
        killer_id = payload.get("killer_id")
        if not killer_id:
            return None

        if killer_id not in self._kill_log:
            self._kill_log[killer_id] = []

        self._kill_log[killer_id].append({
            "weapon": payload.get("weapon"),
            "distance": payload.get("distance_units", 0),
            "is_headshot": payload.get("is_headshot", False),
        })
        return None

    async def _detect_spray_noob(self, event: dict) -> dict | None:
        for player_id, kills in self._kill_log.items():
            rifle_kills = [k for k in kills if k["weapon"] in ("ak47", "m4a1", "m4a1_silencer")]
            if len(rifle_kills) < 5:
                continue

            long_spray = [k for k in rifle_kills if k["distance"] > SPRAY_DISTANCE_THRESHOLD]
            rate = len(long_spray) / len(rifle_kills)

            if rate >= SPRAY_RATE_THRESHOLD:
                self._kill_log.clear()
                return {
                    "severity": "error",
                    "category": "aim",
                    "title": f"Spray fora do alcance em {int(rate * 100)}% das mortes com rifle",
                    "description": (
                        f"Em {len(long_spray)} de {len(rifle_kills)} kills com rifle, "
                        f"a distância era >{int(SPRAY_DISTANCE_THRESHOLD)} unidades. "
                        "Rifles têm acurácia efetiva até ~500u em burst, ~300u em spray."
                    ),
                    "actionable_tip": (
                        "Use burst de 3-4 tiros em distâncias médias. "
                        "Para distâncias longas, 1 tiro por vez (tap) ou troque para AWP/Scout."
                    ),
                    "confidence_score": 0.89,
                }
        self._kill_log.clear()
        return None
