"""Agents API Router."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from dashboard.backend.models import AgentModel, AttackTypeStats

router = APIRouter()


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.get("/agents", response_model=List[AgentModel])
async def list_agents():
    """List all swarm agents."""
    return _get_manager().get_agents()


@router.get("/agents/stats")
async def agent_stats():
    """Get attack type statistics."""
    return _get_manager().get_attack_stats()


@router.get("/agents/{agent_id}", response_model=AgentModel)
async def get_agent(agent_id: str):
    """Get a specific agent by ID."""
    agent = _get_manager().get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent
