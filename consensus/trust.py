"""
CDSI Trust Scoring — Dynamic trust management for agents.

Trust scores evolve based on:
  - Historical accuracy of detections
  - Consensus alignment (does the agent agree with final decisions?)
  - Uptime and reliability
  - Rogue behaviour detection
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

INITIAL_TRUST = 90.0
MIN_TRUST = 0.0
MAX_TRUST = 100.0

# Reward/penalty weights
CORRECT_VOTE_REWARD = 1.5
WRONG_VOTE_PENALTY = 3.0
TIMEOUT_PENALTY = 2.0
UPTIME_BONUS = 0.1
ROGUE_THRESHOLD = 30.0  # trust below this → rogue


@dataclass
class TrustRecord:
    """Per-agent trust state."""
    agent_id: str
    score: float = INITIAL_TRUST
    total_votes: int = 0
    correct_votes: int = 0
    incorrect_votes: int = 0
    timeouts: int = 0
    last_updated: float = field(default_factory=time.time)
    flagged_rogue: bool = False


class TrustManager:
    """
    Manages trust scores for all agents in the swarm.
    Trust is used to weight votes in consensus decisions.
    """

    def __init__(self) -> None:
        self._records: Dict[str, TrustRecord] = {}

    def register_agent(self, agent_id: str, initial_trust: float = INITIAL_TRUST) -> None:
        """Register an agent with an initial trust score."""
        self._records[agent_id] = TrustRecord(
            agent_id=agent_id, score=initial_trust
        )

    def get_trust(self, agent_id: str) -> float:
        """Get the current trust score for an agent."""
        rec = self._records.get(agent_id)
        return rec.score if rec else INITIAL_TRUST

    def get_all_scores(self) -> Dict[str, float]:
        """Return all agent trust scores."""
        return {aid: r.score for aid, r in self._records.items()}

    def record_correct_vote(self, agent_id: str) -> float:
        """Agent voted in alignment with final consensus."""
        rec = self._ensure_record(agent_id)
        rec.total_votes += 1
        rec.correct_votes += 1
        rec.score = min(MAX_TRUST, rec.score + CORRECT_VOTE_REWARD)
        rec.last_updated = time.time()
        rec.flagged_rogue = False
        return rec.score

    def record_incorrect_vote(self, agent_id: str) -> float:
        """Agent voted against final consensus."""
        rec = self._ensure_record(agent_id)
        rec.total_votes += 1
        rec.incorrect_votes += 1
        rec.score = max(MIN_TRUST, rec.score - WRONG_VOTE_PENALTY)
        rec.last_updated = time.time()
        self._check_rogue(rec)
        return rec.score

    def record_timeout(self, agent_id: str) -> float:
        """Agent failed to vote within timeout."""
        rec = self._ensure_record(agent_id)
        rec.timeouts += 1
        rec.score = max(MIN_TRUST, rec.score - TIMEOUT_PENALTY)
        rec.last_updated = time.time()
        self._check_rogue(rec)
        return rec.score

    def apply_uptime_bonus(self, agent_id: str) -> float:
        """Small periodic bonus for being online and responsive."""
        rec = self._ensure_record(agent_id)
        rec.score = min(MAX_TRUST, rec.score + UPTIME_BONUS)
        rec.last_updated = time.time()
        return rec.score

    def update_trust(self, agent_id: str, new_score: float) -> float:
        """Directly set an agent's trust score (used by TTIAR for penalties)."""
        rec = self._ensure_record(agent_id)
        rec.score = max(MIN_TRUST, min(MAX_TRUST, new_score))
        rec.last_updated = time.time()
        self._check_rogue(rec)
        return rec.score

    def is_rogue(self, agent_id: str) -> bool:
        """Check if an agent is flagged as rogue."""
        rec = self._records.get(agent_id)
        return rec.flagged_rogue if rec else False

    def get_rogue_agents(self) -> List[str]:
        """Return list of agent IDs flagged as rogue."""
        return [aid for aid, r in self._records.items() if r.flagged_rogue]

    def _ensure_record(self, agent_id: str) -> TrustRecord:
        if agent_id not in self._records:
            self.register_agent(agent_id)
        return self._records[agent_id]

    def _check_rogue(self, rec: TrustRecord) -> None:
        if rec.score < ROGUE_THRESHOLD:
            if not rec.flagged_rogue:
                logger.warning(
                    "trust.rogue_detected",
                    agent_id=rec.agent_id,
                    trust_score=rec.score,
                )
            rec.flagged_rogue = True
