"""
CDSI Correlation Engine — The core differentiator of CDSI.

This engine:
  - Collects outputs from ALL agents
  - Reduces false positives via ensemble logic
  - Combines signals using weighted Bayesian fusion
  - Escalates only high-confidence threats
  - Tracks attack chains and multi-stage campaigns
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
import numpy as np

from agents.base.base_agent import ThreatSeverity, ThreatStatus
from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Minimum confidence threshold to escalate
ESCALATION_THRESHOLD = 75.0
# Time window for correlating related events (seconds)
CORRELATION_WINDOW = 300
# Minimum agents that must agree for high confidence
MIN_CORROBORATING_AGENTS = 2


class CorrelatedThreat:
    """A threat correlated across multiple agent detections."""

    def __init__(self, primary_threat: Dict[str, Any]):
        self.id = primary_threat["id"]
        self.primary = primary_threat
        self.corroborating: List[Dict[str, Any]] = []
        self.combined_confidence: float = primary_threat.get("confidence", 0)
        self.severity = primary_threat.get("severity", "medium")
        self.timestamp = time.time()
        self.escalated = False
        self.false_positive_score: float = 0.0

    def add_corroboration(self, event: Dict[str, Any]) -> None:
        """Add a corroborating detection from another agent."""
        self.corroborating.append(event)
        self._recompute_confidence()

    def _recompute_confidence(self) -> None:
        """Bayesian-style confidence fusion."""
        confidences = [self.primary.get("confidence", 50)]
        for c in self.corroborating:
            confidences.append(c.get("confidence", 50))

        # Weighted combination: more agents = higher confidence
        if len(confidences) == 1:
            self.combined_confidence = confidences[0]
        else:
            # Noisy-OR fusion
            p_safe = 1.0
            for conf in confidences:
                p_threat = conf / 100.0
                p_safe *= (1 - p_threat)
            self.combined_confidence = (1 - p_safe) * 100

        # Upgrade severity if multiple agents agree
        if len(self.corroborating) >= 2 and self.combined_confidence > 90:
            self.severity = "critical"
        elif len(self.corroborating) >= 1 and self.combined_confidence > 75:
            self.severity = "high"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "primary": self.primary,
            "corroborating": self.corroborating,
            "combined_confidence": round(self.combined_confidence, 1),
            "severity": self.severity,
            "num_agents": 1 + len(self.corroborating),
            "escalated": self.escalated,
            "false_positive_score": round(self.false_positive_score, 2),
            "timestamp": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
        }


class CorrelationEngine:
    """
    Collects all agent outputs, reduces false positives,
    and only escalates high-confidence threats.
    """

    def __init__(self):
        self._recent_events: deque = deque(maxlen=10000)
        self._correlated_threats: Dict[str, CorrelatedThreat] = {}
        self._ip_threat_map: Dict[str, List[str]] = defaultdict(list)
        self._agent_reliability: Dict[str, float] = {}
        self._false_positive_history: deque = deque(maxlen=1000)
        self._comms: Any = None

    def set_comms(self, comms: Any) -> None:
        self._comms = comms

    async def ingest_detection(self, event: Dict[str, Any]) -> Optional[CorrelatedThreat]:
        """
        Process a detection event from any agent.
        Returns a CorrelatedThreat if the event should be escalated.
        """
        self._recent_events.append({**event, "_ingested_at": time.time()})

        # Check for correlation with existing threats
        correlated = self._find_correlation(event)

        if correlated:
            correlated.add_corroboration(event)
            logger.info(
                "correlation.corroboration",
                threat_id=correlated.id,
                agents=1 + len(correlated.corroborating),
                confidence=correlated.combined_confidence,
            )
        else:
            correlated = CorrelatedThreat(event)
            self._correlated_threats[correlated.id] = correlated

        # Track by IP for chain detection
        src_ip = event.get("sourceIP") or event.get("src_ip")
        if src_ip:
            self._ip_threat_map[src_ip].append(correlated.id)

        # Apply false positive reduction
        correlated.false_positive_score = self._compute_fp_score(correlated)

        # Decide whether to escalate
        if self._should_escalate(correlated):
            correlated.escalated = True
            if self._comms:
                await self._comms.publish(
                    "escalated_threats", correlated.to_dict()
                )
            logger.info(
                "correlation.escalated",
                threat_id=correlated.id,
                confidence=correlated.combined_confidence,
                severity=correlated.severity,
            )
            return correlated

        return None

    def _find_correlation(self, event: Dict[str, Any]) -> Optional[CorrelatedThreat]:
        """Find an existing threat that correlates with this event."""
        src_ip = event.get("sourceIP") or event.get("src_ip")
        dst_ip = event.get("targetIP") or event.get("dst_ip")
        event_type = event.get("type", "")
        now = time.time()

        for threat_id, threat in self._correlated_threats.items():
            if now - threat.timestamp > CORRELATION_WINDOW:
                continue

            # Same source IP → likely related
            primary_src = threat.primary.get("sourceIP") or threat.primary.get("src_ip")
            if src_ip and primary_src and src_ip == primary_src:
                return threat

            # Same target → coordinated attack
            primary_dst = threat.primary.get("targetIP") or threat.primary.get("dst_ip")
            if dst_ip and primary_dst and dst_ip == primary_dst:
                return threat

        return None

    def _compute_fp_score(self, threat: CorrelatedThreat) -> float:
        """
        Compute false positive likelihood (0-1, lower is better).
        Uses:
          - Number of corroborating agents
          - Historical FP rate for this attack type
          - Confidence levels
        """
        # More agents agreeing → lower FP chance
        agent_factor = max(0, 1.0 - (len(threat.corroborating) * 0.3))

        # Low confidence → higher FP chance
        confidence_factor = 1.0 - (threat.combined_confidence / 100)

        # Historical FP rate for the attack type
        attack_type = threat.primary.get("type", "")
        historical_fp = self._get_historical_fp_rate(attack_type)

        # Weighted combination
        fp_score = (agent_factor * 0.4 + confidence_factor * 0.4 + historical_fp * 0.2)
        return min(1.0, max(0.0, fp_score))

    def _get_historical_fp_rate(self, attack_type: str) -> float:
        """Get historical false positive rate for attack type."""
        relevant = [
            fp for fp in self._false_positive_history
            if fp.get("type") == attack_type
        ]
        if not relevant:
            return 0.1  # default low FP rate
        fp_count = sum(1 for fp in relevant if fp.get("was_fp", False))
        return fp_count / len(relevant)

    def _should_escalate(self, threat: CorrelatedThreat) -> bool:
        """Determine if a threat should be escalated for response."""
        if threat.escalated:
            return False

        # Must have high enough combined confidence
        if threat.combined_confidence < ESCALATION_THRESHOLD:
            return False

        # Low FP score required
        if threat.false_positive_score > 0.5:
            return False

        # Critical severity always escalated
        if threat.severity == "critical":
            return True

        # High severity with multiple agents
        if threat.severity == "high" and len(threat.corroborating) >= 1:
            return True

        # Multiple agents agree → escalate
        if len(threat.corroborating) >= MIN_CORROBORATING_AGENTS:
            return True

        return False

    def record_feedback(self, threat_id: str, was_false_positive: bool) -> None:
        """Record feedback on whether a threat was a false positive."""
        threat = self._correlated_threats.get(threat_id)
        if threat:
            self._false_positive_history.append({
                "type": threat.primary.get("type", ""),
                "was_fp": was_false_positive,
                "confidence": threat.combined_confidence,
            })

    def get_active_threats(self) -> List[Dict[str, Any]]:
        """Return all active correlated threats."""
        now = time.time()
        return [
            t.to_dict() for t in self._correlated_threats.values()
            if now - t.timestamp < CORRELATION_WINDOW
        ]

    def get_attack_chains(self) -> Dict[str, List[str]]:
        """Return attack chains grouped by source IP."""
        return dict(self._ip_threat_map)

    def get_stats(self) -> Dict[str, Any]:
        """Return correlation statistics."""
        return {
            "total_events": len(self._recent_events),
            "active_threats": len(self._correlated_threats),
            "escalated": sum(1 for t in self._correlated_threats.values() if t.escalated),
            "avg_confidence": np.mean([
                t.combined_confidence for t in self._correlated_threats.values()
            ]) if self._correlated_threats else 0,
        }
