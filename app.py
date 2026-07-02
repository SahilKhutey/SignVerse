import streamlit as st
import cv2
import json
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import time
import os
from datetime import datetime
import gc
import psutil
import plotly.graph_objects as go
import math

# Append current directory to path
sys.path.append(str(Path(__file__).parent.resolve()))

from core.pose_extractor import PoseExtractor
from core.motion_capture import MotionCapture
from core.input_sources import InputManager
from core.renderer_3d import Skeleton3DRenderer
from core.blender_export import BVHExporter, RobotRetargeter

from backend.core.database import db
from backend.core.action_segmenter import ActionSegmenter
from backend.services.profiling.memory_tracker import MemorySnapshot
from backend.services.export_engine import export_json, export_bvh_string, export_robot_json
from backend.models.database import SessionLocal, MotionSession

# Initialize Directories
Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/outputs").mkdir(parents=True, exist_ok=True)

# ----------------- UI / UX Configurations -----------------
st.set_page_config(
    page_title="SignVerse Robotics Studio",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Cyberpunk Glassmorphism Aesthetics
st.markdown("""
<style>
    /* Global Styles */
    body {
        background-color: #0A0E17;
        color: #E2E8F0;
    }
    
    /* Neon Text Header */
    .main-header {
        font-family: 'Outfit', 'Inter', sans-serif;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00D9FF 0%, #FF0055 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.1rem;
        letter-spacing: -0.05em;
    }
    
    .sub-header {
        font-family: 'Inter', sans-serif;
        font-size: 1.05rem;
        color: #718096;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    /* Glassmorphism Metric Cards */
    .metric-card {
        background: rgba(16, 22, 37, 0.6);
        border: 1px solid rgba(0, 217, 255, 0.15);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease;
        margin-bottom: 1rem;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 0, 85, 0.4);
    }
    
    .metric-title {
        color: #718096;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #E2E8F0;
    }

    /* Diagnostics Card Styling */
    .diag-card {
        background: rgba(20, 26, 45, 0.5);
        border-left: 4px solid #00D9FF;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        border-top: 1px solid rgba(255,255,255,0.03);
        border-right: 1px solid rgba(255,255,255,0.03);
        border-bottom: 1px solid rgba(255,255,255,0.03);
    }
    .diag-card.warning {
        border-left-color: #FFB300;
    }
    .diag-card.error {
        border-left-color: #FF0055;
    }
    .diag-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #E2E8F0;
        margin-bottom: 0.25rem;
    }
    .diag-text {
        font-size: 0.85rem;
        color: #A0AEC0;
    }
    
    /* Streamlit Sidebar Style overrides */
    section[data-testid="stSidebar"] {
        background-color: #0B0F19;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Accent Buttons */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #00D9FF 0%, #007799 100%);
        color: #0A0E17;
        border: none;
        font-weight: 700;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        background: linear-gradient(135deg, #FF0055 0%, #990033 100%);
        color: #FFFFFF;
        box-shadow: 0 0 15px rgba(255, 0, 85, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# Header Title Block
st.markdown('<h1 class="main-header">🤖 SignVerse Robotics Studio</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Universal Human-to-Robot Motion Intelligence and Kinematic Transfer Pipeline</p>', unsafe_allow_html=True)

# ----------------- Helper Functions -----------------

def generate_annotated_preview(input_video_path: str, output_video_path: str, frames: list):
    """Draws 2D skeletal coordinates onto source frames and exports a preview MP4"""
    import mediapipe as mp
    
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))
    
    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose
    mp_hands = mp.solutions.hands
    
    for idx, pose_frame in enumerate(frames):
        ret, frame = cap.read()
        if not ret:
            break
            
        # Draw Pose skeleton connections
        if pose_frame.landmarks_33:
            landmark_list = mp_pose.NormalizedLandmarkList()
            for lm in pose_frame.landmarks_33:
                landmark_list.landmark.add(x=lm['x'], y=lm['y'], z=lm['z'], visibility=lm.get('visibility', 1.0))
                
            mp_drawing.draw_landmarks(
                frame, 
                landmark_list, 
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 217, 255), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 217, 255), thickness=2)
            )
            
        # Draw Left Hand
        if pose_frame.left_hand_21:
            hand_list = mp_hands.NormalizedLandmarkList()
            for lm in pose_frame.left_hand_21:
                hand_list.landmark.add(x=lm['x'], y=lm['y'], z=lm['z'])
            mp_drawing.draw_landmarks(
                frame, 
                hand_list, 
                mp_hands.HAND_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(255, 0, 85), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(255, 0, 85), thickness=2)
            )
            
        # Draw Right Hand
        if pose_frame.right_hand_21:
            hand_list = mp_hands.NormalizedLandmarkList()
            for lm in pose_frame.right_hand_21:
                hand_list.landmark.add(x=lm['x'], y=lm['y'], z=lm['z'])
            mp_drawing.draw_landmarks(
                frame, 
                hand_list, 
                mp_hands.HAND_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 102), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 255, 102), thickness=2)
            )
            
        out.write(frame)
        
    cap.release()
    out.release()

def map_db_frame_to_visualizer(f):
    """Maps frame formats defensively to visualizer keys"""
    if hasattr(f, "to_dict"):
        f_dict = f.to_dict()
    elif isinstance(f, dict):
        f_dict = f
    else:
        f_dict = {}
        
    return {
        "frame_id": f_dict.get("frame_id") or f_dict.get("frame_idx") or 0,
        "timestamp": f_dict.get("timestamp") or (f_dict.get("timestamp_ms", 0) / 1000.0),
        "landmarks_33": f_dict.get("landmarks_33") or f_dict.get("pose_33") or f_dict.get("pose") or [],
        "left_hand_21": f_dict.get("left_hand_21") or f_dict.get("left_hand") or [],
        "right_hand_21": f_dict.get("right_hand_21") or f_dict.get("right_hand") or [],
        "face_mesh": f_dict.get("face_mesh") or f_dict.get("face") or f_dict.get("face_468") or [],
        "joint_angles": f_dict.get("joint_angles") or f_dict.get("kinematics", {}).get("euler_deg", {})
    }

def get_session_frames(session_id: str):
    """Query frames directly from SQLite DB when file is missing"""
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM motion_frames WHERE session_id = ? ORDER BY frame_idx",
            (session_id,)
        ).fetchall()
        
        frames = []
        for r in rows:
            p_json = json.loads(r["perception_json"]) if r["perception_json"] else {}
            kin_json = json.loads(r["kinematics_json"]) if r["kinematics_json"] else {}
            frames.append({
                "frame_id": r["frame_idx"],
                "timestamp": r["timestamp_ms"] / 1000.0,
                "landmarks_33": p_json.get("pose", []),
                "left_hand_21": p_json.get("left_hand", []),
                "right_hand_21": p_json.get("right_hand", []),
                "face_mesh": p_json.get("face", []),
                "joint_angles": kin_json.get("euler_deg", {}),
            })
        return frames

def load_session_frames(session: dict):
    """Load frames dynamically checking JSON file first, falling back to SQLite"""
    json_path = session.get("skeleton_json_path")
    if json_path and Path(json_path).exists():
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                frames = data.get("frames", [])
                if frames:
                    return [map_db_frame_to_visualizer(fr) for fr in frames]
        except Exception as e:
            st.warning(f"Error reading session file: {e}")
            
    # Fallback
    return get_session_frames(session["session_id"])

def export_session_data(session_id: str, fmt: str):
    """Integrates directly with the backend's SessionDataLoader, SceneComposer, and Exporters"""
    from backend.models.database import SessionLocal
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
    import struct as _struct

    session_db = SessionLocal()
    try:
        loader = SessionDataLoader()
        
        # Check if the session exists in SQLAlchemy session
        from backend.models.database import MotionSession
        session = session_db.query(MotionSession).filter_by(id=session_id).first()
        if not session:
            return None, "Session not found", "text/plain"

        # Check format type (scene vs person-only)
        is_scene_fmt = fmt in ("gltf_scene", "glb_scene", "bvh_scene", "mujoco_scene", "usd_scene")

        if is_scene_fmt:
            composer = SceneComposer()
            scene = composer.load(session_id, session_db)
            
            if fmt == "gltf_scene":
                gltf_sc = GLTFSceneExporter()
                gltf_dict, _ = gltf_sc.export_scene(scene, embed_binary=True)
                return json.dumps(gltf_dict, indent=2).encode('utf-8'), f"scene_{session_id[:8]}.gltf", "model/gltf+json"
                
            elif fmt == "glb_scene":
                gltf_sc = GLTFSceneExporter()
                gltf_dict, bin_buf = gltf_sc.export_scene(scene, embed_binary=False)
                gltf_dict["buffers"][0].pop("uri", None)
                json_bytes = json.dumps(gltf_dict).encode("utf-8")
                if len(json_bytes) % 4:
                    json_bytes += b" " * (4 - len(json_bytes) % 4)
                if len(bin_buf) % 4:
                    bin_buf += b"\x00" * (4 - len(bin_buf) % 4)
                total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_buf)
                header = _struct.pack("<III", 0x46546C67, 2, total_len)
                json_chunk = _struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
                bin_chunk = _struct.pack("<II", len(bin_buf), 0x004E4942) + bin_buf
                return header + json_chunk + bin_chunk, f"scene_{session_id[:8]}.glb", "model/gltf-binary"
                
            elif fmt == "bvh_scene":
                bvh_sc = BVHSceneExporter()
                content = bvh_sc.export_scene(scene)
                return content.encode('utf-8'), f"scene_{session_id[:8]}.bvh", "text/plain"
                
            elif fmt == "mujoco_scene":
                mj_sc = MuJoCoSceneExporter()
                content = mj_sc.export_scene(scene)
                return content.encode('utf-8'), f"scene_{session_id[:8]}_mujoco.xml", "application/xml"
                
            elif fmt == "usd_scene":
                usd_sc = USDExporter()
                content = usd_sc.export_scene(scene)
                return content.encode('utf-8'), f"scene_{session_id[:8]}.usda", "text/plain"

        else:
            # Person-only formats
            data = loader.load(session_id, session_db)
            
            if fmt == "bvh":
                exporter = BVHExporter()
                content = exporter.export(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}.bvh", "text/plain"
                
            elif fmt == "fbx":
                exporter = FBXExporter()
                content = exporter.export(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}.fbx", "text/plain"
                
            elif fmt == "gltf":
                exporter = GLTFExporter()
                gltf_dict, _ = exporter.export(data, embed_binary=True)
                return json.dumps(gltf_dict, indent=2).encode('utf-8'), f"session_{session_id[:8]}.gltf", "model/gltf+json"
                
            elif fmt == "glb":
                exporter = GLTFExporter()
                gltf_dict, bin_buf = exporter.export(data, embed_binary=False)
                gltf_dict["buffers"][0].pop("uri", None)
                json_bytes = json.dumps(gltf_dict).encode("utf-8")
                if len(json_bytes) % 4:
                    json_bytes += b" " * (4 - len(json_bytes) % 4)
                if len(bin_buf) % 4:
                    bin_buf += b"\x00" * (4 - len(bin_buf) % 4)
                total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_buf)
                header = _struct.pack("<III", 0x46546C67, 2, total_len)
                json_chunk = _struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
                bin_chunk = _struct.pack("<II", len(bin_buf), 0x004E4942) + bin_buf
                return header + json_chunk + bin_chunk, f"session_{session_id[:8]}.glb", "model/gltf-binary"
                
            elif fmt == "mujoco":
                exporter = MuJoCoExporter()
                content = exporter.export(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}_mujoco.xml", "application/xml"
                
            elif fmt == "urdf":
                exporter = URDFExporter()
                content = exporter.export_urdf(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}.urdf", "application/xml"
                
            elif fmt == "ros2":
                exporter = URDFExporter()
                content = exporter.export_ros2_trajectory(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}_ros2.yaml", "text/yaml"
                
            elif fmt == "csv":
                exporter = URDFExporter()
                content = exporter.export_csv(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}.csv", "text/csv"
                
            elif fmt == "pinocchio":
                exporter = URDFExporter()
                content = exporter.export_pinocchio_json(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}_pinocchio.json", "application/json"
                
            elif fmt == "blender":
                exporter = URDFExporter()
                content = exporter.export_blender_script(data)
                return content.encode('utf-8'), f"session_{session_id[:8]}_blender.py", "text/x-python"
                
            elif fmt in ("json", "signverse"):
                from backend.services.export_engine import export_json
                result = export_json(session, session_db)
                return json.dumps(result, indent=2).encode('utf-8'), f"session_{session_id[:8]}.json", "application/json"
                
    except Exception as e:
        st.error(f"Failed to generate export file: {e}")
    finally:
        session_db.close()
    return None, None, None

