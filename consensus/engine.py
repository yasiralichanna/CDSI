"""
CDSI Consensus Engine — Orchestrates threat validation via swarm voting.

Flow:
  1. Agent publishes threat proposal
  2. Engine collects votes from all agents (with timeout)
  3. Trust-weighted scoring applied
  4. Decision made if ≥66% agreement
  5. Result published to comms + dashboard
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import structlog

from consensus.trust import TrustManager
from config.settings import get_settings

logger = structlog.get_logger(__name__)

VoteType = Literal["threat", "safe", "uncertain"]


class ConsensusVote:
    """A single agent's vote on a threat proposal."""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        vote: VoteType,
        confidence: float,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.vote = vote
        self.confidence = confidence
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agentId": self.agent_id,
            "agentType": self.agent_type,
            "vote": self.vote,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


class ConsensusDecision:
    """Final decision after voting on a threat."""

    def __init__(
        self,
        threat_id: str,
        votes: List[ConsensusVote],
        final_decision: VoteType,
        consensus_reached: bool,
        time_to_consensus: int,
        trust_weighted_score: float,
    ):
        self.threat_id = threat_id
        self.votes = votes
        self.final_decision = final_decision
        self.consensus_reached = consensus_reached
        self.time_to_consensus = time_to_consensus
        self.trust_weighted_score = trust_weighted_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threatId": self.threat_id,
            "votes": [v.to_dict() for v in self.votes],
            "finalDecision": self.final_decision,
            "consensusReached": self.consensus_reached,
            "timeToConsensus": self.time_to_consensus,
            "trustWeightedScore": round(self.trust_weighted_score, 1),
        }


class ConsensusEngine:
    """
    Main consensus orchestrator.
    Decoupled from agents — receives proposals and votes via comms.
    """

    def __init__(self, trust_manager: Optional[TrustManager] = None):
        settings = get_settings()
        self._threshold = settings.consensus_threshold
        self._timeout_ms = settings.consensus_timeout_ms
        self._trust = trust_manager or TrustManager()
        self._pending: Dict[str, Dict] = {}  # threat_id → proposal state
        self._decisions: List[ConsensusDecision] = []
        self._comms: Any = None

    def set_comms(self, comms: Any) -> None:
        """Attach communication interface."""
        self._comms = comms

    @property
    def trust_manager(self) -> TrustManager:
        return self._trust

    @property
    def decisions(self) -> List[ConsensusDecision]:
        return self._decisions.copy()

    async def propose_threat(
        self,
        threat_id: str,
        proposer_id: str,
        threat_data: Dict[str, Any],
        expected_voters: List[str],
    ) -> str:
        """
        Start a consensus round for a threat.
        Returns the proposal ID.
        """
        proposal_id = f"CSN-{uuid.uuid4().hex[:8].upper()}"
        self._pending[threat_id] = {
            "proposal_id": proposal_id,
            "threat_data": threat_data,
            "proposer": proposer_id,
            "expected_voters": expected_voters,
            "votes": [],
            "start_time": time.time(),
        }

        logger.info(
            "consensus.proposal_started",
            threat_id=threat_id,
            proposer=proposer_id,
            expected_voters=len(expected_voters),
        )

        # Start timeout timer
        asyncio.create_task(self._timeout_handler(threat_id))
        return proposal_id

    async def submit_vote(
        self,
        threat_id: str,
        agent_id: str,
        agent_type: str,
        vote: VoteType,
        confidence: float,
    ) -> Optional[ConsensusDecision]:
        """
        Submit a vote for a pending threat.
        Returns ConsensusDecision if quorum reached, else None.
        """
        pending = self._pending.get(threat_id)
        if not pending:
            logger.warning("consensus.vote_for_unknown", threat_id=threat_id)
            return None

        # Check for duplicate votes
        existing_ids = {v.agent_id for v in pending["votes"]}
        if agent_id in existing_ids:
            return None

        cv = ConsensusVote(
            agent_id=agent_id,
            agent_type=agent_type,
            vote=vote,
            confidence=confidence,
        )
        pending["votes"].append(cv)

        # Check if all expected voters have voted
        if len(pending["votes"]) >= len(pending["expected_voters"]):
            return await self._finalize(threat_id)

        return None

    async def _finalize(self, threat_id: str) -> ConsensusDecision:
        """Compute final decision using trust-weighted voting."""
        pending = self._pending.pop(threat_id, None)
        if not pending:
            raise ValueError(f"No pending proposal for {threat_id}")

        votes: List[ConsensusVote] = pending["votes"]
        start_time: float = pending["start_time"]
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Trust-weighted scoring
        weighted_threat = 0.0
        weighted_safe = 0.0
        weighted_uncertain = 0.0
        total_weight = 0.0

        for v in votes:
            trust = self._trust.get_trust(v.agent_id)
            weight = (trust / 100.0) * (v.confidence / 100.0)
            total_weight += weight

            if v.vote == "threat":
                weighted_threat += weight
            elif v.vote == "safe":
                weighted_safe += weight
            else:
                weighted_uncertain += weight

        # Determine decision
        if total_weight == 0:
            trust_weighted_score = 0.0
            final_decision: VoteType = "uncertain"
            consensus_reached = False
        else:
            threat_ratio = weighted_threat / total_weight
            safe_ratio = weighted_safe / total_weight
            trust_weighted_score = threat_ratio * 100

            if threat_ratio >= self._threshold:
                final_decision = "threat"
                consensus_reached = True
            elif safe_ratio >= self._threshold:
                final_decision = "safe"
                consensus_reached = True
            else:
                final_decision = "uncertain"
                consensus_reached = False

        decision = ConsensusDecision(
            threat_id=threat_id,
            votes=votes,
            final_decision=final_decision,
            consensus_reached=consensus_reached,
            time_to_consensus=elapsed_ms,
            trust_weighted_score=trust_weighted_score,
        )

        # Update trust scores based on alignment with decision
        for v in votes:
            if consensus_reached:
                if v.vote == final_decision:
                    self._trust.record_correct_vote(v.agent_id)
                else:
                    self._trust.record_incorrect_vote(v.agent_id)

        self._decisions.append(decision)

        logger.info(
            "consensus.decision",
            threat_id=threat_id,
            decision=final_decision,
            reached=consensus_reached,
            elapsed_ms=elapsed_ms,
            trust_score=round(trust_weighted_score, 1),
        )

        # Publish decision
        if self._comms:
            await self._comms.publish("consensus", decision.to_dict())

        return decision

    async def _timeout_handler(self, threat_id: str) -> None:
        """Finalize after timeout if not all votes received."""
        await asyncio.sleep(self._timeout_ms / 1000)
        if threat_id in self._pending:
            # Record timeouts for non-voters
            pending = self._pending[threat_id]
            voted = {v.agent_id for v in pending["votes"]}
            for expected in pending["expected_voters"]:
                if expected not in voted:
                    self._trust.record_timeout(expected)

            logger.warning(
                "consensus.timeout",
                threat_id=threat_id,
                received=len(pending["votes"]),
                expected=len(pending["expected_voters"]),
            )
            await self._finalize(threat_id)

    def get_pending_count(self) -> int:
        return len(self._pending)

    def get_decision_for_threat(self, threat_id: str) -> Optional[ConsensusDecision]:
        for d in self._decisions:
            if d.threat_id == threat_id:
                return d
        return None
