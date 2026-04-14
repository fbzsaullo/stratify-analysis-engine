"""
Base Analyzer — Classe pai de todos os analyzers do Stratify.

Para criar um novo analyzer, herde desta classe e implemente:
  - subscribed_events: list[str]
  - analyze(event: dict) -> dict | None
"""
import abc
import os
import uuid
from datetime import datetime, timezone
import structlog

from shared.event_bus import EventBus

log = structlog.get_logger()


class BaseAnalyzer(abc.ABC):
    """
    Analyzer base. Gerencia a conexão com o Event Bus,
    a filtragem de eventos relevantes e o ACK após processamento.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Nome único do analyzer (ex: 'crosshair-coach')"""
        ...

    @property
    @abc.abstractmethod
    def subscribed_events(self) -> list[str]:
        """Lista de event_types que este analyzer deve processar."""
        ...

    @abc.abstractmethod
    async def analyze(self, event: dict) -> dict | None:
        """
        Processa um evento e opcionalmente retorna um FeedbackGenerated payload.
        Retorne None se nenhum feedback deve ser gerado para este evento.
        """
        ...

    def __init__(self, redis_url: str):
        self._bus = EventBus(redis_url=redis_url)
        self._group_name = f"{self.name}-group"
        self._consumer_name = f"{self.name}-{os.getpid()}"

    async def run(self):
        """Inicia o loop de consumo de eventos."""
        await self._bus.connect()
        log.info("analyzer_running", analyzer=self.name, events=self.subscribed_events)

        async for msg_id, event in self._bus.consume(
            group_name=self._group_name,
            consumer_name=self._consumer_name,
        ):
            event_type = event.get("event_type")

            if event_type not in self.subscribed_events:
                await self._bus.ack(self._group_name, msg_id)
                continue

            try:
                feedback_payload = await self.analyze(event)
                if feedback_payload:
                    await self._emit_feedback(event, feedback_payload)
            except Exception as e:
                log.error("analyzer_error", analyzer=self.name, event_type=event_type, error=str(e))
            finally:
                await self._bus.ack(self._group_name, msg_id)

    async def _emit_feedback(self, source_event: dict, payload: dict):
        """Publica um FeedbackGenerated event no bus."""
        feedback = {
            "event_type": "FeedbackGenerated",
            "schema_version": "1.0",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "match_id": source_event.get("match_id"),
            "player_id": source_event.get("player_id"),
            "game": source_event.get("game", "cs2"),
            "payload": {
                "analyzer": self.name,
                **payload,
            },
        }
        await self._bus.publish_feedback(feedback)
        log.info("feedback_emitted", analyzer=self.name, title=payload.get("title"))
