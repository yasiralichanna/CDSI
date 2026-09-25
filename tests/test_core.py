"""
CDSI Unit Tests — Core component tests.
"""
import asyncio
import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock

# ── Trust Manager Tests ──

class TestTrustManager:
    def setup_method(self):
        from consensus.trust import TrustManager, INITIAL_TRUST
        self.tm = TrustManager()
        self.tm.register_agent("AGT-001")
        self.initial = INITIAL_TRUST

    def test_initial_trust(self):
        assert self.tm.get_trust("AGT-001") == self.initial

    def test_correct_vote_increases_trust(self):
        score = self.tm.record_correct_vote("AGT-001")
        assert score > self.initial

    def test_incorrect_vote_decreases_trust(self):
        score = self.tm.record_incorrect_vote("AGT-001")
        assert score < self.initial

    def test_timeout_decreases_trust(self):
        score = self.tm.record_timeout("AGT-001")
        assert score < self.initial

    def test_rogue_detection(self):
        for _ in range(50):
            self.tm.record_incorrect_vote("AGT-001")
        assert self.tm.is_rogue("AGT-001")

    def test_unregistered_agent_gets_initial(self):
        assert self.tm.get_trust("UNKNOWN") == self.initial

    def test_get_all_scores(self):
        self.tm.register_agent("AGT-002")
        scores = self.tm.get_all_scores()
        assert "AGT-001" in scores
        assert "AGT-002" in scores


# ── Consensus Engine Tests ──

class TestConsensusEngine:
    def setup_method(self):
        from consensus.engine import ConsensusEngine
        from consensus.trust import TrustManager
        self.tm = TrustManager()
        self.engine = ConsensusEngine(self.tm)

        for aid in ["AGT-001", "AGT-002", "AGT-003"]:
            self.tm.register_agent(aid)

    @pytest.mark.asyncio
    async def test_propose_and_vote(self):
        pid = await self.engine.propose_threat(
            "THR-001", "AGT-001", {"severity": "high"}, ["AGT-001", "AGT-002", "AGT-003"]
        )
        assert pid.startswith("CSN-")

        await self.engine.submit_vote("THR-001", "AGT-001", "ddos", "threat", 90)
        result = await self.engine.submit_vote("THR-001", "AGT-002", "anomaly", "threat", 85)
        # Not all voted yet
        if result is None:
            result = await self.engine.submit_vote("THR-001", "AGT-003", "malware", "threat", 80)

        assert result is not None
        assert result.consensus_reached
        assert result.final_decision == "threat"

    @pytest.mark.asyncio
    async def test_safe_consensus(self):
        await self.engine.propose_threat(
            "THR-002", "AGT-001", {}, ["AGT-001", "AGT-002", "AGT-003"]
        )
        await self.engine.submit_vote("THR-002", "AGT-001", "ddos", "safe", 90)
        await self.engine.submit_vote("THR-002", "AGT-002", "anomaly", "safe", 85)
        result = await self.engine.submit_vote("THR-002", "AGT-003", "malware", "safe", 80)

        assert result is not None
        assert result.final_decision == "safe"

    @pytest.mark.asyncio
    async def test_duplicate_vote_ignored(self):
        await self.engine.propose_threat(
            "THR-003", "AGT-001", {}, ["AGT-001", "AGT-002"]
        )
        await self.engine.submit_vote("THR-003", "AGT-001", "ddos", "threat", 90)
        result = await self.engine.submit_vote("THR-003", "AGT-001", "ddos", "threat", 90)
        assert result is None  # Duplicate, not finalized


# ── Hash Log Tests ──

class TestHashLog:
    def setup_method(self):
        from consensus.blockchain.hash_log import HashLog
        self.log = HashLog()

    def test_genesis_block(self):
        assert len(self.log) == 1

    def test_add_decision(self):
        self.log.add_decision({"decision": "threat", "id": "THR-001"})
        assert len(self.log) == 2

    def test_chain_integrity(self):
        for i in range(5):
            self.log.add_decision({"decision": f"threat_{i}"})
        assert self.log.verify_chain()

    def test_get_chain(self):
        self.log.add_decision({"test": True})
        chain = self.log.get_chain()
        assert len(chain) == 2
        assert chain[1]["data"]["test"] is True


# ── PBFT Tests ──

