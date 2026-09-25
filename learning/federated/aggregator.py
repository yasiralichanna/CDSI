"""
CDSI Federated Learning — FedAvg aggregation server.

Each agent trains locally; this server aggregates model weights.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class FederatedAggregator:
    """
    Federated Averaging (FedAvg) server.
    Collects local model updates from agents and produces a global model.
    """

    def __init__(self):
        self._global_weights: Optional[np.ndarray] = None
        self._round = 0
        self._client_updates: List[Dict[str, Any]] = []
        self._history: List[Dict[str, Any]] = []

    def register_update(
        self,
        agent_id: str,
        weights: np.ndarray,
        num_samples: int,
        metrics: Dict[str, float],
    ) -> None:
        """Register a local model update from an agent."""
        self._client_updates.append({
            "agent_id": agent_id,
            "weights": weights,
            "num_samples": num_samples,
            "metrics": metrics,
        })
        logger.info(
            "federated.update_received",
            agent_id=agent_id,
            samples=num_samples,
            round=self._round,
        )

    def aggregate(self, min_clients: int = 2) -> Optional[np.ndarray]:
        """
        Perform weighted FedAvg aggregation.
        Returns aggregated global weights, or None if not enough clients.
        """
        if len(self._client_updates) < min_clients:
            logger.warning(
                "federated.insufficient_clients",
                received=len(self._client_updates),
                required=min_clients,
            )
            return None

        self._round += 1
        total_samples = sum(u["num_samples"] for u in self._client_updates)

        # Weighted average of model weights
        aggregated = None
        for update in self._client_updates:
            weight_factor = update["num_samples"] / total_samples
            scaled = update["weights"] * weight_factor
            if aggregated is None:
                aggregated = scaled
            else:
                aggregated += scaled

        self._global_weights = aggregated

        # Log round history
        avg_accuracy = np.mean([
            u["metrics"].get("accuracy", 0) for u in self._client_updates
        ])
        self._history.append({
            "round": self._round,
            "num_clients": len(self._client_updates),
            "total_samples": total_samples,
            "avg_accuracy": float(avg_accuracy),
        })

        logger.info(
            "federated.aggregated",
            round=self._round,
            clients=len(self._client_updates),
            avg_accuracy=float(avg_accuracy),
        )

        self._client_updates.clear()
        return self._global_weights

    def get_global_weights(self) -> Optional[np.ndarray]:
        """Return the current global model weights."""
        return self._global_weights

    def get_history(self) -> List[Dict[str, Any]]:
        return self._history.copy()


class FederatedClient:
    """Mixin for agents to participate in federated learning."""

    def extract_weights(self, model: Any) -> np.ndarray:
        """Extract model weights as a flat numpy array."""
        if hasattr(model, "coef_"):
            return np.concatenate([model.coef_.flatten(), model.intercept_.flatten()])
        elif hasattr(model, "feature_importances_"):
            return model.feature_importances_
        elif hasattr(model, "get_booster"):
            # XGBoost
            booster = model.get_booster()
            return np.array(list(booster.get_score(importance_type="weight").values()))
        else:
            raise ValueError("Cannot extract weights from this model type")

    def apply_weights(self, model: Any, weights: np.ndarray) -> Any:
        """Apply aggregated weights back to a model. Returns updated model."""
        if hasattr(model, "feature_importances_"):
            model.feature_importances_ = weights[:len(model.feature_importances_)]
        return model
