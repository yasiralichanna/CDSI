"""
CDSI Blockchain Hash Log — Immutable audit trail for consensus decisions.

Each block contains:
  - SHA-256 hash of previous block
  - Consensus decision data
  - Timestamp
  - Nonce for integrity verification
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Block:
    """A single block in the hash chain."""
    index: int
    timestamp: float
    data: Dict[str, Any]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        block_str = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_str.encode()).hexdigest()


class HashLog:
    """
    Append-only blockchain-style hash log for immutable
    record of all consensus decisions.
    """

    def __init__(self) -> None:
        self._chain: List[Block] = []
        self._create_genesis()

    def _create_genesis(self) -> None:
        genesis = Block(
            index=0,
            timestamp=time.time(),
            data={"type": "genesis", "message": "CDSI Hash Log Genesis Block"},
            previous_hash="0" * 64,
        )
        self._chain.append(genesis)

    def add_decision(self, decision_data: Dict[str, Any]) -> Block:
        """Add a consensus decision to the hash chain."""
        prev = self._chain[-1]
        block = Block(
            index=prev.index + 1,
            timestamp=time.time(),
            data=decision_data,
            previous_hash=prev.hash,
        )
        self._chain.append(block)
        logger.info(
            "hashlog.block_added",
            index=block.index,
            hash=block.hash[:16],
        )
        return block

    def verify_chain(self) -> bool:
        """Verify the integrity of the entire chain."""
        for i in range(1, len(self._chain)):
            current = self._chain[i]
            previous = self._chain[i - 1]

            if current.hash != current.compute_hash():
                logger.error("hashlog.tampered", index=current.index)
                return False

            if current.previous_hash != previous.hash:
                logger.error("hashlog.chain_broken", index=current.index)
                return False

        return True

    def get_chain(self) -> List[Dict[str, Any]]:
        """Return the full chain as dicts."""
        return [
            {
                "index": b.index,
                "timestamp": b.timestamp,
                "data": b.data,
                "hash": b.hash,
                "previousHash": b.previous_hash,
            }
            for b in self._chain
        ]

    def get_latest_block(self) -> Block:
        return self._chain[-1]

    def __len__(self) -> int:
        return len(self._chain)