class TestPBFT:
    def test_pre_prepare(self):
        from consensus.pbft.pbft import PBFTNode, PBFTPhase
        node = PBFTNode("node-1", 4)
        msg = node.pre_prepare("hash123", {"data": "test"})
        assert msg.phase == PBFTPhase.PRE_PREPARE
        assert msg.proposal_hash == "hash123"

    def test_prepare_to_commit(self):
        from consensus.pbft.pbft import PBFTNode
        node = PBFTNode("node-1", 4)

        pp = node.pre_prepare("hash123", {})
        prep = node.handle_pre_prepare(pp)
        assert prep is not None

        # Simulate more prepares to reach 2f+1
        for i in range(2):
            from consensus.pbft.pbft import PBFTMessage, PBFTPhase
            fake = PBFTMessage(PBFTPhase.PREPARE, 0, 1, f"node-{i+2}", "hash123", {})
            node.handle_prepare(fake)


# ── Correlation Engine Tests ──

class TestCorrelationEngine:
    def setup_method(self):
        from correlation.engine import CorrelationEngine
        self.engine = CorrelationEngine()

    @pytest.mark.asyncio
    async def test_ingest_single(self):
        event = {
            "id": "THR-001",
            "type": "ddos",
            "confidence": 90,
            "severity": "high",
            "sourceIP": "1.2.3.4",
        }
        result = await self.engine.ingest_detection(event)
        stats = self.engine.get_stats()
        assert stats["total_events"] == 1

    @pytest.mark.asyncio
    async def test_correlation_by_ip(self):
        event1 = {"id": "THR-001", "type": "ddos", "confidence": 90, "severity": "high", "sourceIP": "1.2.3.4"}
        event2 = {"id": "THR-002", "type": "anomaly", "confidence": 85, "severity": "medium", "sourceIP": "1.2.3.4"}
        await self.engine.ingest_detection(event1)
        await self.engine.ingest_detection(event2)
        threats = self.engine.get_active_threats()
        assert len(threats) == 1  # Correlated


# ── Event Normalizer Tests ──

class TestEventNormalizer:
    def setup_method(self):
        from ingestion.normalizer import EventNormalizer
        self.norm = EventNormalizer()

    def test_normalize_wazuh(self):
        raw = {
            "data": {
                "timestamp": "2025-01-01T00:00:00",
                "rule": {"id": "1001", "description": "Test alert", "level": 10},
                "srcip": "10.0.0.1",
            }
        }
        event = self.norm.normalize_wazuh(raw)
        assert event.source == "wazuh"
        assert event.severity == "high"
        assert event.src_ip == "10.0.0.1"

    def test_normalize_netflow(self):
        raw = {"src_addr": "10.0.0.1", "dst_addr": "10.0.0.2", "src_port": 80, "bytes": 1024}
        event = self.norm.normalize_netflow(raw)
        assert event.source == "netflow"
        assert event.src_ip == "10.0.0.1"


# ── Communication Tests ──

class TestInMemoryComm:
    @pytest.mark.asyncio
    async def test_pub_sub(self):
        from comms.interface import InMemoryComm
        comm = InMemoryComm()
        await comm.connect()

        received = []
        async def handler(msg):
            received.append(msg)

        await comm.subscribe("test_topic", handler)
        await comm.publish("test_topic", {"data": "hello"})

        assert len(received) == 1
        assert received[0]["data"] == "hello"
        await comm.disconnect()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        from comms.interface import InMemoryComm
        comm = InMemoryComm()
        await comm.connect()

        counts = {"a": 0, "b": 0}
        async def handler_a(msg): counts["a"] += 1
        async def handler_b(msg): counts["b"] += 1

        await comm.subscribe("topic", handler_a)
        await comm.subscribe("topic", handler_b)
        await comm.publish("topic", {"x": 1})

        assert counts["a"] == 1
        assert counts["b"] == 1


# ── Adaptive Threshold Tests ──

class TestAdaptiveThreshold:
    def test_threshold_update(self):
        from learning.rl.adaptive_threshold import AdaptiveThresholdAgent
        agent = AdaptiveThresholdAgent(initial_threshold=0.7)
        new_threshold = agent.step(fp_rate=0.1, fn_rate=0.05, detection_rate=0.9, avg_confidence=85)
        assert 0.3 <= new_threshold <= 0.99

    def test_stats(self):
        from learning.rl.adaptive_threshold import AdaptiveThresholdAgent
        agent = AdaptiveThresholdAgent()
        agent.step(0.1, 0.05, 0.9, 85)
        stats = agent.get_stats()
        assert "threshold" in stats
        assert stats["history_length"] == 1
