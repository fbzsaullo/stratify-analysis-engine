"""
Crosshair Coach Analyzer

Detecta padrões de crosshair placement incorreto baseado nos eventos
CrosshairMoved e PlayerKilled.
"""
from collections import defaultdict

from analyzers.base_analyzer import BaseAnalyzer


class CrosshairCoachAnalyzer(BaseAnalyzer):

    name = "crosshair-coach"
    subscribed_events = ["CrosshairMoved", "RoundEnded"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Estado temporário por partida (limpo a cada round)
        self._crosshair_samples: dict[str, list[float]] = defaultdict(list)

    async def analyze(self, event: dict) -> dict | None:
        event_type = event["event_type"]

        if event_type == "CrosshairMoved":
            return await self._process_crosshair_moved(event)

        if event_type == "RoundEnded":
            return await self._process_round_ended(event)

        return None

    async def _process_crosshair_moved(self, event: dict) -> dict | None:
        """Acumula amostras de offset vertical da mira."""
        player_id = event.get("player_id")
        payload = event.get("payload", {})
        offset = payload.get("crosshair_offset_degrees", 0)

        if player_id:
            self._crosshair_samples[player_id].append(offset)

        return None  # Feedback gerado apenas no fim do round

    async def _process_round_ended(self, event: dict) -> dict | None:
        """Analisa as amostras acumuladas e gera feedback se necessário."""
        match_id = event.get("match_id")
        results = []

        for player_id, samples in self._crosshair_samples.items():
            if len(samples) < 20:
                continue

            avg_offset = sum(samples) / len(samples)
            low_crosshair_pct = sum(1 for s in samples if s < -5) / len(samples)

            if low_crosshair_pct > 0.60:
                results.append({
                    "player_id": player_id,
                    "feedback": {
                        "severity": "warning",
                        "category": "aim",
                        "title": f"Crosshair baixo em {int(low_crosshair_pct * 100)}% das amostras",
                        "description": (
                            f"Sua mira estava abaixo de -5° em {int(low_crosshair_pct * 100)}% "
                            f"das posições registradas neste round. "
                            f"Offset médio: {avg_offset:.1f}°."
                        ),
                        "actionable_tip": (
                            "Mantenha a crosshair na altura da cabeça ao aproximar-se de ângulos. "
                            "Pratique no mapa 'Aim Botz' focando em pre-aim."
                        ),
                        "confidence_score": min(0.95, 0.60 + len(samples) / 500),
                    },
                })

        # Reset para o próximo round
        self._crosshair_samples.clear()

        # Retorna o primeiro feedback gerado (por simplicidade no MVP)
        if results:
            return results[0]["feedback"]
        return None
