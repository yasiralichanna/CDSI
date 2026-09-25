"""
CDSI Wazuh Integration — Connects to Wazuh SIEM for alert ingestion.
"""
from __future__ import annotations

import asyncio
import ssl
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import httpx
import structlog

from config.settings import get_settings
from ingestion.normalizer import EventNormalizer, NormalizedEvent

logger = structlog.get_logger(__name__)


class WazuhClient:
    """Wazuh API client for real-time alert ingestion."""

    def __init__(self):
        settings = get_settings()
        self._api_url = settings.wazuh_api_url
        self._user = settings.wazuh_api_user
        self._password = settings.wazuh_api_password
        self._token: Optional[str] = None
        self._normalizer = EventNormalizer()

    async def authenticate(self) -> bool:
        """Authenticate with Wazuh API."""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    f"{self._api_url}/security/user/authenticate",
                    auth=(self._user, self._password),
                )
                if response.status_code == 200:
                    self._token = response.json().get("data", {}).get("token")
                    logger.info("wazuh.authenticated")
                    return True
        except Exception as e:
            logger.warning("wazuh.auth_failed", error=str(e))
        return False

    async def get_alerts(
        self,
        limit: int = 100,
        offset: int = 0,
        level_min: int = 3,
    ) -> List[NormalizedEvent]:
        """Fetch recent alerts from Wazuh."""
        if not self._token:
            await self.authenticate()

        headers = {"Authorization": f"Bearer {self._token}"}
        params = {"limit": limit, "offset": offset, "level": f"{level_min}+"}

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self._api_url}/alerts",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                alerts = response.json().get("data", {}).get("affected_items", [])
                return [self._normalizer.normalize_wazuh(a) for a in alerts]
        except Exception as e:
            logger.error("wazuh.fetch_failed", error=str(e))
            return []

    async def stream_alerts(
        self,
        poll_interval: float = 5.0,
        level_min: int = 3,
    ) -> AsyncIterator[NormalizedEvent]:
        """Stream alerts in real-time via polling."""
        last_offset = 0
        while True:
            alerts = await self.get_alerts(limit=50, offset=last_offset, level_min=level_min)
            for alert in alerts:
                yield alert
                last_offset += 1
            await asyncio.sleep(poll_interval)
