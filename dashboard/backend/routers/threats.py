"""Threats API Router."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dashboard.backend.models import ThreatModel, AgentType, ThreatSeverity, ThreatStatus

router = APIRouter()


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.get("/threats", response_model=List[ThreatModel])
async def list_threats():
    """List all detected threats."""
    return _get_manager().get_threats()


@router.get("/threats/{threat_id}", response_model=ThreatModel)
async def get_threat(threat_id: str):
    """Get a specific threat by ID."""
    threat = _get_manager().get_threat(threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail=f"Threat {threat_id} not found")
    return threat


class CreateThreatRequest(BaseModel):
    id: Optional[str] = None
    type: AgentType
    detectedBy: List[str] = Field(default_factory=list)
    severity: ThreatSeverity = ThreatSeverity.HIGH
    confidence: float = 80.0
    sourceIP: Optional[str] = None
    targetIP: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ThreatStatus] = ThreatStatus.PENDING_CONSENSUS
    timestamp: Optional[datetime] = None


@router.post("/threats", response_model=ThreatModel, status_code=201)
async def create_threat(threat_req: CreateThreatRequest):
    """Report a new threat to the CDSI swarm."""
    import uuid
    from datetime import datetime, timezone

    threat_dict = threat_req.model_dump()
    if not threat_dict.get("id"):
        threat_dict["id"] = f"THR-{uuid.uuid4().hex[:6].upper()}"
    if not threat_dict.get("timestamp"):
        threat_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    else:
        threat_dict["timestamp"] = threat_dict["timestamp"].isoformat()
    if not threat_dict.get("description"):
        threat_dict["description"] = f"Reported {threat_dict['type'].value if hasattr(threat_dict['type'], 'value') else threat_dict['type']} threat from {threat_dict.get('sourceIP', 'unknown')}"
    if not threat_dict.get("status"):
        threat_dict["status"] = ThreatStatus.PENDING_CONSENSUS.value
    else:
        threat_dict["status"] = threat_dict["status"].value if hasattr(threat_dict["status"], "value") else threat_dict["status"]

    if hasattr(threat_dict["type"], "value"):
        threat_dict["type"] = threat_dict["type"].value
    if hasattr(threat_dict["severity"], "value"):
        threat_dict["severity"] = threat_dict["severity"].value

    return await _get_manager().report_threat(threat_dict)

