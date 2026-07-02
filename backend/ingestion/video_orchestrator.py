import asyncio
import os
import psutil
from typing import Optional
from pathlib import Path
from backend.ingestion.orchestrator import IngestionOrchestrator, IngestionJob, JobStatus
from backend.models.database import SessionLocal
from backend.services.dataset_builder import DatasetBuilder
from backend.services.youtube_ingester import download_youtube

class AsyncVideoOrchestrator(IngestionOrchestrator):
    """
    Asynchronous implementation of the IngestionOrchestrator.
    Runs the actual perception pipeline on local or YouTube videos frame-by-frame
    in a background thread to prevent blocking the event loop and to keep memory usage low.
    """
    
    def __init__(self, max_concurrent: int = 2, max_memory_mb: int = 4096, max_queue_size: int = 50):
        super().__init__(max_concurrent=max_concurrent, max_memory_mb=max_memory_mb, max_queue_size=max_queue_size)

    async def _do_processing(self, job: IngestionJob) -> str:
        # Check cancellation
        if job.cancel_requested:
            raise asyncio.CancelledError()

        # Handle YouTube download if source is YouTube
        video_path = job.source_path
        if job.source_type == "youtube":
            job.status = JobStatus.VALIDATING
            await self._emit_progress(job)
            try:
                # Download YouTube video
                youtube_path = await download_youtube(job.source_url, job.job_id)
                video_path = str(Path(youtube_path).resolve())
                job.source_path = video_path
            except Exception as e:
                raise ValueError(f"YouTube download failed: {str(e)}")

        if not video_path or not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Check cancellation
        if job.cancel_requested:
            raise asyncio.CancelledError()

        # Database session and dataset builder
        db_session = SessionLocal()
        try:
            builder = DatasetBuilder(db_session)
            
            # Progress callback for the dataset builder
            loop = asyncio.get_running_loop()
            def on_progress(p: float):
                job.progress = p
                # Run the async callback in the event loop thread
                loop.call_soon_threadsafe(lambda: asyncio.create_task(self._emit_progress(job)))

            def check_cancelled() -> bool:
                return job.cancel_requested

            # Run the heavy processing in a separate OS thread to avoid blocking the event loop
            session_id = await asyncio.to_thread(
                builder.build_session_from_video,
                job_id=job.job_id,
                video_path=video_path,
                source_type=job.source_type,
                name=Path(video_path).name,
                progress_callback=on_progress,
                check_cancelled=check_cancelled
            )
            
            return session_id

        finally:
            db_session.close()
            # Clean up the downloaded/uploaded temporary video file to save disk space
            # but only if it's in the upload directory
            if video_path and Path(video_path).exists():
                try:
                    # If it's a YouTube download or temporary upload, we can clean it up
                    if "uploads" in str(video_path) or "datasets" in str(video_path):
                        Path(video_path).unlink(missing_ok=True)
                except Exception:
                    pass
