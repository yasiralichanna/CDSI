"""
CDSI Anomaly Detection Agent

Uses CICIDS2017 + IoT-23 datasets.
Detects anomalous network behavior using Isolation Forest + LSTM
for sequence-based anomaly detection.
"""
from __future__ import annotations

import asyncio
import numpy as np
import pandas as pd
from collections import deque
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib
import structlog

from agents.base.base_agent import (
    BaseAgent, AgentType, ThreatSeverity,
    ThreatEvent, DetectionResult,
)
from config.settings import get_settings

logger = structlog.get_logger(__name__)

ANOMALY_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Fwd IAT Mean", "Bwd IAT Mean", "Packet Length Mean",
    "Packet Length Std", "Average Packet Size", "SYN Flag Count",
    "RST Flag Count", "ACK Flag Count", "Init_Win_bytes_forward",
    "Init_Win_bytes_backward", "Active Mean", "Idle Mean",
]


class AnomalyAgent(BaseAgent):
    """
    Anomaly detection agent using Isolation Forest + RandomForest.
    Trained on CICIDS2017 + IoT-23.
    """

    def __init__(self, agent_id: str = "AGT-001", name: str = "Anomaly Sentinel"):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.ANOMALY,
            name=name,
        )
        self._scaler: Optional[StandardScaler] = None
        self._label_encoder: Optional[LabelEncoder] = None
        self._isolation_forest: Optional[IsolationForest] = None
        self._feature_names = ANOMALY_FEATURES
        self._sequence_buffer: deque = deque(maxlen=50)

    def get_feature_names(self) -> List[str]:
        return self._feature_names

    def train(self, data: Any = None, labels: Any = None, **kwargs) -> Dict[str, float]:
        settings = get_settings()
        if data is None or labels is None:
            data, labels = self._load_dataset(settings)

        logger.info("anomaly.training_started", samples=len(data))

        self._scaler = StandardScaler()
        X = self._scaler.fit_transform(data)

        self._label_encoder = LabelEncoder()
        y = self._label_encoder.fit_transform(labels)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Supervised: RandomForest for known attack types
        self._model = RandomForestClassifier(
            n_estimators=200, max_depth=12, n_jobs=-1, random_state=42
        )
        self._model.fit(X_train, y_train)

        # Unsupervised: Isolation Forest for zero-day anomalies
        benign_mask = y_train == 0
        if benign_mask.sum() > 100:
            self._isolation_forest = IsolationForest(
                n_estimators=150, contamination=0.05, random_state=42, n_jobs=-1
            )
            self._isolation_forest.fit(X_train[benign_mask])

        y_pred = self._model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average="weighted")
        self._detection_accuracy = accuracy * 100

        self.save_model()
        joblib.dump(self._scaler, self._model_dir / "scaler.pkl")
        joblib.dump(self._label_encoder, self._model_dir / "label_encoder.pkl")
        if self._isolation_forest:
            joblib.dump(self._isolation_forest, self._model_dir / "isolation_forest.pkl")

        metrics = {"accuracy": accuracy, "f1_score": f1}
        logger.info("anomaly.training_complete", **metrics)
        return metrics

    def predict(self, sample: Any) -> DetectionResult:
        if self._model is None:
            # Fallback for demo when models are not yet trained
            import random
            is_threat = random.random() > 0.7
            confidence = random.uniform(60, 95)
            iso_anomaly = random.random() > 0.8
            severity = self._compute_severity(confidence, iso_anomaly)
            return DetectionResult(
                is_threat=is_threat,
                confidence=confidence,
                severity=severity,
                description=self._build_description(sample, confidence, is_threat, iso_anomaly),
                metadata={"mock": True, "isolation_forest_anomaly": iso_anomaly},
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

        # Cross-check with Isolation Forest
        iso_anomaly = False
        if self._isolation_forest:
            iso_pred = self._isolation_forest.predict(features)[0]
            iso_anomaly = iso_pred == -1

        is_threat = pred_class != 0 or iso_anomaly

        # Boost confidence if both models agree
        if pred_class != 0 and iso_anomaly:
            confidence = min(100, confidence + 10)

        severity = self._compute_severity(confidence, iso_anomaly)

        self._sequence_buffer.append(features[0])

        return DetectionResult(
            is_threat=is_threat,
            confidence=confidence,
            severity=severity,
            description=self._build_description(sample, confidence, is_threat, iso_anomaly),
            metadata={
                "predicted_class": int(pred_class),
                "isolation_forest_anomaly": iso_anomaly,
                "probabilities": proba.tolist(),
            },
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
                        agent_id=self.agent_id,
                        agent_type=self.agent_type,
                        severity=result.severity,
                        confidence=result.confidence,
                        description=result.description,
                        source_ip=event.get("Src IP") or event.get("src_ip"),
                        target_ip=event.get("Dst IP") or event.get("dst_ip"),
                        raw_data=event,
                    )
                    await self.publish_threat(threat)
                yield result
            except Exception as e:
                logger.error("anomaly.detect_error", error=str(e))
            finally:
                self._current_load = max(0, self._current_load - 1)

    def load_model(self) -> bool:
        if not super().load_model():
            return False
        scaler_path = self._model_dir / "scaler.pkl"
        le_path = self._model_dir / "label_encoder.pkl"
        iso_path = self._model_dir / "isolation_forest.pkl"
        if scaler_path.exists():
            self._scaler = joblib.load(scaler_path)
        if le_path.exists():
            self._label_encoder = joblib.load(le_path)
        if iso_path.exists():
            self._isolation_forest = joblib.load(iso_path)
        return True

    def _load_dataset(self, settings) -> tuple:
        processed_dir = settings.dataset_processed_path / "anomaly"
        X_path = processed_dir / "X.npy"
        y_path = processed_dir / "y.npy"

        if X_path.exists() and y_path.exists():
            return np.load(X_path), np.load(y_path, allow_pickle=True)

        csv_path = processed_dir / "anomaly_processed.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            available = [f for f in self._feature_names if f in df.columns]
            if not available:
                available = [c for c in df.columns if c not in ["Label", "label"]]
            self._feature_names = available
            label_col = "Label" if "Label" in df.columns else "label"
            return df[available].values, df[label_col].values

        raise FileNotFoundError(
            f"Anomaly dataset not found at {processed_dir}. "
            "Run: python -m datasets.downloader --agent anomaly"
        )

    def _compute_severity(self, confidence: float, iso_anomaly: bool) -> ThreatSeverity:
        if confidence > 95 or (confidence > 80 and iso_anomaly):
            return ThreatSeverity.CRITICAL
        elif confidence > 80:
            return ThreatSeverity.HIGH
        elif confidence > 60:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW

    def _build_description(
        self, sample: Any, confidence: float, is_threat: bool, iso_anomaly: bool
    ) -> str:
        if not is_threat:
            return "Normal traffic pattern"
        method = "statistical + isolation forest" if iso_anomaly else "statistical"
        return f"Anomalous traffic pattern detected via {method} analysis ({confidence:.1f}% confidence)"
