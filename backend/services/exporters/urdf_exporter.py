"""
URDF (Unified Robot Description Format) exporter.
Generates:
  1. signverse_humanoid.urdf   — robot description for ROS/Gazebo
  2. trajectory.yaml           — ROS2 JointTrajectory-compatible YAML
  3. trajectory.csv            — flat CSV for MATLAB / Pandas / Excel
  4. pinocchio_model.json      — Pinocchio / TSID compatible JSON
"""
import csv
import io
import json
from .data_loader import UnifiedMotionData, CANONICAL_JOINTS


# Joint map: canonical → URDF link/joint names
_JOINT_MAP = {
    "Hips":          "hips_joint",
    "Spine":         "spine_joint",
    "Chest":         "chest_joint",
    "Neck":          "neck_joint",
    "Head":          "head_joint",
    "LeftShoulder":  "left_shoulder_joint",
    "LeftArm":       "left_elbow_joint",
    "LeftForeArm":   "left_wrist_joint",
    "LeftHand":      "left_hand_joint",
    "RightShoulder": "right_shoulder_joint",
    "RightArm":      "right_elbow_joint",
    "RightForeArm":  "right_wrist_joint",
    "RightHand":     "right_hand_joint",
    "LeftUpLeg":     "left_hip_joint",
    "LeftLeg":       "left_knee_joint",
    "LeftFoot":      "left_ankle_joint",
    "RightUpLeg":    "right_hip_joint",
    "RightLeg":      "right_knee_joint",
    "RightFoot":     "right_ankle_joint",
}

# Joints that are revolute (all except the floating hips root)
_REVOLUTE_JOINTS = {k: v for k, v in _JOINT_MAP.items() if k != "Hips"}


