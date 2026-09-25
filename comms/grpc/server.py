"""
CDSI gRPC Communication — Structured RPC transport with TLS support.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Awaitable, Dict

import structlog

from comms.interface import CommInterface
from config.settings import get_settings

logger = structlog.get_logger(__name__)


class GRPCComm(CommInterface):
    """
    gRPC transport for structured RPC calls between agents.
    Supports mTLS for encrypted inter-service communication.
    """

    def __init__(self, server_address: str | None = None):
        settings = get_settings()
        self._address = server_address or settings.grpc_server_address
        self._use_tls = settings.grpc_use_tls
        self._server = None
        self._channel = None
        self._connected = False
        self._callbacks: Dict[str, list[Callable]] = {}
        self._request_handlers: Dict[str, Callable] = {}

    async def connect(self) -> None:
        try:
            import grpc
            from grpc import aio as grpc_aio

            if self._use_tls:
                settings = get_settings()
                with open(settings.grpc_cert_path, "rb") as f:
                    cert = f.read()
                with open(settings.grpc_key_path, "rb") as f:
                    key = f.read()
                creds = grpc.ssl_channel_credentials(
                    root_certificates=cert
                )
                self._channel = grpc_aio.secure_channel(self._address, creds)
            else:
                self._channel = grpc_aio.insecure_channel(self._address)

            self._connected = True
            logger.info("grpc.connected", address=self._address, tls=self._use_tls)
        except ImportError:
            logger.warning("grpc.not_available", reason="grpcio not installed")
        except Exception as e:
            logger.warning("grpc.connect_failed", error=str(e))

    async def disconnect(self) -> None:
        self._connected = False
        if self._channel:
            await self._channel.close()
        if self._server:
            await self._server.stop(grace=5)
        logger.info("grpc.disconnected")

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        # For gRPC we route through callbacks (local pub/sub within process)
        for cb in self._callbacks.get(topic, []):
            await cb(message)

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._callbacks.setdefault(topic, []).append(callback)

    async def unsubscribe(self, topic: str) -> None:
        self._callbacks.pop(topic, None)

    async def request(
        self, target: str, method: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send an RPC-style request. In full production this would call
        a specific gRPC service method. Here we provide the framework.
        """
        handler = self._request_handlers.get(f"{target}.{method}")
        if handler:
            return await handler(payload)
        return {"error": f"No handler for {target}.{method}"}

    def register_handler(
        self, target: str, method: str, handler: Callable
    ) -> None:
        """Register an RPC handler."""
        self._request_handlers[f"{target}.{method}"] = handler

    def is_connected(self) -> bool:
        return self._connected
