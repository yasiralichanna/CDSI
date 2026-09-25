"""
CDSI Prometheus Metrics — Observability instrumentation.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, Info

# ── Agent Metrics ──
AGENT_DETECTIONS = Counter(
    "cdsi_agent_detections_total",
    "Total detections by agent",
    ["agent_id", "agent_type"],
)

AGENT_TRUST_SCORE = Gauge(
    "cdsi_agent_trust_score",
    "Current trust score per agent",
    ["agent_id"],
)

AGENT_LOAD = Gauge(
    "cdsi_agent_current_load",
    "Current load percentage per agent",
    ["agent_id"],
)

# ── Threat Metrics ──
THREATS_DETECTED = Counter(
    "cdsi_threats_detected_total",
    "Total threats detected",
    ["severity", "type"],
)

FALSE_POSITIVES = Counter(
    "cdsi_false_positives_total",
    "Total false positives",
    ["type"],
)

# ── Consensus Metrics ──
CONSENSUS_LATENCY = Histogram(
    "cdsi_consensus_latency_ms",
    "Consensus decision latency in milliseconds",
    buckets=[100, 250, 500, 1000, 2000, 5000],
)

CONSENSUS_DECISIONS = Counter(
    "cdsi_consensus_decisions_total",
    "Total consensus decisions",
    ["decision"],
)

# ── System Metrics ──
ACTIVE_AGENTS = Gauge(
    "cdsi_active_agents",
    "Number of active agents",
)

ACTIVE_THREATS = Gauge(
    "cdsi_active_threats",
    "Number of unresolved threats",
)

MODEL_ACCURACY = Gauge(
    "cdsi_model_accuracy",
    "Current model accuracy",
    ["agent_type"],
)

# ── System Info ──
SYSTEM_INFO = Info(
    "cdsi_system",
    "CDSI system information",
)
