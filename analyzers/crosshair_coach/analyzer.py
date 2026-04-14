"""
Crosshair Coach Analyzer

ROADMAP Phase 2 metrics:
  1. Crosshair Z-Axis Average    — altura média da mira vs cabeça do oponente (já implementado)
  2. Flick vs. Tracking Ratio    — estilo de correção de mira em duelos (NOVO)
"""
from collections import defaultdict
from analyzers.base_analyzer import BaseAnalyzer

LOW_CROSSHAIR_THRESHOLD_DEG = -5.0   # graus abaixo da cabeça
LOW_CROSSHAIR_RATE = 0.60            # 60% das amostras abaixo

FLICK_VELOCITY_THRESHOLD = 15.0      # delta graus/sample para classificar como flick
MIN_SAMPLES = 20


class CrosshairCoachAnalyzer(BaseAnalyzer):

    name = "crosshair-coach"
    subscribed_events = ["CrosshairMoved", "RoundEnded"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._samples: dict[str, list[float]] = defaultdict(list)
        self._prev_offset: dict[str, float] = {}

    async def analyze(self, event: dict) -> dict | None:
        etype = event["event_type"]

        if etype == "CrosshairMoved":
            return await self._process_crosshair_moved(event)
        if etype == "RoundEnded":
            return await self._process_round_ended(event)
        return None

    async def _process_crosshair_moved(self, event: dict) -> dict | None:
        player_id = event.get("player_id")
        payload = event.get("payload", {})
        offset = payload.get("crosshair_offset_degrees", 0)

        if player_id:
            self._samples[player_id].append(offset)
            self._prev_offset[player_id] = offset

        return None

    async def _process_round_ended(self, event: dict) -> dict | None:
        results = []

        for player_id, samples in self._samples.items():
            if len(samples) < MIN_SAMPLES:
                continue

            # ── Metric 1: Crosshair Z-Axis (height) ─────────────────────
            avg_offset = sum(samples) / len(samples)
            low_rate = sum(1 for s in samples if s < LOW_CROSSHAIR_THRESHOLD_DEG) / len(samples)

            if low_rate > LOW_CROSSHAIR_RATE:
                results.append({
                    "severity": "warning",
                    "category": "aim",
                    "title": f"Crosshair baixo em {int(low_rate * 100)}% das amostras",
                    "description": (
                        f"Sua mira estava abaixo de {LOW_CROSSHAIR_THRESHOLD_DEG}° em "
                        f"{int(low_rate * 100)}% das posições registradas neste round. "
                        f"Offset médio: {avg_offset:.1f}°."
                    ),
                    "actionable_tip": (
                        "Mantenha a crosshair na altura da cabeça ao aproximar-se de ângulos. "
                        "Pratique no mapa 'Aim Botz' focando em pre-aim."
                    ),
                    "confidence_score": min(0.95, 0.60 + len(samples) / 500),
                })
                continue  # Só emite um feedback por round por jogador

            # ── Metric 2: Flick vs. Tracking Ratio ──────────────────────
            deltas = [abs(samples[i] - samples[i - 1]) for i in range(1, len(samples))]
            if not deltas:
                continue

            flick_count = sum(1 for d in deltas if d >= FLICK_VELOCITY_THRESHOLD)
            tracking_count = len(deltas) - flick_count
            flick_ratio = flick_count / len(deltas)

            if flick_ratio > 0.75:
                results.append({
                    "severity": "info",
                    "category": "aim",
                    "title": f"Estilo Flick detectado em {int(flick_ratio * 100)}% dos movimentos",
                    "description": (
                        f"Sua mira apresentou movimentos bruscos (flick) em {int(flick_ratio * 100)}% "
                        "das amostras. Jogadores de alto nível variam entre flick e tracking conforme a situação."
                    ),
                    "actionable_tip": (
                        "Para inimigos parados ou lentos, use tracking suave. "
                        "Para duelos rápidos de ângulo, flick com counter-strafe é mais eficiente. "
                        "Pratique ambos no 'Workshop: AIMTASTIC'."
                    ),
                    "confidence_score": 0.72,
                })
            elif flick_ratio < 0.25 and avg_offset < -3:
                results.append({
                    "severity": "info",
                    "category": "aim",
                    "title": "Estilo Tracking, mas mira consistentemente baixa",
                    "description": (
                        "Você usa tracking suave (bom!), mas a trajetória da mira fica "
                        f"sistematicamente baixa (avg offset: {avg_offset:.1f}°). "
                        "Isso sugere que seu crosshair placement começa no lugar errado."
                    ),
                    "actionable_tip": (
                        "Ajuste a posição inicial da sua mira para a altura da cabeça antes de cada ângulo. "
                        "A velocidade do flick não importa se o ponto de partida está errado."
                    ),
                    "confidence_score": 0.68,
                })

        self._samples.clear()
        self._prev_offset.clear()

        return results[0] if results else None
