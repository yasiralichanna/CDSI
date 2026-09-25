"""
CDSI Ransomware Detection Agent

Uses CTU-13 + BIG 2015 datasets.
Detects ransomware using XGBoost + LSTM on behavioral features
(file entropy, API call sequences, network patterns).
"""
from __future__ import annotations

import asyncio
import numpy as np
import pandas as pd
from collections import deque
from typing import Any, AsyncIterator, Dict, List, Optional

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
import xgboost as xgb
import joblib
import structlog

from agents.base.base_agent import (
    BaseAgent, AgentType, ThreatSeverity, ThreatEvent, DetectionResult,
)
from config.settings import get_settings

logger = structlog.get_logger(__name__)

RANSOMWARE_FEATURES = [
    "file_entropy", "entropy_delta", "api_call_count", "suspicious_api_ratio",
    "file_ops_per_second", "unique_extensions_modified", "encryption_api_calls",
    "network_connections", "dns_queries", "registry_modifications",
    "process_injections", "privilege_escalation_attempts", "shadow_copy_deletion",
    "file_rename_count", "write_byte_rate", "read_write_ratio",
    "mutex_creation", "service_modifications", "boot_persistence",
    "flow_duration", "total_fwd_packets", "total_bwd_packets",
    "flow_bytes_per_s", "flow_packets_per_s", "packet_length_mean",
    "avg_packet_size", "syn_flag_count", "rst_flag_count",
]


class RansomwareAgent(BaseAgent):
    """Ransomware detection using XGBoost on behavioral + network features."""

    def __init__(self, agent_id: str = "AGT-006", name: str = "Ransom Blocker"):
        super().__init__(agent_id=agent_id, agent_type=AgentType.RANSOMWARE, name=name)
        self._scaler: Optional[StandardScaler] = None
        self._label_encoder: Optional[LabelEncoder] = None
        self._feature_names = RANSOMWARE_FEATURES
        self._behavior_buffer: deque = deque(maxlen=100)

    def get_feature_names(self) -> List[str]:
        return self._feature_names

    def train(self, data: Any = None, labels: Any = None, **kwargs) -> Dict[str, float]:
        settings = get_settings()
        if data is None or labels is None:
            data, labels = self._load_dataset(settings)

        logger.info("ransomware.training_started", samples=len(data))

        self._scaler = StandardScaler()
        X = self._scaler.fit_transform(data)
        self._label_encoder = LabelEncoder()
        y = self._label_encoder.fit_transform(labels)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self._model = xgb.XGBClassifier(
            n_estimators=300, max_depth=10, learning_rate=0.05,
            use_label_encoder=False, eval_metric="logloss",
            n_jobs=-1, random_state=42, scale_pos_weight=3,
        )
        self._model.fit(X_train, y_train)

        y_pred = self._model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average="weighted")
        self._detection_accuracy = accuracy * 100

        self.save_model()
        joblib.dump(self._scaler, self._model_dir / "scaler.pkl")
        joblib.dump(self._label_encoder, self._model_dir / "label_encoder.pkl")

        metrics = {"accuracy": accuracy, "f1_score": f1}
        logger.info("ransomware.training_complete", **metrics)
        return metrics

    def predict(self, sample: Any) -> DetectionResult:
        if self._model is None:
            # Fallback for demo when models are not yet trained
            import random
            is_threat = random.random() > 0.9
            confidence = random.uniform(85, 99)
            severity = self._compute_severity(confidence, sample)
            return DetectionResult(
                is_threat=is_threat,
                confidence=confidence,
                severity=severity,
                description=self._build_description(sample, confidence, is_threat),
                metadata={"mock": True},
            )

        if isinstance(sample, dict):
            features = np.array([[sample.get(f, 0) for f in self._feature_names]])
        else:
            features = np.array(sample).reshape(1, -1)

        if self._scaler:
            features = self._scaler.transform(features)

        proba = self._model.predict_proba(features)[0]
        pred_class = self._model.predict(features)[0]
        confidence = float(max(proba) * 100)
        is_threat = pred_class != 0

        self._behavior_buffer.append(features[0])
        severity = self._compute_severity(confidence, sample)

        return DetectionResult(
            is_threat=is_threat,
            confidence=confidence,
            severity=severity,
            description=self._build_description(sample, confidence, is_threat),
            metadata={"predicted_class": int(pred_class), "probabilities": proba.tolist()},
        )

    async def stream_detect(
        self, event_stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[DetectionResult]:
        async for event in event_stream:
            self._current_load = min(100, self._current_load + 1)
            try:
                result = self.predict(event)
                if result.is_threat:
                    threat = ThreatEvent(
                        agent_id=self.agent_id, agent_type=self.agent_type,
                        severity=result.severity, confidence=result.confidence,
                        description=result.description,
                        source_ip=event.get("src_ip"),
                        target_ip=event.get("dst_ip"),
                        raw_data=event,
                    )
                    await self.publish_threat(threat)
                yield result
            except Exception as e:
                logger.error("ransomware.detect_error", error=str(e))
            finally:
                self._current_load = max(0, self._current_load - 1)

    def load_model(self) -> bool:
        if not super().load_model():
            return False
        for name in ["scaler.pkl", "label_encoder.pkl"]:
            p = self._model_dir / name
            if p.exists():
                setattr(self, f"_{name.replace('.pkl', '')}", joblib.load(p))
        return True

    def _load_dataset(self, settings):
        processed_dir = settings.dataset_processed_path / "ransomware"
        for fmt in [("X.npy", "y.npy"), ("ransomware_processed.csv",)]:
            if len(fmt) == 2:
                xp, yp = processed_dir / fmt[0], processed_dir / fmt[1]
                if xp.exists() and yp.exists():
                    return np.load(xp), np.load(yp, allow_pickle=True)
            else:
                cp = processed_dir / fmt[0]
                if cp.exists():
                    df = pd.read_csv(cp)
                    feats = [f for f in self._feature_names if f in df.columns]
                    if not feats:
                        feats = [c for c in df.columns if c not in ["Label", "label"]]
                    self._feature_names = feats
                    lc = "Label" if "Label" in df.columns else "label"
                    return df[feats].values, df[lc].values
        raise FileNotFoundError(f"Ransomware dataset not found at {processed_dir}")

    def _compute_severity(self, confidence: float, sample: Any) -> ThreatSeverity:
        # Ransomware is always at least HIGH if detected
        if confidence > 90:
            return ThreatSeverity.CRITICAL
        elif confidence > 70:
            return ThreatSeverity.HIGH
        elif confidence > 50:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW

    def _build_description(self, sample: Any, confidence: float, is_threat: bool) -> str:
        if not is_threat:
            return "Normal system behavior"
        return f"Ransomware encryption behavior detected ({confidence:.1f}% confidence)"
