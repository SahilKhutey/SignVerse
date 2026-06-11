"""
Inter-module communication bus.
Provides pub/sub with delivery guarantees, error handling, monitoring.
"""
import asyncio
import time
import uuid
import traceback
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

import logging
logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    """A message on the bus."""
    id: str
    topic: str
    payload: Any
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    sender: Optional[str] = None
    correlation_id: Optional[str] = None  # For request/response patterns
    
    # Retry tracking
    delivery_attempts: int = 0
    max_delivery_attempts: int = 3
    
    # Error tracking
    last_error: Optional[str] = None

    def __lt__(self, other):
        if not isinstance(other, Message):
            return NotImplemented
        # Higher priority value (e.g. CRITICAL=3) comes first.
        # PriorityQueue defaults to lowest value first, so we push (-priority.value).
        # In case of tie in priority and timestamp, we compare priority values.
        return self.priority.value > other.priority.value


class MessageBus:
    """
    Pub/sub message bus for inter-module communication.
    Features:
    - Priority queues
    - Delivery guarantees (with retry)
    - Dead-letter queue for poison messages
    - Request/response patterns (via correlation_id)
    - Subscriber health monitoring
    - Backpressure (slow subscriber handling)
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self.topics: Dict[str, List[Callable]] = defaultdict(list)
        self.queues: Dict[str, asyncio.PriorityQueue] = {}
        self.workers: Dict[str, asyncio.Task] = {}
        self.dead_letter_queue: List[Message] = []
        self.max_queue_size = max_queue_size
        
        # Request/response tracking
        self.pending_responses: Dict[str, asyncio.Future] = {}
        
        # Stats
        self.stats = {
            "messages_published": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "messages_dead_lettered": 0,
        }
        
        # Subscriber liveness
        self.subscriber_last_seen: Dict[str, float] = {}
        
        # Health monitor task
        self._health_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self._lock = asyncio.Lock()
    
    def subscribe(self, topic: str, handler: Callable, subscriber_id: str = None) -> str:
        """Subscribe a handler to a topic."""
        sid = subscriber_id or f"sub_{uuid.uuid4().hex[:8]}"
        self.topics[topic].append(handler)
        self.subscriber_last_seen[sid] = time.time()
        return sid
    
    def unsubscribe(self, topic: str, handler: Callable):
        """Unsubscribe a handler."""
        if topic in self.topics:
            try:
                self.topics[topic].remove(handler)
            except ValueError:
                pass
    
    async def publish(
        self,
        topic: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        sender: str = None,
        correlation_id: str = None,
    ) -> str:
        """Publish a message to a topic. Returns message ID."""
        msg = Message(
            id=uuid.uuid4().hex,
            topic=topic,
            payload=payload,
            priority=priority,
            sender=sender,
            correlation_id=correlation_id,
        )
        
        async with self._lock:
            # Enqueue with priority
            if topic not in self.queues:
                self.queues[topic] = asyncio.PriorityQueue(maxsize=self.max_queue_size)
            
            # Start worker for the topic if not already running
            if topic not in self.workers or self.workers[topic].done():
                self.workers[topic] = asyncio.create_task(self._topic_worker(topic))
        
        try:
            # Negate priority for min-heap (higher priority value -> smaller number -> pops first)
            await self.queues[topic].put((-priority.value, msg.timestamp, msg))
        except asyncio.QueueFull:
            logger.error(f"Queue full for topic {topic}, dropping message {msg.id}")
            self.dead_letter_queue.append(msg)
            self.stats["messages_dead_lettered"] += 1
            return msg.id
        
        self.stats["messages_published"] += 1
        return msg.id
    
    async def _topic_worker(self, topic: str):
        """Background worker per topic to process queued messages in priority order."""
        queue = self.queues[topic]
        while not self._shutdown:
            try:
                # Get next message
                _, _, msg = await queue.get()
                
                # Deliver to all subscribers
                handlers = self.topics.get(topic, [])
                if handlers:
                    # Deliver concurrently to all handlers of this topic
                    await asyncio.gather(
                        *[self._deliver_with_retry(msg, handler) for handler in list(handlers)],
                        return_exceptions=True
                    )
                else:
                    if msg.priority == MessagePriority.CRITICAL:
                        logger.warning(f"CRITICAL message {msg.id} on topic '{msg.topic}' has no subscribers")
                
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error on topic {topic}: {e}")
                await asyncio.sleep(0.1)

    async def _deliver_with_retry(self, msg: Message, handler: Callable):
        """Deliver a message with exponential backoff retry."""
        attempts = 0
        max_attempts = msg.max_delivery_attempts
        
        while attempts < max_attempts and not self._shutdown:
            attempts += 1
            msg.delivery_attempts = attempts
            try:
                # Update subscriber health activity
                for sid in list(self.subscriber_last_seen.keys()):
                    self.subscriber_last_seen[sid] = time.time()
                
                # Call handler
                if asyncio.iscoroutinefunction(handler):
                    await asyncio.wait_for(handler(msg), timeout=30.0)
                else:
                    # Sync handler - run in thread executor
                    await asyncio.get_event_loop().run_in_executor(
                        None, handler, msg
                    )
                
                self.stats["messages_delivered"] += 1
                return  # Success
                
            except asyncio.TimeoutError:
                msg.last_error = "Handler timeout (30s)"
            except Exception as e:
                msg.last_error = f"{type(e).__name__}: {str(e)[:200]}"
                logger.error(
                    f"Handler failed for {msg.id} (attempt {attempts}/{max_attempts}): {msg.last_error}"
                )
            
            if attempts < max_attempts and not self._shutdown:
                # Exponential backoff: 0.1s, 0.2s, 0.4s...
                backoff = 0.05 * (2 ** attempts)
                await asyncio.sleep(backoff)
        
        # If we reach here, it failed all attempts
        self.dead_letter_queue.append(msg)
        self.stats["messages_dead_lettered"] += 1
        self.stats["messages_failed"] += 1
        logger.error(f"Message {msg.id} dead-lettered after {attempts} attempts. Error: {msg.last_error}")
    
    async def request(
        self,
        topic: str,
        payload: Any,
        timeout: float = 5.0,
    ) -> Any:
        """Request/response pattern. Publishes and waits for response."""
        correlation_id = uuid.uuid4().hex
        future = asyncio.get_event_loop().create_future()
        self.pending_responses[correlation_id] = future
        
        # Subscribe a one-shot response handler
        response_topic = f"{topic}.response"
        
        async def response_handler(msg: Message):
            if msg.correlation_id == correlation_id:
                if not future.done():
                    future.set_result(msg.payload)
                self.unsubscribe(response_topic, response_handler)
                if correlation_id in self.pending_responses:
                    del self.pending_responses[correlation_id]
        
        self.subscribe(response_topic, response_handler)
        await self.publish(topic, payload, correlation_id=correlation_id)
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.unsubscribe(response_topic, response_handler)
            if correlation_id in self.pending_responses:
                del self.pending_responses[correlation_id]
            raise
    
    async def respond(self, correlation_id: str, payload: Any, topic: str = "response"):
        """Send a response to a previous request."""
        await self.publish(
            topic,
            payload,
            correlation_id=correlation_id,
        )
    
    def get_stats(self) -> Dict:
        """Get bus statistics."""
        return {
            **self.stats,
            "topics": list(self.topics.keys()),
            "subscribers_per_topic": {
                t: len(handlers) for t, handlers in self.topics.items()
            },
            "queue_sizes": {
                t: q.qsize() for t, q in self.queues.items()
            },
            "dead_letter_count": len(self.dead_letter_queue),
        }
    
    async def start_health_monitor(self, interval: float = 10.0):
        """Start the health monitoring task."""
        self._health_task = asyncio.create_task(self._health_loop(interval))
    
    async def _health_loop(self, interval: float):
        """Periodically check subscriber health."""
        while not self._shutdown:
            try:
                await asyncio.sleep(interval)
                now = time.time()
                stale_threshold = 60.0  # 60s without activity = stale
                
                stale_subs = [
                    sid for sid, last in self.subscriber_last_seen.items()
                    if now - last > stale_threshold
                ]
                
                if stale_subs:
                    logger.warning(f"Stale subscribers detected: {stale_subs}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
    
    async def shutdown(self):
        """Graceful shutdown."""
        self._shutdown = True
        if self._health_task:
            self._health_task.cancel()
        for worker in self.workers.values():
            worker.cancel()
        # Wait a brief moment to let tasks clean up
        await asyncio.sleep(0.05)


# Singleton
bus = MessageBus()
