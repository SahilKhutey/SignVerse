import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Any

class BVHExporter:
    """Exports frame sequences to Biovision Hierarchy (BVH) files for Blender integration"""
    
    # Define rigid BVH skeletal offsets (approximate humanoid proportions in cm)
    HIERARCHY = {
        'Hips': {
            'offset': [0.0, 95.0, 0.0],
            'channels': 6,
            'children': ['Spine', 'LeftUpLeg', 'RightUpLeg']
        },
        'Spine': {
            'offset': [0.0, 15.0, 0.0],
            'channels': 3,
            'children': ['Spine1']
        },
        'Spine1': {
            'offset': [0.0, 15.0, 0.0],
            'channels': 3,
            'children': ['Neck', 'LeftShoulder', 'RightShoulder']
        },
        'Neck': {
            'offset': [0.0, 10.0, 0.0],
            'channels': 3,
            'children': ['Head']
        },
        'Head': {
            'offset': [0.0, 10.0, 0.0],
            'channels': 3,
            'children': []  # Leaf node (automatic End Site generated)
        },
        'LeftShoulder': {
            'offset': [15.0, 5.0, 0.0],
            'channels': 3,
            'children': ['LeftArm']
        },
        'LeftArm': {
            'offset': [25.0, 0.0, 0.0],
            'channels': 3,
            'children': ['LeftForeArm']
        },
        'LeftForeArm': {
            'offset': [25.0, 0.0, 0.0],
            'channels': 3,
            'children': ['LeftHand']
        },
        'LeftHand': {
            'offset': [10.0, 0.0, 0.0],
            'channels': 3,
            'children': []
        },
        'RightShoulder': {
            'offset': [-15.0, 5.0, 0.0],
            'channels': 3,
            'children': ['RightArm']
        },
        'RightArm': {
            'offset': [-25.0, 0.0, 0.0],
            'channels': 3,
            'children': ['RightForeArm']
        },
        'RightForeArm': {
            'offset': [-25.0, 0.0, 0.0],
            'channels': 3,
            'children': ['RightHand']
        },
        'RightHand': {
            'offset': [-10.0, 0.0, 0.0],
            'channels': 3,
            'children': []
        },
        'LeftUpLeg': {
            'offset': [12.0, -10.0, 0.0],
            'channels': 3,
            'children': ['LeftLeg']
        },
        'LeftLeg': {
            'offset': [0.0, -40.0, 0.0],
            'channels': 3,
            'children': ['LeftFoot']
        },
        'LeftFoot': {
            'offset': [0.0, -10.0, 0.0],
            'channels': 3,
            'children': []
        },
        'RightUpLeg': {
            'offset': [-12.0, -10.0, 0.0],
            'channels': 3,
            'children': ['RightLeg']
        },
        'RightLeg': {
            'offset': [0.0, -40.0, 0.0],
            'channels': 3,
            'children': ['RightFoot']
        },
        'RightFoot': {
            'offset': [0.0, -10.0, 0.0],
            'channels': 3,
            'children': []
        }
    }

    def generate(self, frames: List[Dict[str, Any]], output_path: str, fps: int = 30):
        """Generates the full BVH file content"""
        # Save output directory
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            # Write Hierarchy
            f.write("HIERARCHY\n")
            self._write_hierarchy(f, 'Hips', 0)
            
            # Write Motion header
            f.write("MOTION\n")
            f.write(f"Frames: {len(frames)}\n")
            f.write(f"Frame Time: {1.0/fps:.6f}\n")
            
            # Write Frame Motion lines
            for frame in frames:
                rotations = self._extract_frame_channels(frame)
                f.write(" ".join(f"{val:.4f}" for val in rotations) + "\n")

    def _write_hierarchy(self, f, joint: str, depth: int):
        """Recursively formats the joint offsets, channels, and child relationships"""
        indent = "  " * depth
        info = self.HIERARCHY[joint]
        
        if joint == 'Hips':
            f.write(f"{indent}ROOT {joint}\n")
        else:
            f.write(f"{indent}JOINT {joint}\n")
            
        f.write(f"{indent}{{\n")
        f.write(f"{indent}  OFFSET " + " ".join(f"{v:.2f}" for v in info['offset']) + "\n")
        
        if info['channels'] == 6:
            f.write(f"{indent}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n")
        else:
            f.write(f"{indent}  CHANNELS 3 Zrotation Xrotation Yrotation\n")
            
        if info['children']:
            for child in info['children']:
                self._write_hierarchy(f, child, depth + 1)
        else:
            # Leaf node requires End Site offset definition
            f.write(f"{indent}  End Site\n")
            f.write(f"{indent}  {{\n")
            # Set a small offset extension for end sites (e.g. head tip, hands tip, feet tip)
            end_offset = [0.0, 5.0, 0.0]
            if "Leg" in joint or "Foot" in joint:
                end_offset = [0.0, -5.0, 0.0]
            f.write(f"{indent}    OFFSET " + " ".join(f"{v:.2f}" for v in end_offset) + "\n")
            f.write(f"{indent}  }}\n")
            
        f.write(f"{indent}}}\n")

    def _extract_frame_channels(self, frame: Dict[str, Any]) -> List[float]:
        """Collects the channel values (position & rotations) in pre-order traversal order"""
        channel_data = []
        angles = frame.get('joint_angles', {})
        landmarks = frame.get('landmarks_33', [])
        
        # Traverse joint list in identical pre-order sequence
        ordered_joints = [
            'Hips', 'Spine', 'Spine1', 'Neck', 'Head', 
            'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
            'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
            'LeftUpLeg', 'LeftLeg', 'LeftFoot',
            'RightUpLeg', 'RightLeg', 'RightFoot'
        ]
        
        for joint in ordered_joints:
            info = self.HIERARCHY[joint]
            if info['channels'] == 6:
                # Root Hip Position (scaled to cm) + Rotations
                px, py, pz = 0.0, 95.0, 0.0
                if len(landmarks) >= 24:
                    # Estimate hip center from left hip (23) and right hip (24)
                    px = (landmarks[23]['x'] + landmarks[24]['x']) / 2.0 * 100.0
                    py = (1.0 - (landmarks[23]['y'] + landmarks[24]['y']) / 2.0) * 100.0
                    pz = (landmarks[23]['z'] + landmarks[24]['z']) / 2.0 * 100.0
                    
                channel_data.extend([px, py, pz, 0.0, 0.0, 0.0]) # Root translation + rotation (ZXY)
            else:
                # Map physical calculated angles to rotational channels (Degrees)
                # Map angles to Zrot/Xrot/Yrot
                z_rot, x_rot, y_rot = 0.0, 0.0, 0.0
                
                if joint == 'LeftArm':
                    z_rot = angles.get('left_shoulder', 0.0) - 90.0
                elif joint == 'LeftForeArm':
                    # Elbow flexion
                    z_rot = -(180.0 - angles.get('left_elbow', 180.0))
                elif joint == 'RightArm':
                    z_rot = -(angles.get('right_shoulder', 0.0) - 90.0)
                elif joint == 'RightForeArm':
                    z_rot = (180.0 - angles.get('right_elbow', 180.0))
                elif joint == 'LeftLeg':
                    # Knee flexion
                    x_rot = 180.0 - angles.get('left_knee', 180.0)
                elif joint == 'RightLeg':
                    x_rot = 180.0 - angles.get('right_knee', 180.0)
                elif joint == 'LeftUpLeg':
                    x_rot = -(angles.get('left_hip', 180.0) - 180.0)
                elif joint == 'RightUpLeg':
                    x_rot = -(angles.get('right_hip', 180.0) - 180.0)
                    
                channel_data.extend([z_rot, x_rot, y_rot])
                
        return channel_data


