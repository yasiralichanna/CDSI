"""
CDSI Dashboard Backend — FastAPI application with REST + WebSocket APIs.

Integrates all CDSI subsystems:
  - Agent management and status monitoring
  - Real-time threat streaming
  - Consensus engine visualization
  - Automated response tracking
  - MITRE ATT&CK mapping
  - Audit logging
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from dashboard.backend.routers import agents, threats, consensus, responses, intel, logs, websocket
from dashboard.backend.services.swarm_manager import SwarmManager

logger = structlog.get_logger(__name__)

# Global swarm manager instance
swarm_manager = SwarmManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("cdsi.starting", version="1.0.0")

    # Initialize the swarm
    await swarm_manager.initialize()

    # Start real-time processing
    swarm_manager.start_background_tasks()

    yield

    # Shutdown
    logger.info("cdsi.shutting_down")
    await swarm_manager.shutdown()


app = FastAPI(
    title="CDSI — Cyber Defense Swarm Intelligence",
    description="Distributed multi-agent cybersecurity defense platform API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(agents.router, prefix="/api", tags=["Agents"])
app.include_router(threats.router, prefix="/api", tags=["Threats"])
app.include_router(consensus.router, prefix="/api", tags=["Consensus"])
app.include_router(responses.router, prefix="/api", tags=["Responses"])
app.include_router(intel.router, prefix="/api", tags=["Intelligence"])
app.include_router(logs.router, prefix="/api", tags=["Audit Logs"])
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agents": len(swarm_manager.get_agents()),
        "version": "1.0.0",
    }


@app.get("/api/stats")
async def system_stats():
    """System-wide statistics."""
    return swarm_manager.get_system_stats()

@app.get("/api/attack_stats")
async def attack_stats():
    """Attack type specific statistics."""
    return swarm_manager.get_attack_stats()
