import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from backend.core.database import db

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/skeleton/{session_id}")
async def export_skeleton_json(session_id: str):
    """Retrieve and download the full raw coordinate JSON sequence file for a session"""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    skeleton_path = session.get("skeleton_json_path")
    if not skeleton_path or not Path(skeleton_path).exists():
        raise HTTPException(404, "Skeleton landmarks JSON file not found")

    with open(skeleton_path) as f:
        content = f.read()

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={session_id}_skeleton.json"
        },
    )
