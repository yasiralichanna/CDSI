"""Audit Logs API Router."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter

from dashboard.backend.models import AuditLogModel

router = APIRouter()


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.get("/logs", response_model=List[AuditLogModel])
async def list_logs():
    """List audit logs."""
    return _get_manager().get_audit_logs()
