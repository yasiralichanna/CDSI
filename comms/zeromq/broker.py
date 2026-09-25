"""
CDSI ZeroMQ Communication — Fast P2P pub/sub transport.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Awaitable, Dict

import zmq
import zmq.asyncio
import structlog

from comms.interface import CommInterface
from config.settings import get_settings

logger = structlog.get_logger(__name__)


class ZeroMQComm(CommInterface):
    """
    ZeroMQ PUB/SUB transport for fast inter-agent messaging.
    Uses XPUB/XSUB proxy pattern for many-to-many communication.
    """

    def __init__(
        self,
        pub_address: str | None = None,
        sub_address: str | None = None,
    ):
        settings = get_settings()
        self._pub_address = pub_address or settings.zmq_pub_address
        self._sub_address = sub_address or settings.zmq_sub_address
        self._ctx: zmq.asyncio.Context | None = None
        self._pub_socket: zmq.asyncio.Socket | None = None
        self._sub_socket: zmq.asyncio.Socket | None = None
        self._subscribers: Dict[str, list[Callable]] = {}
        self._connected = False
        self._relay_enabled = False
        self._listen_task: asyncio.Task | None = None

    async def connect(self, bind_pub: bool = False, bind_sub: bool = False, relay_enabled: bool = False) -> None:
        self._ctx = zmq.asyncio.Context()
        self._relay_enabled = relay_enabled

        self._pub_socket = self._ctx.socket(zmq.PUB)
        if bind_pub:
            self._pub_socket.bind(self._pub_address)
        else:
            # Spoke: Connect its PUB to the Hub's SUB address
            self._pub_socket.connect(self._sub_address.replace("*", "localhost"))

        self._sub_socket = self._ctx.socket(zmq.SUB)
        if bind_sub:
            self._sub_socket.bind(self._sub_address)
        else:
            # Spoke: Connect its SUB to the Hub's PUB address
            self._sub_socket.connect(self._pub_address.replace("*", "localhost"))

        self._connected = True
        
        # If we are the Hub (bind_sub) and relay is enabled, 
        # we MUST subscribe to everything to be able to relay it.
        if bind_sub and self._relay_enabled:
            self._sub_socket.subscribe(b"")
            logger.info("zmq.relay_subscribed_all")

        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info("zmq.connected", pub=self._pub_address, sub=self._sub_address, bind_pub=bind_pub, bind_sub=bind_sub)

    async def disconnect(self) -> None:
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
        if self._pub_socket:
            self._pub_socket.close()
        if self._sub_socket:
            self._sub_socket.close()
        if self._ctx:
            self._ctx.term()
        logger.info("zmq.disconnected")

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if not self._pub_socket:
            raise RuntimeError("ZMQ not connected")
        payload = json.dumps(message).encode("utf-8")
        await self._pub_socket.send_multipart([topic.encode("utf-8"), payload])

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        if not self._sub_socket:
            raise RuntimeError("ZMQ not connected")
        self._sub_socket.subscribe(topic.encode("utf-8"))
        self._subscribers.setdefault(topic, []).append(callback)
        logger.info("zmq.subscribed", topic=topic)

    async def unsubscribe(self, topic: str) -> None:
        if self._sub_socket:
            self._sub_socket.unsubscribe(topic.encode("utf-8"))
        self._subscribers.pop(topic, None)

    async def request(
        self, target: str, method: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        # ZMQ PUB/SUB doesn't support RPC — use gRPC for that
        raise NotImplementedError("Use gRPC for RPC-style requests")

    def is_connected(self) -> bool:
        return self._connected

    async def _listen_loop(self) -> None:
        """Background loop dispatching incoming messages to subscribers."""
        while self._connected and self._sub_socket:
            try:
                # Use multipart to get topic and message separately
                parts = await self._sub_socket.recv_multipart()
                if len(parts) == 2:
                    topic_bytes = parts[0]
                    msg_bytes = parts[1]
                    topic_str = topic_bytes.decode("utf-8")
                    payload = json.loads(msg_bytes.decode("utf-8"))
                    
                    # Relay logic: If relay is enabled, re-publish received messages to the PUB socket
                    if self._relay_enabled:
                        logger.debug("zmq.relaying", topic=topic_str)
                        await self._pub_socket.send_multipart([topic_bytes, msg_bytes])

                    for cb in self._subscribers.get(topic_str, []):
                        asyncio.create_task(cb(payload))
            except zmq.ZMQError as e:
                if self._connected:
                    logger.exception("zmq.recv_error", error=str(e))
                # If ZMQError occurs and we are still connected, it might be a recoverable error
                # or a socket issue. Breaking the loop might be too aggressive if it's transient.
                # For now, keep the original behavior of breaking on ZMQError.
                break
            except asyncio.CancelledError:
                break
            except Exception as e: # Catch other potential errors during decoding or callback
                if self._connected:
                    logger.error("zmq.processing_error", error=str(e))
                await asyncio.sleep(0.1) # Prevent busy-loop on continuous errors

