"""
CDSI Phishing Detection Agent

Uses PhishTank + UCI Phishing dataset.
Detects phishing URLs and emails using URL feature analysis with XGBoost.
"""
from __future__ import annotations

import asyncio
import numpy as np
import pandas as pd
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

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

PHISHING_FEATURES = [
    "url_length", "hostname_length", "path_length", "num_dots",
    "num_hyphens", "num_underscores", "num_slashes", "num_questionmarks",
    "num_ats", "num_equals", "num_ampersands", "num_digits",
    "num_subdomains", "has_ip", "has_https", "has_port",
    "path_depth", "domain_entropy", "tld_length", "has_suspicious_tld",
    "num_special_chars", "has_login_keyword", "has_secure_keyword",
    "has_update_keyword", "has_bank_keyword", "digit_ratio",
    "letter_ratio", "is_shortened", "domain_age_proxy",
    "alexa_rank_proxy",
]


class PhishingAgent(BaseAgent):
    """Phishing detection using XGBoost on URL + content features."""

    def __init__(self, agent_id: str = "AGT-003", name: str = "Phishing Guard"):
        super().__init__(agent_id=agent_id, agent_type=AgentType.PHISHING, name=name)
        self._scaler: Optional[StandardScaler] = None
        self._label_encoder: Optional[LabelEncoder] = None
        self._feature_names = PHISHING_FEATURES

    def get_feature_names(self) -> List[str]:
        return self._feature_names

    def extract_url_features(self, url: str) -> Dict[str, float]:
        """Extract features from a URL for prediction."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""

        suspicious_tlds = {"tk", "ml", "ga", "cf", "gq", "xyz", "top", "work", "click"}
        login_keywords = {"login", "signin", "verify", "account", "secure", "update", "bank"}

        tld = hostname.split(".")[-1] if "." in hostname else ""

        features = {
            "url_length": len(url),
            "hostname_length": len(hostname),
            "path_length": len(path),
            "num_dots": url.count("."),
            "num_hyphens": url.count("-"),
            "num_underscores": url.count("_"),
            "num_slashes": url.count("/"),
            "num_questionmarks": url.count("?"),
            "num_ats": url.count("@"),
            "num_equals": url.count("="),
            "num_ampersands": url.count("&"),
            "num_digits": sum(c.isdigit() for c in url),
            "num_subdomains": max(0, hostname.count(".") - 1),
            "has_ip": 1 if any(c.isdigit() for c in hostname.split(".")[0]) and hostname.replace(".", "").isdigit() else 0,
            "has_https": 1 if parsed.scheme == "https" else 0,
            "has_port": 1 if parsed.port else 0,
            "path_depth": path.count("/"),
            "domain_entropy": self._entropy(hostname),
            "tld_length": len(tld),
            "has_suspicious_tld": 1 if tld in suspicious_tlds else 0,
            "num_special_chars": sum(not c.isalnum() and c not in ".-/" for c in url),
            "has_login_keyword": 1 if any(kw in url.lower() for kw in login_keywords) else 0,
            "has_secure_keyword": 1 if "secure" in url.lower() else 0,
            "has_update_keyword": 1 if "update" in url.lower() else 0,
            "has_bank_keyword": 1 if "bank" in url.lower() else 0,
            "digit_ratio": sum(c.isdigit() for c in url) / max(len(url), 1),
            "letter_ratio": sum(c.isalpha() for c in url) / max(len(url), 1),
            "is_shortened": 1 if len(hostname) < 10 and len(path) > 5 else 0,
            "domain_age_proxy": 0,
            "alexa_rank_proxy": 0,
        }
        return features

    def train(self, data: Any = None, labels: Any = None, **kwargs) -> Dict[str, float]:
        settings = get_settings()
        if data is None or labels is None:
            data, labels = self._load_dataset(settings)

        logger.info("phishing.training_started", samples=len(data))

        self._scaler = StandardScaler()
        X = self._scaler.fit_transform(data)
        self._label_encoder = LabelEncoder()
        y = self._label_encoder.fit_transform(labels)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self._model = xgb.XGBClassifier(
            n_estimators=300, max_depth=10, learning_rate=0.1,
            use_label_encoder=False, eval_metric="logloss",
            n_jobs=-1, random_state=42,
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
        logger.info("phishing.training_complete", **metrics)
        return metrics

    def predict(self, sample: Any) -> DetectionResult:
        if self._model is None:
            # Fallback for demo when models are not yet trained
            import random
            is_threat = random.random() > 0.7
            confidence = random.uniform(60, 94)
            severity = self._compute_severity(confidence)
            return DetectionResult(
                is_threat=is_threat,
                confidence=confidence,
                severity=severity,
                description=self._build_description(sample, confidence, is_threat),
                metadata={"mock": True},
            )

        if isinstance(sample, str):
            sample = self.extract_url_features(sample)

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

        return DetectionResult(
            is_threat=is_threat,
            confidence=confidence,
            severity=self._compute_severity(confidence),
            description=self._build_description(sample, confidence, is_threat),
            metadata={"predicted_class": int(pred_class), "probabilities": proba.tolist()},
        )

    async def stream_detect(
        self, event_stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[DetectionResult]:
        async for event in event_stream:
            self._current_load = min(100, self._current_load + 1)
            try:
                if "url" in event:
                    sample = self.extract_url_features(event["url"])
                else:
                    sample = event
                result = self.predict(sample)
                if result.is_threat:
                    threat = ThreatEvent(
                        agent_id=self.agent_id, agent_type=self.agent_type,
                        severity=result.severity, confidence=result.confidence,
                        description=result.description,
                        source_ip=event.get("src_ip"),
                        raw_data=event,
                    )
                    await self.publish_threat(threat)
                yield result
            except Exception as e:
                logger.error("phishing.detect_error", error=str(e))
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
        processed_dir = settings.dataset_processed_path / "phishing"
        for fmt in [("X.npy", "y.npy"), ("phishing_processed.csv",)]:
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
                        feats = [c for c in df.columns if c not in ["Label", "label", "Result"]]
                    self._feature_names = feats
                    lc = next(c for c in ["Label", "label", "Result"] if c in df.columns)
                    return df[feats].values, df[lc].values
        raise FileNotFoundError(f"Phishing dataset not found at {processed_dir}")

    def _entropy(self, s: str) -> float:
        from collections import Counter
        import math
        if not s:
            return 0
        counts = Counter(s)
        length = len(s)
        return -sum((c / length) * math.log2(c / length) for c in counts.values())

    def _compute_severity(self, confidence: float) -> ThreatSeverity:
        if confidence > 95:
            return ThreatSeverity.CRITICAL
        elif confidence > 80:
            return ThreatSeverity.HIGH
        elif confidence > 60:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW

    def _build_description(self, sample: Any, confidence: float, is_threat: bool) -> str:
        if not is_threat:
            return "Legitimate URL/content"
        return f"Phishing attempt detected ({confidence:.1f}% confidence)"
