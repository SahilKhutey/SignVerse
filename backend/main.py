from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.middleware.profiling import ProfilingMiddleware
from backend.routers.profiling import router as profiling_router

from backend.config import settings
from backend.routers.capture import router as capture_router
from backend.routers.stream import router as stream_router
from backend.routers.dataset import router as dataset_router
from backend.routers.export import router as export_router
from backend.routers.exporters import router as exporters_router  # NEW: multi-format
from backend.routers.analytics import router as analytics_router
from backend.routers.sessions import router as sessions_router
from backend.routers.live import router as live_ws_router
from backend.routers.live_control import router as live_ctrl_router
from backend.routers.hoi import router as hoi_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("signverse")

app = FastAPI(
    title="SignVerse Robotics API",
    version="5.0.0",
    description="SignVerse v5 — 3D Scene Export + HOI Detection + Object Trajectories. Formats: BVH, FBX, GLTF/GLB, MuJoCo, URDF, ROS2, CSV, Pinocchio, Blender, USD",
)

# Configure strict CORS
from backend.security.cors_config import configure_cors
configure_cors(app)

# Profiling middleware (added after CORS for timing accuracy)
app.add_middleware(ProfilingMiddleware, track_all=False)


app.include_router(capture_router)
app.include_router(stream_router)
app.include_router(dataset_router)
app.include_router(export_router)
app.include_router(exporters_router)  # NEW: multi-format export
app.include_router(analytics_router)
app.include_router(sessions_router)
app.include_router(live_ws_router)
app.include_router(live_ctrl_router)
app.include_router(hoi_router)
app.include_router(profiling_router)  # NEW: profiling endpoints

@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": "4.0.0",
        "status": "online - EXPORT ENGINE READY",
        "features": [
            "kinematic_math",
            "bvh_export",
            "fbx_export",
            "gltf_export",
            "glb_export",
            "mujoco_xml_export",
            "urdf_export",
            "ros2_trajectory_export",
            "csv_timeseries_export",
            "pinocchio_json_export",
            "blender_script_export",
            "robot_retargeting",
            "sqlite_dataset",
            "three_js_3d_viewer",
            "action_segmentation",
            "dataset_analytics",
            "yolov8_detector",
            "hoi_detection",
            "object_3d_tracking",
            "scene_composer",
            "gltf_scene_export",
            "mujoco_scene_export",
            "usd_scene_export",
            "interaction_timeline",
        ],
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Authentication endpoint
from backend.security.auth import LoginRequest, authenticate_user, create_jwt_token
from fastapi import HTTPException

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = await authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    token = create_jwt_token(req.username, user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

# System health endpoint
from backend.resilience.circuit_breaker import BREAKER_REGISTRY
from backend.communication.bus import bus

@app.get("/api/system/stats")
async def get_system_stats():
    breakers_data = {
        name: breaker.get_state() for name, breaker in BREAKER_REGISTRY.items()
    }
    return {
        "bus": bus.get_stats(),
        "breakers": breakers_data,
        "jobs": []
    }


from fastapi.staticfiles import StaticFiles

# Mount static folder for thumbnail rendering
app.mount("/thumbnails", StaticFiles(directory="datasets/thumbnails"), name="thumbnails")

@app.on_event("startup")
async def startup():
    logger.info("SignVerse v5.0.0 starting — HOI + Scene Reconstruction enabled")
    logger.info(f"Dataset dir: {settings.dataset_dir}")
    logger.info(f"Upload dir: {settings.upload_dir}")
    logger.info(f"Export dir: {settings.export_dir}")
    
    # Start continuous memory profiling
    from backend.services.profiling.memory_tracker import memory_tracker
    memory_tracker.start()
    
    # Start message bus health monitor
    from backend.communication.bus import bus
    await bus.start_health_monitor(interval=10.0)

@app.on_event("shutdown")
async def shutdown():
    from backend.services.profiling.memory_tracker import memory_tracker
    memory_tracker.stop()
    
    from backend.communication.bus import bus
    await bus.shutdown()
    logger.info("SignVerse API shutting down")

