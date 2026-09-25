"""
CDSI DDoS Detection Agent

Uses CIC-DDoS2019 dataset for training.
Detects volumetric, protocol, and application-layer DDoS attacks
using flow-based features with XGBoost + LightGBM ensemble.
"""
from __future__ import annotations

import asyncio
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from sklearn.ensemble import VotingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.preprocessing import StandardScaler, LabelEncoder
import xgboost as xgb
import lightgbm as lgb
import joblib
import structlog

from agents.base.base_agent import (
    BaseAgent, AgentType, AgentStatus, ThreatSeverity,
    ThreatStatus, ThreatEvent, DetectionResult,
)
from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Key flow-based features for DDoS detection
DDOS_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Max", "Fwd Packet Length Min", "Fwd Packet Length Mean",
    "Bwd Packet Length Max", "Bwd Packet Length Min", "Bwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Flow IAT Max", "Flow IAT Min", "Fwd IAT Total", "Fwd IAT Mean",
    "Fwd IAT Std", "Fwd IAT Max", "Fwd IAT Min", "Bwd IAT Total",
    "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min",
    "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags",
    "Fwd Packets/s", "Bwd Packets/s", "Packet Length Min", "Packet Length Max",
    "Packet Length Mean", "Packet Length Std", "Packet Length Variance",
    "SYN Flag Count", "RST Flag Count", "PSH Flag Count", "ACK Flag Count",
    "URG Flag Count", "Average Packet Size", "Avg Fwd Segment Size",
    "Avg Bwd Segment Size", "Init_Win_bytes_forward", "Init_Win_bytes_backward",
    "Active Mean", "Active Std", "Idle Mean", "Idle Std",
]


class DDoSAgent(BaseAgent):
    """
    DDoS detection agent using XGBoost + LightGBM ensemble.
    Trained on CIC-DDoS2019 dataset.
    """

    def __init__(self, agent_id: str = "AGT-004", name: str = "DDoS Shield"):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.DDOS,
            name=name,
        )
        self._scaler: Optional[StandardScaler] = None
        self._label_encoder: Optional[LabelEncoder] = None
        self._feature_names = DDOS_FEATURES

    def get_feature_names(self) -> List[str]:
        return self._feature_names

    def train(self, data: Any = None, labels: Any = None, **kwargs) -> Dict[str, float]:
        """
        Train on CIC-DDoS2019 dataset.
        If data/labels not provided, loads from processed dataset path.
        """
        settings = get_settings()

        if data is None or labels is None:
            data, labels = self._load_dataset(settings)

        logger.info("ddos.training_started", samples=len(data))

        # Preprocessing
        self._scaler = StandardScaler()
        X = self._scaler.fit_transform(data)

        self._label_encoder = LabelEncoder()
        y = self._label_encoder.fit_transform(labels)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Ensemble: XGBoost + LightGBM
        xgb_clf = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="logloss",
            n_jobs=-1,
            random_state=42,
        )

        lgb_clf = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.1,
            n_jobs=-1,
            random_state=42,
            verbose=-1,
        )

        self._model = VotingClassifier(
            estimators=[("xgb", xgb_clf), ("lgb", lgb_clf)],
            voting="soft",
        )

        self._model.fit(X_train, y_train)

        # Evaluate
        y_pred = self._model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average="weighted")

        self._detection_accuracy = accuracy * 100

        # Save model + scaler
        self.save_model()
        joblib.dump(self._scaler, self._model_dir / "scaler.pkl")
        joblib.dump(self._label_encoder, self._model_dir / "label_encoder.pkl")

        metrics = {"accuracy": accuracy, "f1_score": f1}
        logger.info("ddos.training_complete", **metrics)
        return metrics

    def predict(self, sample: Any) -> DetectionResult:
        """Run inference on a single flow sample."""
        if self._model is None:
            # Fallback for demo when models are not yet trained
            import random
            is_threat = random.random() > 0.5
            confidence = random.uniform(70, 99)
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
        elif isinstance(sample, np.ndarray):
            features = sample.reshape(1, -1) if sample.ndim == 1 else sample
        else:
            features = np.array(sample).reshape(1, -1)

        if self._scaler:
            features = self._scaler.transform(features)

        proba = self._model.predict_proba(features)[0]
        pred_class = self._model.predict(features)[0]
        confidence = float(max(proba) * 100)

        is_threat = pred_class != 0  # 0 = benign
        severity = self._compute_severity(confidence, sample)

        self._last_activity = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )

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
        """Streaming detection on flow events."""
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
                logger.error("ddos.detect_error", error=str(e))
            finally:
                self._current_load = max(0, self._current_load - 1)

    def load_model(self) -> bool:
        """Load pre-trained model, scaler, and label encoder."""
        if not super().load_model():
            return False
        scaler_path = self._model_dir / "scaler.pkl"
        le_path = self._model_dir / "label_encoder.pkl"
        if scaler_path.exists():
            self._scaler = joblib.load(scaler_path)
        if le_path.exists():
            self._label_encoder = joblib.load(le_path)
        return True

    def _load_dataset(self, settings) -> tuple:
        """Load CIC-DDoS2019 dataset from processed path."""
        processed_dir = settings.dataset_processed_path / "ddos"
        X_path = processed_dir / "X.npy"
        y_path = processed_dir / "y.npy"

        if X_path.exists() and y_path.exists():
            X = np.load(X_path)
            y = np.load(y_path, allow_pickle=True)
            return X, y

        # Try to load from CSV
        csv_path = processed_dir / "ddos_processed.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            available_features = [f for f in self._feature_names if f in df.columns]
            if not available_features:
                available_features = [c for c in df.columns if c not in ["Label", "label"]]
            self._feature_names = available_features
            X = df[available_features].values
            label_col = "Label" if "Label" in df.columns else "label"
            y = df[label_col].values
            return X, y

        raise FileNotFoundError(
            f"DDoS dataset not found at {processed_dir}. "
            "Run: python -m datasets.downloader --agent ddos"
        )

    def _compute_severity(self, confidence: float, sample: Any) -> ThreatSeverity:
        """Determine severity based on confidence and traffic volume."""
        flow_rate = 0
        if isinstance(sample, dict):
            flow_rate = sample.get("Flow Packets/s", 0) or 0

        if confidence > 95 or flow_rate > 100000:
            return ThreatSeverity.CRITICAL
        elif confidence > 85:
            return ThreatSeverity.HIGH
        elif confidence > 70:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW

    def _build_description(self, sample: Any, confidence: float, is_threat: bool) -> str:
        if not is_threat:
            return "Benign traffic flow detected"
        src = sample.get("Src IP", "unknown") if isinstance(sample, dict) else "unknown"
        return f"DDoS attack detected from {src} with {confidence:.1f}% confidence"