def delete_session_files(session_id: str):
    """Delete session's visual and dataset artifacts from disk"""
    json_path = Path("datasets/skeletons") / f"{session_id}_skeleton.json"
    json_path.unlink(missing_ok=True)
    
    preview_path = Path("data/outputs") / f"annotated_{session_id}.mp4"
    preview_path.unlink(missing_ok=True)

def get_session_interactions(session_id: str):
    """Query hand-object interaction events for a session from SQLite"""
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hand_object_interactions WHERE session_id = ? ORDER BY frame_id",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_session_objects(session_id: str):
    """Query 3D object trajectories for a session from SQLite"""
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM object_trajectories WHERE session_id = ? ORDER BY frame_id, track_id",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

# ----------------- Background Live WebSocket Receiver -----------------
import threading
import queue
import asyncio
import websockets

def live_stream_thread_worker(q, stop_event):
    """Async websocket client running inside a dedicated background worker thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def listen():
        uri = "ws://127.0.0.1:8000/ws/live"
        try:
            async with websockets.connect(uri) as ws:
                q.put({"type": "status", "val": "connected"})
                async for msg in ws:
                    if stop_event.is_set():
                        break
                    q.put({"type": "msg", "val": msg})
        except Exception as e:
            q.put({"type": "status", "val": "error", "error": str(e)})
            
    try:
        loop.run_until_complete(listen())
    except Exception as e:
        q.put({"type": "status", "val": "error", "error": str(e)})
    finally:
        loop.close()

# ----------------- Sidebar Navigation -----------------

with st.sidebar:
    st.markdown("### 🧭 Main Navigation")
    current_page = st.radio(
        "Select Studio Module:",
        [
            "🤖 Capture Studio",
            "📁 Datasets Manager",
            "🌐 3D Render Studio",
            "📡 Live Stream Sync",
            "📊 Analytics Dashboard",
            "⚙️ System Diagnostics"
        ]
    )
    
    st.divider()
    st.markdown("### 🚀 Launch Platform Services")
    
    # Check if backend is online
    backend_online = False
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:8000/", timeout=1.0) as response:
            if response.status == 200:
                backend_online = True
    except:
        pass

    if backend_online:
        st.success("🟢 API Services: Active")
    else:
        st.error("🔴 API Services: Offline")
        if st.button("🚀 Launch Complete Stack"):
            import subprocess
            import sys
            try:
                # Use subprocess to launch start.bat in a separate new console window
                if sys.platform == "win32":
                    subprocess.Popen(["cmd.exe", "/c", "start.bat"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["sh", "run.sh"])
                st.info("⚡ Services triggered! Reloading...")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to launch: {e}")

    st.divider()
    st.info("🎓 **SignVerse Robotics Studio**\n- 11-DoF Humanoid Retargeting\n- Action Segmentation & HOI\n- SQLite Persistence Layer")

# ----------------- Page 1: Capture Studio -----------------

if current_page == "🤖 Capture Studio":
    st.subheader("🤖 Capture Studio")
    st.write("Acquire motion coordinate data sequences from local video files, webcams, or YouTube feeds.")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### ⚙️ Solver Configuration")
        smoothing_factor = st.slider("EMA Smoothing (Alpha)", 0.1, 1.0, 0.5, 0.05,
                                    help="Lower = smoother motion (higher latency), Higher = lower latency (raw coordinates).")
        
        st.divider()
        st.markdown("### 🔬 Perception Filters")
        enable_hands = st.checkbox("Track Hand Keypoints", value=True, help="Disable to bypass MediaPipe Hand model processing and optimize speed.")
        enable_face = st.checkbox("Track Face Mesh", value=True, help="Disable to bypass MediaPipe Face Mesh model processing and optimize speed.")
        
        st.divider()
        st.info("💡 **Webcam Notice**: Facing a window/light source and keeping a 1.5-meter distance yields highest landmark tracking accuracy.")
        
    with col1:
        st.markdown("### 📥 Source Ingest")
        input_source = st.radio(
            "Select Data Acquisition Source",
            ["📤 Video Upload", "🎥 Live Camera Feed", "📺 YouTube URL"],
            horizontal=True
        )
        
        input_mgr = InputManager()
        video_path = None
        
        if input_source == "📤 Video Upload":
            uploaded_file = st.file_uploader("Upload human movement video clip (MP4, AVI, MOV)", type=['mp4', 'avi', 'mov'])
            if uploaded_file:
                video_path = input_mgr.from_upload(uploaded_file)
                st.success(f"✅ Video file loaded: `{uploaded_file.name}`")
                
        elif input_source == "🎥 Live Camera Feed":
            cam_duration = st.slider("Recording Duration (seconds)", 3, 15, 5)
            cam_id = st.number_input("Webcam Device ID Index", min_value=0, max_value=5, value=0)
            if st.button("🎬 Record Webcam"):
                with st.spinner("Recording webcam video stream... Please move within frame."):
                    try:
                        video_path = input_mgr.from_camera(camera_id=cam_id, duration_sec=cam_duration)
                        if video_path:
                            st.success("✅ Webcam recording sequence captured successfully.")
                        else:
                            st.error("❌ Capture returned empty frames. Verify device permissions.")
                    except Exception as err:
                        st.error(f"❌ Webcam device error: {err}")
                        
        elif input_source == "📺 YouTube URL":
            yt_url = st.text_input("Enter YouTube Video Link", placeholder="https://www.youtube.com/watch?v=...")
            if yt_url and st.button("📥 Fetch YouTube Stream"):
                with st.spinner("Downloading YouTube video feed stream..."):
                    try:
                        video_path = input_mgr.from_youtube(yt_url)
                        st.success("✅ YouTube stream downloaded successfully.")
                    except Exception as err:
                        st.error(f"❌ YouTube fetch error: {err}")
                        
        # Action execution block
        if video_path:
            st.divider()
            if st.button("🚀 Execute Ingestion & Perception Engine", type="primary"):
                progress_bar = st.progress(0.0)
                st_text = st.empty()
                
                def update_progress(frame_num, total_frames, percent):
                    progress_bar.progress(percent)
                    st_text.text(f"Landmark perception extraction: {frame_num}/{total_frames} ({int(percent*100)}%)")
                    
                try:
                    # Run perception with active config flags
                    mc = MotionCapture(alpha=smoothing_factor, enable_hands=enable_hands, enable_face=enable_face)
                    with st.spinner("Processing perception stack (MediaPipe Holistic)..."):
                        result = mc.capture_from_video(video_path, progress_callback=update_progress)
                    
                    st_text.text("Ingesting kinematic calculations...")
                    
                    # Generate unique session ID and filename
                    session_id = f"session_{int(time.time())}"
                    source_map = {
                        "📤 Video Upload": "upload",
                        "🎥 Live Camera Feed": "camera",
                        "📺 YouTube URL": "youtube"
                    }
                    source_type = source_map.get(input_source, "upload")
                    orig_filename = uploaded_file.name if input_source == "📤 Video Upload" else Path(video_path).name
                    
                    frame_count = len(result['frames'])
                    duration_sec = result['joint_summary']['duration_sec']
                    
                    # Save skeleton file
                    skeleton_dir = Path("datasets/skeletons")
                    skeleton_dir.mkdir(parents=True, exist_ok=True)
                    skeleton_path = skeleton_dir / f"{session_id}_skeleton.json"
                    
                    skeleton_data = {
                        "metadata": {
                            "session_id": session_id,
                            "source": source_type,
                            "filename": orig_filename,
                            "fps": 30.0,
                            "frame_count": frame_count,
                            "duration_sec": duration_sec
                        },
                        "frames": [f.to_dict() for f in result['frames']]
                    }
                    with open(skeleton_path, "w") as f:
                        json.dump(skeleton_data, f, indent=2)
                        
                    # Save to DB
                    db.create_session(
                        session_id=session_id,
                        source=source_type,
                        filename=orig_filename,
                        fps=30.0,
                        frame_count=frame_count,
                        duration_sec=duration_sec,
                        video_path=video_path
                    )
                    
                    # Compute segments and save
                    segmenter = ActionSegmenter(fps=30.0)
                    segments = segmenter.segment_sequence([f.landmarks_33 for f in result['frames']])
                    segments_dict = [seg.to_dict() for seg in segments]
                    db.save_segments(session_id, segments_dict)
                    
                    # Estimate dominant action label
                    from collections import Counter
                    if segments_dict:
                        dominant = Counter(s['action'] for s in segments_dict).most_common(1)[0][0]
                    else:
                        dominant = "idle"
                        
                    db.label_session(session_id, dominant, f"Automatically captured from {source_type}. Hands={enable_hands}, Face={enable_face}.")
                    db.update_skeleton_path(session_id, str(skeleton_path))
                    db.update_session_status(session_id, "ready")
                    
                    # Generate overlay video preview named exactly for the session
                    st_text.text("Generating 2D overlay preview video...")
                    output_preview_path = str(Path("data/outputs") / f"annotated_{session_id}.mp4")
                    generate_annotated_preview(video_path, output_preview_path, result['frames'])
                    
                    st.balloons()
                    st.success(f"🎉 Processing complete! Session `{session_id}` has been saved to the database.")
                    
                    # Display metrics
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Frames Captured", frame_count)
                    with c2:
                        st.metric("Total Duration", f"{duration_sec:.2f}s")
                    with c3:
                        st.metric("Detected Gesture", dominant.upper())
                        
                    if Path(output_preview_path).exists() and Path(output_preview_path).stat().st_size > 0:
                        st.video(output_preview_path)
                    
                    mc.close()
                except Exception as e:
                    st.error(f"Perception pipeline failed: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# ----------------- Page 2: Datasets Manager -----------------

elif current_page == "📁 Datasets Manager":
    st.subheader("📁 Datasets Manager")
    st.write("Browse, search, label, and export kinematic dataset assets from SQLite database.")
    
    sessions = db.list_sessions(limit=100)
    
    if not sessions:
        st.info("No captured sessions found. Use the Capture Studio to ingest some motion data.")
    else:
        # Format session list for selectbox
        session_options = {s["session_id"]: f"{s['filename']} ({s['action_label'].upper()} - {s['duration_sec']:.1f}s) - {s['session_id'][:8]}" for s in sessions}
        selected_id = st.selectbox("Select Motion Session:", list(session_options.keys()), format_func=lambda x: session_options[x])
        
        # Find selected session details
        selected_session = next(s for s in sessions if s["session_id"] == selected_id)
        
        st.divider()
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📋 Session Metadata")
            
            # Metadata Cards
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Source Type</div>
                    <div class="metric-value">{selected_session['source'].upper()}</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Frames Count</div>
                    <div class="metric-value">{selected_session['frame_count']}</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Duration</div>
                    <div class="metric-value">{selected_session['duration_sec']:.2f}s</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Avg Confidence</div>
                    <div class="metric-value">{selected_session.get('avg_confidence', 0.0):.2%}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Action classification
            st.markdown("### 🏷️ Classification & Labels")
            current_label = selected_session.get("action_label", "unlabeled")
            new_label = st.selectbox("Action Label Class:", ["wave", "walk", "grab", "sit", "idle", "gesture", "unlabeled"], index=["wave", "walk", "grab", "sit", "idle", "gesture", "unlabeled"].index(current_label))
            new_notes = st.text_area("Session Notes:", value=selected_session.get("notes") or "")
            
            if st.button("💾 Update Label & Notes"):
                db.label_session(selected_id, new_label, new_notes)
                st.success("✅ Database record updated successfully.")
                st.rerun()
                
        with col2:
            st.markdown("### 📺 2D Pose Overlay Playback")
            preview_mp4 = Path("data/outputs") / f"annotated_{selected_id}.mp4"
            if preview_mp4.exists():
                st.video(str(preview_mp4))
            elif selected_session.get("video_path") and Path(selected_session.get("video_path")).exists():
                st.video(selected_session["video_path"])
                st.info("Displaying raw source video. 2D overlay preview is not generated.")
            else:
                st.warning("No video source file found on disk.")
                
        st.divider()
        
        # Action segments table
        st.markdown("### ⏱️ Action Segments Timeline")
        segments = db.get_segments(selected_id)
        if segments:
            seg_data = []
            for s in segments:
                seg_data.append({
                    "Action Detected": s["action"].upper(),
                    "Start Frame": s["start_frame"],
                    "End Frame": s["end_frame"],
                    "Confidence Score": f"{s['confidence']:.2%}",
                })
            st.table(seg_data)
        else:
            st.info("No action segments computed for this session.")
            
        st.divider()
        
        # Interactive HOI Timeline Events Log
        st.markdown("### 🤝 Human-Object Interaction (HOI) Event Log")
        interactions = get_session_interactions(selected_id)
        if interactions:
            unique_objs = list(set(i["object_class"] for i in interactions if i["object_class"]))
            st.markdown(f"""
            <div class="diag-card">
                <div class="diag-title">HOI Diagnostics Summary</div>
                <div class="diag-text">
                    • <b>Total Interaction Events:</b> {len(interactions)} frames<br>
                    • <b>Unique Object Classes Detected:</b> {", ".join(unique_objs).upper() if unique_objs else "NONE"}<br>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            hoi_data = []
            for i in interactions:
                hoi_data.append({
                    "Frame": i["frame_id"],
                    "Time (s)": f"{i['timestamp_ms']/1000.0:.2f}s",
                    "Hand": i["hand"].upper(),
                    "Object Class": i["object_class"].upper(),
                    "Interaction Type": i["interaction_type"].upper(),
                    "Distance 3D": f"{i['distance_3d']:.3f}m" if i.get('distance_3d') is not None else "N/A"
                })
            st.table(hoi_data)
        else:
            st.info("No spatial hand-object interactions logged for this session.")
            
        st.divider()
        
        # Export options
        st.markdown("### 📦 Universal Multi-Format Exporter")
        st.write("Convert and download the motion session or scene layout in any standard simulation, robot control, or 3D animation format.")
        
        export_formats = {
            "bvh": "Biovision Hierarchy Skeleton (.bvh) [Person-Only]",
            "fbx": "Autodesk FBX ASCII (.fbx) [Person-Only]",
            "gltf": "GLTF 2.0 Armature (.gltf) [Person-Only]",
            "glb": "Binary GLTF Armature (.glb) [Person-Only]",
            "mujoco": "MuJoCo XML Armature (.xml) [Person-Only]",
            "urdf": "URDF Humanoid Robot Linkage (.urdf) [Person-Only]",
            "usd": "Universal Scene Description ASCII (.usd) [Person-Only]",
            "ros2": "ROS2 JointTrajectory (.yaml) [Person-Only]",
            "csv": "Time Series Coordinate Coordinates (.csv) [Person-Only]",
            "pinocchio": "Pinocchio Joint JSON (.json) [Person-Only]",
            "blender": "Blender Keyframe Python Script (.py) [Person-Only]",
            "json": "SignVerse Legacy JSON (.json) [Person-Only]",
            "gltf_scene": "GLTF 2.0 Full Scene (.gltf) [Scene-Level]",
            "glb_scene": "Binary GLB Full Scene (.glb) [Scene-Level]",
            "bvh_scene": "BVH with Object ROOT Joints (.bvh) [Scene-Level]",
            "mujoco_scene": "MuJoCo XML Full Scene (.xml) [Scene-Level]",
            "usd_scene": "USDA Scene with Objects (.usda) [Scene-Level]"
        }
        
        col_sel_fmt, col_btn_fmt = st.columns([3, 2])
        with col_sel_fmt:
            selected_export_fmt = st.selectbox(
                "Choose Export Format Target:",
                list(export_formats.keys()),
                format_func=lambda x: export_formats[x]
            )
        with col_btn_fmt:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            bytes_content, filename, mime_type = export_session_data(selected_id, selected_export_fmt)
            if bytes_content:
                st.download_button(
                    label=f"⬇️ Download {selected_export_fmt.upper()} File",
                    data=bytes_content,
                    file_name=filename,
                    mime=mime_type,
                    use_container_width=True
                )
            else:
                st.button("⚠️ Export File Unavailable", disabled=True, use_container_width=True)
                
        st.divider()
        
        # Delete Session option
        st.markdown("### ⚠️ Danger Zone")
        if st.button("🗑️ Permanent Delete Session", type="secondary"):
            delete_session_files(selected_id)
            db.delete_session(selected_id)
            st.success(f"Session {selected_id} deleted successfully.")
            st.rerun()

