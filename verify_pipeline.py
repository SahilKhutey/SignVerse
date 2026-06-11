import cv2
import numpy as np
import json
from pathlib import Path
import os
import sys

# Append root to path
sys.path.append(str(Path(__file__).parent.resolve()))

def create_mock_video(filepath: str, num_frames: int = 30, w: int = 640, h: int = 480):
    """Generates a synthetic video with moving blocks to simulate frames for CV testing"""
    print(f"Generating synthetic test video: {filepath}...")
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filepath, fourcc, 30, (w, h))
    
    for idx in range(num_frames):
        # Create a black frame
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        
        # Draw a moving human-like shape (circles for head, torso, limbs) to trick MediaPipe
        # Draw head
        cv2.circle(frame, (w // 2, h // 4 + int(np.sin(idx * 0.2) * 20)), 40, (255, 255, 255), -1)
        # Draw torso line
        cv2.line(frame, (w // 2, h // 4 + 40), (w // 2, h // 2), (255, 255, 255), 5)
        # Draw left arm waving
        arm_wave = int(np.sin(idx * 0.4) * 50)
        cv2.line(frame, (w // 2, h // 3), (w // 2 - 80, h // 3 + arm_wave), (255, 255, 255), 4)
        # Draw right arm
        cv2.line(frame, (w // 2, h // 3), (w // 2 + 80, h // 3 + 20), (255, 255, 255), 4)
        # Draw legs
        cv2.line(frame, (w // 2, h // 2), (w // 2 - 40, h // 2 + 100), (255, 255, 255), 5)
        cv2.line(frame, (w // 2, h // 2), (w // 2 + 40, h // 2 + 100), (255, 255, 255), 5)
        
        out.write(frame)
        
    out.release()
    print("Mock video created successfully.")

def run_verification():
    """Runs the entire pipeline from end-to-end to verify correctness"""
    print("--- Starting SignVerse Robotics Verification ---\n")
    
    # 1. Paths
    mock_video = "data/uploads/mock_test_video.mp4"
    bvh_output = "data/outputs/verify_motion.bvh"
    robot_output = "data/outputs/verify_robot_dataset.json"
    raw_output = "data/outputs/verify_landmarks_raw.json"
    
    # 2. Generate Mock Video
    create_mock_video(mock_video)
    
    # 3. Import modules (inside try to catch import errors)
    try:
        from core.motion_capture import MotionCapture
        from core.blender_export import BVHExporter, RobotRetargeter
        print("[OK] Core pipeline modules imported successfully.")
    except Exception as err:
        print(f"[FAIL] Failed to import core modules: {err}")
        return False
        
    # 4. Process Video through Perception & Kinematics
    print("\nProcessing video through Perception and Motion Capture...")
    mc = None
    try:
        mc = MotionCapture(alpha=0.5)
        results = mc.capture_from_video(mock_video)
        print("[OK] Motion capture completed.")
        print(f"  Frame count processed: {results['frame_count']}")
        print(f"  Captured duration: {results['joint_summary']['duration_sec']:.2f}s")
        print(f"  Detected intensity: {results['joint_summary']['motion_intensity']}")
    except Exception as err:
        print(f"[FAIL] Error during motion capture processing: {err}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if mc:
            mc.close()
            
    # 5. Export BVH
    print("\nTesting BVH Export...")
    try:
        exporter = BVHExporter()
        dict_frames = [f.to_dict() for f in results['frames']]
        exporter.generate(dict_frames, bvh_output)
        
        # Verify file exists and is not empty
        if Path(bvh_output).exists() and Path(bvh_output).stat().st_size > 0:
            print(f"[OK] BVH exported successfully to: {bvh_output} ({Path(bvh_output).stat().st_size} bytes)")
        else:
            print("[FAIL] BVH export failed (file empty or missing).")
            return False
    except Exception as err:
        print(f"[FAIL] Error during BVH export: {err}")
        return False
        
    # 6. Export Robot Dataset
    print("\nTesting Robot Retargeting Export...")
    try:
        retargeter = RobotRetargeter()
        robot_traj = retargeter.retarget_to_angles(dict_frames)
        retargeter.save_robot_dataset(robot_traj, robot_output)
        
        if Path(robot_output).exists() and Path(robot_output).stat().st_size > 0:
            print(f"[OK] Robot Dataset exported successfully to: {robot_output} ({Path(robot_output).stat().st_size} bytes)")
        else:
            print("[FAIL] Robot Dataset export failed (file empty or missing).")
            return False
    except Exception as err:
        print(f"[FAIL] Error during Robot Dataset export: {err}")
        return False
        
    # 7. Export Raw landmarks JSON
    print("\nTesting Raw Landmarks JSON Export...")
    try:
        raw_data = {
            "summary": results['joint_summary'],
            "frame_count": len(dict_frames),
            "landmarks": dict_frames
        }
        with open(raw_output, 'w') as f:
            json.dump(raw_data, f, indent=2)
            
        if Path(raw_output).exists() and Path(raw_output).stat().st_size > 0:
            print(f"[OK] Raw Landmarks exported successfully to: {raw_output} ({Path(raw_output).stat().st_size} bytes)")
        else:
            print("[FAIL] Raw Landmarks export failed.")
            return False
    except Exception as err:
        print(f"[FAIL] Error during Raw Landmarks export: {err}")
        return False
        
    print("\n[SUCCESS] --- ALL PIPELINE STACKS VERIFIED SUCCESSFULLY ---")
    return True

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
