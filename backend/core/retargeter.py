import json
import numpy as np
from typing import List, Dict
from datetime import datetime
from .skeleton_graph import SkeletonGraph, MP
from .kinematics import Kinematics

class RobotRetargeter:
    """
    Translates tracked human skeleton motions into a clean 11-DoF joint space.
    Saves trajectories as json formatted files readable by MuJoCo, Isaac Sim, or ROS2.
    """

    HUMAN_TO_ROBOT = {
        "head": MP.NOSE,
        "torso": (MP.LEFT_SHOULDER + MP.RIGHT_SHOULDER) // 2,
        "left_shoulder_pitch": MP.LEFT_SHOULDER,
        "left_elbow": MP.LEFT_ELBOW,
        "right_shoulder_pitch": MP.RIGHT_SHOULDER,
        "right_elbow": MP.RIGHT_ELBOW,
        "left_hip_yaw": MP.LEFT_HIP,
        "left_knee": MP.LEFT_KNEE,
        "right_hip_yaw": MP.RIGHT_HIP,
        "right_knee": MP.RIGHT_KNEE,
    }

    ROBOT_JOINT_NAMES = [
        "head_yaw",
        "torso_yaw",
        "left_shoulder_pitch",
        "left_elbow",
        "right_shoulder_pitch",
        "right_elbow",
        "left_hip_yaw",
        "left_knee",
        "right_hip_yaw",
        "right_knee",
        "root_z",  # base height
    ]

    def __init__(self):
        self.graph = SkeletonGraph()
        self.kinematics = Kinematics()

    def retarget_frame(self, landmarks: List[dict]) -> List[float]:
        """Convert one frame of human landmarks to robot joint angles (radians)"""
        if len(landmarks) < 33:
            return [0.0] * len(self.ROBOT_JOINT_NAMES)

        angles = []

        # 1. Head yaw
        angles.append(self._compute_head_yaw(landmarks))

        # 2. Torso yaw
        angles.append(self._compute_torso_yaw(landmarks))

        # 3-4. Left shoulder pitch + elbow
        angles.extend(self._compute_arm_angles(landmarks, side="left"))

        # 5-6. Right shoulder pitch + elbow
        angles.extend(self._compute_arm_angles(landmarks, side="right"))

        # 7-8. Left hip + knee
        angles.extend(self._compute_leg_angles(landmarks, side="left"))

        # 9-10. Right hip + knee
        angles.extend(self._compute_leg_angles(landmarks, side="right"))

        # 11. Root Z
        angles.append(self._compute_root_z(landmarks))

        return angles

    def _compute_head_yaw(self, landmarks: List[dict]) -> float:
        nose = landmarks[MP.NOSE]
        l_sh = landmarks[MP.LEFT_SHOULDER]
        r_sh = landmarks[MP.RIGHT_SHOULDER]
        shoulder_mid_x = (l_sh["x"] + r_sh["x"]) / 2.0
        dx = nose["x"] - shoulder_mid_x
        # approximate scale based on standard neck length
        return float(np.arctan2(dx, 100.0))

    def _compute_torso_yaw(self, landmarks: List[dict]) -> float:
        l_sh = landmarks[MP.LEFT_SHOULDER]
        r_sh = landmarks[MP.RIGHT_SHOULDER]
        l_hip = landmarks[MP.LEFT_HIP]
        r_hip = landmarks[MP.RIGHT_HIP]
        
        sh_dx = r_sh["x"] - l_sh["x"]
        sh_dz = r_sh["z"] - l_sh["z"]
        
        hip_dx = r_hip["x"] - l_hip["x"]
        hip_dz = r_hip["z"] - l_hip["z"]
        
        sh_angle = np.arctan2(sh_dz, sh_dx)
        hip_angle = np.arctan2(hip_dz, hip_dx)
        return float(sh_angle - hip_angle)

    def _compute_arm_angles(self, landmarks: List[dict], side: str) -> List[float]:
        if side == "left":
            sh_idx, el_idx, wr_idx = MP.LEFT_SHOULDER, MP.LEFT_ELBOW, MP.LEFT_WRIST
        else:
            sh_idx, el_idx, wr_idx = MP.RIGHT_SHOULDER, MP.RIGHT_ELBOW, MP.RIGHT_WRIST

        sh = landmarks[sh_idx]
        el = landmarks[el_idx]
        wr = landmarks[wr_idx]

        # Shoulder pitch
        upper_dx = el["x"] - sh["x"]
        upper_dy = el["y"] - sh["y"]
        shoulder_pitch = float(np.arctan2(upper_dx, -upper_dy))

        # Elbow flexion
        v1 = np.array([sh["x"] - el["x"], sh["y"] - el["y"]])
        v2 = np.array([wr["x"] - el["x"], wr["y"] - el["y"]])
        norm_product = (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        cos_a = np.dot(v1, v2) / norm_product
        elbow = float(np.arccos(np.clip(cos_a, -1.0, 1.0)))
        # Convert so 0.0 is straight, positive is bent
        elbow = np.pi - elbow

        return [shoulder_pitch, elbow]

    def _compute_leg_angles(self, landmarks: List[dict], side: str) -> List[float]:
        if side == "left":
            hip_idx, knee_idx, ankle_idx = MP.LEFT_HIP, MP.LEFT_KNEE, MP.LEFT_ANKLE
        else:
            hip_idx, knee_idx, ankle_idx = MP.RIGHT_HIP, MP.RIGHT_KNEE, MP.RIGHT_ANKLE

        hip = landmarks[hip_idx]
        knee = landmarks[knee_idx]
        ankle = landmarks[ankle_idx]

        # Hip yaw
        upper_dx = knee["x"] - hip["x"]
        upper_dy = knee["y"] - hip["y"]
        hip_yaw = float(np.arctan2(upper_dx, -upper_dy))

        # Knee flexion
        v1 = np.array([hip["x"] - knee["x"], hip["y"] - knee["y"]])
        v2 = np.array([ankle["x"] - knee["x"], ankle["y"] - knee["y"]])
        norm_product = (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        cos_a = np.dot(v1, v2) / norm_product
        knee_angle = float(np.arccos(np.clip(cos_a, -1.0, 1.0)))
        knee_angle = np.pi - knee_angle  # 0.0 is straight

        return [hip_yaw, knee_angle]

    def _compute_root_z(self, landmarks: List[dict]) -> float:
        l_hip = landmarks[MP.LEFT_HIP]
        r_hip = landmarks[MP.RIGHT_HIP]
        avg_y = (l_hip["y"] + r_hip["y"]) / 2.0
        # Normalize relative displacement
        return float((avg_y - 200.0) / 100.0)

    def retarget_sequence(self, frames_landmarks: List[List[dict]], fps: float = 30.0) -> Dict:
        """Process full landmark sequence and compile joint positions/velocities/accelerations"""
        joint_angles = []
        velocities = []
        timestamps = []

        for i, landmarks in enumerate(frames_landmarks):
            angles = self.retarget_frame(landmarks)
            joint_angles.append(angles)
            timestamps.append(i / fps)

        # Compute velocities
        dt = 1.0 / fps
        for i, angles in enumerate(joint_angles):
            if i == 0:
                velocities.append([0.0] * len(angles))
            else:
                prev = np.array(joint_angles[i - 1])
                curr = np.array(angles)
                vel = (curr - prev) / dt
                velocities.append(vel.tolist())

        # Compute accelerations
        accelerations = []
        for i, vel in enumerate(velocities):
            if i == 0:
                accelerations.append([0.0] * len(vel))
            else:
                prev = np.array(velocities[i - 1])
                curr = np.array(vel)
                acc = (curr - prev) / dt
                accelerations.append(acc.tolist())

        return {
            "metadata": {
                "type": "human_to_robot_retarget",
                "robot_morphology": "simple_humanoid_11dof",
                "joint_names": self.ROBOT_JOINT_NAMES,
                "joint_count": len(self.ROBOT_JOINT_NAMES),
                "sequence_length": len(joint_angles),
                "fps": fps,
                "duration_sec": len(joint_angles) / fps,
                "format_version": "1.0",
                "compatible_with": ["MuJoCo", "Isaac Sim", "ROS2"],
                "created_at": datetime.utcnow().isoformat(),
            },
            "trajectory": {
                "timestamps_sec": timestamps,
                "joint_angles_rad": joint_angles,
                "velocities_rad_per_sec": velocities,
                "accelerations_rad_per_sec2": accelerations,
            },
        }

    def save_dataset(self, dataset: Dict, output_path: str) -> str:
        """Save retargeted RL dataset to JSON file"""
        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2)
        return output_path