# ----------------- Page 3: 3D Render Studio -----------------

elif current_page == "🌐 3D Render Studio":
    st.subheader("🌐 3D Render Studio")
    st.write("Scrub and playback extracted coordinates in an interactive WebGL canvas.")
    
    sessions = db.list_sessions(limit=100)
    
    if not sessions:
        st.info("No captured sessions found. Use the Capture Studio to ingest some motion data.")
    else:
        session_options = {s["session_id"]: f"{s['filename']} ({s['action_label'].upper()}) - {s['session_id'][:8]}" for s in sessions}
        selected_id = st.selectbox("Select Session to Render:", list(session_options.keys()), format_func=lambda x: session_options[x])
        
        selected_session = next(s for s in sessions if s["session_id"] == selected_id)
        
        # Load frame landmarks
        frames = load_session_frames(selected_session)
        
        # Fetch object trajectories
        session_objects = get_session_objects(selected_id)
        
        if not frames:
            st.warning("Frame database records are empty for this session.")
        else:
            st.divider()
            
            # Animation Timeline Slider
            frame_idx = st.slider("Timeline Playback Scrubber (Frames):", 0, len(frames)-1, 0,
                                  help="Drag slider to scrub forward/backward in the capture sequence.")
            
            selected_frame = frames[frame_idx]
            st.caption(f"Frame ID: `{selected_frame['frame_id']}` | Timestamp: `{selected_frame['timestamp']:.3f} seconds`")
            
            col_render, col_angles = st.columns([3, 2])
            
            with col_render:
                st.markdown("#### 🕺 3D Skeletal Canvas")
                
                # Render Pose
                renderer = Skeleton3DRenderer()
                plotly_fig = renderer.render_frame_3d(selected_frame)
                
                # Dynamic 3D Tracked Objects Rendering inside Plotly Scatter3d
                frame_objs = [obj for obj in session_objects if obj["frame_id"] == frame_idx]
                for obj in frame_objs:
                    ox, oy, oz = obj.get("pos_x"), obj.get("pos_y"), obj.get("pos_z")
                    if ox is not None and oy is not None and oz is not None:
                        plotly_fig.add_trace(go.Scatter3d(
                            x=[ox], y=[-oy], z=[oz],  # flip y to align with MediaPipe coordinates
                            mode='markers+text',
                            marker=dict(
                                size=9,
                                color='#FFD700',  # glowing gold for object
                                symbol='diamond',
                                line=dict(color='#FFFFFF', width=1.5)
                            ),
                            text=[f"{obj['class_name'].upper()} (#{obj['track_id']})"],
                            textposition="top center",
                            name=f"Object: {obj['class_name']}",
                            hoverinfo='text'
                        ))
                
                st.plotly_chart(plotly_fig, use_container_width=True)
                if frame_objs:
                    st.caption("✨ *Gold diamond markers indicate 3D tracked object coordinates lifted into metric camera space.*")
                
            with col_angles:
                st.markdown("#### 🤖 Robot Joint Commands")
                
                # Retrieve robot joint retargeter angles
                retargeter = RobotRetargeter()
                q_list = retargeter.retarget_to_angles([selected_frame])
                
                if q_list:
                    q = q_list[0]
                    joint_names = [
                        "neck_yaw", "l_shoulder_pitch", "l_shoulder_roll", "l_elbow_yaw", "l_elbow_roll",
                        "r_shoulder_pitch", "r_shoulder_roll", "r_elbow_yaw", "r_elbow_roll",
                        "l_knee_pitch", "r_knee_pitch"
                    ]
                    
                    # Create joints mapping table
                    table_rows = []
                    for name, rad_val in zip(joint_names, q):
                        deg_val = np.degrees(rad_val)
                        table_rows.append({
                            "Manipulator Joint": name,
                            "Angle (Radians)": f"{rad_val:.4f}",
                            "Degrees": f"{deg_val:.1f}°"
                        })
                    st.table(table_rows)
                else:
                    st.warning("Anatomical skeletal keypoints not present in frame.")
                    
                # Range of Motion (ROM) Radar Chart
                st.markdown("#### 🕸️ Biomechanical Range of Motion (ROM)")
                curr_angles = selected_frame.get("joint_angles", {})
                rom_joints = ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_hip", "right_hip", "left_knee", "right_knee"]
                
                curr_vals = []
                min_vals = []
                max_vals = []
                
                for j in rom_joints:
                    curr_vals.append(curr_angles.get(j, 180.0))
                    all_vals = [f.get("joint_angles", {}).get(j, 180.0) for f in frames]
                    min_vals.append(min(all_vals) if all_vals else 180.0)
                    max_vals.append(max(all_vals) if all_vals else 180.0)
                    
                categories = [j.replace("_", " ").title() for j in rom_joints]
                
                # Close loop
                categories.append(categories[0])
                curr_vals.append(curr_vals[0])
                min_vals.append(min_vals[0])
                max_vals.append(max_vals[0])
                
                radar_fig = go.Figure()
                radar_fig.add_trace(go.Scatterpolar(
                    r=curr_vals,
                    theta=categories,
                    fill='toself',
                    name='Current Frame',
                    line_color='#00D9FF',
                    fillcolor='rgba(0, 217, 255, 0.2)'
                ))
                radar_fig.add_trace(go.Scatterpolar(
                    r=max_vals,
                    theta=categories,
                    name='Max Extension',
                    line=dict(color='#00FF66', dash='dash'),
                ))
                radar_fig.add_trace(go.Scatterpolar(
                    r=min_vals,
                    theta=categories,
                    name='Max Flexion',
                    line=dict(color='#FF0055', dash='dot'),
                ))
                
                radar_fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 180],
                            gridcolor='rgba(255,255,255,0.1)',
                            linecolor='rgba(255,255,255,0.1)',
                        ),
                        angularaxis=dict(
                            gridcolor='rgba(255,255,255,0.1)',
                            linecolor='rgba(255,255,255,0.1)',
                        )
                    ),
                    showlegend=True,
                    template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=20, l=40, r=40),
                    height=300
                )
                st.plotly_chart(radar_fig, use_container_width=True)
                
            st.divider()
            
            # Interactive Joint Trajectory plotting
            st.markdown("### 📈 Interactive Joint Angle Trajectories Over Time")
            selected_joints = st.multiselect(
                "Select Joints to Plot Flexion (Degrees):",
                ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_hip", "right_hip", "left_knee", "right_knee"],
                default=["left_elbow", "right_elbow"],
                help="Select one or more joints to display coordinate flexions over the full temporal timeline."
            )
            
            if selected_joints:
                chart_data = {j.replace("_", " ").title(): [] for j in selected_joints}
                frame_indices = []
                
                for f in frames:
                    frame_indices.append(f["frame_id"])
                    angles = f.get("joint_angles", {})
                    for j in selected_joints:
                        chart_data[j.replace("_", " ").title()].append(angles.get(j, 180.0))
                        
                chart_df = pd.DataFrame(chart_data, index=frame_indices)
                st.line_chart(chart_df)
                st.info("Visualizes angular flexions (Straight = 180°, Bent = 0°–90°) across the complete capture timeline.")
            else:
                st.info("Please select at least one joint to display the line graph.")

            # Kinematic Velocity Profiles
            st.markdown("### 🏃 Wrists Velocity Profile")
            left_speeds = [0.0]
            right_speeds = [0.0]
            vel_indices = [0]
            
            for idx in range(1, len(frames)):
                f_prev = frames[idx-1]
                f_curr = frames[idx]
                dt = max(f_curr["timestamp"] - f_prev["timestamp"], 1e-4)
                
                p_prev = f_prev.get("landmarks_33", [])
                p_curr = f_curr.get("landmarks_33", [])
                
                if len(p_prev) >= 17 and len(p_curr) >= 17:
                    lw_p = p_prev[15]
                    lw_c = p_curr[15]
                    lw_dist = np.sqrt((lw_c["x"]-lw_p["x"])**2 + (lw_c["y"]-lw_p["y"])**2 + (lw_c["z"]-lw_p["z"])**2)
                    left_speeds.append(lw_dist / dt)
                    
                    rw_p = p_prev[16]
                    rw_c = p_curr[16]
                    rw_dist = np.sqrt((rw_c["x"]-rw_p["x"])**2 + (rw_c["y"]-rw_p["y"])**2 + (rw_c["z"]-rw_p["z"])**2)
                    right_speeds.append(rw_dist / dt)
                else:
                    left_speeds.append(0.0)
                    right_speeds.append(0.0)
                vel_indices.append(f_curr["frame_id"])
                
            vel_df = pd.DataFrame({
                "Left Wrist Speed (px/s)": left_speeds,
                "Right Wrist Speed (px/s)": right_speeds
            }, index=vel_indices)
            st.line_chart(vel_df)
            st.info("Profiles movement acceleration peaks and jerk rates to evaluate imitation learning trajectory smoothness.")

