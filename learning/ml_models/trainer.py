"""
CDSI ML Model Trainer — Unified training framework.

Supports: XGBoost, RandomForest, LightGBM, LSTM.
Includes model versioning and hyperparameter tuning.
"""
from __future__ import annotations

import time
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import joblib
import structlog
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from config.settings import get_settings

logger = structlog.get_logger(__name__)

ModelType = Literal["xgboost", "random_forest", "lightgbm", "lstm"]


class ModelTrainer:
    """Unified model training with versioning and hyperparameter tuning."""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        settings = get_settings()
        self._model_dir = settings.model_storage_path / agent_type
        self._model_dir.mkdir(parents=True, exist_ok=True)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        model_type: ModelType = "xgboost",
        hyperparams: Optional[Dict[str, Any]] = None,
        tune: bool = False,
    ) -> Tuple[Any, Dict[str, float]]:
        """
        Train a model with optional hyperparameter tuning.
        Returns (model, metrics_dict).
        """
        logger.info(
            "trainer.start",
            agent=self.agent_type,
            model_type=model_type,
            samples=len(X_train),
        )

        model = self._create_model(model_type, hyperparams)

        if tune:
            model = self._tune_hyperparams(model, X_train, y_train, model_type)

        start = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start

        # Cross-validation
        cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="accuracy")

        metrics = {
            "cv_accuracy_mean": float(cv_scores.mean()),
            "cv_accuracy_std": float(cv_scores.std()),
            "train_time_seconds": train_time,
        }

        logger.info("trainer.complete", **metrics)
        return model, metrics

    def evaluate(
        self,
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> Dict[str, float]:
        """Evaluate a trained model."""
        y_pred = model.predict(X_test)
        return {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "f1_score": float(f1_score(y_test, y_pred, average="weighted")),
            "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
        }

    def save_versioned(self, model: Any, metrics: Dict[str, float], version: Optional[str] = None) -> Path:
        """Save model with version metadata."""
        if version is None:
            version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        version_dir = self._model_dir / f"v_{version}"
        version_dir.mkdir(parents=True, exist_ok=True)

        model_path = version_dir / "model.pkl"
        joblib.dump(model, model_path)

        meta = {
            "version": version,
            "agent_type": self.agent_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
        }
        meta_path = version_dir / "metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2))

        # Update latest symlink
        latest_path = self._model_dir / f"{self.agent_type}_model.pkl"
        joblib.dump(model, latest_path)

        logger.info("trainer.saved", version=version, path=str(model_path))
        return model_path

    def _create_model(self, model_type: ModelType, hyperparams: Optional[Dict] = None) -> Any:
        params = hyperparams or {}

        if model_type == "xgboost":
            import xgboost as xgb
            return xgb.XGBClassifier(
                n_estimators=params.get("n_estimators", 200),
                max_depth=params.get("max_depth", 8),
                learning_rate=params.get("learning_rate", 0.1),
                use_label_encoder=False,
                eval_metric="logloss",
                n_jobs=-1,
                random_state=42,
                **{k: v for k, v in params.items() if k not in ["n_estimators", "max_depth", "learning_rate"]},
            )
        elif model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(
                n_estimators=params.get("n_estimators", 200),
                max_depth=params.get("max_depth", 12),
                n_jobs=-1,
                random_state=42,
                **{k: v for k, v in params.items() if k not in ["n_estimators", "max_depth"]},
            )
        elif model_type == "lightgbm":
            import lightgbm as lgb
            return lgb.LGBMClassifier(
                n_estimators=params.get("n_estimators", 200),
                max_depth=params.get("max_depth", 8),
                learning_rate=params.get("learning_rate", 0.1),
                n_jobs=-1,
                random_state=42,
                verbose=-1,
                **{k: v for k, v in params.items() if k not in ["n_estimators", "max_depth", "learning_rate"]},
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def _tune_hyperparams(
        self, model: Any, X: np.ndarray, y: np.ndarray, model_type: ModelType
    ) -> Any:
        """Grid search hyperparameter tuning."""
        param_grids = {
            "xgboost": {
                "n_estimators": [100, 200, 300],
                "max_depth": [6, 8, 10],
                "learning_rate": [0.05, 0.1, 0.2],
            },
            "random_forest": {
                "n_estimators": [100, 200, 300],
                "max_depth": [8, 12, 16],
            },
            "lightgbm": {
                "n_estimators": [100, 200, 300],
                "max_depth": [6, 8, 10],
                "learning_rate": [0.05, 0.1, 0.2],
            },
        }

        grid = param_grids.get(model_type, {})
        if grid:
            gs = GridSearchCV(model, grid, cv=3, scoring="accuracy", n_jobs=-1)
            gs.fit(X, y)
            logger.info("trainer.tuned", best_params=gs.best_params_, best_score=gs.best_score_)
            return gs.best_estimator_
        return model
