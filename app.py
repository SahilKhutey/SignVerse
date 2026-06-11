import streamlit as st
import cv2
import json
import numpy as np
from pathlib import Path
import sys
import time
import os

# Append current directory to path
sys.path.append(str(Path(__file__).parent.resolve()))

from core.pose_extractor import PoseExtractor
from core.motion_capture import MotionCapture
from core.input_sources import InputManager
from core.renderer_3d import Skeleton3DRenderer
from core.blender_export import BVHExporter, RobotRetargeter

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
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00D9FF 0%, #FF0055 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
        letter-spacing: -0.05em;
    }
    
    .sub-header {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        color: #718096;
        text-align: center;
        margin-bottom: 2rem;
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

# ----------------- Session State Initialization -----------------
if 'motion_data' not in st.session_state:
    st.session_state['motion_data'] = None
if 'processed_video' not in st.session_state:
    st.session_state['processed_video'] = None
if 'annotated_video_path' not in st.session_state:
    st.session_state['annotated_video_path'] = None
if 'active_input_source' not in st.session_state:
    st.session_state['active_input_source'] = None

# Header Title Block
st.markdown('<h1 class="main-header">🤖 SignVerse Robotics Studio</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Universal Human-to-Robot Motion Intelligence and Kinematic Transfer Pipeline</p>', unsafe_allow_html=True)

# ----------------- Sidebar Controls -----------------
with st.sidebar:
    st.markdown("### 🎛️ Pipeline Settings")
    
    input_source = st.radio(
        "📥 Data Acquisition Source",
        ["📤 Video Upload", "🎥 Live Camera Feed", "📺 YouTube URL"]
    )
    
    st.divider()
    
    st.markdown("### ⚙️ Kinematic Solver Options")
    smoothing_factor = st.slider("EMA Smoothing (Alpha)", 0.1, 1.0, 0.5, 0.05,
                                help="Lower values yield smoother motion but add minor latency. Higher values reduce latency but preserve camera noise.")
    
    st.divider()
    st.info("🎓 **Minor Project Specification**\n- 72-Hour Rapid Deployment MVP\n- Full Body + Hand + Face Mesh tracking\n- ROS2 / Blender format exporter")

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
    
    # Output writer using H264 or MP4V
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

# ----------------- Pipeline Execution Block -----------------
input_mgr = InputManager()
video_path = None

# Input Ingestion Forms
if input_source == "📤 Video Upload":
    uploaded_file = st.file_uploader("Upload human movement video clip (MP4, AVI, MOV)", type=['mp4', 'avi', 'mov'])
    if uploaded_file:
        video_path = input_mgr.from_upload(uploaded_file)
        st.success(f"✅ Loaded file: `{uploaded_file.name}`")

elif input_source == "🎥 Live Camera Feed":
    cam_duration = st.slider("Recording Duration (seconds)", 3, 15, 5)
    cam_id = st.number_input("Webcam Device ID Index", min_value=0, max_value=5, value=0)
    if st.button("🎬 Record & Track"):
        with st.spinner("Recording webcam video stream... Please move within frame."):
            try:
                video_path = input_mgr.from_camera(camera_id=cam_id, duration_sec=cam_duration)
                if video_path:
                    st.success("✅ Webcam recording sequence captured successfully.")
                else:
                    st.error("❌ Capture returned empty frames. Verify device permissions.")
            except Exception as err:
                st.error(f"❌ Device Error: {err}")

elif input_source == "📺 YouTube URL":
    yt_url = st.text_input("Enter YouTube Video Link", placeholder="https://www.youtube.com/watch?v=...")
    if yt_url and st.button("📥 Fetch & Extract"):
        with st.spinner("Downloading video feed stream..."):
            try:
                video_path = input_mgr.from_youtube(yt_url)
                st.success("✅ YouTube stream downloaded.")
            except Exception as err:
                st.error(f"❌ YouTube fetch error: {err}")

# Motion Capturing Processing Action
if video_path:
    # Reset session if source changes
    if st.session_state['active_input_source'] != video_path:
        st.session_state['motion_data'] = None
        st.session_state['processed_video'] = None
        st.session_state['annotated_video_path'] = None
        st.session_state['active_input_source'] = video_path
        
    if st.button("🚀 Execute Ingestion & Perception Engine", type="primary"):
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        def update_progress(frame_num, total_frames, percent):
            progress_bar.progress(percent)
            status_text.text(f"Extracting landmarks from frame {frame_num}/{total_frames} ({int(percent*100)}%)...")
            
        try:
            # Initialize Pipeline
            mc = MotionCapture(alpha=smoothing_factor)
            
            with st.spinner("Running Perception Stack (MediaPipe Pose + Hands + Face Mesh)..."):
                result = mc.capture_from_video(video_path, progress_callback=update_progress)
                st.session_state['motion_data'] = result
                st.session_state['processed_video'] = video_path
                
            status_text.text("Generating 2D Skeleton overlay video...")
            with st.spinner("Drawing kinematic connections on source frames..."):
                output_preview_filename = f"annotated_{int(time.time())}.mp4"
                output_preview_path = str(Path("data/outputs") / output_preview_filename)
                
                generate_annotated_preview(
                    video_path, 
                    output_preview_path, 
                    result['frames']
                )
                
                # Check file size & existence
                if Path(output_preview_path).exists() and Path(output_preview_path).stat().st_size > 0:
                    st.session_state['annotated_video_path'] = output_preview_path
                    st.success("🎉 Pipeline tracking complete!")
                else:
                    st.warning("⚠️ 2D overlay preview generation skipped or failed. Visualizer dashboard active.")
                    st.session_state['annotated_video_path'] = None
            
            # Clean up
            mc.close()
            
        except Exception as e:
            st.error(f"Pipeline execution failed: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

# ----------------- Visualizer Studio Tabs -----------------
st.divider()

if st.session_state['motion_data'] is not None:
    data = st.session_state['motion_data']
    
    # Header Statistics Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Captured Frames</div>
            <div class="metric-value">{data['frame_count']}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Duration</div>
            <div class="metric-value">{data['joint_summary']['duration_sec']:.2f}s</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Motion Intensity</div>
            <div class="metric-value" style="color: {'#FF0055' if data['joint_summary']['motion_intensity'] == 'high' else '#00FF66'}">
                {data['joint_summary']['motion_intensity'].upper()}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Skeletal Keypoints</div>
            <div class="metric-value">569 pts</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.divider()
    
    # Tab Layouts
    tab_playback, tab_3d, tab_retarget, tab_export = st.tabs([
        "🎬 2D Pose Playback", 
        "🌐 3D Render Studio", 
        "🤖 Robot Joint retargeting", 
        "📦 Export Assets"
    ])
    
    with tab_playback:
        st.subheader("2D Skeleton Tracking Overlay")
        if st.session_state['annotated_video_path'] and Path(st.session_state['annotated_video_path']).exists():
            st.video(st.session_state['annotated_video_path'])
            st.info("Direct frame overlay utilizing custom MediaPipe Canvas painting. Ideal for validating coordinate alignment.")
        else:
            st.info("Preview video generation requires a valid output encoder. You can interact with the 3D Render Studio directly below.")
            
    with tab_3d:
        st.subheader("Interactive 3D Skeleton Visualizer")
        if data['frames']:
            # Render Controls
            renderer = Skeleton3DRenderer()
            
            # Setup Animation Slider
            frame_selection = st.slider("Select Timeline Frame", 0, len(data['frames'])-1, 0,
                                        help="Drag to step through captured skeleton coordinates.")
            
            # Frame info
            selected_frame = data['frames'][frame_selection]
            st.caption(f"Frame ID: `{selected_frame.frame_id}` | Time: `{selected_frame.timestamp:.3f} seconds`")
            
            # Draw
            plotly_fig = renderer.render_frame_3d(selected_frame.to_dict())
            st.plotly_chart(plotly_fig, use_container_width=True)
            
    with tab_retarget:
        st.subheader("Human-to-Robot Kinematic Mapping")
        retargeter = RobotRetargeter()
        
        # Calculate joint sequence
        dict_frames = [f.to_dict() for f in data['frames']]
        robot_traj = retargeter.retarget_to_angles(dict_frames)
        
        # Display joint details
        st.markdown("### Human Joint Angles (Degrees) vs Humanoid Robot Output (Radians)")
        
        # Render a sample table of joint states
        joints_metadata = retargeter.retarget_to_angles([dict_frames[0]])[0] if robot_traj else []
        joint_names = [
            "neck_yaw", "l_shoulder_pitch", "l_shoulder_roll", "l_elbow_yaw", "l_elbow_roll",
            "r_shoulder_pitch", "r_shoulder_roll", "r_elbow_yaw", "r_elbow_roll",
            "l_knee_pitch", "r_knee_pitch"
        ]
        
        col_table, col_graph = st.columns([1, 1])
        
        with col_table:
            st.markdown("**First Frame Joint Mapping States**")
            table_rows = []
            for j_name, rad_val in zip(joint_names, joints_metadata):
                deg_val = np.degrees(rad_val)
                table_rows.append({"Joint Joint": j_name, "Robot Command (Rad)": f"{rad_val:.4f}", "Equivalent (Deg)": f"{deg_val:.1f}°"})
            st.table(table_rows)
            
        with col_graph:
            st.markdown("**Physical Elbow Joint Angles Over Time**")
            # Draw simple line charts of elbow flexions
            left_elbow_angles = [f.get('joint_angles', {}).get('left_elbow', 180.0) for f in dict_frames]
            right_elbow_angles = [f.get('joint_angles', {}).get('right_elbow', 180.0) for f in dict_frames]
            
            chart_data = {
                "Left Elbow": left_elbow_angles,
                "Right Elbow": right_elbow_angles
            }
            st.line_chart(chart_data)
            
    with tab_export:
        st.subheader("Export Kinematic Assets")
        st.markdown("Retrieve the processed skeleton parameters for 3D simulation or Robot policy training.")
        
        c_bvh, c_robot, c_json = st.columns(3)
        
        dict_frames = [f.to_dict() for f in data['frames']]
        
        with c_bvh:
            st.markdown("#### 🎮 3D Animation Asset")
            st.write("Blender-compatible Biovision Hierarchy skeleton file.")
            bvh_file = Path("data/outputs/motion_export.bvh")
            exporter = BVHExporter()
            exporter.generate(dict_frames, str(bvh_file))
            
            with open(bvh_file, 'rb') as f:
                st.download_button(
                    "⬇️ Download BVH",
                    data=f,
                    file_name="signverse_motion.bvh",
                    mime="text/plain",
                    use_container_width=True
                )
                
        with c_robot:
            st.markdown("#### 🤖 Robot Trajectory Dataset")
            st.write("JSON formatted angular trajectory (11 DoF Humanoid) in Radians.")
            robot_file = Path("data/outputs/robot_dataset.json")
            retargeter = RobotRetargeter()
            robot_traj = retargeter.retarget_to_angles(dict_frames)
            retargeter.save_robot_dataset(robot_traj, str(robot_file))
            
            with open(robot_file, 'rb') as f:
                st.download_button(
                    "⬇️ Download Robot Dataset",
                    data=f,
                    file_name="robot_dataset.json",
                    mime="application/json",
                    use_container_width=True
                )
                
        with c_json:
            st.markdown("#### 📊 Raw Landmark Sequence")
            st.write("Standardized coordinates for all 569 extracted coordinates.")
            raw_json_file = Path("data/outputs/landmarks_raw.json")
            
            raw_data = {
                "summary": data['joint_summary'],
                "frame_count": len(dict_frames),
                "landmarks": dict_frames
            }
            with open(raw_json_file, 'w') as f:
                json.dump(raw_data, f, indent=2)
                
            with open(raw_json_file, 'rb') as f:
                st.download_button(
                    "⬇️ Download Raw Landmarks",
                    data=f,
                    file_name="raw_landmarks.json",
                    mime="application/json",
                    use_container_width=True
                )

else:
    st.info("👋 Upload a video, record using your camera, or supply a YouTube link in the sidebar and click 'Execute Ingestion & Perception Engine' to begin.")
