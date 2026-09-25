"""
CDSI RL Adaptive Threshold — Reinforcement learning for dynamic threshold tuning.

Uses a simple DQN agent to optimize detection thresholds based on
false positive/negative rates.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class AdaptiveThresholdAgent:
    """
    RL agent that tunes detection thresholds to minimize
    false positives while maintaining detection rate.

    State: [current_threshold, fp_rate, fn_rate, detection_rate, avg_confidence]
    Actions: [decrease_threshold, keep_threshold, increase_threshold]
    """

    def __init__(
        self,
        initial_threshold: float = 0.7,
        learning_rate: float = 0.01,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
    ):
        self.threshold = initial_threshold
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.step_size = 0.02

        # Simple Q-table (discretized states)
        self.q_table: Dict[tuple, np.ndarray] = {}
        self.memory: deque = deque(maxlen=10000)
        self.history: List[Dict[str, float]] = []

    def get_state(
        self,
        fp_rate: float,
        fn_rate: float,
        detection_rate: float,
        avg_confidence: float,
    ) -> tuple:
        """Discretize continuous state into bins."""
        return (
            round(self.threshold, 2),
            round(fp_rate, 1),
            round(fn_rate, 1),
            round(detection_rate, 1),
            round(avg_confidence, 1),
        )

    def select_action(self, state: tuple) -> int:
        """Epsilon-greedy action selection. 0=decrease, 1=keep, 2=increase."""
        if random.random() < self.epsilon:
            return random.randint(0, 2)

        q_values = self.q_table.get(state, np.zeros(3))
        return int(np.argmax(q_values))

    def step(
        self,
        fp_rate: float,
        fn_rate: float,
        detection_rate: float,
        avg_confidence: float,
    ) -> float:
        """
        Take one RL step: observe environment, select action, update threshold.
        Returns updated threshold.
        """
        state = self.get_state(fp_rate, fn_rate, detection_rate, avg_confidence)
        action = self.select_action(state)

        # Execute action
        if action == 0:
            self.threshold = max(0.3, self.threshold - self.step_size)
        elif action == 2:
            self.threshold = min(0.99, self.threshold + self.step_size)

        # Compute reward
        reward = self._compute_reward(fp_rate, fn_rate, detection_rate)

        # New state
        new_state = self.get_state(fp_rate, fn_rate, detection_rate, avg_confidence)

        # Q-learning update
        self._update_q(state, action, reward, new_state)

        self.history.append({
            "threshold": self.threshold,
            "fp_rate": fp_rate,
            "fn_rate": fn_rate,
            "detection_rate": detection_rate,
            "reward": reward,
        })

        return self.threshold

    def _compute_reward(
        self,
        fp_rate: float,
        fn_rate: float,
        detection_rate: float,
    ) -> float:
        """
        Reward function:
          - Penalize false positives (annoying alerts)
          - Heavily penalize false negatives (missed attacks)
          - Reward high detection rate
        """
        reward = detection_rate * 2.0  # Encourage high detection
        reward -= fp_rate * 3.0       # Penalize false positives
        reward -= fn_rate * 5.0       # Heavily penalize missed attacks
        return reward

    def _update_q(
        self,
        state: tuple,
        action: int,
        reward: float,
        next_state: tuple,
    ) -> None:
        """Q-learning value update."""
        if state not in self.q_table:
            self.q_table[state] = np.zeros(3)
        if next_state not in self.q_table:
            self.q_table[next_state] = np.zeros(3)

        best_next = np.max(self.q_table[next_state])
        current = self.q_table[state][action]

        self.q_table[state][action] = current + self.lr * (
            reward + self.gamma * best_next - current
        )

    def get_threshold(self) -> float:
        return self.threshold

    def get_stats(self) -> Dict[str, Any]:
        return {
            "threshold": self.threshold,
            "q_table_size": len(self.q_table),
            "history_length": len(self.history),
            "epsilon": self.epsilon,
        }