# ----------------- Page 4: Live Stream Sync -----------------

elif current_page == "📡 Live Stream Sync":
    st.subheader("📡 Live Stream Sync")
    st.write("Subscribe to the live FastAPI WebSocket stream to visualize body tracking coordinates in real-time with low-latency synchronization metrics.")
    
    col_ctrl, col_info = st.columns([1, 2])
    with col_ctrl:
        if "sync_active" not in st.session_state:
            st.session_state["sync_active"] = False
            
        if not st.session_state["sync_active"]:
            if st.button("🔌 Start Real-Time Sync", type="primary", use_container_width=True):
                st.session_state["sync_active"] = True
                st.rerun()
        else:
            if st.button("🛑 Stop Real-Time Sync", type="secondary", use_container_width=True):
                st.session_state["sync_active"] = False
                st.rerun()
                
    with col_info:
        if st.session_state["sync_active"]:
            st.success("🟢 Connection active! Streaming live perception landmarks.")
        else:
            st.info("💡 Click **Start Real-Time Sync** to open a background thread and connect to `ws://127.0.0.1:8000/ws/live`.")

    if st.session_state["sync_active"]:
        col_metrics_1, col_metrics_2, col_metrics_3 = st.columns(3)
        with col_metrics_1:
            m1 = st.empty()
            # Initial placeholder state
            m1.markdown("""
            <div class="metric-card">
                <div class="metric-title">Sync Status</div>
                <div class="metric-value" style="color: #f59e0b;">CONNECTING</div>
            </div>
            """, unsafe_allow_html=True)
        with col_metrics_2:
            m2 = st.empty()
            m2.markdown("""
            <div class="metric-card">
                <div class="metric-title">Sync speed</div>
                <div class="metric-value">-- FPS</div>
            </div>
            """, unsafe_allow_html=True)
        with col_metrics_3:
            m3 = st.empty()
            m3.markdown("""
            <div class="metric-card">
                <div class="metric-title">Avg Latency</div>
                <div class="metric-value">-- ms</div>
            </div>
            """, unsafe_allow_html=True)
            
        col_c, col_info_p = st.columns([3, 2])
        with col_c:
            st.markdown("#### 🕺 3D Skeletal Live Preview")
            canvas_placeholder = st.empty()
        with col_info_p:
            st.markdown("#### 📉 Low-Latency Telemetry Timeline")
            latency_chart_placeholder = st.empty()
            st.markdown("#### 📦 Detected Objects & HOI")
            objects_placeholder = st.empty()

        # Initialize thread and queue
        q = queue.Queue()
        stop_event = threading.Event()
        t = threading.Thread(target=live_stream_thread_worker, args=(q, stop_event))
        t.start()
        
        frame_count = 0
        start_time = time.time()
        latencies = []
        
        try:
            # Main render loop
            while st.session_state["sync_active"]:
                try:
                    item = q.get(timeout=0.01)
                    
                    if item["type"] == "status":
                        if item["val"] == "connected":
                            m1.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-title">Sync Status</div>
                                <div class="metric-value" style="color: #00FF66;">CONNECTED</div>
                            </div>
                            """, unsafe_allow_html=True)
                        elif item["val"] == "error":
                            st.session_state["sync_active"] = False
                            st.error(f"❌ Connection error: {item['error']}")
                            break
                            
                    elif item["type"] == "msg":
                        data = json.loads(item["val"])
                        
                        if data.get("type") == "frame":
                            frame_count += 1
                            elapsed = time.time() - start_time
                            fps_val = frame_count / max(elapsed, 0.1)
                            
                            frame_data = data.get("data", {})
                            mapped_frame = map_db_frame_to_visualizer(frame_data)
                            
                            proc_time = frame_data.get("processing_time_ms", 15.0)
                            latencies.append(proc_time)
                            if len(latencies) > 50:
                                latencies.pop(0)
                            avg_lat = sum(latencies) / len(latencies)
                            
                            # Update metrics
                            m2.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-title">Sync speed</div>
                                <div class="metric-value">{fps_val:.1f} FPS</div>
                            </div>
                            """, unsafe_allow_html=True)
                            m3.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-title">Avg Latency</div>
                                <div class="metric-value">{avg_lat:.1f} ms</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Render 3D Canvas
                            renderer = Skeleton3DRenderer()
                            plotly_fig = renderer.render_frame_3d(mapped_frame)
                            plotly_fig.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
                            canvas_placeholder.plotly_chart(plotly_fig, use_container_width=True)
                            
                            # Render Latency Chart
                            latency_chart_placeholder.line_chart(pd.DataFrame({"Latency (ms)": latencies}))
                            
                            # Render Objects List
                            objs = frame_data.get("objects", [])
                            if objs:
                                obj_text = "<ul>"
                                for o in objs:
                                    obj_text += f"<li><b>{o.get('class_name', 'object').upper()}</b> (Track #{o.get('track_id', 0)}, Conf: {o.get('confidence', 0.0):.2%})</li>"
                                obj_text += "</ul>"
                                objects_placeholder.markdown(obj_text, unsafe_allow_html=True)
                            else:
                                objects_placeholder.info("No objects detected in the current camera view.")
                                
                except queue.Empty:
                    pass
                
                # Yield CPU
                time.sleep(0.01)
                
        except Exception as err:
            st.error(f"Render loop error: {err}")
        finally:
            stop_event.set()
            t.join(timeout=1.0)

