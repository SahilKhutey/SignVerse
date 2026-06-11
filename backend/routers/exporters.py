"""
Multi-format Motion Export API Router — v5
GET /api/exporters/{session_id}/export?format=<fmt>

Person-only formats:
  bvh, fbx, gltf, glb, mujoco, urdf, ros2, csv, pinocchio, blender, json

Scene-level formats (person + objects):
  gltf_scene   → GLTF 2.0 with animated object nodes
  glb_scene    → Binary GLB with full scene
  bvh_scene    → BVH with object ROOT joints
  mujoco_scene → MuJoCo XML with object bodies + keyframes
  usd_scene    → USD ASCII (.usda) with skeleton + mesh prims
"""
import json
import struct as _struct
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.services.exporters import (
    SessionDataLoader,
    BVHExporter, BVHSceneExporter,
    FBXExporter,
    GLTFExporter, GLTFSceneExporter,
    MuJoCoExporter, MuJoCoSceneExporter,
    URDFExporter,
    USDExporter,
)
from backend.services.scene.scene_composer import SceneComposer
from backend.services.export_engine import export_json  # legacy

logger = logging.getLogger("signverse.exporters")
router = APIRouter(prefix="/api/exporters", tags=["exporters"])

# Singleton exporter + composer instances
_loader   = SessionDataLoader()
_bvh      = BVHExporter()
_bvh_sc   = BVHSceneExporter()
_fbx      = FBXExporter()
_gltf     = GLTFExporter()
_gltf_sc  = GLTFSceneExporter()
_mujoco   = MuJoCoExporter()
_mujoco_sc= MuJoCoSceneExporter()
_urdf     = URDFExporter()
_usd      = USDExporter()
_composer = SceneComposer()


def _load(session_id: str, db: Session):
    """Helper: load UnifiedMotionData or raise 404/422."""
    try:
        return _loader.load(session_id, db)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)


