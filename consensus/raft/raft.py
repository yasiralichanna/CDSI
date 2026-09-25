"""
CDSI Raft — Leader election and majority voting.

Simplified Raft for swarm consensus:
  - Leader election via randomized timeouts
  - Log replication for decision history
  - Majority voting for threat validation
"""
from __future__ import annotations

import asyncio
import random
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class RaftState(str, Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RaftNode:
    """
    Raft consensus node. Used for leader election and
    majority-based threat validation.
    """

    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.leader_id: Optional[str] = None
        self.log: List[Dict[str, Any]] = []
        self.commit_index = -1
        self._votes_received: set = set()
        self._election_timeout = self._random_timeout()
        self._last_heartbeat = time.time()

    def _random_timeout(self) -> float:
        """Random election timeout between 150-300ms."""
        return random.uniform(0.15, 0.30)

    def start_election(self) -> Dict[str, Any]:
        """Transition to candidate and request votes."""
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self._votes_received = {self.node_id}

        logger.info(
            "raft.election_started",
            node_id=self.node_id,
            term=self.current_term,
        )

        return {
            "type": "request_vote",
            "term": self.current_term,
            "candidate_id": self.node_id,
            "last_log_index": len(self.log) - 1,
            "last_log_term": self.log[-1]["term"] if self.log else 0,
        }

    def handle_vote_request(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a vote request from a candidate."""
        if msg["term"] > self.current_term:
            self.current_term = msg["term"]
            self.state = RaftState.FOLLOWER
            self.voted_for = None

        vote_granted = False
        if msg["term"] >= self.current_term and self.voted_for in (None, msg["candidate_id"]):
            vote_granted = True
            self.voted_for = msg["candidate_id"]
            self._last_heartbeat = time.time()

        return {
            "type": "vote_response",
            "term": self.current_term,
            "voter_id": self.node_id,
            "vote_granted": vote_granted,
        }

    def handle_vote_response(self, msg: Dict[str, Any]) -> bool:
        """Handle vote response. Returns True if elected leader."""
        if msg["vote_granted"] and msg["term"] == self.current_term:
            self._votes_received.add(msg["voter_id"])

        majority = (len(self.peers) + 1) // 2 + 1
        if len(self._votes_received) >= majority:
            self.state = RaftState.LEADER
            self.leader_id = self.node_id
            logger.info(
                "raft.leader_elected",
                node_id=self.node_id,
                term=self.current_term,
                votes=len(self._votes_received),
            )
            return True
        return False

    def append_entry(self, entry: Dict[str, Any]) -> bool:
        """Leader appends an entry to the log."""
        if self.state != RaftState.LEADER:
            return False

        entry["term"] = self.current_term
        entry["index"] = len(self.log)
        self.log.append(entry)
        return True

    def handle_append(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Follower handles log append from leader."""
        if msg.get("term", 0) >= self.current_term:
            self.state = RaftState.FOLLOWER
            self.current_term = msg["term"]
            self.leader_id = msg.get("leader_id")
            self._last_heartbeat = time.time()

            if "entry" in msg:
                self.log.append(msg["entry"])

        return {
            "type": "append_response",
            "term": self.current_term,
            "node_id": self.node_id,
            "success": True,
        }

    def needs_election(self) -> bool:
        """Check if election timeout has elapsed."""
        return (
            self.state != RaftState.LEADER
            and time.time() - self._last_heartbeat > self._election_timeout
        )

    def heartbeat(self) -> Dict[str, Any]:
        """Leader heartbeat message."""
        self._last_heartbeat = time.time()
        return {
            "type": "heartbeat",
            "term": self.current_term,
            "leader_id": self.node_id,
        }
