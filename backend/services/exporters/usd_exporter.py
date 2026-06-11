"""
USD ASCII Scene Exporter (.usda)
Generates a complete USD ASCII scene with:
  - Person skeleton using UsdSkel primitives
  - Mesh prims for each tracked object (box geometry)
  - Per-frame animation via UsdGeom.Xformable xformOp:translate / xformOp:orient
  - Pure ASCII output — no pxr/USD library required

USD references:
  https://openusd.org/release/spec.html
  https://openusd.org/release/api/usd_skel_page_front.html
"""
import math
from typing import List, Optional

from .data_loader import UnifiedMotionData, CANONICAL_JOINTS
# scene_composer imported lazily in export_scene to avoid circular imports
from backend.services.scene.object_library import get_model



# ─── Joint hierarchy (parent relationships) ─────────────────────── #
_PARENTS = {
    "Hips": None,
    "Spine":"Hips", "Chest":"Spine", "Neck":"Chest", "Head":"Neck",
    "LeftShoulder":"Chest",  "LeftArm":"LeftShoulder",
    "LeftForeArm":"LeftArm", "LeftHand":"LeftForeArm",
    "RightShoulder":"Chest", "RightArm":"RightShoulder",
    "RightForeArm":"RightArm","RightHand":"RightForeArm",
    "LeftUpLeg":"Hips",      "LeftLeg":"LeftUpLeg",  "LeftFoot":"LeftLeg",
    "RightUpLeg":"Hips",     "RightLeg":"RightUpLeg","RightFoot":"RightLeg",
}

_T_POSE = {
    "Hips":[0,0,0],"Spine":[0,.2,0],"Chest":[0,.4,0],"Neck":[0,.5,0],"Head":[0,.6,0],
    "LeftShoulder":[-.15,.4,0],"LeftArm":[-.35,.4,0],"LeftForeArm":[-.55,.4,0],"LeftHand":[-.65,.4,0],
    "RightShoulder":[.15,.4,0],"RightArm":[.35,.4,0],"RightForeArm":[.55,.4,0],"RightHand":[.65,.4,0],
    "LeftUpLeg":[-.1,-.1,0],"LeftLeg":[-.1,-.52,0],"LeftFoot":[-.1,-.9,0],
    "RightUpLeg":[.1,-.1,0],"RightLeg":[.1,-.52,0],"RightFoot":[.1,-.9,0],
}

JOINT_ORDER = list(CANONICAL_JOINTS)


def _fmtv3(v: List[float], p: int = 6) -> str:
    return f"({v[0]:.{p}f}, {v[1]:.{p}f}, {v[2]:.{p}f})"


def _fmtq(q: List[float], p: int = 6) -> str:
    """q = [w,x,y,z] → USD quaternion = (real, i, j, k)"""
    return f"({q[0]:.{p}f}, {q[1]:.{p}f}, {q[2]:.{p}f}, {q[3]:.{p}f})"


