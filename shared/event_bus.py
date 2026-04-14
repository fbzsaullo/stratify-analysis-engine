"""
Shared/event_bus.py — Abstração do Redis Streams para publicar e consumir eventos.
"""
import json
import redis.asyncio as aioredis
import structlog

log = structlog.get_logger()

STREAM_KEY = "stratify:events"
FEEDBACK_STREAM_KEY = "stratify:feedback"


class EventBus:
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self):
        self._client = await aioredis.from_url(self._redis_url, decode_responses=True)
        log.info("event_bus_connected", url=self._redis_url)

    async def publish(self, stream: str, event: dict) -> str:
        """Publica um evento no stream. Retorna o message ID."""
        msg_id = await self._client.xadd(stream, {"data": json.dumps(event)})
        log.debug("event_published", stream=stream, event_type=event.get("event_type"), msg_id=msg_id)
        return msg_id

    async def publish_feedback(self, feedback: dict) -> str:
        return await self.publish(FEEDBACK_STREAM_KEY, feedback)

    async def consume(
        self,
        group_name: str,
        consumer_name: str,
        stream: str = STREAM_KEY,
        count: int = 10,
        block_ms: int = 5000,
    ):
        """
        Consome eventos de um consumer group.
        Cria o group automaticamente se não existir.
        """
        try:
            await self._client.xgroup_create(stream, group_name, id="0", mkstream=True)
        except Exception:
            pass  # Group já existe

        while True:
            results = await self._client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream: ">"},
                count=count,
                block=block_ms,
            )
            if not results:
                continue

            for _, messages in results:
                for msg_id, fields in messages:
                    try:
                        event = json.loads(fields["data"])
                        yield msg_id, event
                    except json.JSONDecodeError as e:
                        log.error("event_parse_error", msg_id=msg_id, error=str(e))

    async def ack(self, group_name: str, msg_id: str, stream: str = STREAM_KEY):
        """Confirma o processamento de uma mensagem."""
        await self._client.xack(stream, group_name, msg_id)
