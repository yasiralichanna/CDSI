"""
CDSI Backend Models — Pydantic models matching frontend TypeScript types exactly.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    ANOMALY = "anomaly"
    MALWARE = "malware"
    PHISHING = "phishing"
    DDOS = "ddos"
    MITM = "mitm"
    RANSOMWARE = "ransomware"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class ThreatSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatStatus(str, Enum):
    PENDING_CONSENSUS = "pending_consensus"
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    FALSE_POSITIVE = "false_positive"


# ── Models matching frontend types.ts ──────────────────────────────────

class AgentModel(BaseModel):
    id: str
    name: str
    type: AgentType
    status: AgentStatus
    trustScore: float
    detectionAccuracy: float
    currentLoad: float
    lastActivity: datetime
    recentDetections: int

    model_config = {"from_attributes": True}


class ThreatModel(BaseModel):
    id: str
    type: AgentType
    detectedBy: List[str]
    severity: ThreatSeverity
    confidence: float
    timestamp: datetime
    status: ThreatStatus
    description: str
    sourceIP: Optional[str] = None
    targetIP: Optional[str] = None

    model_config = {"from_attributes": True}


class ConsensusVoteModel(BaseModel):
    agentId: str
    agentType: AgentType
    vote: Literal["threat", "safe", "uncertain"]
    confidence: float
    timestamp: datetime


class ConsensusDecisionModel(BaseModel):
    threatId: str
    votes: List[ConsensusVoteModel]
    finalDecision: Literal["threat", "safe", "uncertain"]
    consensusReached: bool
    timeToConsensus: int  # ms
    trustWeightedScore: float


class AutomatedResponseModel(BaseModel):
    id: str
    threatId: str
    action: Literal["ip_blocked", "vm_isolated", "iot_quarantined", "domain_blocked", "traffic_rerouted"]
    timestamp: datetime
    success: bool
    canRollback: bool
    details: str


class MitreAttackTechniqueModel(BaseModel):
    id: str
    name: str
    tactic: str
    killChainPhase: str
    threatCount: int


class AuditLogModel(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    action: str
    details: str
    reasoning: Optional[str] = None


class AttackTypeStats(BaseModel):
    detected: int
    mitigated: int
    accuracy: float


class SystemStats(BaseModel):
    activeAgents: int
    totalAgents: int
    activeThreats: int
    consensusToday: int
    autoResponses: int
    avgConsensusLatency: float
    detectionRate: float
    falsePositiveRate: float
