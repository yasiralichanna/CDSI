"""Responses API Router."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException

from dashboard.backend.models import AutomatedResponseModel

router = APIRouter()


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.get("/responses", response_model=List[AutomatedResponseModel])
async def list_responses():
    """List all automated responses."""
    return _get_manager().get_responses()


@router.post("/responses/{response_id}/rollback")
async def rollback_response(response_id: str):
    """Rollback an automated response."""
    result = await _get_manager().rollback_response(response_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Response {response_id} not found or cannot be rolled back")
    return {"status": "rolled_back", "response": result}
