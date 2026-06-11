"""
BVH Scene Exporter — extends BVHExporter to include tracked objects
as additional ROOT joints with Xposition Yposition Zposition channels.

BVH does not support mesh geometry natively; objects are represented
as position-only joints. This is correct for Blender import — Blender
creates empties for each object that can be parent-constrained to meshes.

Entry points:
  BVHExporter().export(data)               — person-only (unchanged)
  BVHSceneExporter().export_scene(scene)   — person + objects
"""
import math
from typing import List
from .data_loader import UnifiedMotionData, CANONICAL_JOINTS
# NOTE: scene_composer imported lazily inside export_scene to avoid circular imports



# ─── Original person-only exporter (preserved exactly) ─────────── #

class BVHExporter:
    """Exports person-only motion to BVH format."""

    BVH_HIERARCHY = [
        ("Hips",         None,           (0.00, 0.00, 0.00)),
        ("Spine",        "Hips",         (0.00, 10.00, 0.00)),
        ("Chest",        "Spine",        (0.00, 15.00, 0.00)),
        ("Neck",         "Chest",        (0.00, 20.00, 0.00)),
        ("Head",         "Neck",         (0.00, 10.00, 0.00)),
        ("LeftShoulder", "Chest",       (-15.0, 0.00, 0.00)),
        ("LeftArm",      "LeftShoulder",(-10.0, 0.00, 0.00)),
        ("LeftForeArm",  "LeftArm",     (-28.0, 0.00, 0.00)),
        ("LeftHand",     "LeftForeArm", (-25.0, 0.00, 0.00)),
        ("RightShoulder","Chest",       ( 15.0, 0.00, 0.00)),
        ("RightArm",     "RightShoulder",(10.0, 0.00, 0.00)),
        ("RightForeArm", "RightArm",    ( 28.0, 0.00, 0.00)),
        ("RightHand",    "RightForeArm",( 25.0, 0.00, 0.00)),
        ("LeftUpLeg",    "Hips",        (-10.0, 0.00, 0.00)),
        ("LeftLeg",      "LeftUpLeg",   (0.00,-42.0, 0.00)),
        ("LeftFoot",     "LeftLeg",     (0.00,-38.0, 0.00)),
        ("RightUpLeg",   "Hips",        ( 10.0, 0.00, 0.00)),
        ("RightLeg",     "RightUpLeg",  (0.00,-42.0, 0.00)),
        ("RightFoot",    "RightLeg",    (0.00,-38.0, 0.00)),
    ]

    def export(self, data: UnifiedMotionData) -> str:
        lines = ["HIERARCHY"]
        self._write_joint(lines, "Hips", None, indent=0)
        lines.append("MOTION")
        lines.append(f"Frames: {data.num_frames}")
        lines.append(f"Frame Time: {1.0 / data.fps:.6f}")

        for frame_idx in range(data.num_frames):
            row = []
            root_pos = data.root_positions[frame_idx]
            row.extend([root_pos[0], root_pos[1], root_pos[2]])
            for joint_name, _, _ in self.BVH_HIERARCHY:
                angles = data.joint_angles_deg[frame_idx].get(joint_name, [0.0, 0.0, 0.0])
                row.extend(angles)
            lines.append(" ".join(f"{v:.4f}" for v in row))

        return "\n".join(lines)

    def _write_joint(self, lines, name, parent, indent):
        pad = "  " * indent
        joint_info = next((j for j in self.BVH_HIERARCHY if j[0] == name), None)
        if not joint_info:
            return
        offset = joint_info[2]
        has_children = any(j[1] == name for j in self.BVH_HIERARCHY)

        if parent is None:
            lines.append(f"{pad}ROOT {name}")
        else:
            lines.append(f"{pad}JOINT {name}")

        lines.append(f"{pad}{{")
        lines.append(f"{pad}  OFFSET {offset[0]:.2f} {offset[1]:.2f} {offset[2]:.2f}")

        if parent is None:
            lines.append(f"{pad}  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation")
        else:
            lines.append(f"{pad}  CHANNELS 3 Zrotation Yrotation Xrotation")

        if has_children:
            for child_name, child_parent, _ in self.BVH_HIERARCHY:
                if child_parent == name:
                    self._write_joint(lines, child_name, name, indent + 1)
        else:
            lines.append(f"{pad}  End Site")
            lines.append(f"{pad}  {{")
            lines.append(f"{pad}    OFFSET 0.00 5.00 0.00")
            lines.append(f"{pad}  }}")

        lines.append(f"{pad}}}")


