"""Consensus API Router."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException

from dashboard.backend.models import ConsensusDecisionModel

router = APIRouter()


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.get("/consensus", response_model=List[ConsensusDecisionModel])
async def list_consensus():
    """List all consensus decisions."""
    return _get_manager().get_consensus_decisions()


@router.get("/consensus/{threat_id}", response_model=ConsensusDecisionModel)
async def get_consensus(threat_id: str):
    """Get consensus decision for a specific threat."""
    decision = _get_manager().get_consensus_for_threat(threat_id)
    if not decision:
        raise HTTPException(status_code=404, detail=f"No consensus for threat {threat_id}")
    return decision
