import uuid
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends

from backend.models.database import SessionLocal
from backend.services.dataset_builder import DatasetBuilder
from backend.services.youtube_ingester import validate_youtube_url, download_youtube
from backend.config import settings
from backend.security.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/capture", tags=["capture"], dependencies=[Depends(check_rate_limit("ingest"))])

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
    """Upload a local video file, run holistic tracking, and save session metadata to SQLite"""
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

    # Process pose coordinates using DatasetBuilder
    db_session = SessionLocal()
    try:
        import cv2
        cap = cv2.VideoCapture(str(save_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = []
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame.astype(float) / 255.0)
        cap.release()

        if not frames:
            raise HTTPException(400, "Empty video file or failed to decode frames")

        builder = DatasetBuilder(db_session)
        session_id = builder.build_session(
            job_id=uuid.uuid4().hex[:10],
            frames=frames,
            fps=fps,
            source_type="upload",
            name=file.filename
        )

        return {
            "session_id": session_id,
            "frames_extracted": len(frames),
            "status": "ready"
        }
    except Exception as e:
        raise HTTPException(500, f"Perception pipeline processing failed: {str(e)}")
    finally:
        db_session.close()

@router.post("/youtube")
async def capture_youtube(url: str = Form(...)):
    """Ingests a YouTube link, downloads the video, runs holistic pose tracking, and saves session metadata to SQLite"""
    if not validate_youtube_url(url):
        raise HTTPException(400, "Invalid YouTube URL format")
        
    try:
        # Generate temporary job id for downloading
        job_id = str(uuid.uuid4().hex[:10])
        video_path = await download_youtube(url, job_id)
        video_path = Path(video_path)
    except Exception as e:
        raise HTTPException(400, f"YouTube download failed: {str(e)}")

    # Validate video
    valid, msg = validate_video(video_path)
    if not valid:
        video_path.unlink(missing_ok=True)
        raise HTTPException(400, f"YouTube file validation failed: {msg}")

    db_session = SessionLocal()
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = []
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame.astype(float) / 255.0)
        cap.release()

        if not frames:
            raise HTTPException(400, "Empty YouTube video or failed to decode frames")

        builder = DatasetBuilder(db_session)
        session_id = builder.build_session(
            job_id=uuid.uuid4().hex[:10],
            frames=frames,
            fps=fps,
            source_type="youtube",
            name=video_path.name
        )

        return {
            "session_id": session_id,
            "frames_extracted": len(frames),
            "status": "ready"
        }
    except Exception as e:
        raise HTTPException(500, f"Perception pipeline processing failed: {str(e)}")
    finally:
        db_session.close()
