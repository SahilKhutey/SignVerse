"""
Verification script for SignVerse Security, Ingestion, Communication, and Resilience Hardening.
Covers 8 critical verification areas in self-contained checks.
"""
import asyncio
import time
import sys
import unittest
from pathlib import Path
from fastapi import HTTPException

# Add current directory to path
sys.path.append(str(Path(__file__).parent.resolve()))

# Imports to verify
from backend.security.auth import (
    create_jwt_token, verify_jwt_token, revoke_token, is_token_revoked,
    hash_api_key, generate_api_key, verify_api_key, authenticate_user
)
from backend.security.rate_limiter import RateLimiter, TokenBucket
from backend.ingestion.validators import _sanitize_filename, validate_url
from backend.ingestion.orchestrator import IngestionOrchestrator, JobStatus
from backend.communication.bus import MessageBus, MessagePriority, Message
from backend.resilience.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitState,
    circuit_breaker, retry_with_backoff
)

class TestICRSPipeline(unittest.IsolatedAsyncioTestCase):

    # ==========================================
    # 1. SECURITY & AUTHENTICATION TESTS
    # ==========================================
    def test_jwt_lifecycle(self):
        print("Running Check 1: JWT Lifecycle...")
        user_id = "user_test_999"
        role = "admin"
        
        # Create token
        token = create_jwt_token(user_id, role, expiry_hours=1)
        self.assertIsNotNone(token)
        
        # Verify token
        payload = verify_jwt_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], user_id)
        self.assertEqual(payload["role"], role)
        
        # Test revocation
        jti = payload["jti"]
        self.assertFalse(is_token_revoked(jti))
        revoke_token(jti)
        self.assertTrue(is_token_revoked(jti))

    def test_api_keys(self):
        print("Running Check 2: API Keys...")
        key = generate_api_key()
        self.assertTrue(key.startswith("sv_"))
        
        # Verify valid hash
        h = hash_api_key("demo-key-1234")
        meta = verify_api_key("demo-key-1234")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["role"], "admin")
        
        # Verify invalid key
        self.assertIsNone(verify_api_key("invalid-key"))

    # ==========================================
    # 2. RATE LIMITER TESTS
    # ==========================================
    def test_rate_limiter_token_bucket(self):
        print("Running Check 3: Rate Limiter Token Bucket...")
        limiter = RateLimiter()
        client_id = "test-client-1"
        
        # Check defaults
        bucket = limiter._get_bucket(client_id, "ingest")
        self.assertEqual(bucket.capacity, 10)
        self.assertEqual(bucket.refill_rate, 1.0)
        
        # Consume allowed tokens
        for _ in range(10):
            allowed, _, _ = limiter.is_allowed(client_id, "ingest")
            self.assertTrue(allowed)
            
        # 11th request should fail
        allowed, retry_after, remaining = limiter.is_allowed(client_id, "ingest")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0.0)
        self.assertEqual(remaining, 0.0)

    def test_rate_limiter_lockout(self):
        print("Running Check 4: Rate Limiter Lockout...")
        limiter = RateLimiter()
        client_id = "test-client-lockout"
        
        # Consume initial capacity
        for _ in range(10):
            limiter.is_allowed(client_id, "ingest")
            
        # Reject 51 times to trigger lockout
        for _ in range(52):
            limiter.is_allowed(client_id, "ingest")
            
        bucket = limiter._get_bucket(client_id, "ingest")
        self.assertGreater(bucket.locked_until, time.time())
        
        allowed, retry_after, _ = limiter.is_allowed(client_id, "ingest")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 50.0)  # Locked for 60s

    # ==========================================
    # 3. INGESTION & URL SANITIZATION TESTS
    # ==========================================
    def test_filename_sanitization(self):
        print("Running Check 5: Filename Sanitization...")
        self.assertEqual(_sanitize_filename("valid_video.mp4"), "valid_video.mp4")
        self.assertEqual(_sanitize_filename("subfolder/video.mp4"), "video.mp4")
        self.assertEqual(_sanitize_filename("../../etc/passwd"), "passwd")
        self.assertIsNone(_sanitize_filename("video\0.mp4"))
        self.assertIsNone(_sanitize_filename("invalid_char_$.mp4"))

    def test_url_ssrf_validation(self):
        print("Running Check 6: URL SSRF Validation...")
        # Valid URLs
        valid, msg = validate_url("https://example.com/video.mp4")
        self.assertTrue(valid)
        self.assertEqual(msg, "OK")
        
        # Invalid / SSRF URLs
        self.assertFalse(validate_url("http://localhost/video.mp4")[0])
        self.assertFalse(validate_url("http://127.0.0.1/video.mp4")[0])
        self.assertFalse(validate_url("http://192.168.1.100/video.mp4")[0])
        self.assertFalse(validate_url("http://10.0.0.1/video.mp4")[0])
        self.assertFalse(validate_url("gopher://example.com")[0])
        self.assertFalse(validate_url("https://")[0])

    # ==========================================
    # 4. INGESTION ORCHESTRATOR TESTS
    # ==========================================
    async def test_ingestion_orchestrator(self):
        print("Running Check 7: Ingestion Orchestrator Concurrency & Limits...")
        # Custom orchestrator with max 2 concurrent jobs
        orch = IngestionOrchestrator(max_concurrent=2, max_memory_mb=16384)
        
        progress_calls = []
        complete_calls = []
        
        def on_prog(job):
            progress_calls.append(job.job_id)
            
        def on_comp(job):
            complete_calls.append(job.job_id)
            
        orch.on_progress = on_prog
        orch.on_complete = on_comp
        
        # Submit 4 jobs
        j1 = await orch.submit_job("demo")
        j2 = await orch.submit_job("demo")
        j3 = await orch.submit_job("demo")
        j4 = await orch.submit_job("demo")
        
        # Yield control to allow tasks to start running
        await asyncio.sleep(0.01)
        
        self.assertEqual(len(orch.active_jobs), 2)
        self.assertEqual(len(orch.pending_queue), 2)
        
        # Wait for them to complete
        await asyncio.sleep(0.5)
        
        self.assertEqual(len(orch.active_jobs), 0)
        self.assertEqual(len(orch.pending_queue), 0)
        self.assertEqual(j1.status, JobStatus.COMPLETED)
        self.assertEqual(j2.status, JobStatus.COMPLETED)
        self.assertEqual(j3.status, JobStatus.COMPLETED)
        self.assertEqual(j4.status, JobStatus.COMPLETED)

    # ==========================================
    # 5. COMMUNICATION BUS TESTS
    # ==========================================
    async def test_message_bus_pub_sub(self):
        print("Running Check 8: Message Bus Pub/Sub...")
        bus = MessageBus()
        received = []
        
        async def handler(msg):
            received.append(msg.payload)
            
        bus.subscribe("test.topic", handler)
        await bus.publish("test.topic", "hello world")
        
        # Wait a moment for workers to process queue
        await asyncio.sleep(0.1)
        self.assertEqual(received, ["hello world"])
        await bus.shutdown()

    async def test_message_bus_priority(self):
        print("Running Check 9: Message Bus Priority Queueing...")
        bus = MessageBus()
        received = []
        
        # We subscribe a slow handler to block first message so others queue up
        started = asyncio.Event()
        blocker = asyncio.Event()
        
        async def handler(msg):
            if msg.payload == "first":
                started.set()
                await blocker.wait()
            else:
                received.append(msg.payload)
                
        bus.subscribe("prio.topic", handler)
        
        # Publish blocker message
        await bus.publish("prio.topic", "first", priority=MessagePriority.LOW)
        await started.wait()
        
        # Publish messages with different priorities while queue is blocked
        await bus.publish("prio.topic", "low_msg", priority=MessagePriority.LOW)
        await bus.publish("prio.topic", "critical_msg", priority=MessagePriority.CRITICAL)
        await bus.publish("prio.topic", "high_msg", priority=MessagePriority.HIGH)
        await bus.publish("prio.topic", "normal_msg", priority=MessagePriority.NORMAL)
        
        # Let blocker continue
        blocker.set()
        await asyncio.sleep(0.15)
        
        # Verify that messages were processed in priority order: CRITICAL -> HIGH -> NORMAL -> LOW
        self.assertEqual(received, ["critical_msg", "high_msg", "normal_msg", "low_msg"])
        await bus.shutdown()

    async def test_message_bus_request_response(self):
        print("Running Check 10: Message Bus Request/Response...")
        bus = MessageBus()
        
        async def ping_responder(msg):
            if msg.payload == "PING":
                await bus.respond(msg.correlation_id, "PONG", topic=f"{msg.topic}.response")
                
        bus.subscribe("ping.topic", ping_responder)
        
        response = await bus.request("ping.topic", "PING", timeout=2.0)
        self.assertEqual(response, "PONG")
        await bus.shutdown()

    async def test_message_bus_dead_letter_queue(self):
        print("Running Check 11: Message Bus Dead-Letter Queue...")
        bus = MessageBus()
        
        async def failing_handler(msg):
            raise ValueError("Intentional failure")
            
        bus.subscribe("fail.topic", failing_handler)
        await bus.publish("fail.topic", "poison pill")
        
        # Wait for retries to complete (exponential backoff: 0.1s, 0.2s)
        await asyncio.sleep(0.5)
        
        self.assertEqual(len(bus.dead_letter_queue), 1)
        dead_msg = bus.dead_letter_queue[0]
        self.assertEqual(dead_msg.payload, "poison pill")
        self.assertEqual(dead_msg.delivery_attempts, 3)
        self.assertIn("ValueError", dead_msg.last_error)
        await bus.shutdown()

    # ==========================================
    # 6. RESILIENCE & CIRCUIT BREAKER TESTS
    # ==========================================
    async def test_circuit_breaker_transitions(self):
        print("Running Check 12: Circuit Breaker State Transitions...")
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_s=0.2,
            expected_exceptions=(ValueError,)
        )
        
        breaker = CircuitBreaker("test-cb", config)
        self.assertEqual(breaker.state, CircuitState.CLOSED)
        
        # Raise 2 failures -> remains closed
        try:
            breaker.record_failure(ValueError("err"))
            breaker.record_failure(ValueError("err"))
        except Exception:
            pass
        self.assertEqual(breaker.state, CircuitState.CLOSED)
        
        # 3rd failure -> Opens
        breaker.record_failure(ValueError("err"))
        self.assertEqual(breaker.state, CircuitState.OPEN)
        
        # Calls should not be allowed
        self.assertFalse(breaker.can_execute())
        
        # Wait for timeout (0.2s) to transition to HALF_OPEN
        await asyncio.sleep(0.25)
        self.assertTrue(breaker.can_execute())
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)
        
        # Record 1 success -> still half open
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)
        
        # Record 2nd success -> closes
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    def test_circuit_breaker_decorators(self):
        print("Running Check 13: Circuit Breaker Decorators...")
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout_s=0.1,
            expected_exceptions=(ValueError,)
        )
        
        calls = 0
        
        @circuit_breaker("sync-cb", config)
        def sync_func(should_fail=False):
            nonlocal calls
            calls += 1
            if should_fail:
                raise ValueError("sync err")
            return "ok"

        # Success call
        self.assertEqual(sync_func(), "ok")
        self.assertEqual(calls, 1)
        
        # First failure
        with self.assertRaises(ValueError):
            sync_func(should_fail=True)
            
        # Second failure (should open)
        with self.assertRaises(ValueError):
            sync_func(should_fail=True)
            
        # Subsequent call should raise CircuitBreakerOpen without calling function
        with self.assertRaises(CircuitBreakerOpen):
            sync_func()
            
        self.assertEqual(calls, 3) # Function called only 3 times total

    async def test_retry_decorator(self):
        print("Running Check 14: Retry with Exponential Backoff Decorator...")
        attempts = 0
        
        @retry_with_backoff(max_retries=2, initial_delay=0.01, backoff_factor=2.0)
        async def flakey_async_func():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("try again")
            return "success"
            
        res = await flakey_async_func()
        self.assertEqual(res, "success")
        self.assertEqual(attempts, 3)

if __name__ == "__main__":
    unittest.main()
