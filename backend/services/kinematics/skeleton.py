from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np


# MediaPipe pose landmark indices
class MP:
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_FOOT = 31
    RIGHT_FOOT = 32


# Hierarchical skeleton graph
# Format: bone_name: (parent_mp_index, child_mp_index)
SKELETON_GRAPH = {
    'spine':           (23, 11),   # left_hip → left_shoulder
    'chest':           (11, 12),   # left_shoulder → right_shoulder
    'neck':            (12, 0),    # right_shoulder → nose
    'head':            (0, 0),     # nose (self-loop for tracking)
    'l_upper_arm':     (11, 13),   # shoulder → elbow
    'l_lower_arm':     (13, 15),   # elbow → wrist
    'l_hand':          (15, 19),   # wrist → index_finger_mcp
    'r_upper_arm':     (12, 14),
    'r_lower_arm':     (14, 16),
    'r_hand':          (16, 20),
    'l_thigh':         (23, 25),
    'l_shin':          (25, 27),
    'l_foot':          (27, 31),
    'r_thigh':         (24, 26),
    'r_shin':          (26, 28),
    'r_foot':          (28, 32),
}


@dataclass
class BoneVector:
    """3D vector representation of a bone."""
    name: str
    parent_pos: np.ndarray   # (3,)
    child_pos: np.ndarray    # (3,)
    direction: np.ndarray    # (3,) unit vector
    length: float


@dataclass
class Skeleton:
    """Complete skeleton state for one frame."""
    joints: Dict[str, np.ndarray]  # joint_name → (x, y, z)
    bones: Dict[str, BoneVector]
    bone_lengths: Dict[str, float]  # reference lengths (T-pose)
    root_position: np.ndarray = field(default_factory=lambda: np.zeros(3))


