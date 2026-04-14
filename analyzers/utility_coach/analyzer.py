"""Utility Coach Analyzer — detecta smokes/flashes de baixa efetividade."""
from analyzers.base_analyzer import BaseAnalyzer

EFFECTIVENESS_THRESHOLD = 0.75
MIN_SAMPLES = 3


class UtilityCoachAnalyzer(BaseAnalyzer):
    name = "utility-coach"
    subscribed_events = ["UtilityUsed", "MatchEnded"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._utility_log: dict[str, list[dict]] = {}  # player_id -> list of uses

    async def analyze(self, event: dict) -> dict | None:
        if event["event_type"] == "UtilityUsed":
            return await self._log_utility(event)
        if event["event_type"] == "MatchEnded":
            return await self._summarize(event)
        return None

    async def _log_utility(self, event: dict) -> dict | None:
        player_id = event.get("player_id") or event.get("payload", {}).get("killer_id")
        payload = event.get("payload", {})
        player_id = player_id or "unknown"

        if player_id not in self._utility_log:
            self._utility_log[player_id] = []

        self._utility_log[player_id].append({
            "type": payload.get("utility_type"),
            "effectiveness": payload.get("effectiveness_score", 1.0),
        })
        return None

    async def _summarize(self, event: dict) -> dict | None:
        for player_id, uses in self._utility_log.items():
            smoke_uses = [u for u in uses if u["type"] == "smoke"]
            if len(smoke_uses) < MIN_SAMPLES:
                continue

            avg_eff = sum(u["effectiveness"] for u in smoke_uses) / len(smoke_uses)
            if avg_eff < EFFECTIVENESS_THRESHOLD:
                self._utility_log.clear()
                return {
                    "severity": "warning",
                    "category": "utility",
                    "title": f"Smokes com efetividade média de {int(avg_eff * 100)}%",
                    "description": (
                        f"Em {len(smoke_uses)} smokes lançadas, a cobertura média foi "
                        f"{int(avg_eff * 100)}% (ideal: >{int(EFFECTIVENESS_THRESHOLD * 100)}%). "
                        "Lineups imprecisos reduzem o controle de mapa."
                    ),
                    "actionable_tip": "Memorize 2-3 lineups essenciais por mapa. Pratique no modo offline.",
                    "confidence_score": 0.82,
                }
        self._utility_log.clear()
        return None
