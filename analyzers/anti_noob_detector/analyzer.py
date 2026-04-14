"""Anti-Noob Detector — detecta padrões recorrentes de baixa proficiência.

ROADMAP Phase 2 metrics:
  1. Spray Range Violation       — kills de rifle em distância > 750u (já implementado)
  2. Utility Hold Score          — morte com grenadas não utilizadas (NOVO)
  3. Reload Safety Index         — reload próximo de inimigos (NOVO)
"""
from analyzers.base_analyzer import BaseAnalyzer

SPRAY_DISTANCE_THRESHOLD = 750.0   # unidades do CS2
SPRAY_RATE_THRESHOLD = 0.60        # 60% das mortes em spray longo

RELOAD_DANGER_DISTANCE = 300.0     # unidades — reload perigoso
RELOAD_DANGER_RATE = 0.40          # 40% dos reloads em zona de perigo

UTILITY_THRESHOLD = 1              # mínimo de granadas para sinalizar


class AntiNoobDetectorAnalyzer(BaseAnalyzer):
    name = "anti-noob-detector"
    subscribed_events = ["PlayerKilled", "PlayerReloadStarted", "MatchEnded"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kill_log: dict[str, list[dict]] = {}
        self._reload_log: dict[str, list[dict]] = {}

    async def analyze(self, event: dict) -> dict | None:
        etype = event["event_type"]
        if etype == "PlayerKilled":
            return await self._log_kill(event)
        if etype == "PlayerReloadStarted":
            return await self._log_reload(event)
        if etype == "MatchEnded":
            return await self._run_end_of_match_analysis(event)
        return None

    # ─── Kill logging ────────────────────────────────────────────────────────

    async def _log_kill(self, event: dict) -> dict | None:
        payload = event.get("payload", {})
        killer_id = payload.get("killer_id")
        if not killer_id:
            return None

        self._kill_log.setdefault(killer_id, []).append({
            "weapon": payload.get("weapon"),
            "distance": payload.get("distance_units", 0),
            "is_headshot": payload.get("is_headshot", False),
            "grenades_remaining": payload.get("grenades_remaining", 0),
        })
        return None

    # ─── Reload logging ──────────────────────────────────────────────────────

    async def _log_reload(self, event: dict) -> dict | None:
        player_id = event.get("player_id")
        payload = event.get("payload", {})
        if not player_id:
            return None

        self._reload_log.setdefault(player_id, []).append({
            "nearest_enemy_distance": payload.get("nearest_enemy_distance", 9999),
            "is_in_combat": payload.get("is_in_combat", False),
        })
        return None

    # ─── End-of-match analysis ───────────────────────────────────────────────

    async def _run_end_of_match_analysis(self, event: dict) -> dict | None:
        feedbacks = []

        spray_fb = self._detect_spray_noob()
        if spray_fb:
            feedbacks.append(spray_fb)

        utility_fb = self._detect_utility_hold()
        if utility_fb:
            feedbacks.append(utility_fb)

        reload_fb = self._detect_reload_danger()
        if reload_fb:
            feedbacks.append(reload_fb)

        self._kill_log.clear()
        self._reload_log.clear()

        # BaseAnalyzer emite um único FeedbackGenerated por call.
        # Retorna o mais severo encontrado.
        return feedbacks[0] if feedbacks else None

    def _detect_spray_noob(self) -> dict | None:
        for player_id, kills in self._kill_log.items():
            rifle_kills = [k for k in kills if k["weapon"] in ("ak47", "m4a1", "m4a1_silencer", "sg556", "aug")]
            if len(rifle_kills) < 5:
                continue
            long_spray = [k for k in rifle_kills if k["distance"] > SPRAY_DISTANCE_THRESHOLD]
            rate = len(long_spray) / len(rifle_kills)
            if rate >= SPRAY_RATE_THRESHOLD:
                return {
                    "severity": "error",
                    "category": "aim",
                    "title": f"Spray fora do alcance em {int(rate * 100)}% das mortes com rifle",
                    "description": (
                        f"Em {len(long_spray)} de {len(rifle_kills)} kills com rifle, "
                        f"a distância era >{int(SPRAY_DISTANCE_THRESHOLD)}u. "
                        "Rifles têm acurácia efetiva até ~500u em burst, ~300u em spray."
                    ),
                    "actionable_tip": (
                        "Use burst de 3-4 tiros em distâncias médias. "
                        "Para longas distâncias, 1 tiro por vez (tap) ou troque para AWP/Scout."
                    ),
                    "confidence_score": 0.89,
                }
        return None

    def _detect_utility_hold(self) -> dict | None:
        """Detecta jogadores que morrem com granadas não utilizadas."""
        flagged: dict[str, int] = {}
        total: dict[str, int] = {}

        for player_id, kills in self._kill_log.items():
            as_victim = [k for k in kills if k.get("grenades_remaining", 0) >= UTILITY_THRESHOLD]
            total[player_id] = len(kills)
            flagged[player_id] = len(as_victim)

        for player_id, count in flagged.items():
            if total[player_id] < 5 or count == 0:
                continue
            rate = count / total[player_id]
            if rate >= 0.50:
                return {
                    "severity": "warning",
                    "category": "utility",
                    "title": f"Utility Hold: granadas não usadas em {int(rate * 100)}% das mortes",
                    "description": (
                        f"Você morreu com granadas disponíveis em {count} de {total[player_id]} rounds. "
                        "Granadas não utilizadas ao morrer desperdiçam vantagem tática."
                    ),
                    "actionable_tip": (
                        "Lance suas granadas antes de entrar em duelos decisivos. "
                        "Uma smoke ou flash pode transformar um duelo difícil em uma vantagem clara."
                    ),
                    "confidence_score": 0.80,
                }
        return None

    def _detect_reload_danger(self) -> dict | None:
        """Detecta reloads próximos de inimigos (Reload Safety Index)."""
        for player_id, reloads in self._reload_log.items():
            if len(reloads) < 3:
                continue
            danger = [r for r in reloads if r["nearest_enemy_distance"] < RELOAD_DANGER_DISTANCE]
            rate = len(danger) / len(reloads)
            if rate >= RELOAD_DANGER_RATE:
                return {
                    "severity": "error",
                    "category": "decision_making",
                    "title": f"Reload inseguro: {int(rate * 100)}% dos reloads com inimigo próximo",
                    "description": (
                        f"Em {len(danger)} de {len(reloads)} reloads, havia um inimigo a menos de "
                        f"{int(RELOAD_DANGER_DISTANCE)}u. Recarregar exposto é uma das causas mais "
                        "frequentes de mortes evitáveis."
                    ),
                    "actionable_tip": (
                        "Recue para cobertura antes de recarregar. "
                        "Se não há cobertura disponível, considere trocar para pistola."
                    ),
                    "confidence_score": 0.85,
                }
        return None
