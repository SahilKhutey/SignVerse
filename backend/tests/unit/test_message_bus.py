"""
Unit tests for message bus.
"""
import pytest
import asyncio
from backend.communication.bus import MessageBus, MessagePriority, Message


@pytest.mark.asyncio
@pytest.mark.unit
class TestMessageBus:
    """Tests for pub/sub message bus."""
    
    async def test_publish_and_subscribe(self):
        """Subscriber should receive published messages."""
        bus = MessageBus()
        received = []
        
        async def handler(msg: Message):
            received.append(msg.payload)
        
        bus.subscribe("test_topic", handler)
        await bus.publish("test_topic", {"data": "hello"})
        await asyncio.sleep(0.1)  # Allow dispatch
        
        assert len(received) == 1
        assert received[0]["data"] == "hello"
    
    async def test_multiple_subscribers(self):
        """All subscribers should receive the message."""
        bus = MessageBus()
        results = []
        
        async def handler1(msg):
            results.append("h1")
        async def handler2(msg):
            results.append("h2")
        
        bus.subscribe("test", handler1)
        bus.subscribe("test", handler2)
        
        await bus.publish("test", "data")
        await asyncio.sleep(0.1)
        
        assert "h1" in results
        assert "h2" in results
    
    async def test_priority_ordering(self):
        """High priority messages should be delivered first."""
        bus = MessageBus()
        results = []
        
        async def handler(msg):
            results.append(msg.payload)
        
        bus.subscribe("test", handler)
        
        # Pause queue processing temporarily if possible, or just publish back-to-back
        # Since the bus runs a worker loop:
        await bus.publish("test", "low", priority=MessagePriority.LOW)
        await bus.publish("test", "critical", priority=MessagePriority.CRITICAL)
        await bus.publish("test", "high", priority=MessagePriority.HIGH)
        
        await asyncio.sleep(0.2)
        # Verify critical is processed before low
        assert "critical" in results
        assert "high" in results
        assert "low" in results
        # Find index of critical vs low
        assert results.index("critical") < results.index("low")
    
    async def test_dead_letter_on_max_retries(self):
        """Messages exceeding retry limit go to dead letter."""
        bus = MessageBus()
        
        async def failing(msg):
            raise Exception("always fails")
        
        bus.subscribe("test", failing)
        await bus.publish("test", "data")
        await asyncio.sleep(0.8)  # Wait for retries (0.1s + 0.2s + overhead)
        
        assert len(bus.dead_letter_queue) > 0
        assert bus.stats["messages_dead_lettered"] > 0
    
    async def test_request_response(self):
        """Request/response pattern should work."""
        bus = MessageBus()
        
        async def responder(msg):
            await bus.respond(msg.correlation_id, {"reply": "ok"}, topic="rpc.response")
        
        bus.subscribe("rpc", responder)
        
        response = await bus.request("rpc", {"q": "test"}, timeout=2.0)
        assert response["reply"] == "ok"
    
    async def test_unsubscribe(self):
        """Unsubscribed handler should not receive messages."""
        bus = MessageBus()
        received = []
        
        async def handler(msg):
            received.append(msg.payload)
        
        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        await bus.publish("test", "data")
        await asyncio.sleep(0.1)
        
        assert received == []
    
    async def test_stats_tracking(self):
        """Stats should be tracked correctly."""
        bus = MessageBus()
        
        async def handler(msg): pass
        bus.subscribe("test", handler)
        
        await bus.publish("test", "a")
        await bus.publish("test", "b")
        await asyncio.sleep(0.1)
        
        stats = bus.get_stats()
        assert stats["messages_published"] >= 2
