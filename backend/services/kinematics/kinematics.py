import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from backend.core.skeleton_graph import SkeletonGraph, MP

@dataclass
class BoneVector:
    parent: str
    child: str
    vector: np.ndarray  # shape (3,)
    length: float

@dataclass
class JointRotation:
    joint: str
    euler_xyz: Tuple[float, float, float]  # degrees
    quaternion: Tuple[float, float, float, float]  # w, x, y, z

class Kinematics:
    """Computes skeletal bone vectors, relative joint rotation quaternions, and joint angles"""

    def __init__(self):
        self.graph = SkeletonGraph()
        self.rest_bone_lengths: Dict[Tuple[str, str], float] = {}

    def extract_bone_vector(self, landmarks: List[dict], parent_idx: int, child_idx: int) -> Optional[np.ndarray]:
        """Calculates direction vector between parent and child landmarks"""
        if parent_idx >= len(landmarks) or child_idx >= len(landmarks):
            return None
        p = landmarks[parent_idx]
        c = landmarks[child_idx]
        # Coordinates in 3D (x, y, z)
        return np.array([c["x"] - p["x"], c["y"] - p["y"], c["z"] - p["z"]])

    def extract_all_bones(self, landmarks: List[dict]) -> Dict[Tuple[str, str], np.ndarray]:
        """Extracts 3D direction vectors for all defined bones"""
        bones = {}
        for parent, child, p_idx, c_idx in self.graph.get_bones():
            v = self.extract_bone_vector(landmarks, p_idx, c_idx)
            if v is not None:
                bones[(parent, child)] = v
        return bones

    def compute_bone_lengths(self, landmarks: List[dict]) -> Dict[Tuple[str, str], float]:
        """Calculates distance lengths of bone vectors"""
        lengths = {}
        for parent, child, p_idx, c_idx in self.graph.get_bones():
            v = self.extract_bone_vector(landmarks, p_idx, c_idx)
            if v is not None:
                lengths[(parent, child)] = float(np.linalg.norm(v))
        return lengths

    @staticmethod
    def _normalize_quat(q: np.ndarray) -> np.ndarray:
        """Normalize quaternion vector to unit scale"""
        norm = np.linalg.norm(q)
        return q / (norm + 1e-8) if norm > 0 else q

    @staticmethod
    def vector_to_quaternion(v_from: np.ndarray, v_to: np.ndarray) -> np.ndarray:
        """Computes the rotation quaternion [w, x, y, z] to orient v_from to v_to"""
        v_from = v_from / (np.linalg.norm(v_from) + 1e-8)
        v_to = v_to / (np.linalg.norm(v_to) + 1e-8)
        
        cross = np.cross(v_from, v_to)
        dot = np.dot(v_from, v_to)
        
        # Guard dot-product boundary condition for parallel opposite directions
        if dot < -0.9999:
            # find orthogonal axis
            axis = np.array([1.0, 0.0, 0.0])
            if abs(v_from[0]) > 0.9:
                axis = np.array([0.0, 1.0, 0.0])
            cross = np.cross(v_from, axis)
            quat = np.array([0.0, cross[0], cross[1], cross[2]])
            return Kinematics._normalize_quat(quat)
            
        w = np.sqrt((1.0 + dot) * 2.0 + 1e-8)
        xyz = cross / (w + 1e-8)
        quat = np.array([w / 2.0, xyz[0], xyz[1], xyz[2]])
        
        return Kinematics._normalize_quat(quat)

    @staticmethod
    def quaternion_to_euler(q: np.ndarray) -> Tuple[float, float, float]:
        """Converts unit quaternion [w, x, y, z] to Tait-Bryan Euler rotations (XYZ order) in degrees"""
        w, x, y, z = q
        
        # Roll (X axis)
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)
        
        # Pitch (Y axis)
        sinp = 2.0 * (w * y - z * x)
        pitch = np.arcsin(np.clip(sinp, -1.0, 1.0))
        
        # Yaw (Z axis)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)
        
        return (float(np.degrees(roll)), float(np.degrees(pitch)), float(np.degrees(yaw)))

    def compute_joint_rotations(self, landmarks: List[dict]) -> Dict[str, JointRotation]:
        """Computes coordinate frame orientation rotation for each joint node"""
        rotations = {}
        # Reference posture vector (Y-down coordinates)
        rest_up = np.array([0.0, -1.0, 0.0])

        for name, joint in self.graph.joints.items():
            if not joint.parent:
                continue
            parent = self.graph.joints[joint.parent]
            bv = self.extract_bone_vector(landmarks, parent.index, joint.index)
            
            if bv is None or np.linalg.norm(bv) < 1e-6:
                rotations[name] = JointRotation(
                    joint=name,
                    euler_xyz=(0.0, 0.0, 0.0),
                    quaternion=(1.0, 0.0, 0.0, 0.0),
                )
                continue
                
            quat = self.vector_to_quaternion(rest_up, bv)
            euler = self.quaternion_to_euler(quat)
            rotations[name] = JointRotation(
                joint=name, euler_xyz=euler, quaternion=tuple(quat)
            )
            
        return rotations

    @staticmethod
    def compute_velocity(positions: List[Dict[str, float]], dt: float = 1 / 30) -> List[Dict[str, float]]:
        """Computes velocity displacement over dt interval"""
        velocities = []
        for i in range(len(positions)):
            if i == 0:
                velocities.append({"x": 0.0, "y": 0.0, "z": 0.0, "mag": 0.0})
            else:
                p_curr = np.array([positions[i]["x"], positions[i]["y"], positions[i]["z"]])
                p_prev = np.array([positions[i - 1]["x"], positions[i - 1]["y"], positions[i - 1]["z"]])
                v = (p_curr - p_prev) / dt
                velocities.append({
                    "x": float(v[0]), 
                    "y": float(v[1]), 
                    "z": float(v[2]), 
                    "mag": float(np.linalg.norm(v))
                })
        return velocities

    def normalize_landmarks(self, landmarks: List[dict], target_height: float = 1.8) -> List[dict]:
        """Scales skeletal coordinates to fixed target height and shifts root hips to local origin"""
        if len(landmarks) < 33:
            return landmarks

        # Measure height based on hip to nose distance
        hip_y = (landmarks[MP.LEFT_HIP]["y"] + landmarks[MP.RIGHT_HIP]["y"]) / 2.0
        head_y = landmarks[MP.NOSE]["y"]
        current_height = abs(hip_y - head_y) + 1e-6

        scale = target_height / current_height
        
        # Hip center translations
        center_x = (landmarks[MP.LEFT_HIP]["x"] + landmarks[MP.RIGHT_HIP]["x"]) / 2.0
        center_z = (landmarks[MP.LEFT_HIP]["z"] + landmarks[MP.RIGHT_HIP]["z"]) / 2.0

        normalized = []
        for lm in landmarks:
            new_lm = dict(lm)
            new_lm["x"] = (lm["x"] - center_x) * scale
            new_lm["y"] = -(lm["y"] - hip_y) * scale  # Flip vertical axis upright
            new_lm["z"] = (lm["z"] - center_z) * scale
            normalized.append(new_lm)
            
        return normalized

    def extract_motion_features(self, all_frames_landmarks: List[List[dict]]) -> dict:
        if not all_frames_landmarks:
            return {}

        ref_landmarks = all_frames_landmarks[0]
        rest_lengths = self.compute_bone_lengths(ref_landmarks)

        frame_rotations = []
        for landmarks in all_frames_landmarks:
            rots = self.compute_joint_rotations(landmarks)
            frame_rotations.append(rots)

        return {
            "rest_bone_lengths": {
                f"{p}->{c}": length for (p, c), length in rest_lengths.items()
            },
            "frame_count": len(all_frames_landmarks),
            "joint_count": len(self.graph.joints),
        }
