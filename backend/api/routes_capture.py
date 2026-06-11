import uuid
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.core.frame_processor import FrameProcessor
from backend.core.database import db
from backend.utils.video_utils import validate_video
from backend.utils.youtube_utils import download_youtube
from backend.config import settings

router = APIRouter(prefix="/api/capture", tags=["capture"])

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

    # Process pose coordinates
    processor = FrameProcessor(source="upload", filename=file.filename)
    try:
        metadata = processor.process_video(save_path)
    except Exception as e:
        raise HTTPException(500, f"Holistic perception processing failed: {str(e)}")

    # Persist session to local SQLite database
    db.create_session(
        session_id=processor.session_id,
        source="upload",
        filename=file.filename,
        fps=metadata.fps,
        frame_count=metadata.frame_count,
        duration_sec=metadata.duration_sec,
        video_path=str(save_path),
    )

    # Export raw skeleton coordinate JSON file
    skeleton_path = settings.dataset_dir / f"{processor.session_id}_skeleton.json"
    with open(skeleton_path, "w") as f:
        f.write(processor.to_json())
        
    db.update_skeleton_path(processor.session_id, str(skeleton_path))
    db.update_session_status(processor.session_id, "ready")

    return {
        "session_id": processor.session_id,
        "metadata": metadata.model_dump(mode="json"),
        "frames_extracted": len(processor.frames),
    }

@router.post("/youtube")
async def capture_youtube(url: str = Form(...)):
    """Ingets a YouTube link, downloads the video, runs holistic pose tracking, and saves session metadata to SQLite"""
    try:
        video_path = download_youtube(url)
    except Exception as e:
        raise HTTPException(400, f"YouTube download failed: {str(e)}")

    processor = FrameProcessor(source="youtube", filename=video_path.name)
    try:
        metadata = processor.process_video(video_path)
    except Exception as e:
        raise HTTPException(500, f"Holistic perception processing failed: {str(e)}")

    # Save session
    db.create_session(
        session_id=processor.session_id,
        source="youtube",
        filename=video_path.name,
        fps=metadata.fps,
        frame_count=metadata.frame_count,
        duration_sec=metadata.duration_sec,
        video_path=str(video_path),
    )

    # Save skeleton JSON
    skeleton_path = settings.dataset_dir / f"{processor.session_id}_skeleton.json"
    with open(skeleton_path, "w") as f:
        f.write(processor.to_json())
        
    db.update_skeleton_path(processor.session_id, str(skeleton_path))
    db.update_session_status(processor.session_id, "ready")

    return {
        "session_id": processor.session_id,
        "metadata": metadata.model_dump(mode="json"),
        "frames_extracted": len(processor.frames),
    }
