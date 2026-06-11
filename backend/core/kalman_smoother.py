import numpy as np
from typing import List
from .schemas import Landmark

class LandmarkKalman:
    """3D Kalman filter for tracking a single landmark coordinate (x, y, z) over time"""

    def __init__(self, process_noise: float = 0.01, measurement_noise: float = 0.1):
        # State array: [x, y, z, vx, vy, vz]
        self.state = np.zeros(6)
        self.P = np.eye(6) * 1.0  # Covariance matrix
        self.Q = np.eye(6) * process_noise  # Process noise matrix
        self.R = np.eye(3) * measurement_noise  # Measurement noise matrix
        
        # State transition matrix F
        self.F = np.eye(6)
        for i in range(3):
            self.F[i, i + 3] = 1.0  # position += velocity
            
        # Measurement matrix H
        self.H = np.zeros((3, 6))
        for i in range(3):
            self.H[i, i] = 1.0
            
        self.initialized = False

    def update(self, measurement: np.ndarray) -> np.ndarray:
        # Predict State
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q

        # If first measurement, initialize state and return measurement directly
        if not self.initialized:
            self.state[:3] = measurement
            self.initialized = True
            return measurement

        # Update State
        y = measurement - self.H @ self.state
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P
        
        return self.state[:3]


class TemporalSmoother:
    """Orchestrates temporal smoothing across full body pose, hands, and face meshes"""

    def __init__(self):
        self.filters: dict = {}  # key format: (slot_prefix, index) -> LandmarkKalman

    def smooth_frame(self, frame_dict: dict) -> dict:
        """frame_dict expects: pose_33, left_hand_21, right_hand_21, face_468"""
        slots = {
            "pose_33": "pose",
            "left_hand_21": "lh",
            "right_hand_21": "rh",
            "face_468": "face",
        }
        smoothed = {}
        for key, prefix in slots.items():
            landmarks = frame_dict.get(key, [])
            smoothed_list = []
            for i, lm in enumerate(landmarks):
                fid = (prefix, i)
                if fid not in self.filters:
                    self.filters[fid] = LandmarkKalman()
                
                # Fetch measurements
                # Check if lm is dict or object
                if isinstance(lm, dict):
                    meas = np.array([lm['x'], lm['y'], lm['z']])
                    v_val = lm.get('v', 1.0)
                else:
                    meas = np.array([lm.x, lm.y, lm.z])
                    v_val = getattr(lm, 'v', 1.0)
                    
                s = self.filters[fid].update(meas)
                smoothed_list.append(
                    Landmark(x=float(s[0]), y=float(s[1]), z=float(s[2]), v=v_val)
                )
            # Dump to dicts
            smoothed[key] = [lm.model_dump() for lm in smoothed_list]
        return smoothed

    def reset(self):
        self.filters.clear()
