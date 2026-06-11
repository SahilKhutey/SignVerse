"""
Unit tests for ingestion orchestrator.
"""
import pytest
import asyncio
from backend.ingestion.orchestrator import IngestionOrchestrator, JobStatus, QueueFull


@pytest.mark.asyncio
@pytest.mark.unit
class TestIngestionOrchestrator:
    """Tests for IngestionOrchestrator job concurrency and limits."""
    
    async def test_submit_job(self):
        """Should submit job and start processing up to limits."""
        orchestrator = IngestionOrchestrator(max_concurrent=1)
        job = await orchestrator.submit_job(source_type="upload", source_path="test.mp4")
        
        assert job.job_id in orchestrator.jobs
        assert job.status in (JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.PROCESSING, JobStatus.COMPLETED)
        
        # Let's wait a moment for job task to run
        await asyncio.sleep(0.2)
        assert job.status == JobStatus.COMPLETED
    
    async def test_queue_full(self):
        """Should raise QueueFull if max queue size exceeded."""
        orchestrator = IngestionOrchestrator(max_queue_size=2)
        
        # Submit 2 jobs to fill queue
        await orchestrator.submit_job(source_type="upload")
        await orchestrator.submit_job(source_type="upload")
        
        # Third submission should raise QueueFull
        with pytest.raises(QueueFull):
            await orchestrator.submit_job(source_type="upload")
    
    async def test_cancel_job(self):
        """Should cancel active or queued job."""
        orchestrator = IngestionOrchestrator(max_concurrent=1)
        
        # Submit job
        job = await orchestrator.submit_job(source_type="upload")
        
        # Cancel the job
        cancelled = await orchestrator.cancel_job(job.job_id)
        assert cancelled is True
        
        # Wait a moment
        await asyncio.sleep(0.2)
        assert job.status == JobStatus.CANCELLED or job.cancel_requested is True
