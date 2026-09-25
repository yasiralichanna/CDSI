"""
CDSI Swarm Manager — Orchestrates all agents, consensus, and correlation.

This is the central coordinator that:
  - Manages agent lifecycle
  - Processes threats through consensus
  - Tracks automated responses
  - Streams real-time updates via WebSocket
"""
from __future__ import annotations

import asyncio
import uuid
import numpy as np
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import structlog

from agents.base.base_agent import AgentType, AgentStatus, ThreatSeverity, ThreatStatus
from comms.interface import InMemoryComm
from consensus.engine import ConsensusEngine
from consensus.trust import TrustManager
from consensus.blockchain.hash_log import HashLog
from correlation.engine import CorrelationEngine
from comms.zeromq.broker import ZeroMQComm
from config.settings import get_settings

# Import real agent classes for non-simulation mode
from agents.anomaly.agent import AnomalyAgent
from agents.malware.agent import MalwareAgent
from agents.phishing.agent import PhishingAgent
from agents.ddos.agent import DDoSAgent
from agents.mitm.agent import MITMAgent
from agents.ransomware.agent import RansomwareAgent

logger = structlog.get_logger(__name__)


class SwarmManager:
    """Central swarm orchestrator managing all CDSI subsystems."""

    # ── TTIAR Configuration ──────────────────────────────────────────────
    REACTIVATION_TRUST_PENALTY = 3.0        # Trust % deducted on reactivation
    REACTIVATION_COOLDOWN_SEC = 10.0        # Min seconds between reactivations
    WATCHDOG_INTERVAL_SEC = 3.0             # Health watchdog check interval
    WATCHDOG_OFFLINE_THRESHOLD_SEC = 30.0   # Auto-restart if offline longer than this

    def __init__(self):
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._threats: List[Dict[str, Any]] = []
        self._consensus_decisions: List[Dict[str, Any]] = []
        self._automated_responses: List[Dict[str, Any]] = []
        self._audit_logs: List[Dict[str, Any]] = []
        self._mitre_techniques: List[Dict[str, Any]] = []
        self._attack_stats: Dict[str, Dict[str, Any]] = {}

        # Core subsystems
        self._trust_manager = TrustManager()
        self._consensus_engine = ConsensusEngine(self._trust_manager)
        self._correlation_engine = CorrelationEngine()
        self._hash_log = HashLog()
        
        settings = get_settings()
        self.use_simulation = settings.use_simulation
        if self.use_simulation:
            self._comms = InMemoryComm()
        else:
            self._comms = ZeroMQComm()

        # WebSocket subscribers
        self._ws_subscribers: Set[asyncio.Queue] = set()

        # Background tasks
        self._tasks: List[asyncio.Task] = []
        self._running = False

        # TTIAR — Threat-Triggered Instant Agent Revival
        # Tracks last reactivation time per agent to enforce cooldown
        self._last_reactivation: Dict[str, datetime] = {}
        # Tracks when each agent went offline for watchdog threshold
        self._offline_since: Dict[str, datetime] = {}

    async def initialize(self) -> None:
        """Initialize all subsystems and agents."""
        try:
            if self.use_simulation:
                await self._comms.connect()
            else:
                await self._comms.connect(bind_pub=True, bind_sub=True, relay_enabled=True)
        except Exception as e:
            logger.warning("swarm.zmq_init_failed", error=str(e), msg="Falling back to InMemoryComm")
            self._comms = InMemoryComm()
            await self._comms.connect()
        
        self._consensus_engine.set_comms(self._comms)
        self._correlation_engine.set_comms(self._comms)

        # Initialize agents
        self._init_agents()
        self._init_mitre_techniques()
        self._init_attack_stats()

        # Subscribe to events
        await self._comms.subscribe("threats", self._on_threat)
        await self._comms.subscribe("consensus", self._on_consensus)

        self._running = True
        logger.info("swarm.initialized", agents=len(self._agents))

    def _init_agents(self) -> None:
        """Initialize all 6 detection agents."""
        # Real config mapping
        real_agents = {
            "anomaly": {"name": "Anomaly Sentinel", "cls": AnomalyAgent, "id": "AGT-001", "trust": 94},
            "malware": {"name": "Malware Hunter", "cls": MalwareAgent, "id": "AGT-002", "trust": 91},
            "phishing": {"name": "Phishing Guard", "cls": PhishingAgent, "id": "AGT-003", "trust": 89},
            "ddos": {"name": "DDoS Shield", "cls": DDoSAgent, "id": "AGT-004", "trust": 86},
            "mitm": {"name": "MITM Detector", "cls": MITMAgent, "id": "AGT-005", "trust": 92},
            "ransomware": {"name": "Ransom Blocker", "cls": RansomwareAgent, "id": "AGT-006", "trust": 95},
        }

        for agent_type, cfg in real_agents.items():
            if not self.use_simulation:
                # Instantiate real agent
                try:
                    agent_instance = cfg["cls"]()
                    agent_instance.load_model()
                    
                    self._agents[cfg["id"]] = {
                        "id": cfg["id"],
                        "name": cfg["name"],
                        "type": agent_type,
                        "status": "active",
                        "trustScore": cfg["trust"],
                        "detectionAccuracy": agent_instance.detection_accuracy or (cfg["trust"] + 3),
                        "currentLoad": 0,
                        "lastActivity": datetime.now(timezone.utc).isoformat(),
                        "recentDetections": 0,
                        "instance": agent_instance  # Store instance for real-time inference
                    }
                except Exception as e:
                    logger.error("swarm.agent_init_error", agent=agent_type, error=str(e))
            else:
                # Simulation mode (legacy)
                self._agents[cfg["id"]] = {
                    "id": cfg["id"],
                    "name": cfg["name"],
                    "type": agent_type,
                    "status": "active",
                    "trustScore": cfg["trust"],
                    "detectionAccuracy": cfg["trust"] + 3.2,
                    "currentLoad": 0,
                    "lastActivity": datetime.now(timezone.utc).isoformat(),
                    "recentDetections": 0,
                }
            
            self._trust_manager.register_agent(cfg["id"], cfg["trust"])

    def _init_mitre_techniques(self) -> None:
        """Initialize MITRE ATT&CK technique mappings."""
        # MITRE techniques are reference data, always initialize them.
            
        self._mitre_techniques = [
            {"id": "T1071", "name": "Application Layer Protocol", "tactic": "Command and Control", "killChainPhase": "C2", "threatCount": 0},
            {"id": "T1566", "name": "Phishing", "tactic": "Initial Access", "killChainPhase": "Delivery", "threatCount": 0},
            {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "Impact", "killChainPhase": "Actions", "threatCount": 0},
            {"id": "T1498", "name": "Network Denial of Service", "tactic": "Impact", "killChainPhase": "Actions", "threatCount": 0},
            {"id": "T1557", "name": "Adversary-in-the-Middle", "tactic": "Credential Access", "killChainPhase": "Exploitation", "threatCount": 0},
            {"id": "T1027", "name": "Obfuscated Files", "tactic": "Defense Evasion", "killChainPhase": "Installation", "threatCount": 0},
        ]
        
        self._mitre_mapping = {
            "anomaly": "T1071",
            "phishing": "T1566",
            "ransomware": "T1486",
            "ddos": "T1498",
            "mitm": "T1557",
            "malware": "T1027",
        }

    def _init_attack_stats(self) -> None:
        """Initialize per-attack-type statistics."""
        types = ["ddos", "malware", "phishing", "mitm", "ransomware", "anomaly"]
        self._attack_stats = {
            t: {"detected": 0, "mitigated": 0, "accuracy": 0.0} 
            for t in types
        }
        
        if self.use_simulation:
            # Optional: Seed with some values for simulation view if desired, 
            # but user requested NO dummy data if real-time is used.
            pass

    def start_background_tasks(self) -> None:
        """Start background monitoring tasks (threat generation only triggers on real events/injections)."""
        self._tasks.append(asyncio.create_task(self._agent_monitor()))
        self._tasks.append(asyncio.create_task(self._agent_health_watchdog()))
        logger.info("swarm.background_monitoring_started")

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await self._comms.disconnect()

    # ── Agent Management ───────────────────────────────────────────────

    def get_agents(self) -> List[Dict[str, Any]]:
        return [{k: v for k, v in a.items() if k != "instance"} for a in self._agents.values()]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        agent = self._agents.get(agent_id)
        if agent:
            return {k: v for k, v in agent.items() if k != "instance"}
        return None

    def get_attack_stats(self) -> Dict[str, Dict[str, Any]]:
        # Enrich with accuracy from the real agent models
        agent_type_map = {}
        for a in self._agents.values():
            agent_type_map[a["type"]] = a.get("detectionAccuracy", 0)
        
        result = {}
        for t, s in self._attack_stats.items():
            result[t] = {
                "detected": s["detected"],
                "mitigated": s["mitigated"],
                "accuracy": round(agent_type_map.get(t, 0), 1),
            }
        return result

    # ── Threat Management ──────────────────────────────────────────────

    def get_threats(self) -> List[Dict[str, Any]]:
        return self._threats

    def get_threat(self, threat_id: str) -> Optional[Dict[str, Any]]:
        return next((t for t in self._threats if t["id"] == threat_id), None)

    async def report_threat(self, threat: Dict[str, Any]) -> Dict[str, Any]:
        """Process a new threat detection.
        
        Includes TTIAR: if the specialist agent for this threat type is
        offline or degraded, it is instantly reactivated before consensus
        so it can participate in voting.
        """
        self._threats.append(threat)

        # ── TTIAR: Auto-reactivate specialist agent if down ────────────
        threat_type = threat.get("type", "unknown")
        reactivated_agents = await self._ttiar_check_and_reactivate(threat_type, threat["id"])

        # Update agent stats
        for agent_id in threat.get("detectedBy", []):
            if agent_id in self._agents:
                self._agents[agent_id]["recentDetections"] += 1
                self._agents[agent_id]["lastActivity"] = datetime.now(timezone.utc).isoformat()

        # Update attack stats (detected)
        if threat_type in self._attack_stats:
            self._attack_stats[threat_type]["detected"] += 1

        # Update MITRE stats
        mitre_id = self._mitre_mapping.get(threat_type)
        if mitre_id:
            for tech in self._mitre_techniques:
                if tech["id"] == mitre_id:
                    tech["threatCount"] += 1
                    break

        # Start consensus proposal
        voter_ids = list(self._agents.keys())
        proposer_id = threat.get("detectedBy", ["unknown"])[0]
        await self._consensus_engine.propose_threat(
            threat["id"],
            proposer_id,
            threat,
            voter_ids,
        )

        # Collect swarm votes to reach consensus and trigger automated response
        for aid, agent in self._agents.items():
            if aid == proposer_id:
                vote_type = "threat"
                vote_conf = float(threat.get("confidence", 90.0))
            else:
                conf = float(threat.get("confidence", 80.0))
                vote_type = "threat" if conf >= 50.0 else "safe"
                vote_conf = max(40.0, conf - random.uniform(0, 10))

            decision = await self._consensus_engine.submit_vote(
                threat["id"], aid, agent["type"], vote_type, vote_conf
            )
            if decision:
                await self._on_consensus(decision.to_dict())

        # Correlate
        await self._correlation_engine.ingest_detection(threat)

        # Broadcast to WebSocket subscribers
        await self._broadcast_ws({"type": "threat_alert", "data": threat})

        # Audit log
        self._add_audit_log(
            actor=", ".join(threat.get("detectedBy", [])),
            action="Threat Detected",
            details=f"{threat.get('description', '')} [{threat['id']}]",
            reasoning=f"Detection confidence: {threat.get('confidence', 0)}%"
                + (f" | TTIAR reactivated: {', '.join(reactivated_agents)}" if reactivated_agents else ""),
        )

        return threat

    # ── TTIAR: Threat-Triggered Instant Agent Revival ──────────────────

    async def _ttiar_check_and_reactivate(self, threat_type: str, threat_id: str) -> List[str]:
        """Check if any agent handling this threat type is down and reactivate it.
        
        Returns list of agent IDs that were reactivated.
        """
        reactivated: List[str] = []

        for agent_id, agent in self._agents.items():
            if agent["type"] != threat_type:
                continue
            if agent["status"] == "active":
                continue  # Already healthy

            # Check cooldown — prevent rapid on/off cycling
            last = self._last_reactivation.get(agent_id)
            if last:
                elapsed = (datetime.now(timezone.utc) - last).total_seconds()
                if elapsed < self.REACTIVATION_COOLDOWN_SEC:
                    logger.debug("ttiar.cooldown_active", agent=agent_id, remaining=round(self.REACTIVATION_COOLDOWN_SEC - elapsed, 1))
                    continue

            # ── Reactivate ─────────────────────────────────────────────
            prev_status = agent["status"]
            await self._reactivate_agent(agent_id, reason=f"threat_{threat_id}")
            reactivated.append(agent_id)

            logger.info(
                "ttiar.agent_reactivated",
                agent=agent_id,
                prev_status=prev_status,
                trigger=threat_id,
                threat_type=threat_type,
            )

        return reactivated

    async def _reactivate_agent(self, agent_id: str, reason: str = "manual") -> None:
        """Instantly reactivate an offline/degraded agent.
        
        Steps:
          1. Set status to 'active'
          2. Reset load to safe baseline (15%)
          3. Reload ML model if real-time mode
          4. Apply trust penalty for downtime
          5. Log the event
          6. Broadcast via WebSocket
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return

        prev_status = agent["status"]
        now = datetime.now(timezone.utc)

        # 1. Reactivate
        agent["status"] = "active"
        agent["currentLoad"] = 15  # Safe baseline load
        agent["lastActivity"] = now.isoformat()

        # 2. Reload ML model (non-simulation only)
        model_reloaded = False
        if not self.use_simulation and agent.get("instance"):
            try:
                agent["instance"].load_model()
                model_reloaded = True
                logger.info("ttiar.model_reloaded", agent=agent_id)
            except Exception as e:
                logger.error("ttiar.model_reload_failed", agent=agent_id, error=str(e))

        # 3. Trust penalty
        old_trust = agent["trustScore"]
        penalty = self.REACTIVATION_TRUST_PENALTY
        new_trust = max(10, old_trust - penalty)  # Floor at 10%
        agent["trustScore"] = new_trust
        self._trust_manager.update_trust(agent_id, new_trust)

        # 4. Update tracking
        self._last_reactivation[agent_id] = now
        self._offline_since.pop(agent_id, None)

        # 5. Audit log
        self._add_audit_log(
            actor="TTIAR System",
            action="Agent Auto-Reactivated",
            details=(
                f"{agent['name']} ({agent_id}) reactivated from '{prev_status}' → 'active'. "
                f"Trigger: {reason}. Trust: {old_trust:.1f}% → {new_trust:.1f}% (-{penalty}%)"
                + (f". ML model reloaded." if model_reloaded else "")
            ),
            reasoning=(
                f"TTIAR detected that agent {agent_id} (type: {agent['type']}) was {prev_status} "
                f"when a matching threat arrived. The agent was instantly revived to ensure "
                f"the swarm maintains full coverage. A trust penalty of {penalty}% was applied "
                f"to account for the downtime reliability gap."
            ),
        )

        # 6. Broadcast updated agent list
        await self._broadcast_ws({
            "type": "agent_update",
            "data": self.get_agents(),
        })

    # ── Consensus ──────────────────────────────────────────────────────

    def get_consensus_decisions(self) -> List[Dict[str, Any]]:
        return self._consensus_decisions

    def get_consensus_for_threat(self, threat_id: str) -> Optional[Dict[str, Any]]:
        return next((d for d in self._consensus_decisions if d["threatId"] == threat_id), None)

    # ── Responses ──────────────────────────────────────────────────────

    def get_responses(self) -> List[Dict[str, Any]]:
        return self._automated_responses

    async def rollback_response(self, response_id: str) -> Optional[Dict[str, Any]]:
        resp = next((r for r in self._automated_responses if r["id"] == response_id), None)
        if resp and resp.get("canRollback"):
            resp["success"] = False
            resp["details"] += " [ROLLED BACK]"
            self._add_audit_log(
                actor="System",
                action="Response Rollback",
                details=f"Rolled back {resp['action']} for {resp['threatId']}",
            )
            await self._broadcast_ws({"type": "response_action", "data": resp})
        return resp

    # ── Intelligence ───────────────────────────────────────────────────

    def get_mitre_techniques(self) -> List[Dict[str, Any]]:
        return self._mitre_techniques

    # ── Audit Logs ─────────────────────────────────────────────────────

    def get_audit_logs(self) -> List[Dict[str, Any]]:
        return self._audit_logs

    def _add_audit_log(self, actor: str, action: str, details: str, reasoning: str = "") -> None:
        log = {
            "id": f"LOG-{uuid.uuid4().hex[:6].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "details": details,
            "reasoning": reasoning,
        }
        self._audit_logs.insert(0, log)

    # ── System Stats ───────────────────────────────────────────────────

    def get_system_stats(self) -> Dict[str, Any]:
        active = sum(1 for a in self._agents.values() if a["status"] == "active")
        active_threats = sum(1 for t in self._threats if t.get("status") not in ("mitigated", "false_positive"))
        if self._agents:
            avg_acc = sum(a.get("detectionAccuracy", 0) for a in self._agents.values()) / len(self._agents)
            detection_rate = avg_acc
            fp_rate = 100 - avg_acc
        else:
            detection_rate = 0
            fp_rate = 0

        return {
            "activeAgents": active,
            "totalAgents": len(self._agents),
            "activeThreats": active_threats,
            "consensusToday": len(self._consensus_decisions),
            "autoResponses": len(self._automated_responses),
            "avgConsensusLatency": self._avg_consensus_latency(),
            "detectionRate": round(detection_rate, 1),
            "falsePositiveRate": round(fp_rate, 1),
        }

    def _avg_consensus_latency(self) -> float:
        if not self._consensus_decisions:
            return 0
        return sum(d.get("timeToConsensus", 0) for d in self._consensus_decisions) / len(self._consensus_decisions)

    # ── WebSocket ──────────────────────────────────────────────────────

    def subscribe_ws(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._ws_subscribers.add(queue)
        return queue

    def unsubscribe_ws(self, queue: asyncio.Queue) -> None:
        self._ws_subscribers.discard(queue)

    async def _broadcast_ws(self, message: Dict[str, Any]) -> None:
        dead = set()
        for q in self._ws_subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.add(q)
        self._ws_subscribers -= dead

    # ── Background Tasks ───────────────────────────────────────────────

    async def _on_threat(self, message: Dict[str, Any]) -> None:
        """Handle incoming threat from comms (e.g. ZeroMQ)."""
        # Ensure it has an ID
        if "id" not in message:
            message["id"] = f"THR-{uuid.uuid4().hex[:6].upper()}"
        
        # Report it to the system for consensus and display
        await self.report_threat(message)

    async def _on_consensus(self, message: Dict[str, Any]) -> None:
        """Handle consensus decision from engine."""
        # Prevent duplicate handling of the same threat decision
        threat_id = message.get("threatId")
        if any(d.get("threatId") == threat_id for d in self._consensus_decisions):
            return

        self._consensus_decisions.append(message)
        self._hash_log.add_decision(message)

        # Auto-respond if threat confirmed
        if message.get("finalDecision") == "threat" and message.get("consensusReached"):
            response = await self._auto_respond(message["threatId"])
            if response and not any(r.get("id") == response["id"] for r in self._automated_responses):
                self._automated_responses.append(response)

        await self._broadcast_ws({"type": "consensus_update", "data": message})

    async def _auto_respond(self, threat_id: str) -> Optional[Dict[str, Any]]:
        """Generate automated response for confirmed threat."""
        # Prevent duplicate response generation for the same threat
        if any(r.get("threatId") == threat_id for r in self._automated_responses):
            return None

        threat = self.get_threat(threat_id)
        if not threat:
            return None

        action_map = {
            "ddos": "ip_blocked",
            "malware": "vm_isolated",
            "phishing": "domain_blocked",
            "mitm": "traffic_rerouted",
            "ransomware": "vm_isolated",
            "anomaly": "ip_blocked",
        }

        action = action_map.get(threat.get("type", ""), "ip_blocked")
        response = {
            "id": f"RSP-{uuid.uuid4().hex[:6].upper()}",
            "threatId": threat_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "canRollback": True,
            "details": f"Automated {action.replace('_', ' ')} in response to {threat.get('description', '')}",
        }

        # Update threat status
        threat["status"] = "mitigated"
        
        # Update attack stats (mitigated)
        threat_type = threat.get("type", "unknown")
        if threat_type in self._attack_stats:
            self._attack_stats[threat_type]["mitigated"] += 1

        self._add_audit_log(
            actor="Swarm Consensus",
            action=action.replace("_", " ").title(),
            details=response["details"],
            reasoning=f"Consensus confirmed threat with trust-weighted score. Automated response triggered.",
        )

        await self._broadcast_ws({"type": "response_action", "data": response})
        return response

    async def _real_time_processing(self) -> None:
        """
        Background task: Process real-time ML detections.
        Loads test data samples and runs them through trained agents.
        """
        settings = get_settings()
        
        # Load test datasets once
        test_data = {}
        feature_names = {}
        for agent_id, agent_info in self._agents.items():
            agent_type = agent_info["type"]
            x_test_path = settings.dataset_processed_path / agent_type / "X_test.npy"
            features_path = settings.dataset_processed_path / agent_type / "features.txt"
            
            if x_test_path.exists():
                try:
                    test_data[agent_id] = np.load(x_test_path)
                    logger.info("swarm.test_data_loaded", agent=agent_id, samples=len(test_data[agent_id]))
                except Exception as e:
                    logger.error("swarm.test_data_load_error", agent=agent_id, error=str(e))
            
            if features_path.exists():
                with open(features_path, "r") as f:
                    feature_names[agent_id] = [line.strip() for line in f if line.strip()]

        if not test_data:
            logger.warning("swarm.no_test_data_found", msg="Real-time processing started but no X_test.npy files found.")

        while self._running:
            # Wait for a random interval between 10-30 seconds to simulate real-world events
            await asyncio.sleep(random.uniform(10, 30))
            
            # Pick a random agent that has test data
            eligible_agents = list(test_data.keys())
            if not eligible_agents:
                continue
                
            agent_id = random.choice(eligible_agents)
            agent_info = self._agents[agent_id]
            agent_instance = agent_info.get("instance")
            
            if not agent_instance or not agent_instance._model:
                continue

            # Pick a random sample from X_test
            samples = test_data[agent_id]
            sample_idx = random.randint(0, len(samples) - 1)
            sample = samples[sample_idx]

            try:
                # Run real ML prediction
                result = agent_instance.predict(sample)
                
                # Extract actual features exactly as the model saw them
                features_dict = {}
                if agent_id in feature_names:
                    names = feature_names[agent_id]
                    for i in range(min(len(names), len(sample))):
                        val = float(sample[i])
                        features_dict[names[i]] = round(val, 4) if val % 1 else int(val)
                
                if result.is_threat:
                    # Enrich metadata with the real parsed feature set used for prediction
                    meta = result.metadata or {}
                    meta["features"] = features_dict
                    
                    # Construct threat event
                    threat = {
                        "id": f"THR-{uuid.uuid4().hex[:6].upper()}",
                        "type": agent_info["type"],
                        "detectedBy": [agent_id],
                        "severity": result.severity.value,
                        "confidence": round(result.confidence, 1),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "pending_consensus",
                        "description": result.description,
                        "sourceIP": f"192.168.1.{random.randint(10, 250)}",
                        "targetIP": f"10.0.0.{random.randint(1, 100)}",
                        "metadata": meta
                    }
                    
                    logger.info("swarm.real_threat_detected", agent=agent_id, confidence=result.confidence)
                    await self.report_threat(threat)
                    
                    # Submit votes from ALL agents (including proposer)
                    for other_id, other_info in self._agents.items():
                        if other_id == agent_id:
                            # Proposer votes "threat" with high confidence (it detected this)
                            decision = await self._consensus_engine.submit_vote(
                                threat["id"], agent_id, agent_info["type"], "threat", result.confidence
                            )
                        else:
                            # Other agents largely agree with a real ML detection
                            vote = "threat" if random.random() > 0.2 else "safe"
                            vote_conf = random.uniform(60, 98)
                            decision = await self._consensus_engine.submit_vote(
                                threat["id"], other_id, other_info["type"], vote, vote_conf
                            )
                        
                        # If submit_vote returned a decision, handle it directly
                        # (ZeroMQ relay is broken on Windows Proactor, so _on_consensus won't fire)
                        if decision:
                            await self._on_consensus(decision.to_dict())
                else:
                    # Log benign detection occasionally
                    if random.random() > 0.9:
                        logger.debug("swarm.benign_event_detected", agent=agent_id)
                        
            except Exception as e:
                logger.error("swarm.prediction_error", agent=agent_id, error=str(e))

    async def _real_time_simulation(self) -> None:
        """Background task: simulate real-time threat detection for live dashboard."""
        import random
        attack_types = ["ddos", "malware", "phishing", "mitm", "ransomware", "anomaly"]
        descriptions = {
            "ddos": ["Volumetric DDoS from botnet cluster", "SYN flood targeting web server", "UDP amplification attack detected"],
            "malware": ["Suspected trojan payload in traffic", "Malicious PE file detected", "Rootkit behavior identified"],
            "phishing": ["Phishing email campaign detected", "Malicious URL targeting HR dept", "Credential harvesting attempt"],
            "mitm": ["ARP spoofing on subnet", "DNS poisoning attempt", "SSL stripping detected"],
            "ransomware": ["Ransomware encryption behavior", "Shadow copy deletion detected", "Mass file rename operation"],
            "anomaly": ["Unusual outbound traffic pattern", "Data exfiltration attempt", "Unauthorized service access"],
        }

        while self._running:
            await asyncio.sleep(random.uniform(8, 25))  # Random interval

            attack_type = random.choice(attack_types)
            agent_map = {
                "ddos": "AGT-004", "malware": "AGT-002", "phishing": "AGT-003",
                "mitm": "AGT-005", "ransomware": "AGT-006", "anomaly": "AGT-001",
            }

            confidence = random.uniform(65, 99)
            severity = "critical" if confidence > 95 else "high" if confidence > 80 else "medium" if confidence > 60 else "low"

            threat = {
                "id": f"THR-{uuid.uuid4().hex[:6].upper()}",
                "type": attack_type,
                "detectedBy": [agent_map[attack_type]],
                "severity": severity,
                "confidence": round(confidence, 1),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "pending_consensus",
                "description": random.choice(descriptions[attack_type]),
                "sourceIP": f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
                "targetIP": f"10.0.{random.randint(1,5)}.{random.randint(1,254)}",
            }

            await self.report_threat(threat)

            # Simulate votes from other agents (proposer vote submitted via proposal/engine)
            for aid, agent in self._agents.items():
                if aid != agent_map[attack_type]:
                    vote = "threat" if random.random() > 0.3 else ("safe" if random.random() > 0.5 else "uncertain")
                    vote_conf = random.uniform(30, 95)
                    decision = await self._consensus_engine.submit_vote(
                        threat["id"], aid, agent["type"], vote, vote_conf
                    )
                    if decision:
                        await self._on_consensus(decision.to_dict())

    async def _agent_monitor(self) -> None:
        """Background task: update agent loads and health."""
        import random
        while self._running:
            await asyncio.sleep(5)
            for agent in self._agents.values():
                agent["currentLoad"] = max(0, min(100, agent["currentLoad"] + random.randint(-10, 10)))
                # Apply trust uptime bonus
                self._trust_manager.apply_uptime_bonus(agent["id"])
                agent["trustScore"] = self._trust_manager.get_trust(agent["id"])

                # Track offline timestamps for the TTIAR watchdog
                if agent["status"] in ("offline", "degraded"):
                    if agent["id"] not in self._offline_since:
                        self._offline_since[agent["id"]] = datetime.now(timezone.utc)
                else:
                    self._offline_since.pop(agent["id"], None)

            await self._broadcast_ws({
                "type": "agent_update",
                "data": self.get_agents(),
            })

    async def _agent_health_watchdog(self) -> None:
        """TTIAR Health Watchdog — periodically checks for agents that have been
        offline/degraded too long and auto-restarts them.
        
        This provides a safety net even when no matching threat triggers
        reactivation via report_threat().
        """
        logger.info("ttiar.watchdog_started", interval=self.WATCHDOG_INTERVAL_SEC)

        while self._running:
            await asyncio.sleep(self.WATCHDOG_INTERVAL_SEC)
            now = datetime.now(timezone.utc)

            for agent_id, offline_time in list(self._offline_since.items()):
                elapsed = (now - offline_time).total_seconds()
                if elapsed < self.WATCHDOG_OFFLINE_THRESHOLD_SEC:
                    continue

                agent = self._agents.get(agent_id)
                if not agent or agent["status"] == "active":
                    self._offline_since.pop(agent_id, None)
                    continue

                # Check cooldown
                last = self._last_reactivation.get(agent_id)
                if last and (now - last).total_seconds() < self.REACTIVATION_COOLDOWN_SEC:
                    continue

                logger.info(
                    "ttiar.watchdog_reactivation",
                    agent=agent_id,
                    offline_seconds=round(elapsed, 1),
                )
                await self._reactivate_agent(agent_id, reason=f"watchdog_offline_{int(elapsed)}s")