class USDExporter:
    """Export person motion + scene objects as USD ASCII (.usda)."""

    def export_person(self, data: UnifiedMotionData) -> str:
        """Person-only USD ASCII."""
        lines = [
            '#usda 1.0',
            '(',
            f'    defaultPrim = "SignVerse"',
            f'    metersPerUnit = 1',
            f'    upAxis = "Y"',
            f'    doc = "SignVerse motion export — session: {data.session_name}"',
            ')',
            '',
            'def Xform "SignVerse"',
            '{',
        ]
        lines.extend(self._skeleton_prim(data))
        lines.append('}')
        return '\n'.join(lines)

    def export_scene(self, scene) -> str:
        """Full scene USD ASCII -- person + objects."""
        from backend.services.scene.scene_composer import SceneData
        data = scene.motion_data
        lines = [
            '#usda 1.0',
            '(',
            f'    defaultPrim = "SignVerseScene"',
            f'    metersPerUnit = 1',
            f'    upAxis = "Y"',
            f'    doc = "SignVerse full scene — {data.session_name} — objects: {scene.unique_classes}"',
            ')',
            '',
            f'def Xform "SignVerseScene"',
            '{',
        ]

        # Person skeleton
        lines.extend(self._skeleton_prim(data))

        # Objects
        for obj in scene.scene_objects:
            lines.extend(self._object_prim(obj, data))

        lines.append('}')
        return '\n'.join(lines)

    # ---------------------------------------------------------------- #
    # Skeleton prim
    # ---------------------------------------------------------------- #

    def _skeleton_prim(self, data: UnifiedMotionData) -> List[str]:
        n  = data.num_frames
        dt = 1.0 / max(data.fps, 1.0)

        lines = [
            '    def SkelRoot "Person"',
            '    {',
            '        def Skeleton "Skeleton"',
            '        {',
        ]

        # Joint names
        jnames = '", "'.join(JOINT_ORDER)
        lines.append(f'            uniform token[] joints = ["{jnames}"]')

        # Rest transforms (translation only for simplicity)
        rest_xforms = ', '.join(
            f'( ({_T_POSE[j][0]}, {_T_POSE[j][1]}, {_T_POSE[j][2]}), (0,0,0,1), (1,1,1) )'
            for j in JOINT_ORDER
        )
        lines.append(f'            uniform matrix4d[] restTransforms = [{rest_xforms}]')

        # Bind transforms (inverse T-pose)
        bind_xforms = ', '.join(
            f'( ({-_T_POSE[j][0]}, {-_T_POSE[j][1]}, {-_T_POSE[j][2]}), (0,0,0,1), (1,1,1) )'
            for j in JOINT_ORDER
        )
        lines.append(f'            uniform matrix4d[] bindTransforms = [{bind_xforms}]')

        # Topology (parent indices)
        parent_indices = []
        for j in JOINT_ORDER:
            p = _PARENTS.get(j)
            parent_indices.append(JOINT_ORDER.index(p) if p else -1)
        lines.append(f'            int[] jointParents = {parent_indices}')

        # Close Skeleton, open SkelAnimation
        lines += [
            '        }',
            '',
            '        def SkelAnimation "Animation"',
            '        {',
        ]

        # Per-joint rotation animation
        for ji, joint in enumerate(JOINT_ORDER):
            rot_samples = []
            for fi in range(n):
                t = fi * dt
                q = data.joint_angles_quat[fi].get(joint, [1.0, 0.0, 0.0, 0.0])
                rot_samples.append(f'{t:.4f}: {_fmtq(q)}')
            samples_str = ', '.join(rot_samples)
            lines.append(f'            quatf xformOp:orient.timeSamples:{ji} = {{ {samples_str} }}')

        # Root translation
        trans_samples = []
        for fi in range(n):
            t = fi * dt
            rp = data.root_positions[fi] if fi < len(data.root_positions) else [0,0,0]
            trans_samples.append(f'{t:.4f}: {_fmtv3(rp)}')
        lines.append(f'            float3 xformOp:translate.timeSamples = {{ {", ".join(trans_samples)} }}')

        lines += [
            '        }',   # close SkelAnimation
            '    }',        # close SkelRoot
        ]
        return lines

    # ---------------------------------------------------------------- #
    # Object prim
    # ---------------------------------------------------------------- #

    def _object_prim(self, obj, data: UnifiedMotionData) -> List[str]:
        model  = obj.model
        cls    = obj.class_name.replace(' ', '_').replace('.', '_')
        tid    = obj.track_id
        prim   = f'Object_{cls}_{tid}'
        n      = data.num_frames
        dt     = 1.0 / max(data.fps, 1.0)

        # Geometry
        d = model.dimensions
        if len(d) == 3:
            sx, sy, sz = d
        elif len(d) == 2:
            sx, sy, sz = d[0]*2, d[1], d[0]*2
        else:
            sx = sy = sz = d[0]*2

        r, g, b, a = model.color_rgba

        lines = [
            f'    def Mesh "{prim}"',
            '    {',
            f'        # Class: {obj.class_name}, TrackID: {tid}',
            f'        # Avg confidence: {obj.avg_confidence}',
            '',
            # Box geometry
            f'        point3f[] points = [',
            f'            (-{sx/2:.4f}, -{sy/2:.4f}, -{sz/2:.4f}), ({sx/2:.4f}, -{sy/2:.4f}, -{sz/2:.4f}),',
            f'            ({sx/2:.4f}, {sy/2:.4f}, -{sz/2:.4f}), (-{sx/2:.4f}, {sy/2:.4f}, -{sz/2:.4f}),',
            f'            (-{sx/2:.4f}, -{sy/2:.4f}, {sz/2:.4f}), ({sx/2:.4f}, -{sy/2:.4f}, {sz/2:.4f}),',
            f'            ({sx/2:.4f}, {sy/2:.4f}, {sz/2:.4f}), (-{sx/2:.4f}, {sy/2:.4f}, {sz/2:.4f})',
            f'        ]',
            f'        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]',
            f'        int[] faceVertexIndices = [0,1,2,3, 4,7,6,5, 0,4,5,1, 3,2,6,7, 1,5,6,2, 0,3,7,4]',
            f'        color3f[] primvars:displayColor = [({r:.3f}, {g:.3f}, {b:.3f})]',
            f'        float primvars:displayOpacity = {a:.3f}',
            '',
        ]

        # Translation animation (per frame)
        trans_samples = []
        for fi in range(n):
            t = fi * dt
            hold = obj.is_held_at(fi)
            if hold:
                pos = hold.relative_offset
            else:
                pos = obj.position_at(fi)
            trans_samples.append(f'{t:.4f}: {_fmtv3(pos)}')

        lines.append(f'        float3 xformOp:translate.timeSamples = {{ {", ".join(trans_samples)} }}')

        # Hold event metadata
        if obj.hold_events:
            for ev in obj.hold_events:
                lines.append(
                    f'        # HOLD: {ev.hand} hand, frames {ev.start_frame}-{ev.end_frame}'
                    f', joint={ev.hand_joint}'
                )

        lines.append('    }')
        return lines
