"""
CDSI Kafka Communication — High-volume telemetry transport.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Awaitable, Dict

import structlog

from comms.interface import CommInterface
from config.settings import get_settings

logger = structlog.get_logger(__name__)


class KafkaComm(CommInterface):
    """
    Kafka producer/consumer transport for high-volume telemetry.
    Uses confluent-kafka with async wrappers.
    """

    def __init__(self, bootstrap_servers: str | None = None):
        settings = get_settings()
        self._bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer = None
        self._consumer = None
        self._subscribers: Dict[str, list[Callable]] = {}
        self._connected = False
        self._listen_task: asyncio.Task | None = None

    async def connect(self) -> None:
        try:
            from confluent_kafka import Producer, Consumer

            self._producer = Producer({
                "bootstrap.servers": self._bootstrap,
                "queue.buffering.max.messages": 100000,
                "queue.buffering.max.ms": 50,
                "batch.num.messages": 1000,
            })

            self._consumer = Consumer({
                "bootstrap.servers": self._bootstrap,
                "group.id": "cdsi-agents",
                "auto.offset.reset": "latest",
                "enable.auto.commit": True,
            })

            self._connected = True
            logger.info("kafka.connected", bootstrap=self._bootstrap)
        except ImportError:
            logger.warning("kafka.not_available", reason="confluent-kafka not installed")
            self._connected = False
        except Exception as e:
            logger.warning("kafka.connect_failed", error=str(e))
            self._connected = False

    async def disconnect(self) -> None:
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
        if self._producer:
            self._producer.flush(timeout=5)
        if self._consumer:
            self._consumer.close()
        logger.info("kafka.disconnected")

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if not self._producer:
            raise RuntimeError("Kafka producer not connected")
        payload = json.dumps(message).encode("utf-8")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._producer.produce, topic, payload
        )
        self._producer.poll(0)

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._subscribers.setdefault(topic, []).append(callback)
        if self._consumer:
            topics = list(self._subscribers.keys())
            self._consumer.subscribe(topics)
            if not self._listen_task or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._consume_loop())

    async def unsubscribe(self, topic: str) -> None:
        self._subscribers.pop(topic, None)

    async def request(
        self, target: str, method: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise NotImplementedError("Use gRPC for RPC-style requests")

    def is_connected(self) -> bool:
        return self._connected

    async def _consume_loop(self) -> None:
        """Background loop consuming Kafka messages."""
        loop = asyncio.get_event_loop()
        while self._connected and self._consumer:
            try:
                msg = await loop.run_in_executor(
                    None, self._consumer.poll, 0.1
                )
                if msg is None:
                    await asyncio.sleep(0.01)
                    continue
                if msg.error():
                    logger.error("kafka.consume_error", error=str(msg.error()))
                    continue

                topic = msg.topic()
                message = json.loads(msg.value().decode("utf-8"))
                for cb in self._subscribers.get(topic, []):
                    asyncio.create_task(cb(message))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("kafka.consume_error")
                await asyncio.sleep(1)