class SkeletonBuilder:
    """Builds Skeleton objects from MediaPipe pose landmarks."""
    
    def build(self, pose_landmarks: List, frame_id: int = 0) -> Skeleton:
        """
        Build skeleton from MediaPipe 33-point pose.
        pose_landmarks: list of 33 (x, y, z) tuples in normalized coords
        """
        # Convert to numpy
        if len(pose_landmarks) > 0 and hasattr(pose_landmarks[0], 'x'):
            # MediaPipe NormalizedLandmark objects
            joints = {
                'nose': np.array([pose_landmarks[MP.NOSE].x, pose_landmarks[MP.NOSE].y, pose_landmarks[MP.NOSE].z]),
                'l_shoulder': np.array([pose_landmarks[MP.LEFT_SHOULDER].x, pose_landmarks[MP.LEFT_SHOULDER].y, pose_landmarks[MP.LEFT_SHOULDER].z]),
                'r_shoulder': np.array([pose_landmarks[MP.RIGHT_SHOULDER].x, pose_landmarks[MP.RIGHT_SHOULDER].y, pose_landmarks[MP.RIGHT_SHOULDER].z]),
                'l_elbow': np.array([pose_landmarks[MP.LEFT_ELBOW].x, pose_landmarks[MP.LEFT_ELBOW].y, pose_landmarks[MP.LEFT_ELBOW].z]),
                'r_elbow': np.array([pose_landmarks[MP.RIGHT_ELBOW].x, pose_landmarks[MP.RIGHT_ELBOW].y, pose_landmarks[MP.RIGHT_ELBOW].z]),
                'l_wrist': np.array([pose_landmarks[MP.LEFT_WRIST].x, pose_landmarks[MP.LEFT_WRIST].y, pose_landmarks[MP.LEFT_WRIST].z]),
                'r_wrist': np.array([pose_landmarks[MP.RIGHT_WRIST].x, pose_landmarks[MP.RIGHT_WRIST].y, pose_landmarks[MP.RIGHT_WRIST].z]),
                'l_hip': np.array([pose_landmarks[MP.LEFT_HIP].x, pose_landmarks[MP.LEFT_HIP].y, pose_landmarks[MP.LEFT_HIP].z]),
                'r_hip': np.array([pose_landmarks[MP.RIGHT_HIP].x, pose_landmarks[MP.RIGHT_HIP].y, pose_landmarks[MP.RIGHT_HIP].z]),
                'l_knee': np.array([pose_landmarks[MP.LEFT_KNEE].x, pose_landmarks[MP.LEFT_KNEE].y, pose_landmarks[MP.LEFT_KNEE].z]),
                'r_knee': np.array([pose_landmarks[MP.RIGHT_KNEE].x, pose_landmarks[MP.RIGHT_KNEE].y, pose_landmarks[MP.RIGHT_KNEE].z]),
                'l_ankle': np.array([pose_landmarks[MP.LEFT_ANKLE].x, pose_landmarks[MP.LEFT_ANKLE].y, pose_landmarks[MP.LEFT_ANKLE].z]),
                'r_ankle': np.array([pose_landmarks[MP.RIGHT_ANKLE].x, pose_landmarks[MP.RIGHT_ANKLE].y, pose_landmarks[MP.RIGHT_ANKLE].z]),
                'l_foot': np.array([pose_landmarks[MP.LEFT_FOOT].x, pose_landmarks[MP.LEFT_FOOT].y, pose_landmarks[MP.LEFT_FOOT].z]),
                'r_foot': np.array([pose_landmarks[MP.RIGHT_FOOT].x, pose_landmarks[MP.RIGHT_FOOT].y, pose_landmarks[MP.RIGHT_FOOT].z]),
            }
        elif len(pose_landmarks) > 0:
            # Already dicts or tuples
            def parse_lm(idx):
                lm = pose_landmarks[idx]
                if isinstance(lm, dict):
                    return np.array([lm.get("x", 0), lm.get("y", 0), lm.get("z", 0)])
                return np.array(lm[:3])

            joints = {
                'nose': parse_lm(MP.NOSE),
                'l_shoulder': parse_lm(MP.LEFT_SHOULDER),
                'r_shoulder': parse_lm(MP.RIGHT_SHOULDER),
                'l_elbow': parse_lm(MP.LEFT_ELBOW),
                'r_elbow': parse_lm(MP.RIGHT_ELBOW),
                'l_wrist': parse_lm(MP.LEFT_WRIST),
                'r_wrist': parse_lm(MP.RIGHT_WRIST),
                'l_hip': parse_lm(MP.LEFT_HIP),
                'r_hip': parse_lm(MP.RIGHT_HIP),
                'l_knee': parse_lm(MP.LEFT_KNEE),
                'r_knee': parse_lm(MP.RIGHT_KNEE),
                'l_ankle': parse_lm(MP.LEFT_ANKLE),
                'r_ankle': parse_lm(MP.RIGHT_ANKLE),
                'l_foot': parse_lm(MP.LEFT_FOOT),
                'r_foot': parse_lm(MP.RIGHT_FOOT),
            }
        else:
            joints = {}
        
        # Compute bone vectors
        bones = {}
        for bone_name, (parent_idx, child_idx) in SKELETON_GRAPH.items():
            if parent_idx == child_idx:
                continue  # Skip self-loops
            if parent_idx >= len(pose_landmarks) or child_idx >= len(pose_landmarks):
                continue
            
            parent_pos = self._get_joint_pos(pose_landmarks, parent_idx)
            child_pos = self._get_joint_pos(pose_landmarks, child_idx)
            
            raw_vec = child_pos - parent_pos
            length = np.linalg.norm(raw_vec)
            direction = raw_vec / (length + 1e-8)
            
            bones[bone_name] = BoneVector(
                name=bone_name,
                parent_pos=parent_pos,
                child_pos=child_pos,
                direction=direction,
                length=float(length),
            )
        
        # Compute reference bone lengths
        bone_lengths = {name: b.length for name, b in bones.items()}
        
        # Root at hip center
        root = (joints.get('l_hip', np.zeros(3)) + joints.get('r_hip', np.zeros(3))) / 2
        
        return Skeleton(
            joints=joints,
            bones=bones,
            bone_lengths=bone_lengths,
            root_position=root,
        )
    
    @staticmethod
    def _get_joint_pos(landmarks, idx: int) -> np.ndarray:
        lm = landmarks[idx]
        if hasattr(lm, 'x'):
            return np.array([lm.x, lm.y, lm.z])
        if isinstance(lm, dict):
            return np.array([lm.get("x", 0), lm.get("y", 0), lm.get("z", 0)])
        return np.array(lm[:3])

# Static definition for export engine joint list
SKELETON = {
    "spine": {}, "chest": {}, "neck": {},
    "l_shoulder": {}, "l_elbow": {}, "l_wrist": {},
    "r_shoulder": {}, "r_elbow": {}, "r_wrist": {},
    "l_hip": {}, "l_knee": {}, "l_ankle": {},
    "r_hip": {}, "r_knee": {}, "r_ankle": {}
}

