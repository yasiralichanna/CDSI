"""
CDSI Communication Interface — Abstract base for all transport backends.

Every transport (ZeroMQ, gRPC, Kafka) implements this interface so agents
and the consensus engine can publish/subscribe without coupling to a
specific protocol.
"""
from __future__ import annotations

import abc
import asyncio
from typing import Any, Callable, Awaitable, Dict, Optional


class CommInterface(abc.ABC):
    """
    Abstract communication interface.

    Concrete implementations: ZeroMQComm, GRPCComm, KafkaComm.
    """

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish connection to the transport."""
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Cleanly close the transport."""
        ...

    @abc.abstractmethod
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish a message to a topic/channel."""
        ...

    @abc.abstractmethod
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Subscribe to a topic with an async callback."""
        ...

    @abc.abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        ...

    @abc.abstractmethod
    async def request(
        self, target: str, method: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send an RPC-style request and await a response."""
        ...

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Return True if the transport is connected."""
        ...


class InMemoryComm(CommInterface):
    """
    In-process pub/sub for local development, testing, and single-node mode.
    No external dependencies — messages go through asyncio queues.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, list[Callable]] = {}
        self._connected = False
        self._message_log: list[Dict[str, Any]] = []

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        self._subscribers.clear()

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        self._message_log.append({"topic": topic, "message": message})
        for cb in self._subscribers.get(topic, []):
            await cb(message)

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._subscribers.setdefault(topic, []).append(callback)

    async def unsubscribe(self, topic: str) -> None:
        self._subscribers.pop(topic, None)

    async def request(
        self, target: str, method: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "ok", "target": target, "method": method}

    def is_connected(self) -> bool:
        return self._connected

    def get_message_log(self) -> list[Dict[str, Any]]:
        """For testing: retrieve all published messages."""
        return self._message_log.copy()
