"""
CDSI WebSocket Router — Real-time streaming endpoint.

Streams:
  - threat_alert: new threat detections
  - agent_update: agent status changes
  - consensus_update: consensus results
  - response_action: defense actions
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

router = APIRouter()
logger = structlog.get_logger(__name__)


def _get_manager():
    from dashboard.backend.main import swarm_manager
    return swarm_manager


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    
    Sends JSON messages with format:
    {
        "type": "threat_alert" | "agent_update" | "consensus_update" | "response_action",
        "data": { ... }
    }
    """
    await websocket.accept()
    manager = _get_manager()
    queue = manager.subscribe_ws()

    logger.info("ws.connected", client=str(websocket.client))

    try:
        def _json_serialize(obj: Any) -> Any:
            if hasattr(obj, "item"):  # Convert numpy scalars (bool_, int64, float64, etc.)
                return obj.item()
            if isinstance(obj, (set, tuple)):
                return list(obj)
            return str(obj)

        async def send_ws_json(data: Dict[str, Any]):
            text = json.dumps(data, default=_json_serialize, ensure_ascii=False)
            await websocket.send_text(text)

        # Send initial state
        await send_ws_json({
            "type": "initial_state",
            "data": {
                "agents": manager.get_agents(),
                "threats": manager.get_threats()[-20:],  # Last 20
                "consensus": manager.get_consensus_decisions()[-10:],
                "responses": manager.get_responses()[-10:],
                "stats": manager.get_system_stats(),
            },
        })

        # Stream updates
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30)
                await send_ws_json(message)
            except asyncio.TimeoutError:
                # Send heartbeat
                await send_ws_json({"type": "heartbeat", "data": {}})
            except Exception:
                break

    except WebSocketDisconnect:
        logger.info("ws.disconnected", client=str(websocket.client))
    finally:
        manager.unsubscribe_ws(queue)
