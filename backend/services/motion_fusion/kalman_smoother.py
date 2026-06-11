import numpy as np
from typing import Dict
from backend.services.perception.holistic_extractor import PerceptionResult, Landmark


class JointKalmanFilter:
    """Per-joint 3D Kalman filter (position + velocity)."""
    
    def __init__(self, dt: float = 1/30, process_noise: float = 0.01, measurement_noise: float = 0.1):
        # State: [x, y, z, vx, vy, vz]
        self.x = np.zeros(6)
        
        # Covariance
        self.P = np.eye(6) * 0.1
        
        # State transition (constant velocity model)
        self.F = np.eye(6)
        self.F[0, 3] = dt
        self.F[1, 4] = dt
        self.F[2, 5] = dt
        
        # Measurement matrix (we observe position only)
        self.H = np.zeros((3, 6))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
        self.H[2, 2] = 1
        
        # Process noise
        self.Q = np.eye(6) * process_noise
        
        # Measurement noise
        self.R = np.eye(3) * measurement_noise
        
        self.initialized = False
    
    def predict(self) -> np.ndarray:
        """Predict next state. Returns [x, y, z] estimate."""
        if not self.initialized:
            return np.zeros(3)
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x[:3]
    
    def update(self, measurement: np.ndarray, confidence: float = 1.0) -> np.ndarray:
        """Update with new measurement. Returns smoothed [x, y, z]."""
        if not self.initialized:
            self.x[:3] = measurement
            self.initialized = True
            return measurement
        
        # Adjust measurement noise based on confidence
        # Low confidence → trust prediction more
        R_adjusted = self.R / max(confidence, 0.1)
        
        # Predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        # Innovation
        y = measurement - self.H @ self.x
        
        # Kalman gain
        S = self.H @ self.P @ self.H.T + R_adjusted
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P
        
        return self.x[:3]


class TemporalSmoother:
    """Manages Kalman filters for all landmarks (553 total)."""
    
    def __init__(self):
        self.filters: Dict[tuple, JointKalmanFilter] = {}
    
    def _get_key(self, group: str, idx: int) -> tuple:
        return (group, idx)
    
    def smooth(self, result: PerceptionResult) -> PerceptionResult:
        """Apply temporal smoothing to all landmarks in result."""
        
        groups = {
            'pose': result.pose,
            'left_hand': result.left_hand,
            'right_hand': result.right_hand,
            'face': result.face,
        }
        
        for group_name, landmarks in groups.items():
            for i, lm in enumerate(landmarks):
                key = self._get_key(group_name, i)
                
                if key not in self.filters:
                    self.filters[key] = JointKalmanFilter()
                
                filt = self.filters[key]
                meas = np.array([lm.x, lm.y, lm.z])
                smoothed = filt.update(meas, lm.v)
                
                # Update landmark in place
                lm.x = float(smoothed[0])
                lm.y = float(smoothed[1])
                lm.z = float(smoothed[2])
        
        return result
    
    def reset(self):
        """Clear all filters (call on new session)."""
        self.filters.clear()
