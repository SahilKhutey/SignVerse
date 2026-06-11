"""
MuJoCo Scene Exporter — extended to include scene objects.

MuJoCoSceneExporter adds:
  • One <body> per tracked object in <worldbody>
  • Geometry from the ObjectLibrary (box/cylinder dimensions)
  • Per-frame keyframe qpos augmented with free-joint floats
  • Object bodies have free joints so they can be animated

Original MuJoCoExporter (person-only) is preserved intact.
"""
from .data_loader import UnifiedMotionData, CANONICAL_JOINTS
from backend.services.scene.object_library import get_model
# scene_composer imported lazily inside export_scene to avoid circular imports



# ─── Original person-only exporter (preserved exactly) ─────────── #

class MuJoCoExporter:
    """Exports motion as MuJoCo-compatible XML + trajectory."""

    def export(self, data: UnifiedMotionData, robot_name: str = "signverse_humanoid") -> str:
        xml = f'''<?xml version="1.0" encoding="utf-8"?>
<mujoco model="{robot_name}">
    <compiler angle="degree" coordinate="local" inertiafromgeom="true"/>
    <default>
        <joint armature="0.01" damping="0.1" limited="true"/>
        <geom contype="1" convalue="1" friction="1 0.1 0.1" rgba="0.7 0.7 0.7 1"/>
        <motor ctrllimited="true" ctrlrange="-1 1"/>
    </default>
    <option integrator="RK4" timestep="0.01"/>
    <size nstack="{min(1000, data.num_frames)}"/>

    <worldbody>
        <geom name="floor" pos="0 0 0" size="0 0 .25" type="plane" material="grid"/>
        <body name="torso" pos="0 0 1.4">
            <joint name="root" type="free"/>
            <geom name="torso_geom" pos="0 0 -.1" size="0.07" type="capsule" mass="8"/>
            <body name="head" pos="0 0 .1">
                <joint name="head_swivel" type="hinge" axis="0 1 0" range="-50 50"/>
                <geom name="head_geom" pos="0 0 .05" size="0.09" type="sphere" mass="1.5"/>
            </body>
'''
        xml += self._add_limb("left_shoulder", "left_arm", "left_elbow", "left_hand", -0.1)
        xml += self._add_limb("right_shoulder", "right_arm", "right_elbow", "right_hand", 0.1)
        xml += self._add_leg("left_hip", "left_knee", "left_ankle", "left_foot", -0.1)
        xml += self._add_leg("right_hip", "right_knee", "right_ankle", "right_foot", 0.1)

        xml += '''
        </body>
    </worldbody>

    <actuator>
        <!-- Motor actuators for each joint -->
        <motor name="head_motor" joint="head_swivel" gear="50"/>
        <motor name="left_shoulder_motor" joint="left_shoulder" gear="80"/>
        <motor name="left_arm_motor" joint="left_arm" gear="80"/>
        <motor name="left_elbow_motor" joint="left_elbow" gear="60"/>
        <motor name="left_hand_motor" joint="left_hand" gear="30"/>
        <motor name="right_shoulder_motor" joint="right_shoulder" gear="80"/>
        <motor name="right_arm_motor" joint="right_arm" gear="80"/>
        <motor name="right_elbow_motor" joint="right_elbow" gear="60"/>
        <motor name="right_hand_motor" joint="right_hand" gear="30"/>
        <motor name="left_hip_motor" joint="left_hip" gear="120"/>
        <motor name="left_knee_motor" joint="left_knee" gear="80"/>
        <motor name="left_ankle_motor" joint="left_ankle" gear="60"/>
        <motor name="left_foot_motor" joint="left_foot" gear="40"/>
        <motor name="right_hip_motor" joint="right_hip" gear="120"/>
        <motor name="right_knee_motor" joint="right_knee" gear="80"/>
        <motor name="right_ankle_motor" joint="right_ankle" gear="60"/>
        <motor name="right_foot_motor" joint="right_foot" gear="40"/>
    </actuator>

    <asset>
        <material name="grid" texture="grid" texrepeat="1 1" reflectance="0"/>
        <texture name="grid" type="2d" builtin="checker" rgb1="0.1 0.1 0.1" rgb2="0.5 0.5 0.5" width="512" height="512"/>
    </asset>

    <!-- Embedded motion data -->
    <keyframe>
'''
        xml += self._build_keyframes(data)
        xml += '''
    </keyframe>
</mujoco>
'''
        return xml

    def _add_limb(self, shoulder, upper, elbow, hand, x_offset):
        return f'''            <body name="{shoulder}_body" pos="{x_offset} 0 0.05">
                <joint name="{shoulder}" type="hinge" axis="0 1 0" range="-180 180"/>
                <geom name="{shoulder}_geom" pos="0 -0.1 0" size="0.04" type="capsule" mass="1.5"/>
                <body name="{upper}_body" pos="0 -0.2 0">
                    <joint name="{upper}" type="hinge" axis="0 0 1" range="-150 0"/>
                    <geom name="{upper}_geom" pos="0 -0.15 0" size="0.03" type="capsule" mass="1.0"/>
                    <body name="{elbow}_body" pos="0 -0.3 0">
                        <joint name="{elbow}" type="hinge" axis="0 0 1" range="-150 0"/>
                        <geom name="{elbow}_geom" pos="0 -0.15 0" size="0.025" type="capsule" mass="0.5"/>
                        <body name="{hand}_body" pos="0 -0.3 0">
                            <joint name="{hand}" type="hinge" axis="0 0 1" range="-60 60"/>
                            <geom name="{hand}_geom" pos="0 -0.05 0" size="0.03" type="sphere" mass="0.3"/>
                        </body>
                    </body>
                </body>
            </body>
'''

    def _add_leg(self, hip, knee, ankle, foot, x_offset):
        return f'''            <body name="{hip}_body" pos="{x_offset} 0 -0.1">
                <joint name="{hip}" type="hinge" axis="1 0 0" range="-120 60"/>
                <geom name="{hip}_geom" pos="0 -0.2 0" size="0.05" type="capsule" mass="3.0"/>
                <body name="{knee}_body" pos="0 -0.4 0">
                    <joint name="{knee}" type="hinge" axis="1 0 0" range="-150 0"/>
                    <geom name="{knee}_geom" pos="0 -0.2 0" size="0.04" type="capsule" mass="2.0"/>
                    <body name="{ankle}_body" pos="0 -0.4 0">
                        <joint name="{ankle}" type="hinge" axis="1 0 0" range="-45 45"/>
                        <geom name="{ankle}_geom" pos="0 -0.05 0" size="0.04" type="sphere" mass="0.5"/>
                        <body name="{foot}_body" pos="0.05 -0.05 0">
                            <joint name="{foot}" type="hinge" axis="0 1 0" range="-30 30"/>
                            <geom name="{foot}_geom" pos="0.05 0 0" size="0.08 0.03 0.02" type="box" mass="0.4"/>
                        </body>
                    </body>
                </body>
            </body>
'''

    def _build_keyframes(self, data) -> str:
        keyframes = []
        joints_list = [
            "head_swivel",
            "left_shoulder", "left_arm", "left_elbow", "left_hand",
            "right_shoulder", "right_arm", "right_elbow", "right_hand",
            "left_hip", "left_knee", "left_ankle", "left_foot",
            "right_hip", "right_knee", "right_ankle", "right_foot"
        ]
        for frame_idx in range(data.num_frames):
            t = frame_idx / data.fps
            root_pos  = data.root_positions[frame_idx]
            root_quat = data.joint_angles_quat[frame_idx].get("Hips", [1.0, 0.0, 0.0, 0.0])
            joint_vals = []
            for jn in joints_list:
                mapped = self._map_to_internal(jn)
                angles = data.joint_angles_deg[frame_idx].get(mapped, [0.0, 0.0, 0.0])
                joint_vals.append(angles[0])

            qpos_str = (
                f"{root_pos[0]:.3f} {root_pos[1]:.3f} {root_pos[2]:.3f} "
                f"{root_quat[0]:.3f} {root_quat[1]:.3f} {root_quat[2]:.3f} {root_quat[3]:.3f} "
                f"{' '.join(f'{v:.3f}' for v in joint_vals)}"
            )
            ctrl_str = " ".join(["0.0"] * len(joints_list))
            keyframes.append(
                f'        <key name="frame_{frame_idx:04d}"\n'
                f'            qpos="{qpos_str}"\n'
                f'            time="{t:.4f}"\n'
                f'            ctrl="{ctrl_str}"\n'
                f'        />'
            )
        return "\n".join(keyframes)

    def _map_to_internal(self, name):
        mapping = {
            "head_swivel":     "Head",
            "left_shoulder":   "LeftShoulder",  "left_arm":     "LeftArm",
            "left_elbow":      "LeftForeArm",   "left_hand":    "LeftHand",
            "right_shoulder":  "RightShoulder", "right_arm":    "RightArm",
            "right_elbow":     "RightForeArm",  "right_hand":   "RightHand",
            "left_hip":        "LeftUpLeg",      "left_knee":    "LeftLeg",
            "left_ankle":      "LeftFoot",       "left_foot":    "LeftFoot",
            "right_hip":       "RightUpLeg",     "right_knee":   "RightLeg",
            "right_ankle":     "RightFoot",      "right_foot":   "RightFoot",
        }
        return mapping.get(name, name)


