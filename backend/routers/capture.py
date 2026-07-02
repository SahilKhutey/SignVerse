import uuid
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends

from backend.models.database import SessionLocal
from backend.services.youtube_ingester import validate_youtube_url
from backend.config import settings
from backend.security.rate_limiter import check_rate_limit
from backend.ingestion.video_orchestrator import AsyncVideoOrchestrator

router = APIRouter(prefix="/api/capture", tags=["capture"], dependencies=[Depends(check_rate_limit("ingest"))])

# Single global instance of the async orchestrator
orchestrator = AsyncVideoOrchestrator()

# Helper for video validation
def validate_video(file_path: Path) -> tuple[bool, str]:
    import cv2
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return False, "Cannot open video file"
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return False, "Failed to read first frame from video"
    return True, ""

@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a local video file, run holistic tracking asynchronously via AsyncVideoOrchestrator"""
    if not file.filename:
        raise HTTPException(400, "Missing filename in upload data")

    # Generate local path
    ext = Path(file.filename).suffix or ".mp4"
    save_name = f"{uuid.uuid4().hex[:10]}{ext}"
    save_path = settings.upload_dir / save_name

    size = 0
    with save_path.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                save_path.unlink(missing_ok=True)
                raise HTTPException(413, f"Uploaded video file size exceeds maximum limit of {settings.max_upload_mb}MB")
            f.write(chunk)

    # Validate video
    valid, msg = validate_video(save_path)
    if not valid:
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Uploaded file validation failed: {msg}")

    try:
        # Submit to orchestrator
        job = await orchestrator.submit_job(
            source_type="upload",
            source_path=str(save_path.resolve())
        )
        return {
            "job_id": job.job_id,
            "source_type": job.source_type,
            "status": job.status.value,
            "progress": job.progress
        }
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to submit ingestion job: {str(e)}")

@router.post("/youtube")
async def capture_youtube(url: str = Form(...)):
    """Ingests a YouTube link and runs tracking asynchronously via AsyncVideoOrchestrator"""
    if not validate_youtube_url(url):
        raise HTTPException(400, "Invalid YouTube URL format")
        
    try:
        # Submit to orchestrator (download is run inside the background job lifecycle)
        job = await orchestrator.submit_job(
            source_type="youtube",
            source_url=url
        )
        return {
            "job_id": job.job_id,
            "source_type": job.source_type,
            "status": job.status.value,
            "progress": job.progress
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to submit YouTube ingestion job: {str(e)}")

@router.get("/jobs")
async def list_jobs():
    """List all ingestion jobs in the queue"""
    return [
        {
            "job_id": j.job_id,
            "source_type": j.source_type,
            "status": j.status.value,
            "progress": round(j.progress, 4),
            "error": j.error,
            "session_id": j.session_id,
            "created_at": j.created_at,
        }
        for j in orchestrator.list_jobs()
    ]

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Retrieve the status and progress of a specific job"""
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.job_id,
        "source_type": job.source_type,
        "status": job.status.value,
        "progress": round(job.progress, 4),
        "error": job.error,
        "session_id": job.session_id,
        "created_at": job.created_at,
    }

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a pending or active ingestion job"""
    cancelled = await orchestrator.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(404, "Job not found or cannot be cancelled")
    return {"status": "cancelled", "job_id": job_id}

