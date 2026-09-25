"""
CDSI API Integration Tests.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from dashboard.backend.main import app
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agents"] > 0


class TestAgentsAPI:
    def test_list_agents(self, client):
        response = client.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 6
        for agent in agents:
            assert "id" in agent
            assert "type" in agent
            assert "trustScore" in agent

    def test_get_agent(self, client):
        response = client.get("/api/agents/AGT-001")
        assert response.status_code == 200
        agent = response.json()
        assert agent["id"] == "AGT-001"
        assert agent["name"] == "Anomaly Sentinel"

    def test_get_agent_not_found(self, client):
        response = client.get("/api/agents/NONEXISTENT")
        assert response.status_code == 404


class TestThreatsAPI:
    def test_list_threats(self, client):
        response = client.get("/api/threats")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_threat(self, client):
        payload = {
            "type": "ddos",
            "detectedBy": ["AGT-004"],
            "severity": "critical",
            "confidence": 94.5,
            "sourceIP": "198.51.100.42",
            "targetIP": "10.0.0.5"
        }
        response = client.post("/api/threats", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "ddos"
        assert data["severity"] == "critical"
        assert data["confidence"] == 94.5
        assert data["sourceIP"] == "198.51.100.42"
        assert data["targetIP"] == "10.0.0.5"
        assert "id" in data



class TestConsensusAPI:
    def test_list_consensus(self, client):
        response = client.get("/api/consensus")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestResponsesAPI:
    def test_list_responses(self, client):
        response = client.get("/api/responses")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestMitreAPI:
    def test_list_mitre(self, client):
        response = client.get("/api/mitre")
        assert response.status_code == 200
        techniques = response.json()
        assert len(techniques) > 0
        for t in techniques:
            assert "id" in t
            assert "name" in t
            assert "tactic" in t


class TestLogsAPI:
    def test_list_logs(self, client):
        response = client.get("/api/logs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestStatsAPI:
    def test_system_stats(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "activeAgents" in stats
        assert "totalAgents" in stats
        assert stats["totalAgents"] == 6
