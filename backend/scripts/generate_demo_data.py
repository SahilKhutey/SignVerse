"""Seed sample data for demonstration."""
import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parents[2].resolve()))

from backend.core.database import db
from backend.config import settings

def seed_demo_data():
    print("[Seed] Seeding demo session data into SignVerse database...")
    
    # Ensure dirs exist
    settings.dataset_dir.mkdir(parents=True, exist_ok=True)
    (settings.dataset_dir / "skeletons").mkdir(parents=True, exist_ok=True)
    
    # Create some dummy sessions
    sessions_to_create = [
        {
            "session_id": "demo_waving",
            "source": "upload",
            "filename": "waving_hand.mp4",
            "fps": 30.0,
            "frame_count": 90,
            "duration_sec": 3.0,
            "action_label": "wave",
            "notes": "Standard waving motion captured via video upload.",
            "status": "ready"
        },
        {
            "session_id": "demo_walking",
            "source": "camera",
            "filename": "camera_0",
            "fps": 30.0,
            "frame_count": 150,
            "duration_sec": 5.0,
            "action_label": "walk",
            "notes": "Walking exercise captured via live webcam feed.",
            "status": "ready"
        },
        {
            "session_id": "demo_grabbing",
            "source": "youtube",
            "filename": "grabbing_mug.mp4",
            "fps": 24.0,
            "frame_count": 72,
            "duration_sec": 3.0,
            "action_label": "grab",
            "notes": "YouTube tutorial video clipping retargeted.",
            "status": "ready"
        }
    ]
    
    for s in sessions_to_create:
        existing = db.get_session(s["session_id"])
        if existing:
            print(f"Session {s['session_id']} already exists, skipping.")
            continue
            
        # Insert session
        db.create_session(
            session_id=s["session_id"],
            source=s["source"],
            filename=s["filename"],
            fps=s["fps"],
            frame_count=s["frame_count"],
            duration_sec=s["duration_sec"]
        )
        db.label_session(s["session_id"], s["action_label"], s["notes"])
        db.update_session_status(s["session_id"], "ready")
        
        # Write a dummy skeleton file
        skeleton_path = settings.dataset_dir / "skeletons" / f"{s['session_id']}_skeleton.json"
        
        # Build dummy frame landmarks
        frames = []
        for f_idx in range(s["frame_count"]):
            # Simulate movement
            t = f_idx / s["fps"]
            pose = []
            for l_idx in range(33):
                # Idle/simple motion coordinates
                # Just some sine wave coordinate mappings
                offset_x = 0.5 + 0.1 * np.sin(t * 2.0 + l_idx * 0.1)
                offset_y = 0.5 + 0.05 * np.cos(t * 1.5 + l_idx * 0.05)
                # Wrist specific motion
                if l_idx in (15, 16):  # Left/Right wrists
                    offset_y -= 0.15 * np.sin(t * 4.0) if s["action_label"] == "wave" else 0.0
                    offset_x += 0.2 * np.cos(t * 2.0) if s["action_label"] == "grab" else 0.0
                pose.append({
                    "x": offset_x * 640.0,
                    "y": offset_y * 480.0,
                    "z": -0.1 * l_idx,
                    "visibility": 0.99
                })
            
            # Simulated hand joints
            hand = [{"x": 100 + idx, "y": 200, "z": 0} for idx in range(21)]
            
            frames.append({
                "frame_id": f_idx,
                "timestamp": t,
                "pose_33": pose,
                "left_hand_21": hand,
                "right_hand_21": hand,
                "face_468": [],
                "confidence": 0.95
            })
            
        skeleton_data = {
            "metadata": {
                "session_id": s["session_id"],
                "source": s["source"],
                "filename": s["filename"],
                "fps": s["fps"],
                "frame_count": s["frame_count"],
                "duration_sec": s["duration_sec"]
            },
            "frames": frames
        }
        
        with open(skeleton_path, "w") as f:
            json.dump(skeleton_data, f, indent=2)
            
        db.update_skeleton_path(s["session_id"], str(skeleton_path))
        
        # Populate motion_frames table for exporters compatibility
        with db._conn() as conn:
            for f_idx, frame in enumerate(frames):
                p_json = {
                    "pose": frame["pose_33"],
                    "left_hand": frame["left_hand_21"],
                    "right_hand": frame["right_hand_21"],
                    "face": []
                }
                k_json = {
                    "frame_idx": f_idx,
                    "timestamp_ms": (f_idx / s["fps"]) * 1000.0,
                    "euler_deg": {
                        "left_shoulder": [0.0, 0.0, 0.0],
                        "right_shoulder": [0.0, 0.0, 0.0],
                        "left_elbow": [180.0, 0.0, 0.0],
                        "right_elbow": [180.0, 0.0, 0.0],
                        "left_hip": [180.0, 0.0, 0.0],
                        "right_hip": [180.0, 0.0, 0.0],
                        "left_knee": [180.0, 0.0, 0.0],
                        "right_knee": [180.0, 0.0, 0.0]
                    },
                    "euler_rad": {},
                    "quaternions": {},
                    "velocities": {}
                }
                conn.execute(
                    """INSERT INTO motion_frames 
                       (id, session_id, frame_idx, timestamp_ms, perception_json, kinematics_json, confidence_mean)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"{s['session_id']}_frame_{f_idx}",
                        s["session_id"],
                        f_idx,
                        (f_idx / s["fps"]) * 1000.0,
                        json.dumps(p_json),
                        json.dumps(k_json),
                        0.95
                    )
                )

        # Generate and save segments
        segmenter = ActionSegmenter(fps=s["fps"])
        segments = segmenter.segment_sequence([frame["pose_33"] for frame in frames])
        segments_dict = [seg.to_dict() for seg in segments]
        db.save_segments(s["session_id"], segments_dict)
        print(f"[Seed] Seeded session {s['session_id']} with {len(segments_dict)} segments.")

if __name__ == "__main__":
    import numpy as np
    from backend.core.action_segmenter import ActionSegmenter
    seed_demo_data()
