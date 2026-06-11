from typing import List, Dict
import numpy as np
from pathlib import Path
from .skeleton_graph import SkeletonGraph
from .kinematics import Kinematics

class BVHWriter:
    """Exports full 3D skeleton frame coordinate sequences to standard BVH animation files"""

    ROOT_CHANNELS = ["Xposition", "Yposition", "Zposition", "Zrotation", "Xrotation", "Yrotation"]
    JOINT_CHANNELS = ["Zrotation", "Xrotation", "Yrotation"]

    def __init__(self, fps: int = 30):
        self.graph = SkeletonGraph()
        self.kinematics = Kinematics()
        self.fps = fps

    def generate(self, frames_landmarks: List[List[dict]], output_path: str) -> str:
        """Write out a structured Biovision Hierarchy file for the sequence"""
        if not frames_landmarks:
            raise ValueError("Empty frames list supplied to BVH generator")

        # Create output directories
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Compute rest bone offsets from frame 0
        rest_landmarks = frames_landmarks[0]
        rest_offsets = self._compute_rest_offsets(rest_landmarks)

        with open(output_path, "w") as f:
            # 1. Write structure hierarchy
            self._write_hierarchy(f, rest_offsets)
            
            # 2. Write motion channels
            f.write("MOTION\n")
            f.write(f"Frames: {len(frames_landmarks)}\n")
            f.write(f"Frame Time: {1.0 / self.fps:.6f}\n")
            self._write_motion(f, frames_landmarks, rest_offsets)

        return output_path

    def _compute_rest_offsets(self, landmarks: List[dict]) -> Dict[str, List[float]]:
        """Compute relative offsets based on the rest frame"""
        offsets = {}
        for name, joint in self.graph.joints.items():
            if joint.parent is None:
                # Root joint offset translation
                if len(landmarks) > joint.index:
                    p = landmarks[joint.index]
                    offsets[name] = [
                        p["x"] / 100.0,
                        -p["y"] / 100.0,
                        p["z"] / 100.0,
                    ]
                else:
                    offsets[name] = [0.0, 0.0, 0.0]
            else:
                parent = self.graph.joints[joint.parent]
                if len(landmarks) > joint.index and len(landmarks) > parent.index:
                    p = landmarks[parent.index]
                    c = landmarks[joint.index]
                    offsets[name] = [
                        (c["x"] - p["x"]) / 100.0,
                        -(c["y"] - p["y"]) / 100.0,
                        (c["z"] - p["z"]) / 100.0,
                    ]
                else:
                    offsets[name] = [0.0, 0.0, 0.0]
        return offsets

    def _write_hierarchy(self, f, offsets: Dict[str, List[float]]):
        """Recursively formats the joint offset tree structures"""
        f.write("HIERARCHY\n")

        def write_joint(name: str, depth: int):
            joint = self.graph.joints[name]
            indent = "  " * depth
            offset = offsets.get(name, [0.0, 0.0, 0.0])

            if joint.parent is None:
                f.write(f"{indent}ROOT {name}\n")
            elif not joint.children:
                # Leaf joints get standard End Site block
                f.write(f"{indent}End Site\n")
                f.write(f"{indent}{{\n")
                f.write(f"{indent}  OFFSET 0.00 5.00 0.00\n")
                f.write(f"{indent}}}\n")
                return
            else:
                f.write(f"{indent}JOINT {name}\n")

            f.write(f"{indent}{{\n")
            f.write(f"{indent}  OFFSET {offset[0]:.4f} {offset[1]:.4f} {offset[2]:.4f}\n")

            if joint.parent is None:
                channels = self.ROOT_CHANNELS
            else:
                channels = self.JOINT_CHANNELS
                
            f.write(f"{indent}  CHANNELS {len(channels)} {' '.join(channels)}\n")

            for child in joint.children:
                write_joint(child, depth + 1)

            f.write(f"{indent}}}\n")

        write_joint("hips", 0)

    def _write_motion(self, f, frames_landmarks: List[List[dict]], rest_offsets: Dict[str, List[float]]):
        """Saves actual joint position offsets and Euler rotation angles for all frames"""
        ordered = self.graph.get_ordered_joints()
        channel_joints = []
        for j in ordered:
            if j.parent is None:
                channel_joints.append(("root", j.name))
            elif j.children:
                channel_joints.append(("joint", j.name))

        for landmarks in frames_landmarks:
            values = []
            for kind, name in channel_joints:
                if kind == "root":
                    joint = self.graph.joints[name]
                    if len(landmarks) > joint.index:
                        p = landmarks[joint.index]
                        values.extend([p["x"] / 100.0, -p["y"] / 100.0, p["z"] / 100.0])
                    else:
                        values.extend([0.0, 0.0, 0.0])
                    # Root rotation defaults to identity
                    values.extend([0.0, 0.0, 0.0])
                else:
                    rotation = self._compute_joint_rotation(landmarks, name)
                    values.extend(rotation)
            f.write(" ".join(f"{v:.4f}" for v in values) + "\n")

    def _compute_joint_rotation(self, landmarks: List[dict], joint_name: str) -> List[float]:
        """Calculates basic relative orientation angle transformations for the BVH joint channels"""
        joint = self.graph.joints[joint_name]
        parent = self.graph.joints[joint.parent]
        if len(landmarks) <= joint.index or len(landmarks) <= parent.index:
            return [0.0, 0.0, 0.0]

        p = landmarks[parent.index]
        c = landmarks[joint.index]
        dx = c["x"] - p["x"]
        dy = -(c["y"] - p["y"])  # flip coordinates axis upright
        dz = c["z"] - p["z"]

        length = np.sqrt(dx * dx + dy * dy + dz * dz) + 1e-8
        
        yaw = np.arctan2(dx, -dy) * 180.0 / np.pi
        pitch = np.arctan2(dz, -dy) * 180.0 / np.pi
        roll = 0.0

        return [float(yaw), float(pitch), float(roll)]