# ─── Extended scene exporter ────────────────────────────────────── #

class BVHSceneExporter(BVHExporter):
    """
    Extends BVHExporter with additional ROOT joints for each tracked object.
    
    Each object gets:
      ROOT <ClassName>_<TrackID>
        CHANNELS 6  Xposition Yposition Zposition  Zrotation Yrotation Xrotation
        End Site { OFFSET 0 0 0 }

    Motion data: object world-space position per frame (rotation = 0).
    Scale factor: BVH uses cm by convention → multiply metre positions by 100.
    """

    SCALE = 100.0   # metres → centimetres (BVH convention)

    def export_scene(self, scene) -> str:
        """Generate BVH scene file: person skeleton + object ROOT joints."""
        # Lazy import to avoid circular import at module load time
        from backend.services.scene.scene_composer import SceneData
        data = scene.motion_data
        n_frames = data.num_frames
        objects = scene.scene_objects

        lines = ["HIERARCHY"]

        # ── Person skeleton ──
        self._write_joint(lines, "Hips", None, indent=0)

        # ── Object ROOT joints (one per tracked object) ──
        for obj in objects:
            safe_name = f"{obj.class_name.replace(' ', '_')}_{obj.track_id}"
            first_pos = obj.position_at(0)
            ox = round(first_pos[0] * self.SCALE, 3)
            oy = round(first_pos[1] * self.SCALE, 3)
            oz = round(first_pos[2] * self.SCALE, 3)

            lines.append(f"ROOT {safe_name}")
            lines.append("{")
            lines.append(f"  OFFSET {ox:.3f} {oy:.3f} {oz:.3f}")
            lines.append("  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation")
            lines.append("  End Site")
            lines.append("  {")
            lines.append("    OFFSET 0.00 0.00 0.00")
            lines.append("  }")
            lines.append("}")
            lines.append("")

        # ── MOTION section ──
        lines.append("MOTION")
        lines.append(f"Frames: {n_frames}")
        lines.append(f"Frame Time: {1.0 / data.fps:.6f}")

        for frame_idx in range(n_frames):
            row = []

            # Person skeleton channels
            root_pos = data.root_positions[frame_idx]
            row.extend([
                round(root_pos[0] * self.SCALE, 4),
                round(root_pos[1] * self.SCALE, 4),
                round(root_pos[2] * self.SCALE, 4),
            ])
            for joint_name, _, _ in self.BVH_HIERARCHY:
                angles = data.joint_angles_deg[frame_idx].get(joint_name, [0.0, 0.0, 0.0])
                row.extend([round(a, 4) for a in angles])

            # Object channels (position + zero rotation per frame)
            for obj in objects:
                hold = obj.is_held_at(frame_idx)
                if hold:
                    # During hold: use hand joint position + offset
                    hand_joint = hold.hand_joint
                    hand_pos = data.joint_positions_3d[frame_idx].get(hand_joint, [0, 0, 0])
                    off = hold.relative_offset
                    pos = [hand_pos[i] + off[i] for i in range(3)]
                else:
                    pos = obj.position_at(frame_idx)

                row.extend([
                    round(pos[0] * self.SCALE, 4),
                    round(pos[1] * self.SCALE, 4),
                    round(pos[2] * self.SCALE, 4),
                    0.0, 0.0, 0.0,  # No rotation for rigid objects
                ])

            lines.append(" ".join(f"{v:.4f}" for v in row))

        return "\n".join(lines)
