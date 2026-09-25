"""
CDSI Event Router — Routes normalized events to relevant agents.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List

import structlog

from agents.base.base_agent import AgentType
from ingestion.normalizer import NormalizedEvent

logger = structlog.get_logger(__name__)

# Routing rules: keywords/patterns → agent types
ROUTING_RULES: Dict[str, List[AgentType]] = {
    "ddos": [AgentType.DDOS, AgentType.ANOMALY],
    "dos": [AgentType.DDOS, AgentType.ANOMALY],
    "flood": [AgentType.DDOS],
    "syn_flood": [AgentType.DDOS],
    "volumetric": [AgentType.DDOS],
    "malware": [AgentType.MALWARE, AgentType.RANSOMWARE],
    "trojan": [AgentType.MALWARE],
    "virus": [AgentType.MALWARE],
    "worm": [AgentType.MALWARE],
    "ransomware": [AgentType.RANSOMWARE],
    "encrypt": [AgentType.RANSOMWARE],
    "phishing": [AgentType.PHISHING],
    "spear_phishing": [AgentType.PHISHING],
    "email": [AgentType.PHISHING],
    "url": [AgentType.PHISHING],
    "arp": [AgentType.MITM],
    "dns_spoof": [AgentType.MITM],
    "mitm": [AgentType.MITM],
    "spoofing": [AgentType.MITM],
    "anomaly": [AgentType.ANOMALY],
    "unusual": [AgentType.ANOMALY],
    "network_flow": [AgentType.ANOMALY, AgentType.DDOS, AgentType.MITM],
}

# Default: route to anomaly agent if no match
DEFAULT_ROUTES = [AgentType.ANOMALY]


class EventRouter:
    """Routes normalized events to the appropriate detection agents."""

    def __init__(self):
        self._agent_handlers: Dict[AgentType, List[Callable]] = {}
        self._batch_buffer: List[NormalizedEvent] = []
        self._batch_size = 100

    def register_agent(
        self,
        agent_type: AgentType,
        handler: Callable[[NormalizedEvent], Any],
    ) -> None:
        """Register an agent handler for a specific type."""
        self._agent_handlers.setdefault(agent_type, []).append(handler)

    async def route(self, event: NormalizedEvent) -> List[AgentType]:
        """Route an event to relevant agents. Returns list of routed agent types."""
        targets = self._determine_targets(event)

        for agent_type in targets:
            handlers = self._agent_handlers.get(agent_type, [])
            for handler in handlers:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)

        return targets

    async def route_batch(self, events: List[NormalizedEvent]) -> Dict[AgentType, int]:
        """Route a batch of events. Returns count per agent type."""
        counts: Dict[AgentType, int] = {}
        for event in events:
            targets = await self.route(event)
            for t in targets:
                counts[t] = counts.get(t, 0) + 1
        return counts

    def _determine_targets(self, event: NormalizedEvent) -> List[AgentType]:
        """Determine which agents should process this event."""
        targets = set()

        # Match on event type
        event_type = event.event_type.lower()
        for keyword, agent_types in ROUTING_RULES.items():
            if keyword in event_type:
                targets.update(agent_types)

        # Match on source
        source = event.source.lower()
        if source in ("pcap", "netflow"):
            targets.update([AgentType.DDOS, AgentType.ANOMALY, AgentType.MITM])
        elif source == "wazuh":
            targets.add(AgentType.ANOMALY)

        # Fallback to defaults
        if not targets:
            targets.update(DEFAULT_ROUTES)

        return list(targets)

    def get_registered_agents(self) -> List[AgentType]:
        """Return list of registered agent types."""
        return list(self._agent_handlers.keys())
