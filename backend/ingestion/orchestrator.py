"""
Ingestion orchestrator with:
- Backpressure (slow consumer handling)
- Resource quotas
- Job state machine
- Graceful failure handling
"""
import asyncio
import uuid
import time
import psutil
import os
from enum import Enum
from typing import Dict, Optional, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path

from backend.config import settings


class JobStatus(Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IngestionJob:
    """A single ingestion job with full state."""
    job_id: str
    source_type: str                  # "upload" | "youtube" | "camera" | "demo"
    source_path: Optional[str]
    source_url: Optional[str]
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0             # 0-1
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Results
    frame_count: int = 0
    duration_s: float = 0.0
    fps: float = 30.0
    session_id: Optional[str] = None
    
    # Resource usage
    peak_memory_mb: float = 0.0
    cpu_time_s: float = 0.0
    
    # Cancellation
    cancel_requested: bool = False


class IngestionOrchestrator:
    """
    Manages all ingestion jobs with:
    - Concurrency limit
    - Memory limit
    - Cancellation
    - Backpressure (slow consumers)
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        max_memory_mb: int = 4096,
        max_queue_size: int = 50,
    ):
        self.max_concurrent = max_concurrent
        self.max_memory_mb = max_memory_mb
        self.max_queue_size = max_queue_size
        
        self.jobs: Dict[str, IngestionJob] = {}
        self.active_jobs: set = set()
        self.pending_queue: deque = deque()
        self.lock = asyncio.Lock()
        
        # Backpressure: rate at which we emit results
        # If subscribers are slow, we slow down ingestion
        self.subscriber_count: int = 0
        self.min_subscriber_rate: float = 5.0  # FPS
        
        # Callbacks
        self.on_complete: Optional[Callable] = None
        self.on_progress: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    async def submit_job(
        self,
        source_type: str,
        source_path: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> IngestionJob:
        """Submit a new ingestion job. Returns job state."""
        # Check resource limits
        if not self._check_memory_available():
            raise MemoryError("Insufficient memory to start new job")
        
        if len(self.jobs) >= self.max_queue_size:
            raise QueueFull("Job queue is full, try again later")
        
        job = IngestionJob(
            job_id=uuid.uuid4().hex[:12],
            source_type=source_type,
            source_path=source_path,
            source_url=source_url,
        )
        
        async with self.lock:
            self.jobs[job.job_id] = job
            self.pending_queue.append(job.job_id)
        
        # Try to start the job
        asyncio.create_task(self._try_start_jobs())
        
        return job
    
    async def _try_start_jobs(self):
        """Start queued jobs up to concurrency limit."""
        async with self.lock:
            while (
                len(self.active_jobs) < self.max_concurrent
                and self.pending_queue
            ):
                job_id = self.pending_queue.popleft()
                if job_id in self.jobs:
                    self.active_jobs.add(job_id)
                    asyncio.create_task(self._run_job(job_id))
    
    async def _run_job(self, job_id: str):
        """Run a single job with full lifecycle."""
        job = self.jobs[job_id]
        process = psutil.Process(os.getpid())
        
        try:
            # 1. Validating phase
            job.status = JobStatus.VALIDATING
            job.started_at = time.time()
            await self._emit_progress(job)
            
            # 2. Processing phase
            job.status = JobStatus.PROCESSING
            await self._emit_progress(job)
            
            # 3. Run actual processing
            session_id = await self._do_processing(job)
            
            # 4. Track resources
            job.peak_memory_mb = process.memory_info().rss / 1024 / 1024
            job.completed_at = time.time()
            job.session_id = session_id
            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            
            if self.on_complete:
                await self._safe_callback(self.on_complete, job)
                
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.error = "Cancelled by user"
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)[:500]  # Truncate long errors
            
            if self.on_error:
                await self._safe_callback(self.on_error, job)
        finally:
            self.active_jobs.discard(job_id)
            await self._try_start_jobs()  # Start next pending job
    
    async def _do_processing(self, job: IngestionJob) -> str:
        """Actual processing logic. Override in subclass."""
        # Check for cancellation periodically
        if job.cancel_requested:
            raise asyncio.CancelledError()
        
        # Simulate processing with backpressure
        # In real impl: run perception pipeline, write to DB, etc.
        await asyncio.sleep(0.1)
        return "session_" + job.job_id
    
    async def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a job."""
        if job_id in self.jobs:
            self.jobs[job_id].cancel_requested = True
            return True
        return False
    
    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        return self.jobs.get(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> list:
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs
    
    def apply_backpressure(self):
        """
        Apply backpressure: if no subscribers, slow down.
        Returns sleep duration.
        """
        if self.subscriber_count == 0:
            return 1.0  # Sleep 1 second if no one is listening
        return 0.0
    
    def _check_memory_available(self) -> bool:
        """Check if we have enough memory to start a new job."""
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
        return mem_mb < self.max_memory_mb
    
    async def _emit_progress(self, job: IngestionJob):
        if self.on_progress:
            await self._safe_callback(self.on_progress, job)
    
    async def _safe_callback(self, cb, *args):
        try:
            result = cb(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            print(f"Callback error: {e}")


class QueueFull(Exception):
    pass
