"""
CDSI Base Agent — Abstract base class for all detection agents.

Every specialised agent (DDoS, Malware, Phishing, …) must extend this class
and implement the abstract methods.
"""
from __future__ import annotations

import abc
import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import joblib
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


# ── Enums matching frontend types ──────────────────────────────────────────

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


# ── Data classes ───────────────────────────────────────────────────────────

class ThreatEvent:
    """Represents a detected threat that will be published for consensus."""

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        severity: ThreatSeverity,
        confidence: float,
        description: str,
        source_ip: Optional[str] = None,
        target_ip: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ):
        self.id = f"THR-{uuid.uuid4().hex[:8].upper()}"
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.severity = severity
        self.confidence = confidence
        self.description = description
        self.source_ip = source_ip
        self.target_ip = target_ip
        self.raw_data = raw_data or {}
        self.timestamp = datetime.now(timezone.utc)
        self.status = ThreatStatus.PENDING_CONSENSUS
        self.detected_by: List[str] = [agent_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.agent_type.value,
            "detectedBy": self.detected_by,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "description": self.description,
            "sourceIP": self.source_ip,
            "targetIP": self.target_ip,
        }


class DetectionResult:
    """Result of a single prediction."""

    def __init__(
        self,
        is_threat: bool,
        confidence: float,
        severity: ThreatSeverity,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.is_threat = is_threat
        self.confidence = confidence
        self.severity = severity
        self.description = description
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)


# ── Abstract Base Agent ────────────────────────────────────────────────────

class BaseAgent(abc.ABC):
    """
    Abstract base for every CDSI detection agent.

    Lifecycle:
        1. __init__() → configure agent
        2. load_model() → load pre-trained weights
        3. stream_detect(events) → async generator yielding DetectionResults
        4. publish_threat(threat) → push to comms layer
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        name: str,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name

        self._status = AgentStatus.ACTIVE
        self._trust_score: float = 90.0
        self._detection_accuracy: float = 0.0
        self._current_load: float = 0.0
        self._recent_detections: int = 0
        self._last_activity = datetime.now(timezone.utc)
        self._model: Any = None
        self._comms: Any = None  # set externally via set_comms()

        self._total_predictions: int = 0
        self._correct_predictions: int = 0

        settings = get_settings()
        self._model_dir = settings.model_storage_path / self.agent_type.value
        self._model_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "agent.init",
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            name=self.name,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def status(self) -> AgentStatus:
        return self._status

    @status.setter
    def status(self, value: AgentStatus) -> None:
        self._status = value

    @property
    def trust_score(self) -> float:
        return self._trust_score

    @trust_score.setter
    def trust_score(self, value: float) -> None:
        self._trust_score = max(0.0, min(100.0, value))

    @property
    def detection_accuracy(self) -> float:
        if self._total_predictions == 0:
            return self._detection_accuracy
        return (self._correct_predictions / self._total_predictions) * 100

    @property
    def model_path(self) -> Path:
        return self._model_dir / f"{self.agent_type.value}_model.pkl"

    # ── Abstract Methods (must be implemented) ─────────────────────────

    @abc.abstractmethod
    def train(self, data: Any, labels: Any, **kwargs) -> Dict[str, float]:
        """
        Train the agent's model on provided data.
        Returns metrics dict (accuracy, f1, etc.).
        """
        ...

    @abc.abstractmethod
    def predict(self, sample: Any) -> DetectionResult:
        """
        Run inference on a single sample.
        Returns DetectionResult.
        """
        ...

    @abc.abstractmethod
    async def stream_detect(
        self, event_stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[DetectionResult]:
        """
        Async generator: consume streaming events, yield detections.
        """
        ...

    @abc.abstractmethod
    def get_feature_names(self) -> List[str]:
        """Return the feature names this agent expects."""
        ...

    # ── Concrete Methods ───────────────────────────────────────────────

    def set_comms(self, comms: Any) -> None:
        """Attach a communication interface for threat publishing."""
        self._comms = comms

    async def publish_threat(self, threat: ThreatEvent) -> None:
        """Publish a threat event to the communication layer."""
        self._recent_detections += 1
        self._last_activity = datetime.now(timezone.utc)

        if self._comms is not None:
            await self._comms.publish("threats", threat.to_dict())
            logger.info(
                "agent.threat_published",
                agent_id=self.agent_id,
                threat_id=threat.id,
                severity=threat.severity.value,
                confidence=threat.confidence,
            )
        else:
            logger.warning(
                "agent.no_comms",
                agent_id=self.agent_id,
                threat_id=threat.id,
            )

    def save_model(self) -> Path:
        """Persist the current model to disk."""
        if self._model is None:
            raise ValueError(f"Agent {self.agent_id} has no model to save")

        path = self.model_path
        joblib.dump(self._model, path)
        logger.info("agent.model_saved", path=str(path))
        return path

    def load_model(self) -> bool:
        """Load a pre-trained model from disk. Returns True if successful."""
        path = self.model_path
        if path.exists():
            self._model = joblib.load(path)
            logger.info("agent.model_loaded", path=str(path))
            return True
        logger.warning("agent.no_model_found", path=str(path))
        return False

    def update_accuracy(self, predicted: bool, actual: bool) -> None:
        """Update running accuracy tracking."""
        self._total_predictions += 1
        if predicted == actual:
            self._correct_predictions += 1

    def get_status_dict(self) -> Dict[str, Any]:
        """Return status dict matching frontend Agent type."""
        return {
            "id": self.agent_id,
            "name": self.name,
            "type": self.agent_type.value,
            "status": self._status.value,
            "trustScore": self._trust_score,
            "detectionAccuracy": round(self.detection_accuracy, 1),
            "currentLoad": self._current_load,
            "lastActivity": self._last_activity.isoformat(),
            "recentDetections": self._recent_detections,
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "agent_id": self.agent_id,
            "status": self._status.value,
            "model_loaded": self._model is not None,
            "uptime_ok": self._status != AgentStatus.OFFLINE,
        }

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.agent_id} "
            f"type={self.agent_type.value} status={self._status.value}>"
        )