# ──────────────────────────────────────────────────────────────────────────
# Unified export endpoint
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("bvh", description=(
        "Export format: bvh | fbx | gltf | glb | mujoco | "
        "urdf | ros2 | csv | pinocchio | blender | json"
    )),
    db: Session = Depends(get_db),
):
    """
    Export a recorded motion session to the requested format.
    Returns a downloadable file as an attachment.
    """
    fmt = format.lower().strip()
    sid_short = session_id[:8]
    logger.info(f"Export request: session={sid_short} format={fmt}")

    # ── BVH ──────────────────────────────────────────────────────────── #
    if fmt == "bvh":
        data = _load(session_id, db)
        content = _bvh.export(data)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.bvh"'},
        )

    # ── ASCII FBX ────────────────────────────────────────────────────── #
    elif fmt == "fbx":
        data = _load(session_id, db)
        content = _fbx.export(data)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.fbx"'},
        )

    # ── GLTF 2.0 (JSON + embedded base64 buffer) ─────────────────────── #
    elif fmt == "gltf":
        data = _load(session_id, db)
        gltf_dict, _ = _gltf.export(data, embed_binary=True)
        content = json.dumps(gltf_dict, indent=2)
        return Response(
            content=content,
            media_type="model/gltf+json",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.gltf"'},
        )

    # ── GLB (binary GLTF) ─────────────────────────────────────────────── #
    elif fmt == "glb":
        import struct as _struct
        data = _load(session_id, db)
        gltf_dict, bin_buf = _gltf.export(data, embed_binary=False)

        # Update buffer URI to point to embedded buffer (GLB format)
        gltf_dict["buffers"][0].pop("uri", None)

        json_bytes = json.dumps(gltf_dict).encode("utf-8")
        # Pad to 4-byte boundary
        if len(json_bytes) % 4:
            json_bytes += b" " * (4 - len(json_bytes) % 4)
        if len(bin_buf) % 4:
            bin_buf += b"\x00" * (4 - len(bin_buf) % 4)

        # GLB header
        total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_buf)
        header = _struct.pack("<III", 0x46546C67, 2, total_len)
        json_chunk = _struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
        bin_chunk  = _struct.pack("<II", len(bin_buf),   0x004E4942) + bin_buf
        glb_bytes  = header + json_chunk + bin_chunk

        return Response(
            content=glb_bytes,
            media_type="model/gltf-binary",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.glb"'},
        )

    # ── MuJoCo XML ───────────────────────────────────────────────────── #
    elif fmt == "mujoco":
        data = _load(session_id, db)
        content = _mujoco.export(data)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}_mujoco.xml"'},
        )

    # ── URDF ─────────────────────────────────────────────────────────── #
    elif fmt == "urdf":
        data = _load(session_id, db)
        content = _urdf.export_urdf(data)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.urdf"'},
        )

    # ── ROS2 JointTrajectory YAML ─────────────────────────────────────── #
    elif fmt == "ros2":
        data = _load(session_id, db)
        content = _urdf.export_ros2_trajectory(data)
        return Response(
            content=content,
            media_type="text/yaml",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}_ros2.yaml"'},
        )

    # ── CSV Time Series ───────────────────────────────────────────────── #
    elif fmt == "csv":
        data = _load(session_id, db)
        content = _urdf.export_csv(data)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.csv"'},
        )

    # ── Pinocchio JSON ────────────────────────────────────────────────── #
    elif fmt == "pinocchio":
        data = _load(session_id, db)
        pinocchio_dict = _urdf.export_pinocchio(data)
        content = json.dumps(pinocchio_dict, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}_pinocchio.json"'},
        )

    # ── Blender Python Script ─────────────────────────────────────────── #
    elif fmt == "blender":
        data = _load(session_id, db)
        content = _urdf.export_blender_script(data)
        return Response(
            content=content,
            media_type="text/x-python",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}_blender.py"'},
        )

    # ── Legacy SignVerse JSON ─────────────────────────────────────────── #
    elif fmt in ("json", "signverse"):
        from backend.models.database import MotionSession
        session = db.query(MotionSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        result = export_json(session, db)
        content = json.dumps(result, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="session_{sid_short}.json"'},
        )

    # ── GLTF Scene (person + objects) ──────────────────────────────── #
    elif fmt == "gltf_scene":
        scene = _composer.load(session_id, db)
        gltf_dict, _ = _gltf_sc.export_scene(scene, embed_binary=True)
        content = json.dumps(gltf_dict, indent=2)
        return Response(
            content=content,
            media_type="model/gltf+json",
            headers={"Content-Disposition": f'attachment; filename="scene_{sid_short}.gltf"'},
        )

    # ── GLB Scene ────────────────────────────────────────────────────── #
    elif fmt == "glb_scene":
        scene = _composer.load(session_id, db)
        gltf_dict, bin_buf = _gltf_sc.export_scene(scene, embed_binary=False)
        gltf_dict["buffers"][0].pop("uri", None)
        json_bytes = json.dumps(gltf_dict).encode("utf-8")
        if len(json_bytes) % 4:
            json_bytes += b" " * (4 - len(json_bytes) % 4)
        if len(bin_buf) % 4:
            bin_buf += b"\x00" * (4 - len(bin_buf) % 4)
        total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_buf)
        header    = _struct.pack("<III", 0x46546C67, 2, total_len)
        json_chunk = _struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
        bin_chunk  = _struct.pack("<II", len(bin_buf),   0x004E4942) + bin_buf
        return Response(
            content=header + json_chunk + bin_chunk,
            media_type="model/gltf-binary",
            headers={"Content-Disposition": f'attachment; filename="scene_{sid_short}.glb"'},
        )

    # ── BVH Scene ────────────────────────────────────────────────────── #
    elif fmt == "bvh_scene":
        scene = _composer.load(session_id, db)
        content = _bvh_sc.export_scene(scene)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="scene_{sid_short}.bvh"'},
        )

    # ── MuJoCo Scene ─────────────────────────────────────────────────── #
    elif fmt == "mujoco_scene":
        scene = _composer.load(session_id, db)
        content = _mujoco_sc.export_scene(scene)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="scene_{sid_short}_mujoco.xml"'},
        )

    # ── USD Scene (.usda) ─────────────────────────────────────────────── #
    elif fmt == "usd_scene":
        scene = _composer.load(session_id, db)
        content = _usd.export_scene(scene)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="scene_{sid_short}.usda"'},
        )

    # ── Metric 3D JSON ────────────────────────────────────────────────── #
    elif fmt == "metric_json":
        from backend.models.database import MotionSession, MotionFrame
        from backend.services.exporters.metric_exporter import MetricExporter
        session = db.query(MotionSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        frames_db = db.query(MotionFrame).filter_by(session_id=session_id).order_by(MotionFrame.frame_idx).all()
        metric_frames = []
        for f in frames_db:
            if f.metric_json:
                try:
                    m_dict = json.loads(f.metric_json)
                    m_dict["frame_id"] = f.frame_idx
                    m_dict["timestamp_ms"] = f.timestamp_ms
                    metric_frames.append(m_dict)
                except Exception:
                    pass
        if not metric_frames:
            raise HTTPException(status_code=400, detail="No metric data available for this session.")
        
        session_stats = {"fps": session.fps}
        export_dict = MetricExporter.export_metric_json(session.name, metric_frames, session_stats)
        content = json.dumps(export_dict, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="metric_{sid_short}.json"'},
        )

    # ── Metric 3D CSV ─────────────────────────────────────────────────── #
    elif fmt == "metric_csv":
        from backend.models.database import MotionFrame
        from backend.services.exporters.metric_exporter import MetricExporter
        frames_db = db.query(MotionFrame).filter_by(session_id=session_id).order_by(MotionFrame.frame_idx).all()
        metric_frames = []
        for f in frames_db:
            if f.metric_json:
                try:
                    m_dict = json.loads(f.metric_json)
                    m_dict["frame_id"] = f.frame_idx
                    m_dict["timestamp_ms"] = f.timestamp_ms
                    metric_frames.append(m_dict)
                except Exception:
                    pass
        if not metric_frames:
            raise HTTPException(status_code=400, detail="No metric data available for this session.")
        
        content = MetricExporter.export_csv_metric(metric_frames)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="metric_{sid_short}.csv"'},
        )

    # ── Biomechanical CSV ─────────────────────────────────────────────── #
    elif fmt == "measurements_csv":
        from backend.models.database import MotionFrame
        from backend.services.exporters.metric_exporter import MetricExporter
        frames_db = db.query(MotionFrame).filter_by(session_id=session_id).order_by(MotionFrame.frame_idx).all()
        metric_frames = []
        for f in frames_db:
            if f.metric_json:
                try:
                    m_dict = json.loads(f.metric_json)
                    m_dict["frame_id"] = f.frame_idx
                    m_dict["timestamp_ms"] = f.timestamp_ms
                    metric_frames.append(m_dict)
                except Exception:
                    pass
        if not metric_frames:
            raise HTTPException(status_code=400, detail="No metric data available for this session.")
        
        content = MetricExporter.export_measurements_csv(metric_frames)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="measurements_{sid_short}.csv"'},
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported format '{fmt}'. "
                "Person-only: bvh, fbx, gltf, glb, mujoco, urdf, ros2, csv, pinocchio, blender, json, metric_json, metric_csv, measurements_csv. "
                "Scene (person+objects): gltf_scene, glb_scene, bvh_scene, mujoco_scene, usd_scene"
            ),
        )


