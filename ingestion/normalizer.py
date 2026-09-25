"""
CDSI Event Normalizer — Converts diverse event sources to a common schema.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


class NormalizedEvent:
    """Standardized event schema across all ingestion sources."""

    def __init__(
        self,
        event_id: str,
        timestamp: datetime,
        source: str,
        event_type: str,
        severity: str = "info",
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = None,
        dst_port: Optional[int] = None,
        protocol: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event_id = event_id
        self.timestamp = timestamp
        self.source = source
        self.event_type = event_type
        self.severity = severity
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.protocol = protocol
        self.raw_data = raw_data or {}
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "event_type": self.event_type,
            "severity": self.severity,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class EventNormalizer:
    """Normalizes events from various sources to NormalizedEvent."""

    def normalize_wazuh(self, raw: Dict[str, Any]) -> NormalizedEvent:
        """Normalize Wazuh alert."""
        data = raw.get("data", raw)
        return NormalizedEvent(
            event_id=f"WZH-{hashlib.md5(str(raw).encode()).hexdigest()[:8]}",
            timestamp=datetime.fromisoformat(data.get("timestamp", "")) if data.get("timestamp") else datetime.now(timezone.utc),
            source="wazuh",
            event_type=data.get("rule", {}).get("description", "unknown"),
            severity=self._map_wazuh_level(data.get("rule", {}).get("level", 0)),
            src_ip=data.get("srcip") or data.get("data", {}).get("srcip"),
            dst_ip=data.get("dstip"),
            raw_data=raw,
            metadata={"rule_id": data.get("rule", {}).get("id")},
        )

    def normalize_syslog(self, raw: Dict[str, Any]) -> NormalizedEvent:
        """Normalize syslog event."""
        return NormalizedEvent(
            event_id=f"SYS-{hashlib.md5(str(raw).encode()).hexdigest()[:8]}",
            timestamp=datetime.now(timezone.utc),
            source="syslog",
            event_type=raw.get("facility", "unknown"),
            severity=raw.get("severity", "info"),
            src_ip=raw.get("host"),
            raw_data=raw,
        )

    def normalize_netflow(self, raw: Dict[str, Any]) -> NormalizedEvent:
        """Normalize NetFlow record."""
        return NormalizedEvent(
            event_id=f"NF-{hashlib.md5(str(raw).encode()).hexdigest()[:8]}",
            timestamp=datetime.now(timezone.utc),
            source="netflow",
            event_type="network_flow",
            src_ip=raw.get("src_addr") or raw.get("Src IP"),
            dst_ip=raw.get("dst_addr") or raw.get("Dst IP"),
            src_port=raw.get("src_port"),
            dst_port=raw.get("dst_port"),
            protocol=raw.get("protocol"),
            raw_data=raw,
            metadata={"bytes": raw.get("bytes"), "packets": raw.get("packets")},
        )

    def normalize_pcap(self, raw: Dict[str, Any]) -> NormalizedEvent:
        """Normalize PCAP packet data."""
        return NormalizedEvent(
            event_id=f"PCAP-{hashlib.md5(str(raw).encode()).hexdigest()[:8]}",
            timestamp=datetime.now(timezone.utc),
            source="pcap",
            event_type=raw.get("protocol", "unknown"),
            src_ip=raw.get("src_ip"),
            dst_ip=raw.get("dst_ip"),
            src_port=raw.get("src_port"),
            dst_port=raw.get("dst_port"),
            protocol=raw.get("protocol"),
            raw_data=raw,
        )

    def normalize_generic(self, raw: Dict[str, Any], source: str = "generic") -> NormalizedEvent:
        """Normalize any generic event."""
        return NormalizedEvent(
            event_id=f"GEN-{hashlib.md5(str(raw).encode()).hexdigest()[:8]}",
            timestamp=datetime.now(timezone.utc),
            source=source,
            event_type=raw.get("type", "unknown"),
            src_ip=raw.get("src_ip") or raw.get("Src IP"),
            dst_ip=raw.get("dst_ip") or raw.get("Dst IP"),
            raw_data=raw,
        )

    def _map_wazuh_level(self, level: int) -> str:
        if level >= 12:
            return "critical"
        elif level >= 8:
            return "high"
        elif level >= 4:
            return "medium"
        return "low"
