"""
CDSI PBFT — Practical Byzantine Fault Tolerance implementation.

Implements the 3-phase PBFT protocol:
  1. Pre-prepare: leader broadcasts proposal
  2. Prepare: nodes broadcast prepare messages
  3. Commit: nodes broadcast commit messages

Tolerates up to f = (n-1)/3 Byzantine nodes.
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)


class PBFTPhase(str, Enum):
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    DECIDED = "decided"


class PBFTMessage:
    """A PBFT protocol message."""

    def __init__(
        self,
        phase: PBFTPhase,
        view: int,
        sequence: int,
        node_id: str,
        proposal_hash: str,
        payload: Dict[str, Any],
    ):
        self.phase = phase
        self.view = view
        self.sequence = sequence
        self.node_id = node_id
        self.proposal_hash = proposal_hash
        self.payload = payload
        self.timestamp = time.time()


class PBFTNode:
    """
    A single PBFT node. In CDSI, each agent can act as a PBFT node
    for Byzantine-fault-tolerant consensus.
    """

    def __init__(self, node_id: str, total_nodes: int):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.f = (total_nodes - 1) // 3  # max faulty nodes
        self.view = 0
        self.sequence = 0
        self.phase = PBFTPhase.PRE_PREPARE
        self._prepare_votes: Dict[str, Set[str]] = {}  # hash → set of node_ids
        self._commit_votes: Dict[str, Set[str]] = {}
        self._decided: Set[str] = set()

    def is_leader(self) -> bool:
        """The leader is determined by view number."""
        return hash(self.node_id) % self.total_nodes == self.view % self.total_nodes

    def pre_prepare(self, proposal_hash: str, payload: Dict[str, Any]) -> PBFTMessage:
        """Leader initiates pre-prepare phase."""
        self.sequence += 1
        return PBFTMessage(
            phase=PBFTPhase.PRE_PREPARE,
            view=self.view,
            sequence=self.sequence,
            node_id=self.node_id,
            proposal_hash=proposal_hash,
            payload=payload,
        )

    def handle_pre_prepare(self, msg: PBFTMessage) -> Optional[PBFTMessage]:
        """Node receives pre-prepare, responds with prepare if valid."""
        if msg.view != self.view:
            return None

        self._prepare_votes.setdefault(msg.proposal_hash, set())
        self._prepare_votes[msg.proposal_hash].add(self.node_id)

        return PBFTMessage(
            phase=PBFTPhase.PREPARE,
            view=self.view,
            sequence=msg.sequence,
            node_id=self.node_id,
            proposal_hash=msg.proposal_hash,
            payload=msg.payload,
        )

    def handle_prepare(self, msg: PBFTMessage) -> Optional[PBFTMessage]:
        """Node receives prepare message. If 2f+1 prepares, move to commit."""
        self._prepare_votes.setdefault(msg.proposal_hash, set())
        self._prepare_votes[msg.proposal_hash].add(msg.node_id)

        if len(self._prepare_votes[msg.proposal_hash]) >= 2 * self.f + 1:
            self._commit_votes.setdefault(msg.proposal_hash, set())
            self._commit_votes[msg.proposal_hash].add(self.node_id)
            return PBFTMessage(
                phase=PBFTPhase.COMMIT,
                view=self.view,
                sequence=msg.sequence,
                node_id=self.node_id,
                proposal_hash=msg.proposal_hash,
                payload=msg.payload,
            )
        return None

    def handle_commit(self, msg: PBFTMessage) -> bool:
        """Node receives commit message. If 2f+1 commits, decide."""
        self._commit_votes.setdefault(msg.proposal_hash, set())
        self._commit_votes[msg.proposal_hash].add(msg.node_id)

        if (
            len(self._commit_votes[msg.proposal_hash]) >= 2 * self.f + 1
            and msg.proposal_hash not in self._decided
        ):
            self._decided.add(msg.proposal_hash)
            logger.info(
                "pbft.decided",
                node_id=self.node_id,
                proposal_hash=msg.proposal_hash,
            )
            return True
        return False

    def is_decided(self, proposal_hash: str) -> bool:
        return proposal_hash in self._decided
