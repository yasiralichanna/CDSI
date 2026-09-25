# 🛡️ CDSI — Cyber Defense Swarm Intelligence

**Production-grade distributed multi-agent cybersecurity defense platform.**

CDSI deploys a swarm of specialized AI agents that detect, validate, and respond to cybersecurity threats in real-time using machine learning, Byzantine fault-tolerant consensus, and automated defense orchestration.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       CDSI Platform                              │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  DDoS    │ │ Anomaly  │ │ Malware  │ │ Phishing │           │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │           │
│  │ XGB+LGB  │ │ RF+IsoF  │ │ RF+LGB   │ │ XGBoost  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       │             │            │             │                 │
│  ┌────┴─────┐ ┌────┴─────┐                                     │
│  │  MITM    │ │Ransomware│     ┌─────────────────────┐          │
│  │  Agent   │ │  Agent   │     │  Correlation Engine  │          │
│  │   RF     │ │ XGBoost  │     │  Bayesian Fusion +   │          │
│  └────┬─────┘ └────┬─────┘     │  FP Reduction        │          │
│       │             │           └──────────┬──────────┘          │
│       └──────┬──────┘                      │                     │
│              │                             │                     │
│     ┌────────▼─────────────────────────────▼──────────┐         │
│     │            Communication Layer                   │         │
│     │     ZeroMQ (P2P) │ Kafka (Telemetry) │ gRPC     │         │
│     └────────────────────┬─────────────────────────────┘         │
│                          │                                       │
│     ┌────────────────────▼─────────────────────────────┐         │
│     │           Consensus Engine                        │         │
│     │  PBFT + Raft │ Trust Scoring │ Blockchain Log     │         │
│     └────────────────────┬─────────────────────────────┘         │
│                          │                                       │
│     ┌────────────────────▼─────────────────────────────┐         │
│     │           Automated Response                      │         │
│     │  IP Block │ VM Isolate │ Domain Block │ Reroute   │         │
│     └──────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📦 Components

| Component | Description |
|-----------|-------------|
| **agents/** | 6 ML-trained detection agents (DDoS, Anomaly, Malware, Phishing, MITM, Ransomware) |
| **consensus/** | Byzantine FT consensus (PBFT + Raft), trust scoring, blockchain hash log |
| **correlation/** | Bayesian signal fusion, false positive reduction, attack chain tracking |
| **comms/** | Multi-transport communication (ZeroMQ, Kafka, gRPC) |
| **ingestion/** | Event normalizer, router, Wazuh/PCAP/NetFlow collectors |
| **learning/** | ML trainer, federated learning (FedAvg), RL adaptive thresholds |
| **dashboard/backend/** | FastAPI REST + WebSocket API serving the frontend |
| **deployment/** | Docker, docker-compose, Kubernetes manifests with HPA |

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

### 3. Start the Services (Backend & Frontend)

**Backend Server (FastAPI):**
You can use the provided batch script on Windows:
```bash
run_backend.bat
```
Or manually:
```bash
python cli.py start_all   # Starts API server + 6 agents locally
# OR
python cli.py serve       # Starts only the API server
# Server runs at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
# WebSocket at ws://localhost:8000/ws
```

**Frontend Dashboard (Next.js):**
Ensure you have Node.js installed.
```bash
cd dashboard/frontend
npm install           # One-time installation
cd ../..
run_frontend.bat      # Windows batch script
# OR manually: cd dashboard/frontend && npm run dev
# Dashboard available at http://localhost:3000
```

### 4. Train Agents (with datasets)
```bash
# Download datasets
python cli.py download --all

# Preprocess
python cli.py preprocess --all

# Train all agents
python cli.py train --all
```

### 5. Docker Deployment
```bash
cd deployment/docker
docker-compose up -d
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stats` | System statistics |
| GET | `/api/agents` | List all agents |
| GET | `/api/agents/{id}` | Get specific agent |
| GET | `/api/threats` | List detected threats |
| GET | `/api/consensus` | List consensus decisions |
| GET | `/api/responses` | List automated responses |
| POST | `/api/responses/{id}/rollback` | Rollback a response |
| GET | `/api/mitre` | MITRE ATT&CK techniques |
| GET | `/api/logs` | Audit logs |
| WS | `/ws` | Real-time streaming |

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 🔒 Security

- **JWT Authentication** with role-based access control (admin, analyst, viewer)
- **mTLS** support for gRPC inter-service communication
- **Blockchain hash log** for tamper-proof audit trail
- **Trust scoring** with rogue agent detection

---

## 📊 Observability

- **Prometheus** metrics at `/metrics`
- **Grafana** dashboards (port 3001 in docker-compose)
- **Structured logging** via structlog

---

## 🤖 Agents

| Agent | Model | Dataset | Features |
|-------|-------|---------|----------|
| DDoS Shield | XGBoost + LightGBM | CIC-DDoS2019 | 52 flow features |
| Anomaly Sentinel | RandomForest + IsolationForest | CICIDS2017 | 21 flow features |
| Malware Hunter | RandomForest + LightGBM | EMBER | 30 PE features |
| Phishing Guard | XGBoost | PhishTank + UCI | 30 URL features |
| MITM Detector | RandomForest | CICIDS2017 ARP/DNS | 21 flow features |
| Ransom Blocker | XGBoost | CTU-13 + BIG 2015 | 28 behavioral features |

---

## CLI Commands

```bash
python cli.py serve       # Start API server
python cli.py start_all   # Start API server and all agent processes
python cli.py train       # Train agents
python cli.py download    # Download datasets
python cli.py preprocess  # Preprocess datasets
python cli.py status      # Show system status
python cli.py ingest      # Ingest network traffic or sample events
```