# ----------------- Page 5: Analytics Dashboard -----------------

elif current_page == "📊 Analytics Dashboard":
    st.subheader("📊 Analytics Dashboard")
    st.write("Aggregated analytics and metrics derived from the database sessions.")
    
    # Retrieve all sessions for dynamic query filters
    sessions = db.list_sessions(limit=500)
    
    if not sessions:
        st.info("No captured sessions found. Ingest motion sequence files first.")
    else:
        # Interactive Query filters
        st.markdown("### 🔍 Search Query Filters")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_sources = ["ALL"] + list(set(s["source"] for s in sessions if s.get("source")))
            selected_source = st.selectbox("Filter Ingestion Source:", all_sources)
        with col_f2:
            all_labels = ["ALL"] + list(set(s["action_label"] for s in sessions if s.get("action_label")))
            selected_label = st.selectbox("Filter Action Class:", all_labels)
            
        # Apply filters in memory
        filtered_sessions = sessions
        if selected_source != "ALL":
            filtered_sessions = [s for s in filtered_sessions if s.get("source") == selected_source]
        if selected_label != "ALL":
            filtered_sessions = [s for s in filtered_sessions if s.get("action_label") == selected_label]
            
        st.divider()
        
        if not filtered_sessions:
            st.warning("No sessions match the selected search query filters.")
        else:
            # Dynamic stats recalculation
            total_s = len(filtered_sessions)
            total_f = sum(s["frame_count"] for s in filtered_sessions)
            total_d = sum(s["duration_sec"] for s in filtered_sessions)
            labeled_s = sum(1 for s in filtered_sessions if s.get("action_label") != "unlabeled")
            
            # Display aggregate stats cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Filtered Sessions</div>
                    <div class="metric-value">{total_s}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Captured Frames</div>
                    <div class="metric-value">{total_f}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Total Duration</div>
                    <div class="metric-value">{total_d:.1f}s</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Labeled Runs</div>
                    <div class="metric-value">{labeled_s}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.divider()
            
            g1, g2 = st.columns(2)
            
            # 1. Action Labels distribution
            with g1:
                st.markdown("#### 🏷️ Action Label Distribution")
                from collections import Counter
                label_dist = Counter(s["action_label"] for s in filtered_sessions)
                
                labels = list(label_dist.keys())
                counts = list(label_dist.values())
                
                fig = go.Figure(data=[go.Pie(
                    labels=[l.upper() for l in labels], 
                    values=counts, 
                    hole=.3,
                    marker=dict(colors=['#00D9FF', '#FF0055', '#00FF66', '#FFB300', '#990033'])
                )])
                fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)
                
            # 2. Data source distribution
            with g2:
                st.markdown("#### 📥 Ingestion Source Distribution")
                source_dist = Counter(s["source"] for s in filtered_sessions)
                sources = list(source_dist.keys())
                src_counts = list(source_dist.values())
                
                fig_bar = go.Figure(data=[go.Bar(
                    x=[s.upper() for s in sources],
                    y=src_counts,
                    marker_color='#FF0055'
                )])
                fig_bar.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_bar, use_container_width=True)
                
            # 3. Frames timeline chart
            st.divider()
            st.markdown("#### ⏳ Session Durations & Frame Counts")
            s_names = [s["filename"] for s in filtered_sessions]
            s_frames = [s["frame_count"] for s in filtered_sessions]
            
            dur_df = pd.DataFrame({
                "Frame Count": s_frames
            }, index=s_names)
            
            st.bar_chart(dur_df)

            # 4. HOI Grouped Bar Chart
            st.divider()
            st.markdown("### 🤖 Hand-Object Interaction (HOI) Distribution")
            
            session_ids = [s["id"] for s in filtered_sessions]
            placeholders = ",".join("?" for _ in session_ids)
            
            with db._conn() as conn:
                hoi_rows = conn.execute(
                    f"SELECT object_class, interaction_type, COUNT(*) as count "
                    f"FROM hand_object_interactions "
                    f"WHERE session_id IN ({placeholders}) "
                    f"GROUP BY object_class, interaction_type",
                    session_ids
                ).fetchall()
                
            if not hoi_rows:
                st.info("No Hand-Object interactions logged for the filtered sessions.")
            else:
                hoi_data = [dict(r) for r in hoi_rows]
                hoi_df = pd.DataFrame(hoi_data)
                
                fig_hoi = go.Figure()
                types = list(set(r["interaction_type"] for r in hoi_data))
                colors_dict = {"HOLDING": "#00D9FF", "GRASPING": "#FF0055", "NEAR": "#00FF66", "TOUCHING": "#FFB300"}
                
                for t in types:
                    subset = hoi_df[hoi_df["interaction_type"] == t]
                    fig_hoi.add_trace(go.Bar(
                        name=t.upper(),
                        x=subset["object_class"],
                        y=subset["count"],
                        marker_color=colors_dict.get(t, "#990033")
                    ))
                fig_hoi.update_layout(
                    barmode='group',
                    template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=20, l=20, r=20)
                )
                st.plotly_chart(fig_hoi, use_container_width=True)

            # 5. Object Trajectory Speeds
            st.markdown("### 💫 Object Average Speeds")
            with db._conn() as conn:
                traj_rows = conn.execute(
                    f"SELECT class_name, AVG(vel_x*vel_x + vel_y*vel_y + vel_z*vel_z) as speed_sq "
                    f"FROM object_trajectories "
                    f"WHERE session_id IN ({placeholders}) "
                    f"GROUP BY class_name",
                    session_ids
                ).fetchall()
                
            if not traj_rows:
                st.info("No object trajectory velocities logged for the filtered sessions.")
            else:
                speeds = []
                classes = []
                for r in traj_rows:
                    classes.append(r["class_name"].upper())
                    speeds.append(math.sqrt(r["speed_sq"]) if r["speed_sq"] > 0 else 0.0)
                    
                fig_speed = go.Figure(data=[go.Bar(
                    x=classes,
                    y=speeds,
                    marker_color='#00FF66'
                )])
                fig_speed.update_layout(
                    yaxis_title="Average Velocity Magnitude (m/s)",
                    template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=20, l=20, r=20)
                )
                st.plotly_chart(fig_speed, use_container_width=True)

            # 6. Biomechanical Joint Velocity Inspector
            st.divider()
            st.markdown("### 🔬 Session-Level Biomechanical Trajectory Inspector")
            session_options = {s["name"]: s["id"] for s in filtered_sessions}
            selected_session_name = st.selectbox("Select Session to Inspect:", list(session_options.keys()))
            
            if selected_session_name:
                sel_session_id = session_options[selected_session_name]
                
                with db._conn() as conn:
                    frame_rows = conn.execute(
                        "SELECT frame_idx, kinematics_json FROM motion_frames WHERE session_id = ? ORDER BY frame_idx",
                        (sel_session_id,)
                    ).fetchall()
                    
                if not frame_rows:
                    st.info("No frames found for the selected session.")
                else:
                    times = []
                    right_arm_speeds = []
                    left_arm_speeds = []
                    
                    prev_right = None
                    prev_left = None
                    
                    for row in frame_rows:
                        idx = row["frame_idx"]
                        try:
                            kin = json.loads(row["kinematics_json"])
                            euler = kin.get("euler_deg", {})
                            r_joint = euler.get("RightArm", euler.get("RightForeArm", [0, 0, 0]))
                            l_joint = euler.get("LeftArm", euler.get("LeftForeArm", [0, 0, 0]))
                            
                            if prev_right is not None:
                                dr = math.sqrt(sum((r_joint[i] - prev_right[i])**2 for i in range(3)))
                                dl = math.sqrt(sum((l_joint[i] - prev_left[i])**2 for i in range(3)))
                                
                                right_arm_speeds.append(dr)
                                left_arm_speeds.append(dl)
                                times.append(idx)
                                
                            prev_right = r_joint
                            prev_left = l_joint
                        except Exception:
                            pass
                    
                    if times:
                        st.markdown(f"#### 🏃 Joint Rotation Speed over Time ({selected_session_name})")
                        chart_df = pd.DataFrame({
                            "Right Arm Speed (deg/frame)": right_arm_speeds,
                            "Left Arm Speed (deg/frame)": left_arm_speeds
                        }, index=times)
                        st.line_chart(chart_df)
                    else:
                        st.info("Euler rotation angles not found in kinematics data.")


