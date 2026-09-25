"""Intelligence API Router — MITRE ATT&CK."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter

from dashboard.backend.models import MitreAttackTechniqueModel

router = APIRouter()


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.get("/mitre", response_model=List[MitreAttackTechniqueModel])
async def list_mitre():
    """List MITRE ATT&CK techniques."""
    return _get_manager().get_mitre_techniques()
