import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import pytest
import json
from comms.zeromq.broker import ZeroMQComm
from agents.base.base_agent import ThreatSeverity

@pytest.mark.asyncio
async def test_zmq_pipeline():
    """Verify that ZMQ can pass messages from an ingester to an agent."""
    # This test requires ZMQ, but we can mock parts if needed or run a local broker.
    # For now, let's just test that our new connect logic works.
    
    comm_hub = ZeroMQComm(pub_address="tcp://127.0.0.1:5556", sub_address="tcp://127.0.0.1:5557")
    # Both use the same address config; ZeroMQComm.connect handles the swap automatically for Spokes
    comm_agent = ZeroMQComm(pub_address="tcp://127.0.0.1:5556", sub_address="tcp://127.0.0.1:5557")
    
    try:
        # Hub binds
        await comm_hub.connect(bind_pub=True, bind_sub=True)
        # Agent connects
        await comm_agent.connect(bind_pub=False, bind_sub=False)
        
        received_msg = None
        event = asyncio.Event()
        
        async def on_threat(msg):
            nonlocal received_msg
            received_msg = msg
            event.set()
            
        await comm_hub.subscribe("threats", on_threat)
        await asyncio.sleep(0.1) # Wait for subscription to propagate
        
        test_threat = {
            "id": "THR-TEST",
            "type": "ddos",
            "severity": "high",
            "confidence": 99.0,
            "description": "Test threat"
        }
        
        await comm_agent.publish("threats", test_threat)
        
        try:
            await asyncio.wait_for(event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Message not received via ZMQ")
            
        assert received_msg == test_threat
        
    finally:
        await comm_hub.disconnect()
        await comm_agent.disconnect()
