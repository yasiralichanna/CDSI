"""
Agent Runner Script
Used by `cli.py start-all` to run an agent in a standalone process.
"""
import asyncio
import sys
from pathlib import Path

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import structlog
from typing import Any, Dict
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from comms.zeromq.broker import ZeroMQComm
from config.settings import get_settings

logger = structlog.get_logger(__name__)

async def run_agent(agent_type: str):
    from cli import _create_agent
    
    settings = get_settings()
    
    # Initialize the agent
    agent = _create_agent(agent_type)
    
    # Initialize Comms
    comms = ZeroMQComm()
    await comms.connect()
    
    # Attach comms to agent
    agent.set_comms(comms)
    
    # Load model if available
    agent.load_model()
    
    # Subscribe to events for this agent type
    topic = f"events.{agent_type}"
    
    # We'll use a queue to bridge the ZMQ callback to the stream_detect iterator
    event_queue = asyncio.Queue()
    
    async def on_event(msg: Dict[str, Any]):
        logger.info("agent_runner.event_received", agent_type=agent_type, topic=topic)
        await event_queue.put(msg)
        
    await comms.subscribe(topic, on_event)
    
    async def event_generator():
        while True:
            yield await event_queue.get()

    logger.info("agent_runner.started", agent_type=agent_type, topic=topic)
    
    try:
        # Run detection in the background
        async for result in agent.stream_detect(event_generator()):
            # Results are automatically published via agent.publish_threat inside stream_detect
            pass
    except asyncio.CancelledError:
        pass
    finally:
        await comms.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent_runner.py <agent_type>")
        sys.exit(1)
        
    os.environ["USE_SIMULATION"] = "false"
    asyncio.run(run_agent(sys.argv[1]))
