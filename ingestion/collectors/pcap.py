"""
CDSI PCAP Collector — Parse and collect network packets from PCAP files.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import structlog

from ingestion.normalizer import EventNormalizer, NormalizedEvent

logger = structlog.get_logger(__name__)


class PCAPCollector:
    """Parse PCAP files into normalized events for agent processing."""

    def __init__(self):
        self._normalizer = EventNormalizer()

    def parse_file(self, pcap_path: Path) -> List[NormalizedEvent]:
        """Parse a PCAP file and return normalized events."""
        try:
            from scapy.all import rdpcap, IP, TCP, UDP, DNS
        except ImportError:
            logger.error("pcap.scapy_not_installed")
            return []

        events = []
        packets = rdpcap(str(pcap_path))

        for pkt in packets:
            if IP in pkt:
                raw = {
                    "src_ip": pkt[IP].src,
                    "dst_ip": pkt[IP].dst,
                    "protocol": pkt[IP].proto,
                    "length": len(pkt),
                    "ttl": pkt[IP].ttl,
                }
                if TCP in pkt:
                    raw.update({
                        "src_port": pkt[TCP].sport,
                        "dst_port": pkt[TCP].dport,
                        "flags": str(pkt[TCP].flags),
                        "protocol": "TCP",
                    })
                elif UDP in pkt:
                    raw.update({
                        "src_port": pkt[UDP].sport,
                        "dst_port": pkt[UDP].dport,
                        "protocol": "UDP",
                    })
                if DNS in pkt:
                    raw["dns_query"] = str(pkt[DNS].qd.qname) if pkt[DNS].qd else ""
                    raw["protocol"] = "DNS"

                events.append(self._normalizer.normalize_pcap(raw))

        logger.info("pcap.parsed", path=str(pcap_path), packets=len(events))
        return events

    async def stream_file(self, pcap_path: Path, batch_size: int = 100) -> AsyncIterator[NormalizedEvent]:
        """Stream PCAP events in batches."""
        events = self.parse_file(pcap_path)
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            for event in batch:
                yield event
            await asyncio.sleep(0.01)  # Yield control


class NetFlowCollector:
    """Collect and parse NetFlow v5/v9 records."""

    def __init__(self):
        self._normalizer = EventNormalizer()

    async def listen(self, host: str = "0.0.0.0", port: int = 2055) -> AsyncIterator[NormalizedEvent]:
        """Listen for NetFlow UDP datagrams."""
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: NetFlowProtocol(self._normalizer),
            local_addr=(host, port),
        )

        logger.info("netflow.listening", host=host, port=port)

        try:
            while True:
                await asyncio.sleep(1)
        finally:
            transport.close()


class NetFlowProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for NetFlow."""

    def __init__(self, normalizer: EventNormalizer):
        self._normalizer = normalizer
        self._events: asyncio.Queue = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            record = self._parse_netflow(data)
            event = self._normalizer.normalize_netflow(record)
            self._events.put_nowait(event)
        except Exception as e:
            logger.error("netflow.parse_error", error=str(e))

    def _parse_netflow(self, data: bytes) -> Dict[str, Any]:
        """Parse NetFlow v5 header and first record."""
        if len(data) < 24:
            return {}
        version = int.from_bytes(data[0:2], "big")
        count = int.from_bytes(data[2:4], "big")

        if version == 5 and len(data) >= 72:
            record = data[24:72]
            return {
                "src_addr": f"{record[0]}.{record[1]}.{record[2]}.{record[3]}",
                "dst_addr": f"{record[4]}.{record[5]}.{record[6]}.{record[7]}",
                "packets": int.from_bytes(record[16:20], "big"),
                "bytes": int.from_bytes(record[20:24], "big"),
                "src_port": int.from_bytes(record[32:34], "big"),
                "dst_port": int.from_bytes(record[34:36], "big"),
                "protocol": record[38],
            }
        return {"version": version, "count": count}
