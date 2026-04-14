"""Round IQ Analyzer — placeholder skeleton."""
from analyzers.base_analyzer import BaseAnalyzer


class RoundIQAnalyzer(BaseAnalyzer):
    name = "round-iq-analyzer"
    subscribed_events = ["PlayerKilled", "RoundEnded", "PlayerPositioned"]

    async def analyze(self, event: dict) -> dict | None:
        # TODO: Implement round decision quality scoring
        # See: /features/round-iq-analyzer/README.md
        return None
