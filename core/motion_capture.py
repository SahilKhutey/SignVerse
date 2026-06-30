import numpy as np
from typing import List, Dict, Tuple, Optional
from core.pose_extractor import PoseFrame, PoseExtractor

class MotionSmoother:
    """Adaptive Exponential Moving Average (EMA) smoothing for stable landmarks"""
    
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        # Separate state tracking for body, hands, and face
        self.prev_pose = None
        self.prev_left_hand = None
        self.prev_right_hand = None
        self.prev_face = None
        
    def smooth_landmarks(self, current: List[Dict[str, float]], prev_state: Optional[List[Dict[str, float]]]) -> Tuple[List[Dict[str, float]], List[Dict[str, float]]]:
        """Apply EMA filter: S_t = alpha * Y_t + (1 - alpha) * S_{t-1}"""
        if not current:
            return [], None
            
        if prev_state is None or len(current) != len(prev_state):
            # No history or size mismatch, initialize filter state
            return current, current
            
        smoothed = []
        for c, p in zip(current, prev_state):
            sx = self.alpha * c['x'] + (1 - self.alpha) * p['x']
            sy = self.alpha * c['y'] + (1 - self.alpha) * p['y']
            sz = self.alpha * c['z'] + (1 - self.alpha) * p['z']
            
            # Keep additional fields (like visibility/confidence) if present
            s_node = {**c, 'x': sx, 'y': sy, 'z': sz}
            smoothed.append(s_node)
            
        return smoothed, smoothed

    def process_frame(self, frame: PoseFrame) -> PoseFrame:
        """Smooth all landmarks on a frame"""
        frame.landmarks_33, self.prev_pose = self.smooth_landmarks(frame.landmarks_33, self.prev_pose)
        frame.left_hand_21, self.prev_left_hand = self.smooth_landmarks(frame.left_hand_21, self.prev_left_hand)
        frame.right_hand_21, self.prev_right_hand = self.smooth_landmarks(frame.right_hand_21, self.prev_right_hand)
        frame.face_mesh, self.prev_face = self.smooth_landmarks(frame.face_mesh, self.prev_face)
        return frame


class JointCalculator:
    """Calculates anatomical joint angles from 3D skeleton coordinates"""
    
    # MediaPipe pose indices representation
    # Format: JointName: (ParentIndex, CenterIndex, ChildIndex)
    POSE_PAIRS = {
        'left_shoulder': (23, 11, 13),   # Hip - Shoulder - Elbow
        'right_shoulder': (24, 12, 14),
        'left_elbow': (11, 13, 15),      # Shoulder - Elbow - Wrist
        'right_elbow': (12, 14, 16),
        'left_hip': (11, 23, 25),        # Shoulder - Hip - Knee
        'right_hip': (12, 24, 26),
        'left_knee': (23, 25, 27),       # Hip - Knee - Ankle
        'right_knee': (24, 26, 28)
    }
    
    @staticmethod
    def calculate_angle(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float]) -> float:
        """Calculate the 3D angle (in degrees) at point B between vectors BA and BC"""
        # Vector BA
        ba = np.array([a['x'] - b['x'], a['y'] - b['y'], a['z'] - b['z']])
        # Vector BC
        bc = np.array([c['x'] - b['x'], c['y'] - b['y'], c['z'] - b['z']])
        
        # Norms
        norm_ba = np.linalg.norm(ba)
        norm_bc = np.linalg.norm(bc)
        
        if norm_ba < 1e-6 or norm_bc < 1e-6:
            return 0.0
            
        # Cosine rule dot product
        cos_angle = np.dot(ba, bc) / (norm_ba * norm_bc)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        return float(np.degrees(np.arccos(cos_angle)))
    
    def extract_joint_angles(self, pose_landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """Compute all configured joint angles for the frame"""
        angles = {}
        if len(pose_landmarks) < 33:
            return angles
            
        for joint_name, (a, b, c) in self.POSE_PAIRS.items():
            angles[joint_name] = self.calculate_angle(
                pose_landmarks[a], pose_landmarks[b], pose_landmarks[c]
            )
        return angles


class MotionCapture:
    """Coordinates the entire computer vision and kinematics tracking pipeline"""
    
    def __init__(self, alpha: float = 0.5, enable_hands: bool = True, enable_face: bool = True):
        self.extractor = PoseExtractor(enable_hands=enable_hands, enable_face=enable_face)
        self.smoother = MotionSmoother(alpha=alpha)
        self.joint_calc = JointCalculator()
        
    def capture_from_video(self, video_path: str, progress_callback=None) -> Dict:
        """Runs the video through perception, temporal smoothing, and joint extraction"""
        # 1. Extraction
        raw_frames = self.extractor.process_video(video_path, progress_callback=progress_callback)
        
        # 2. Smoothing and Kinematics
        processed_frames = []
        for frame in raw_frames:
            # Smooth in-place
            smoothed_frame = self.smoother.process_frame(frame)
            # Calculate angles
            smoothed_frame.joint_angles = self.joint_calc.extract_joint_angles(smoothed_frame.landmarks_33)
            processed_frames.append(smoothed_frame)
            
        # 3. Analyze Summary
        summary = self._summarize_motion(processed_frames)
        
        return {
            "video_path": video_path,
            "frame_count": len(processed_frames),
            "frames": processed_frames,
            "joint_summary": summary
        }
        
    def _summarize_motion(self, frames: List[PoseFrame]) -> Dict:
        """Generates statistical metrics for physical movement tracking"""
        if not frames:
            return {
                "duration_sec": 0.0,
                "total_displacement": 0.0,
                "motion_intensity": "low"
            }
            
        duration = len(frames) / 30.0  # fallback estimation
        if len(frames) > 1:
            duration = frames[-1].timestamp - frames[0].timestamp
            
        # Sum coordinate changes across key joints (shoulders/hips/elbows/knees)
        joints_to_track = [11, 12, 13, 14, 23, 24, 25, 26]
        total_disp = 0.0
        
        for idx in range(1, len(frames)):
            prev_lms = frames[idx-1].landmarks_33
            curr_lms = frames[idx].landmarks_33
            
            if len(prev_lms) >= 33 and len(curr_lms) >= 33:
                for j in joints_to_track:
                    p = prev_lms[j]
                    c = curr_lms[j]
                    total_disp += np.sqrt((c['x'] - p['x'])**2 + (c['y'] - p['y'])**2 + (c['z'] - p['z'])**2)
                    
        intensity = "low"
        if duration > 0:
            rate = total_disp / duration
            if rate > 2.0:
                intensity = "high"
            elif rate > 0.5:
                intensity = "medium"
                
        return {
            "duration_sec": float(duration),
            "total_displacement": float(total_disp),
            "motion_intensity": intensity
        }

    def close(self):
        self.extractor.close()