# ─── Extended scene exporter ────────────────────────────────────── #

class MuJoCoSceneExporter(MuJoCoExporter):
    """
    Full scene MuJoCo XML: person humanoid + scene objects with free joints.
    Objects animate via qpos keyframe extension (7 floats per object: pos + quat).
    """

    def export_scene(
        self,
        scene,
        robot_name: str = "signverse_scene",
    ) -> str:
        # Lazy import to avoid circular import at module load time
        from backend.services.scene.scene_composer import SceneData
        data    = scene.motion_data
        objects = scene.scene_objects

        # ── Build object body XML ─────────────────────────────────── #
        obj_bodies = ""
        for obj in objects:
            model    = get_model(obj.class_name)
            safe_nm  = f"{obj.class_name.replace(' ', '_')}_{obj.track_id}"
            init_pos = obj.position_at(0)
            size_str = model.mujoco_size_str()
            geom_type= model.geometry
            r, g, b, a = model.color_rgba

            obj_bodies += f"""
        <!-- Object: {obj.class_name} (track {obj.track_id}) -->
        <body name="{safe_nm}" pos="{init_pos[0]:.4f} {init_pos[1]:.4f} {init_pos[2]:.4f}">
            <joint name="{safe_nm}_free" type="free"/>
            <geom name="{safe_nm}_geom"
                  type="{geom_type}"
                  size="{size_str}"
                  rgba="{r:.3f} {g:.3f} {b:.3f} {a:.3f}"
                  mass="0.3"
                  contype="1" convalue="1"/>
        </body>"""

        xml = f'''<?xml version="1.0" encoding="utf-8"?>
<mujoco model="{robot_name}">
    <compiler angle="degree" coordinate="local" inertiafromgeom="true"/>
    <default>
        <joint armature="0.01" damping="0.1" limited="true"/>
        <geom contype="1" convalue="1" friction="1 0.1 0.1" rgba="0.7 0.7 0.7 1"/>
        <motor ctrllimited="true" ctrlrange="-1 1"/>
    </default>
    <option integrator="RK4" timestep="0.01"/>
    <size nstack="{min(1000, data.num_frames)}"/>

    <worldbody>
        <geom name="floor" pos="0 0 0" size="0 0 .25" type="plane" material="grid"/>

        <!-- ═══ PERSON ════════════════════════════════════════════ -->
        <body name="torso" pos="0 0 1.4">
            <joint name="root" type="free"/>
            <geom name="torso_geom" pos="0 0 -.1" size="0.07" type="capsule" mass="8"/>
            <body name="head" pos="0 0 .1">
                <joint name="head_swivel" type="hinge" axis="0 1 0" range="-50 50"/>
                <geom name="head_geom" pos="0 0 .05" size="0.09" type="sphere" mass="1.5"/>
            </body>
'''
        xml += self._add_limb("left_shoulder", "left_arm", "left_elbow", "left_hand", -0.1)
        xml += self._add_limb("right_shoulder", "right_arm", "right_elbow", "right_hand", 0.1)
        xml += self._add_leg("left_hip", "left_knee", "left_ankle", "left_foot", -0.1)
        xml += self._add_leg("right_hip", "right_knee", "right_ankle", "right_foot", 0.1)

        xml += f"""
        </body>

        <!-- ═══ SCENE OBJECTS ═══════════════════════════════════ -->
        {obj_bodies}
    </worldbody>

    <actuator>
        <motor name="head_motor"           joint="head_swivel"       gear="50"/>
        <motor name="left_shoulder_motor"  joint="left_shoulder"     gear="80"/>
        <motor name="left_arm_motor"       joint="left_arm"          gear="80"/>
        <motor name="left_elbow_motor"     joint="left_elbow"        gear="60"/>
        <motor name="left_hand_motor"      joint="left_hand"         gear="30"/>
        <motor name="right_shoulder_motor" joint="right_shoulder"    gear="80"/>
        <motor name="right_arm_motor"      joint="right_arm"         gear="80"/>
        <motor name="right_elbow_motor"    joint="right_elbow"       gear="60"/>
        <motor name="right_hand_motor"     joint="right_hand"        gear="30"/>
        <motor name="left_hip_motor"       joint="left_hip"          gear="120"/>
        <motor name="left_knee_motor"      joint="left_knee"         gear="80"/>
        <motor name="left_ankle_motor"     joint="left_ankle"        gear="60"/>
        <motor name="left_foot_motor"      joint="left_foot"         gear="40"/>
        <motor name="right_hip_motor"      joint="right_hip"         gear="120"/>
        <motor name="right_knee_motor"     joint="right_knee"        gear="80"/>
        <motor name="right_ankle_motor"    joint="right_ankle"       gear="60"/>
        <motor name="right_foot_motor"     joint="right_foot"        gear="40"/>
    </actuator>

    <asset>
        <material name="grid" texture="grid" texrepeat="1 1" reflectance="0"/>
        <texture name="grid" type="2d" builtin="checker" rgb1="0.1 0.1 0.1" rgb2="0.5 0.5 0.5" width="512" height="512"/>
    </asset>

    <!-- ═══ KEYFRAMES (person + objects) ═══════════════════════ -->
    <keyframe>
"""
        xml += self._build_scene_keyframes(data, objects)
        xml += """
    </keyframe>
</mujoco>
"""
        return xml

    def _build_scene_keyframes(self, data: UnifiedMotionData, objects) -> str:
        """Build keyframes augmented with object free-joint qpos."""
        keyframes = []
        joints_list = [
            "head_swivel",
            "left_shoulder", "left_arm", "left_elbow", "left_hand",
            "right_shoulder", "right_arm", "right_elbow", "right_hand",
            "left_hip", "left_knee", "left_ankle", "left_foot",
            "right_hip", "right_knee", "right_ankle", "right_foot",
        ]

        for frame_idx in range(data.num_frames):
            t = frame_idx / data.fps
            root_pos  = data.root_positions[frame_idx]
            root_quat = data.joint_angles_quat[frame_idx].get("Hips", [1.0, 0.0, 0.0, 0.0])
            joint_vals = [
                data.joint_angles_deg[frame_idx].get(self._map_to_internal(jn), [0, 0, 0])[0]
                for jn in joints_list
            ]

            # Person qpos (7 root floats + N joint DOFs)
            qpos_parts = [
                f"{root_pos[0]:.4f} {root_pos[1]:.4f} {root_pos[2]:.4f}",
                f"{root_quat[0]:.4f} {root_quat[1]:.4f} {root_quat[2]:.4f} {root_quat[3]:.4f}",
                " ".join(f"{v:.4f}" for v in joint_vals),
            ]

            # Object qpos: 7 floats each (pos xyz + quat wxyz)
            for obj in objects:
                hold = obj.is_held_at(frame_idx)
                if hold:
                    hand_joint = hold.hand_joint
                    hp = data.joint_positions_3d[frame_idx].get(hand_joint, [0, 0, 0])
                    off = hold.relative_offset
                    pos = [hp[i] + off[i] for i in range(3)]
                else:
                    pos = obj.position_at(frame_idx)
                qpos_parts.append(
                    f"{pos[0]:.4f} {pos[1]:.4f} {pos[2]:.4f} 1.0000 0.0000 0.0000 0.0000"
                )

            qpos_str = " ".join(qpos_parts)
            ctrl_str = " ".join(["0.0"] * len(joints_list))

            keyframes.append(
                f'        <key name="frame_{frame_idx:04d}"\n'
                f'            qpos="{qpos_str}"\n'
                f'            time="{t:.4f}"\n'
                f'            ctrl="{ctrl_str}"\n'
                f'        />'
            )

        return "\n".join(keyframes)