# ──────────────────────────────────────────────────────────────────────────
# Metadata endpoint: list available formats for a session
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/formats")
async def list_export_formats(session_id: str, db: Session = Depends(get_db)):
    """Return the list of available export formats and metadata for this session."""
    from backend.models.database import MotionSession
    session = db.query(MotionSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "session_name": session.name,
        "fps": session.fps,
        "frame_count": session.frame_count,
        "duration_s": session.duration_s,
        "action_label": session.action_label,
        "object_count":     getattr(session, "object_count", 0) or 0,
        "unique_objects":    [],
        "available_formats": [
            # ── Person-only ──
            {"id": "bvh",          "label": "BVH",                  "icon": "🎭", "category": "3D Animation",     "ext": ".bvh",  "scene": False, "compat": "Blender, Maya, MotionBuilder"},
            {"id": "fbx",          "label": "FBX (ASCII 7.4)",      "icon": "🎮", "category": "Game Engine",      "ext": ".fbx",  "scene": False, "compat": "Unity, Unreal, Blender, Maya"},
            {"id": "gltf",         "label": "GLTF 2.0",             "icon": "🌐", "category": "Web / AR",         "ext": ".gltf", "scene": False, "compat": "Three.js, Babylon.js, ARCore"},
            {"id": "glb",          "label": "GLB (Binary GLTF)",    "icon": "🌐", "category": "Web / AR",         "ext": ".glb",  "scene": False, "compat": "Web viewers, AR platforms"},
            {"id": "mujoco",       "label": "MuJoCo XML",           "icon": "🤖", "category": "Robotics / RL",    "ext": ".xml",  "scene": False, "compat": "MuJoCo, MuJoCo MPC, dm_control"},
            {"id": "urdf",         "label": "URDF",                 "icon": "🔩", "category": "Robotics",         "ext": ".urdf", "scene": False, "compat": "ROS, Gazebo, Isaac Sim"},
            {"id": "ros2",         "label": "ROS2 Trajectory",      "icon": "📡", "category": "Robotics",         "ext": ".yaml", "scene": False, "compat": "ROS2 Humble/Iron/Jazzy"},
            {"id": "csv",          "label": "CSV Time Series",      "icon": "📊", "category": "Data Analysis",    "ext": ".csv",  "scene": False, "compat": "Pandas, MATLAB, Excel"},
            {"id": "pinocchio",    "label": "Pinocchio JSON",       "icon": "⚙️", "category": "Control",          "ext": ".json", "scene": False, "compat": "Pinocchio, TSID, OCS2"},
            {"id": "blender",      "label": "Blender Script",       "icon": "🍊", "category": "3D Animation",     "ext": ".py",   "scene": False, "compat": "Blender 3.x / 4.x headless"},
            {"id": "json",         "label": "SignVerse JSON",        "icon": "📋", "category": "Data Exchange",    "ext": ".json", "scene": False, "compat": "SignVerse ecosystem"},
            # ── Metric Data ──
            {"id": "metric_json",  "label": "Metric 3D JSON",       "icon": "📏", "category": "Metric Data",      "ext": ".json", "scene": False, "compat": "Unity, Web viewers, Custom analyses"},
            {"id": "metric_csv",   "label": "Metric 3D CSV",        "icon": "📈", "category": "Metric Data",      "ext": ".csv",  "scene": False, "compat": "Pandas, Excel, MATLAB"},
            {"id": "measurements_csv", "label": "Biomechanical CSV",  "icon": "🦴", "category": "Metric Data",      "ext": ".csv",  "scene": False, "compat": "Ergonomics / Biomedical Analysis"},
            # ── Scene-level (person + objects) ──
            {"id": "gltf_scene",   "label": "GLTF Scene",           "icon": "🎬", "category": "Full Scene",        "ext": ".gltf", "scene": True,  "compat": "Three.js, Babylon.js, Sketchfab"},
            {"id": "glb_scene",    "label": "GLB Scene (Binary)",   "icon": "🎬", "category": "Full Scene",        "ext": ".glb",  "scene": True,  "compat": "Web, Unity, Unreal, Blender"},
            {"id": "bvh_scene",    "label": "BVH Scene + Objects",  "icon": "🏃", "category": "Full Scene",        "ext": ".bvh",  "scene": True,  "compat": "Blender, Maya, MotionBuilder"},
            {"id": "mujoco_scene", "label": "MuJoCo Scene",         "icon": "🦾", "category": "Full Scene / RL",   "ext": ".xml",  "scene": True,  "compat": "MuJoCo, dm_control, IsaacGym"},
            {"id": "usd_scene",    "label": "USD Scene (.usda)",    "icon": "🌌", "category": "Full Scene / VFX",  "ext": ".usda", "scene": True,  "compat": "Houdini, Unreal, USD Composer"},
        ],
    }