# ----------------- Page 5: System Diagnostics -----------------

elif current_page == "⚙️ System Diagnostics":
    st.subheader("⚙️ System Diagnostics & Profiling")
    st.write("Real-time telemetry and resource usage tracking of the Python runtime environment.")
    
    # Trigger GC button
    if st.button("🗑️ Trigger Force Garbage Collection (gc.collect)"):
        before = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        collected = gc.collect()
        after = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        freed = max(0.0, before - after)
        st.success(f"✅ Garbage Collector finished. Collected {collected} memory references. Freed {freed:.2f} MB of RAM.")
        
    st.divider()
    
    # System load snapshots
    snap = MemorySnapshot.capture("dashboard")
    
    # Initialize rolling telemetry history in session state
    if "telemetry_history" not in st.session_state:
        st.session_state["telemetry_history"] = []
        
    # Append current snapshot
    st.session_state["telemetry_history"].append({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "RAM Usage (MB)": snap.rss_mb,
        "CPU Load (%)": snap.cpu_percent
    })
    
    # Rolling window cap
    if len(st.session_state["telemetry_history"]) > 20:
        st.session_state["telemetry_history"].pop(0)
        
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 💻 Process Allocation Telemetry")
        st.table({
            "Resource Metric": [
                "Resident Set Size (RSS)",
                "Virtual Memory Size (VMS)",
                "Active Threads Count",
                "CPU Utilization",
                "System Available Memory",
                "Python Objects Tracked"
            ],
            "Current State": [
                f"{snap.rss_mb:.1f} MB",
                f"{snap.vms_mb:.1f} MB",
                f"{snap.thread_count}",
                f"{snap.cpu_percent:.2f}%",
                f"{snap.available_mb:.1f} MB",
                f"{snap.py_objects}"
            ]
        })
        
    with col2:
        st.markdown("### 📝 System Health Recommendations")
        
        # Diagnostic recommendations checklist
        if snap.rss_mb > 4096:
            st.markdown("""
            <div class="diag-card error">
                <div class="diag-title">CRITICAL: Peak memory allocation exceeds 4 GB</div>
                <div class="diag-text">Suggestion: Set worker threshold parameters or use lighter perception models to decrease Python runtime heap.</div>
            </div>
            """, unsafe_allow_html=True)
        elif snap.rss_mb > 2048:
            st.markdown("""
            <div class="diag-card warning">
                <div class="diag-title">WARNING: RAM usage is elevated (> 2 GB)</div>
                <div class="diag-text">Suggestion: Trigger Garbage Collection or release loaded video captures when not in active timeline rendering.</div>
            </div>
            """, unsafe_allow_html=True)
            
        if snap.thread_count > 50:
            st.markdown("""
            <div class="diag-card warning">
                <div class="diag-title">WARNING: High thread count detected</div>
                <div class="diag-text">Suggestion: Check if background camera acquisition loops or video writer pipelines are terminating cleanly.</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("""
        <div class="diag-card">
            <div class="diag-title">INFO: Database Connection</div>
            <div class="diag-text">Active connection state: Scoped Local Session local SQLite signverse.db is connected.</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="diag-card">
            <div class="diag-title">INFO: Perception Backend</div>
            <div class="diag-text">MediaPipe Solutions Holistic CPU processing is active with model_complexity index 1.</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.divider()
    
    # Telemetry history timeline chart
    st.markdown("### 📈 Live Resource Telemetry History")
    telemetry_df = pd.DataFrame(st.session_state["telemetry_history"])
    st.line_chart(telemetry_df.set_index("timestamp"))
    st.caption("💡 *Updates in real-time as you navigate pages, execute perception tracking, or trigger garbage collection.*")

    # API & WebSocket Telemetry
    st.divider()
    st.markdown("### 📡 API & WebSocket Operational Telemetry")
    
    from backend.services.profiling.telemetry_manager import telemetry_manager
    api_metrics = telemetry_manager.get_api_metrics()
    ws_metrics = telemetry_manager.get_ws_metrics()
    
    col_ws, col_api = st.columns([1, 2])
    
    with col_ws:
        st.markdown("#### 📺 Live WebSocket Stream Stats")
        st.json(ws_metrics)
        
    with col_api:
        st.markdown("#### ⚡ API Response Performance")
        if not api_metrics:
            st.info("No API routes have been measured yet in this session.")
        else:
            api_df = pd.DataFrame(api_metrics)
            # Reorder columns for optimal readability
            columns_order = ["method", "path", "count", "mean_latency_ms", "max_latency_ms", "error_rate_percent"]
            available_cols = [c for c in columns_order if c in api_df.columns]
            st.dataframe(api_df[available_cols], use_container_width=True)
            
    # Resilience & Circuit Breakers
    st.divider()
    st.markdown("### 🛡️ System Resilience & Fault Tolerance (Circuit Breakers)")
    from backend.resilience.circuit_breaker import BREAKER_REGISTRY
    
    if not BREAKER_REGISTRY:
        st.info("No circuit breakers are registered in the active session.")
    else:
        breaker_data = []
        for name, breaker in BREAKER_REGISTRY.items():
            state_data = breaker.get_state()
            breaker_data.append({
                "Breaker Name": state_data["name"],
                "Current State": state_data["state"],
                "Failure Count": state_data["failure_count"],
                "Success Count": state_data["success_count"],
                "Last State Change": datetime.fromtimestamp(breaker.last_state_change).strftime("%Y-%m-%d %H:%M:%S") if breaker.last_state_change else "N/A"
            })
        st.dataframe(pd.DataFrame(breaker_data), use_container_width=True)