class RobotRetargeter:
    """Retargets human landmark kinematics to humanoid/robotic joint states (radians)"""
    
    # Robot Configuration Mapping (e.g. 11 joints for standard bi-pedal manipulator)
    # 0: Neck Yaw, 1: Shoulder Pitch L, 2: Shoulder Roll L, 3: Elbow Yaw L, 4: Elbow Roll L,
    # 5: Shoulder Pitch R, 6: Shoulder Roll R, 7: Elbow Yaw R, 8: Elbow Roll R,
    # 9: Knee Pitch L, 10: Knee Pitch R
    
    def retarget_to_angles(self, human_frames: List[Dict[str, Any]]) -> List[List[float]]:
        """Transforms 3D body landmark sequences into robotic joint coordinates (in radians)"""
        robot_sequences = []
        
        for frame in human_frames:
            angles = frame.get('joint_angles', {})
            landmarks = frame.get('landmarks_33', [])
            
            # Initialize default 11 joint angles
            q = [0.0] * 11
            
            if len(landmarks) >= 33:
                # 1. Left Shoulder Pitch (Flexion/Extension)
                q[1] = np.radians(angles.get('left_shoulder', 90.0) - 90.0)
                
                # 2. Left Elbow Pitch/Roll (Flexion/Extension)
                elbow_l_deg = angles.get('left_elbow', 180.0)
                q[4] = np.radians(180.0 - elbow_l_deg)  # 0 at straight, positive at bent
                
                # 3. Right Shoulder Pitch (Flexion/Extension)
                q[5] = np.radians(angles.get('right_shoulder', 90.0) - 90.0)
                
                # 4. Right Elbow Pitch/Roll (Flexion/Extension)
                elbow_r_deg = angles.get('right_elbow', 180.0)
                q[8] = np.radians(180.0 - elbow_r_deg)
                
                # 5. Knee Pitch Left
                knee_l_deg = angles.get('left_knee', 180.0)
                q[9] = np.radians(180.0 - knee_l_deg)
                
                # 6. Knee Pitch Right
                knee_r_deg = angles.get('right_knee', 180.0)
                q[10] = np.radians(180.0 - knee_r_deg)
                
                # 7. Shoulder Roll Left (estimate outward abduction using vector components)
                # Angle between torso vertical and arm direction
                if all(idx < len(landmarks) for idx in [11, 23, 13]):
                    # vector shoulder -> hip
                    v_sh_hip = np.array([landmarks[23]['x']-landmarks[11]['x'], landmarks[23]['y']-landmarks[11]['y'], landmarks[23]['z']-landmarks[11]['z']])
                    # vector shoulder -> elbow
                    v_sh_elb = np.array([landmarks[13]['x']-landmarks[11]['x'], landmarks[13]['y']-landmarks[11]['y'], landmarks[13]['z']-landmarks[11]['z']])
                    roll_l = self._vector_angle(v_sh_hip, v_sh_elb) - 10.0 # offset
                    q[2] = np.radians(np.clip(roll_l, 0.0, 90.0))
                    
                # 8. Shoulder Roll Right
                if all(idx < len(landmarks) for idx in [12, 24, 14]):
                    v_sh_hip_r = np.array([landmarks[24]['x']-landmarks[12]['x'], landmarks[24]['y']-landmarks[12]['y'], landmarks[24]['z']-landmarks[12]['z']])
                    v_sh_elb_r = np.array([landmarks[14]['x']-landmarks[12]['x'], landmarks[14]['y']-landmarks[12]['y'], landmarks[14]['z']-landmarks[12]['z']])
                    roll_r = self._vector_angle(v_sh_hip_r, v_sh_elb_r) - 10.0
                    q[6] = np.radians(np.clip(roll_r, 0.0, 90.0))

            robot_sequences.append(q)
            
        return robot_sequences
        
    def _vector_angle(self, v1: np.ndarray, v2: np.ndarray) -> float:
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 < 1e-6 or n2 < 1e-6:
            return 0.0
        dot = np.dot(v1, v2)
        return float(np.degrees(np.arccos(np.clip(dot / (n1 * n2), -1.0, 1.0))))
        
    def save_robot_dataset(self, sequences: List[List[float]], output_path: str):
        """Saves joint trajectory sequences as a JSON training dataset"""
        dataset = {
            "metadata": {
                "type": "human_to_robot_retargeting_trajectory",
                "robot_type": "standard_humanoid_11dof",
                "joint_names": [
                    "neck_yaw", "l_shoulder_pitch", "l_shoulder_roll", "l_elbow_yaw", "l_elbow_roll",
                    "r_shoulder_pitch", "r_shoulder_roll", "r_elbow_yaw", "r_elbow_roll",
                    "l_knee_pitch", "r_knee_pitch"
                ],
                "units": "radians",
                "frame_count": len(sequences)
            },
            "trajectory": [
                {
                    "frame_id": idx,
                    "timestamp": idx / 30.0,
                    "joint_angles": q
                }
                for idx, q in enumerate(sequences)
            ]
        }
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(dataset, f, indent=2)