class URDFExporter:
    """Exports motion as URDF + multiple trajectory formats."""

    # ------------------------------------------------------------------ #
    # URDF robot description
    # ------------------------------------------------------------------ #
    def export_urdf(self, data: UnifiedMotionData) -> str:
        """Generate URDF file for the signverse humanoid."""
        return f'''<?xml version="1.0"?>
<robot name="signverse_humanoid">

  <!-- ─── Materials ─────────────────────────────────────────────────── -->
  <material name="dark_metal">
    <color rgba="0.2 0.2 0.25 1.0"/>
  </material>
  <material name="accent">
    <color rgba="0.0 0.85 1.0 1.0"/>
  </material>

  <!-- ─── Base link ─────────────────────────────────────────────────── -->
  <link name="base_link">
    <visual><geometry><box size="0.05 0.05 0.05"/></geometry><material name="dark_metal"/></visual>
    <collision><geometry><box size="0.05 0.05 0.05"/></geometry></collision>
    <inertial>
      <mass value="0.5"/>
      <inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/>
    </inertial>
  </link>

  <!-- ─── Root floating joint ──────────────────────────────────────── -->
  <joint name="hips_joint" type="floating">
    <parent link="base_link"/>
    <child link="hips"/>
    <origin xyz="0 0 1.0" rpy="0 0 0"/>
  </joint>

  <!-- ─── Torso chain ───────────────────────────────────────────────── -->
  {self._urdf_link("hips", mass=8.0, size="0.30 0.20 0.15", material="dark_metal")}
  {self._urdf_revolute("spine_joint", "hips", "spine", axis="0 0 1", lower="-1.57", upper="1.57", effort=100, xyz="0 0 0.15")}
  {self._urdf_link("spine", mass=3.0, size="0.20 0.15 0.10", material="dark_metal")}
  {self._urdf_revolute("chest_joint", "spine", "chest", axis="1 0 0", lower="-0.5", upper="0.5", effort=50, xyz="0 0 0.12")}
  {self._urdf_link("chest", mass=4.0, size="0.35 0.20 0.15", material="dark_metal")}
  {self._urdf_revolute("neck_joint", "chest", "neck", axis="0 0 1", lower="-1.57", upper="1.57", effort=20, xyz="0 0 0.12")}
  {self._urdf_link("neck", mass=0.5, size="0.08 0.08 0.08", material="dark_metal")}
  {self._urdf_revolute("head_joint", "neck", "head", axis="0 0 1", lower="-1.57", upper="1.57", effort=10, xyz="0 0 0.06")}
  {self._urdf_link("head", mass=1.5, size="0.18 0.18 0.22", material="dark_metal")}

  <!-- ─── Left arm ──────────────────────────────────────────────────── -->
  {self._urdf_revolute("left_shoulder_joint", "chest", "left_upper_arm", axis="0 1 0", lower="-3.14", upper="3.14", effort=50, xyz="-0.18 0 0.08")}
  {self._urdf_capsule_link("left_upper_arm", mass=1.5, length=0.30, radius=0.04)}
  {self._urdf_revolute("left_elbow_joint", "left_upper_arm", "left_forearm", axis="0 0 1", lower="-2.5", upper="0", effort=30, xyz="-0.30 0 0")}
  {self._urdf_capsule_link("left_forearm", mass=1.0, length=0.28, radius=0.03)}
  {self._urdf_revolute("left_wrist_joint", "left_forearm", "left_wrist_link", axis="0 1 0", lower="-1.57", upper="1.57", effort=10, xyz="-0.28 0 0")}
  {self._urdf_link("left_wrist_link", mass=0.3, size="0.06 0.04 0.02", material="accent")}
  {self._urdf_revolute("left_hand_joint", "left_wrist_link", "left_hand_link", axis="0 0 1", lower="-0.5", upper="0.5", effort=5, xyz="-0.04 0 0")}
  {self._urdf_link("left_hand_link", mass=0.3, size="0.08 0.06 0.02", material="accent")}

  <!-- ─── Right arm ─────────────────────────────────────────────────── -->
  {self._urdf_revolute("right_shoulder_joint", "chest", "right_upper_arm", axis="0 1 0", lower="-3.14", upper="3.14", effort=50, xyz="0.18 0 0.08")}
  {self._urdf_capsule_link("right_upper_arm", mass=1.5, length=0.30, radius=0.04)}
  {self._urdf_revolute("right_elbow_joint", "right_upper_arm", "right_forearm", axis="0 0 1", lower="0", upper="2.5", effort=30, xyz="0.30 0 0")}
  {self._urdf_capsule_link("right_forearm", mass=1.0, length=0.28, radius=0.03)}
  {self._urdf_revolute("right_wrist_joint", "right_forearm", "right_wrist_link", axis="0 1 0", lower="-1.57", upper="1.57", effort=10, xyz="0.28 0 0")}
  {self._urdf_link("right_wrist_link", mass=0.3, size="0.06 0.04 0.02", material="accent")}
  {self._urdf_revolute("right_hand_joint", "right_wrist_link", "right_hand_link", axis="0 0 1", lower="-0.5", upper="0.5", effort=5, xyz="0.04 0 0")}
  {self._urdf_link("right_hand_link", mass=0.3, size="0.08 0.06 0.02", material="accent")}

  <!-- ─── Left leg ──────────────────────────────────────────────────── -->
  {self._urdf_revolute("left_hip_joint", "hips", "left_thigh", axis="1 0 0", lower="-2.0", upper="1.0", effort=100, xyz="-0.10 0 -0.075")}
  {self._urdf_capsule_link("left_thigh", mass=3.0, length=0.42, radius=0.06)}
  {self._urdf_revolute("left_knee_joint", "left_thigh", "left_shin", axis="1 0 0", lower="0", upper="2.5", effort=80, xyz="0 0 -0.42")}
  {self._urdf_capsule_link("left_shin", mass=2.0, length=0.38, radius=0.05)}
  {self._urdf_revolute("left_ankle_joint", "left_shin", "left_foot_link", axis="1 0 0", lower="-0.78", upper="0.78", effort=40, xyz="0 0 -0.38")}
  {self._urdf_link("left_foot_link", mass=0.8, size="0.18 0.08 0.05", material="dark_metal")}
  {self._urdf_revolute("left_ankle_lateral_joint", "left_foot_link", "left_toe_link", axis="0 1 0", lower="-0.3", upper="0.3", effort=10, xyz="0.08 0 -0.02")}
  {self._urdf_link("left_toe_link", mass=0.2, size="0.08 0.06 0.03", material="dark_metal")}

  <!-- ─── Right leg ─────────────────────────────────────────────────── -->
  {self._urdf_revolute("right_hip_joint", "hips", "right_thigh", axis="1 0 0", lower="-2.0", upper="1.0", effort=100, xyz="0.10 0 -0.075")}
  {self._urdf_capsule_link("right_thigh", mass=3.0, length=0.42, radius=0.06)}
  {self._urdf_revolute("right_knee_joint", "right_thigh", "right_shin", axis="1 0 0", lower="0", upper="2.5", effort=80, xyz="0 0 -0.42")}
  {self._urdf_capsule_link("right_shin", mass=2.0, length=0.38, radius=0.05)}
  {self._urdf_revolute("right_ankle_joint", "right_shin", "right_foot_link", axis="1 0 0", lower="-0.78", upper="0.78", effort=40, xyz="0 0 -0.38")}
  {self._urdf_link("right_foot_link", mass=0.8, size="0.18 0.08 0.05", material="dark_metal")}
  {self._urdf_revolute("right_ankle_lateral_joint", "right_foot_link", "right_toe_link", axis="0 1 0", lower="-0.3", upper="0.3", effort=10, xyz="0.08 0 -0.02")}
  {self._urdf_link("right_toe_link", mass=0.2, size="0.08 0.06 0.03", material="dark_metal")}

</robot>
'''

    def _urdf_link(self, name, mass, size, material="dark_metal"):
        return f'''<link name="{name}">
    <inertial>
      <mass value="{mass}"/>
      <inertia ixx="{mass*0.01:.4f}" ixy="0" ixz="0" iyy="{mass*0.01:.4f}" iyz="0" izz="{mass*0.01:.4f}"/>
    </inertial>
    <visual><geometry><box size="{size}"/></geometry><material name="{material}"/></visual>
    <collision><geometry><box size="{size}"/></geometry></collision>
  </link>'''

    def _urdf_capsule_link(self, name, mass, length, radius):
        return f'''<link name="{name}">
    <inertial>
      <mass value="{mass}"/>
      <inertia ixx="{mass*0.01:.4f}" ixy="0" ixz="0" iyy="{mass*0.01:.4f}" iyz="0" izz="{mass*0.01:.4f}"/>
    </inertial>
    <visual><geometry><cylinder length="{length}" radius="{radius}"/></geometry></visual>
    <collision><geometry><cylinder length="{length}" radius="{radius}"/></geometry></collision>
  </link>'''

    def _urdf_revolute(self, joint_name, parent, child, axis, lower, upper, effort, xyz="0 0 0"):
        return f'''<joint name="{joint_name}" type="revolute">
    <parent link="{parent}"/>
    <child link="{child}"/>
    <origin xyz="{xyz}" rpy="0 0 0"/>
    <axis xyz="{axis}"/>
    <limit lower="{lower}" upper="{upper}" effort="{effort}" velocity="3.0"/>
    <dynamics damping="0.5" friction="0.1"/>
  </joint>'''

    # ------------------------------------------------------------------ #
    # ROS2 JointTrajectory YAML
    # ------------------------------------------------------------------ #
    def export_ros2_trajectory(self, data: UnifiedMotionData) -> str:
        """Generate ROS2 JointTrajectory-compatible YAML."""
        active_joints = {k: v for k, v in _REVOLUTE_JOINTS.items()}

        lines = [
            "# SignVerse → ROS2 JointTrajectory",
            "# Format: trajectory_msgs/JointTrajectory",
            f"# Session: {data.session_name}",
            f"# Source:  {data.source_type}",
            f"# Action:  {data.action_label}",
            f"# Frames:  {data.num_frames}",
            f"# FPS:     {data.fps}",
            f"# Duration: {data.duration_s:.3f}s",
            "",
            "joint_trajectory:",
            "  header:",
            "    stamp: {sec: 0, nanosec: 0}",
            "    frame_id: base_link",
            "  joint_names:",
        ]

        joint_order = list(active_joints.keys())
        for jn in joint_order:
            lines.append(f"    - {active_joints[jn]}")

        lines.append("  points:")

        for frame_idx in range(data.num_frames):
            t = data.timestamps_ms[frame_idx] / 1000.0
            sec = int(t)
            nsec = int((t - sec) * 1e9)

            positions = []
            velocities = []
            for jn in joint_order:
                pos = data.joint_angles_rad[frame_idx].get(jn, [0.0, 0.0, 0.0])
                positions.append(round(pos[0], 6))
                velocities.append(0.0)  # velocity not tracked per-joint yet

            pos_str = ", ".join(str(p) for p in positions)
            vel_str = ", ".join(str(v) for v in velocities)

            lines.append(f"  - time_from_start: {{sec: {sec}, nanosec: {nsec}}}")
            lines.append(f"    positions: [{pos_str}]")
            lines.append(f"    velocities: [{vel_str}]")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # CSV Time Series
    # ------------------------------------------------------------------ #
    def export_csv(self, data: UnifiedMotionData) -> str:
        """Export motion as flat CSV time series for Pandas/MATLAB/Excel."""
        output = io.StringIO()
        joint_order = list(CANONICAL_JOINTS)

        # Build header
        header = ["frame_idx", "timestamp_ms", "action", "intent"]
        for jn in joint_order:
            header += [
                f"{jn}_rad_x", f"{jn}_rad_y", f"{jn}_rad_z",
                f"{jn}_deg_x", f"{jn}_deg_y", f"{jn}_deg_z",
                f"{jn}_qw", f"{jn}_qx", f"{jn}_qy", f"{jn}_qz",
                f"{jn}_pos_x", f"{jn}_pos_y", f"{jn}_pos_z",
            ]

        writer = csv.writer(output)
        writer.writerow(header)

        for frame_idx in range(data.num_frames):
            row = [
                frame_idx,
                round(data.timestamps_ms[frame_idx], 3),
                data.actions_per_frame[frame_idx] if frame_idx < len(data.actions_per_frame) else "",
                data.intents_per_frame[frame_idx] if frame_idx < len(data.intents_per_frame) else "",
            ]
            for jn in joint_order:
                rad = data.joint_angles_rad[frame_idx].get(jn, [0.0, 0.0, 0.0])
                deg = data.joint_angles_deg[frame_idx].get(jn, [0.0, 0.0, 0.0])
                quat = data.joint_angles_quat[frame_idx].get(jn, [1.0, 0.0, 0.0, 0.0])
                pos = data.joint_positions_3d[frame_idx].get(jn, [0.0, 0.0, 0.0])
                row += [
                    round(rad[0], 6), round(rad[1], 6), round(rad[2], 6),
                    round(deg[0], 4), round(deg[1], 4), round(deg[2], 4),
                    round(quat[0], 6), round(quat[1], 6), round(quat[2], 6), round(quat[3], 6),
                    round(pos[0], 6), round(pos[1], 6), round(pos[2], 6),
                ]
            writer.writerow(row)

        return output.getvalue()

    # ------------------------------------------------------------------ #
    # Pinocchio JSON
    # ------------------------------------------------------------------ #
    def export_pinocchio(self, data: UnifiedMotionData) -> dict:
        """Export motion as Pinocchio/TSID compatible JSON structure."""
        joint_order = list(_REVOLUTE_JOINTS.keys())

        frames = []
        for frame_idx in range(data.num_frames):
            t = data.timestamps_ms[frame_idx] / 1000.0
            root_pos = data.root_positions[frame_idx]
            root_quat = data.joint_angles_quat[frame_idx].get("Hips", [1.0, 0.0, 0.0, 0.0])

            q = []
            v = []
            for jn in joint_order:
                rad = data.joint_angles_rad[frame_idx].get(jn, [0.0, 0.0, 0.0])
                q.append(rad[0])
                v.append(0.0)

            frames.append({
                "t": round(t, 6),
                "base_pos": [round(p, 6) for p in root_pos],
                "base_quat_wxyz": [round(q, 6) for q in root_quat],
                "q": [round(x, 6) for x in q],
                "v": v,
            })

        return {
            "schema": "signverse-pinocchio-v1",
            "session_id": data.session_id,
            "session_name": data.session_name,
            "action_label": data.action_label,
            "fps": data.fps,
            "frame_count": data.num_frames,
            "duration_s": data.duration_s,
            "joint_names": [_REVOLUTE_JOINTS[k] for k in joint_order],
            "canonical_names": joint_order,
            "nq": len(joint_order) + 7,     # 7 for floating base (3 pos + 4 quat)
            "nv": len(joint_order) + 6,     # 6 for floating base velocity
            "frames": frames,
        }

    # ------------------------------------------------------------------ #
    # Blender Python script
    # ------------------------------------------------------------------ #
    def export_blender_script(self, data: UnifiedMotionData) -> str:
        """Generate a Blender Python script that creates and animates the skeleton."""
        offsets = {
            "Hips":         "(0, 0, 0)",
            "Spine":        "(0, 0, 0.2)",
            "Chest":        "(0, 0, 0.15)",
            "Neck":         "(0, 0, 0.2)",
            "Head":         "(0, 0, 0.1)",
            "LeftShoulder": "(-0.15, 0, 0)",
            "LeftArm":      "(-0.2, 0, 0)",
            "LeftForeArm":  "(-0.28, 0, 0)",
            "LeftHand":     "(-0.25, 0, 0)",
            "RightShoulder":"(0.15, 0, 0)",
            "RightArm":     "(0.2, 0, 0)",
            "RightForeArm": "(0.28, 0, 0)",
            "RightHand":    "(0.25, 0, 0)",
            "LeftUpLeg":    "(-0.1, 0, 0)",
            "LeftLeg":      "(0, 0, -0.42)",
            "LeftFoot":     "(0, 0, -0.38)",
            "RightUpLeg":   "(0.1, 0, 0)",
            "RightLeg":     "(0, 0, -0.42)",
            "RightFoot":    "(0, 0, -0.38)",
        }

        parents = {
            "Hips": None,
            "Spine": "Hips", "Chest": "Spine", "Neck": "Chest", "Head": "Neck",
            "LeftShoulder": "Chest", "LeftArm": "LeftShoulder",
            "LeftForeArm": "LeftArm", "LeftHand": "LeftForeArm",
            "RightShoulder": "Chest", "RightArm": "RightShoulder",
            "RightForeArm": "RightArm", "RightHand": "RightForeArm",
            "LeftUpLeg": "Hips", "LeftLeg": "LeftUpLeg", "LeftFoot": "LeftLeg",
            "RightUpLeg": "Hips", "RightLeg": "RightUpLeg", "RightFoot": "RightLeg",
        }

        # Build animation data as compact python dict
        anim_data = {}
        for jn in CANONICAL_JOINTS:
            anim_data[jn] = {
                "rx": [round(data.joint_angles_deg[fi].get(jn, [0.0])[0], 3) for fi in range(data.num_frames)],
                "ry": [round(data.joint_angles_deg[fi].get(jn, [0.0, 0.0])[1], 3) for fi in range(data.num_frames)],
                "rz": [round(data.joint_angles_deg[fi].get(jn, [0.0, 0.0, 0.0])[2], 3) for fi in range(data.num_frames)],
            }

        return f'''"""
SignVerse Blender Headless Script
Session:  {data.session_name}
Action:   {data.action_label}
FPS:      {data.fps}
Frames:   {data.num_frames}

Usage:
  blender --background --python this_script.py

Requirements: Blender 3.x or 4.x
"""

import bpy
import math

# ──────────────────────────────────────────────────────────────────
# 1. Scene setup
# ──────────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = {int(data.fps)}
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = {data.num_frames}

# ──────────────────────────────────────────────────────────────────
# 2. Create armature
# ──────────────────────────────────────────────────────────────────
bpy.ops.object.armature_add(enter_editmode=True, align="WORLD", location=(0,0,0))
arm_obj = bpy.context.active_object
arm_obj.name = "SignVerseArmature"
arm = arm_obj.data
arm.name = "SignVerseSkeleton"

# Remove default bone
for b in arm.edit_bones:
    arm.edit_bones.remove(b)

offsets = {offsets}
parents = {parents}

bone_heads = {{}}
bone_tails = {{}}
created_bones = {{}}

JOINT_ORDER = {list(CANONICAL_JOINTS)}

def parse_v(s):
    return tuple(float(x) for x in s.strip("()").split(","))

for name in JOINT_ORDER:
    eb = arm.edit_bones.new(name)
    offset = parse_v(offsets[name])
    parent_name = parents[name]

    if parent_name is None:
        head = (0.0, 0.0, 1.0)
    else:
        head = bone_tails[parent_name]

    tail = tuple(head[i] + offset[i] for i in range(3))
    if tail == head:
        tail = (head[0], head[1], head[2] + 0.05)

    eb.head = head
    eb.tail = tail
    bone_heads[name] = head
    bone_tails[name] = tail

    if parent_name and parent_name in created_bones:
        eb.parent = created_bones[parent_name]
        eb.use_connect = False

    created_bones[name] = eb

bpy.ops.object.mode_set(mode="POSE")

# ──────────────────────────────────────────────────────────────────
# 3. Insert keyframes
# ──────────────────────────────────────────────────────────────────
ANIM_DATA = {anim_data}

for frame_idx in range({data.num_frames}):
    bpy.context.scene.frame_set(frame_idx + 1)
    for bone_name, channels in ANIM_DATA.items():
        if bone_name not in arm_obj.pose.bones:
            continue
        pb = arm_obj.pose.bones[bone_name]
        pb.rotation_mode = "XYZ"
        rx = math.radians(channels["rx"][frame_idx])
        ry = math.radians(channels["ry"][frame_idx])
        rz = math.radians(channels["rz"][frame_idx])
        pb.rotation_euler = (rx, ry, rz)
        pb.keyframe_insert(data_path="rotation_euler", frame=frame_idx + 1)

bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.scene.frame_set(1)
print(f"[SignVerse] Armature created. {{len(ANIM_DATA)}} bones, {data.num_frames} frames.")
print("[SignVerse] Use File > Export > BVH / FBX to export from Blender.")
'''
