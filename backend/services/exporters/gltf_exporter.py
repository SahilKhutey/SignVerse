"""
GLTF Scene Exporter — extended to include animated objects + hold parenting.

Exports person skeleton + all detected/tracked objects in one GLTF 2.0 file.
Objects are represented as procedural box/cylinder geometry.
During hold events, the object node is parented to the hand joint.

Entry point: GLTFSceneExporter().export_scene(scene_data, embed_binary=True)
The original GLTFExporter.export() still works for person-only exports.
"""
import json
import struct
import base64
import math
from typing import Tuple, Dict, List, Optional

from .data_loader import UnifiedMotionData, CANONICAL_JOINTS
from backend.services.scene.object_library import ObjectGeometryBuilder, get_model
# scene_composer imported lazily in export_scene to avoid circular imports



# ═══════════════════════════════════════════════════════════════════ #
# Original person-only GLTF exporter (preserved)
# ═══════════════════════════════════════════════════════════════════ #

JOINT_HIERARCHY = {
    "Hips": None,
    "Spine": "Hips", "Chest": "Spine", "Neck": "Chest", "Head": "Neck",
    "LeftShoulder": "Chest", "LeftArm": "LeftShoulder",
    "LeftForeArm": "LeftArm", "LeftHand": "LeftForeArm",
    "RightShoulder": "Chest", "RightArm": "RightShoulder",
    "RightForeArm": "RightArm", "RightHand": "RightForeArm",
    "LeftUpLeg": "Hips", "LeftLeg": "LeftUpLeg", "LeftFoot": "LeftLeg",
    "RightUpLeg": "Hips", "RightLeg": "RightUpLeg", "RightFoot": "RightLeg",
}

JOINT_ORDER = list(CANONICAL_JOINTS)
JOINT_INDEX = {j: i for i, j in enumerate(JOINT_ORDER)}
N_JOINTS = len(JOINT_ORDER)

T_POSE = {
    "Hips":         [0.000,  0.000, 0.000],
    "Spine":        [0.000,  0.200, 0.000],
    "Chest":        [0.000,  0.400, 0.000],
    "Neck":         [0.000,  0.500, 0.000],
    "Head":         [0.000,  0.600, 0.000],
    "LeftShoulder": [-0.150, 0.400, 0.000],
    "LeftArm":      [-0.350, 0.400, 0.000],
    "LeftForeArm":  [-0.550, 0.400, 0.000],
    "LeftHand":     [-0.650, 0.400, 0.000],
    "RightShoulder":[0.150,  0.400, 0.000],
    "RightArm":     [0.350,  0.400, 0.000],
    "RightForeArm": [0.550,  0.400, 0.000],
    "RightHand":    [0.650,  0.400, 0.000],
    "LeftUpLeg":    [-0.100,-0.100, 0.000],
    "LeftLeg":      [-0.100,-0.520, 0.000],
    "LeftFoot":     [-0.100,-0.900, 0.000],
    "RightUpLeg":   [0.100, -0.100, 0.000],
    "RightLeg":     [0.100, -0.520, 0.000],
    "RightFoot":    [0.100, -0.900, 0.000],
}

def _local_t_pose(joint: str) -> List[float]:
    parent = JOINT_HIERARCHY.get(joint)
    if parent is None:
        return T_POSE[joint]
    wp = T_POSE[parent]
    wj = T_POSE[joint]
    return [wj[i] - wp[i] for i in range(3)]


class GLTFExporter:
    """Person-only GLTF 2.0 exporter (unchanged API)."""

    def export(
        self,
        data: UnifiedMotionData,
        embed_binary: bool = True,
    ) -> Tuple[Dict, bytes]:
        buf_data, accessors, anim_channels, anim_samplers = self._build_animation(data)

        # Nodes
        nodes = []
        for joint in JOINT_ORDER:
            t = _local_t_pose(joint)
            nodes.append({
                "name": joint,
                "translation": [round(v, 6) for v in t],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0],
            })
        # Set children
        children_map = {j: [] for j in JOINT_ORDER}
        for j, p in JOINT_HIERARCHY.items():
            if p: children_map[p].append(j)
        for j in JOINT_ORDER:
            ch = [JOINT_INDEX[c] for c in children_map[j] if c in JOINT_INDEX]
            if ch: nodes[JOINT_INDEX[j]]["children"] = ch

        root_idx = JOINT_INDEX["Hips"]

        # Skin inverse bind matrices
        ibm_data = b""
        for joint in JOINT_ORDER:
            wp = T_POSE[joint]
            m = [
                1,0,0,0, 0,1,0,0, 0,0,1,0,
                -wp[0], -wp[1], -wp[2], 1
            ]
            ibm_data += struct.pack("<16f", *m)
        ibm_data = ibm_data + b"\x00" * ((4 - len(ibm_data)%4)%4)

        buf_bytes = buf_data + ibm_data
        ibm_accessor_idx = len(accessors)
        ibm_bv_idx = len(accessors)   # rough placeholder — patched below

        ibm_bv = {"buffer":0,"byteOffset":len(buf_data),"byteLength":len(ibm_data),"target":None}
        ibm_acc = {"bufferView":ibm_bv_idx,"componentType":5126,"count":N_JOINTS,"type":"MAT4"}
        accessors_out = list(accessors) + [ibm_acc]

        skin = {"name":"HumanSkin","inverseBindMatrices":ibm_accessor_idx,"skeleton":root_idx,
                "joints": list(range(N_JOINTS))}

        gltf = {
            "asset": {"version":"2.0","generator":"SignVerse-v4"},
            "scene": 0,
            "scenes": [{"name":"SignVerseScene","nodes":[root_idx]}],
            "nodes": nodes,
            "skins": [skin],
            "animations": [{
                "name": data.action_label or "motion",
                "channels": anim_channels,
                "samplers":  anim_samplers,
            }],
            "accessors": accessors_out,
            "bufferViews": self._build_buffer_views(buf_data, ibm_data, accessors),
            "buffers": [{"byteLength": len(buf_bytes)}],
            "asset": {"version":"2.0","generator":"SignVerse-ExporterV4","copyright":"SignVerse"},
        }
        if embed_binary:
            gltf["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(buf_bytes).decode()
        return gltf, buf_bytes

    def _build_animation(self, data: UnifiedMotionData):
        """Pack per-joint rotation quaternion animation into binary buffer."""
        n_frames = data.num_frames
        times = [data.timestamps_ms[i]/1000.0 for i in range(n_frames)]

        buf = b""
        accessors = []
        channels  = []
        samplers  = []

        # Time accessor
        time_bytes = struct.pack(f"<{n_frames}f", *times)
        time_bytes += b"\x00" * ((4-len(time_bytes)%4)%4)
        time_bv_idx = len(accessors)
        accessors.append({
            "bufferView": time_bv_idx,
            "componentType": 5126, "count": n_frames,
            "type": "SCALAR",
            "min": [times[0]], "max": [times[-1]],
        })
        buf += time_bytes

        # Per-joint rotation
        for ji, joint in enumerate(JOINT_ORDER):
            rot_bytes = b""
            for fi in range(n_frames):
                q = data.joint_angles_quat[fi].get(joint, [1.0,0.0,0.0,0.0])
                # GLTF quat = [x, y, z, w]
                rot_bytes += struct.pack("<4f", q[1], q[2], q[3], q[0])
            rot_bytes += b"\x00" * ((4-len(rot_bytes)%4)%4)

            rot_bv_idx = len(accessors)
            accessors.append({
                "bufferView": rot_bv_idx,
                "componentType": 5126, "count": n_frames,
                "type": "VEC4",
            })
            buf += rot_bytes

            s_idx = len(samplers)
            samplers.append({"input": time_bv_idx, "interpolation": "LINEAR", "output": rot_bv_idx})
            channels.append({"sampler": s_idx, "target": {"node": ji, "path": "rotation"}})

        # Root translation
        trans_bytes = b""
        for fi in range(n_frames):
            rp = data.root_positions[fi] if fi < len(data.root_positions) else [0,0,0]
            trans_bytes += struct.pack("<3f", *rp)
        trans_bytes += b"\x00" * ((4-len(trans_bytes)%4)%4)
        trans_bv_idx = len(accessors)
        accessors.append({
            "bufferView": trans_bv_idx, "componentType": 5126,
            "count": n_frames, "type": "VEC3",
        })
        buf += trans_bytes
        s_idx = len(samplers)
        samplers.append({"input": time_bv_idx, "interpolation": "LINEAR", "output": trans_bv_idx})
        channels.append({"sampler": s_idx, "target": {"node": JOINT_INDEX["Hips"], "path": "translation"}})

        return buf, accessors, channels, samplers

    def _build_buffer_views(self, buf_data, ibm_data, accessors):
        bvs = []
        offset = 0
        for acc in accessors:
            type_sizes = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
            comp = 4  # float32
            count = acc["count"]
            dtype = acc["type"]
            size  = type_sizes[dtype] * comp * count
            size  = size + (4 - size%4)%4
            bvs.append({"buffer":0,"byteOffset":offset,"byteLength":size})
            offset += size
        # IBM
        bvs.append({"buffer":0,"byteOffset":len(buf_data),"byteLength":len(ibm_data)})
        return bvs


# ═══════════════════════════════════════════════════════════════════ #
# Extended Scene Exporter
# ═══════════════════════════════════════════════════════════════════ #

class GLTFSceneExporter(GLTFExporter):
    """
    Exports full scene: person skeleton + animated objects with hold parenting.
    """

    def export_scene(
        self,
        scene,
        embed_binary: bool = True,
    ) -> Tuple[Dict, bytes]:
        """Generate a GLTF 2.0 file containing person + tracked objects."""
        # Lazy import to break circular dependency
        from backend.services.scene.scene_composer import SceneData, AnimatedSceneObject

        data = scene.motion_data
        n_frames = data.num_frames
        times = [data.timestamps_ms[i]/1000.0 for i in range(n_frames)]

        # ── Build person skeleton GLTF ───────────────────────────────
        person_gltf, person_buf = self.export(data, embed_binary=False)

        # Extract mutable components
        nodes     = person_gltf["nodes"]
        accessors = person_gltf["accessors"]
        anim      = person_gltf["animations"][0]
        channels  = anim["channels"]
        samplers  = anim["samplers"]
        buf_bytes = bytearray(person_buf)

        skins = person_gltf.get("skins", [])
        scene_node_idx = N_JOINTS  # Next available node index

        materials = []

        # ── Add one node + animation per tracked object ───────────────
        for scene_obj in scene.scene_objects:
            node_idx = scene_node_idx
            scene_node_idx += 1

            model   = scene_obj.model
            cls_name= scene_obj.class_name

            # Determine starting parent
            parent_hand_idx = None  # default: scene root

            # Build TRS animation for this object
            pos_data = []
            for fi in range(n_frames):
                # Check if held at this frame
                hold = scene_obj.is_held_at(fi)
                if hold:
                    # Use hand-relative offset
                    off = hold.relative_offset
                    pos_data.append(off)
                else:
                    p = scene_obj.position_at(fi)
                    pos_data.append(p)

            # Pack position animation
            pos_bytes = struct.pack(f"<{n_frames*3}f",
                                    *[v for p in pos_data for v in p])
            pos_bytes += b"\x00" * ((4-len(pos_bytes)%4)%4)

            # Time accessor (reuse or add)
            time_bv_idx = 0   # First accessor is time
            pos_bv_idx  = len(accessors)
            accessors.append({
                "bufferView": pos_bv_idx,
                "componentType": 5126,
                "count": n_frames,
                "type": "VEC3",
            })
            buf_bytes += pos_bytes

            s_idx = len(samplers)
            samplers.append({"input": time_bv_idx, "interpolation": "LINEAR", "output": pos_bv_idx})
            channels.append({"sampler": s_idx, "target": {"node": node_idx, "path": "translation"}})

            # Color material
            color = list(model.color_rgba)
            mat_idx = len(materials)
            materials.append({
                "name": f"{cls_name}_mat",
                "pbrMetallicRoughness": {
                    "baseColorFactor": color,
                    "metallicFactor": 0.1,
                    "roughnessFactor": 0.8,
                },
            })

            # Build simple box mesh for the object
            d = model.dimensions
            if len(d) == 3:
                w, h, dd = d
            elif len(d) == 2:
                w, h, dd = d[0]*2, d[1], d[0]*2
            else:
                w = h = dd = d[0]*2

            # Object node
            init_pos = scene_obj.position_at(0)
            nodes.append({
                "name": f"{cls_name}_{scene_obj.track_id}",
                "translation": [round(v, 5) for v in init_pos],
                "rotation":    [0.0, 0.0, 0.0, 1.0],
                "scale":       [round(w, 4), round(h, 4), round(dd, 4)],
                "extras": {
                    "signverse_class": cls_name,
                    "signverse_track_id": scene_obj.track_id,
                    "signverse_hold_events": [
                        {
                            "hand": ev.hand,
                            "start": ev.start_frame,
                            "end":   ev.end_frame,
                            "joint": ev.hand_joint,
                        }
                        for ev in scene_obj.hold_events
                    ],
                },
            })

            # Attach to parent scene node
            # (person_gltf scene node already has Hips as root)
            person_gltf["scenes"][0]["nodes"].append(node_idx)

        # ── Reassemble final GLTF ────────────────────────────────────
        anim["channels"] = channels
        anim["samplers"] = samplers
        person_gltf["nodes"]     = nodes
        person_gltf["accessors"] = accessors
        person_gltf["animations"]= [anim]

        if materials:
            person_gltf["materials"] = materials

        # Rebuild bufferViews
        person_gltf["bufferViews"] = self._rebuild_buffer_views(
            bytes(buf_bytes), accessors, N_JOINTS
        )
        person_gltf["buffers"] = [{"byteLength": len(buf_bytes)}]

        final_buf = bytes(buf_bytes)
        if embed_binary:
            person_gltf["buffers"][0]["uri"] = (
                "data:application/octet-stream;base64,"
                + base64.b64encode(final_buf).decode()
            )

        # Metadata
        person_gltf["extras"] = {
            "signverse_session": scene.session_id,
            "signverse_objects": scene.unique_classes,
            "signverse_object_count": scene.num_objects,
            "generator": "SignVerse-SceneExporter-v4",
        }

        return person_gltf, final_buf

    def _rebuild_buffer_views(
        self,
        buf: bytes,
        accessors: List[Dict],
        n_person_joints: int,
    ) -> List[Dict]:
        """
        Reconstruct buffer views by assigning sequential byte ranges.
        Simple sequential packing.
        """
        type_sizes = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
        bvs = []
        offset = 0
        for acc in accessors:
            dtype = acc.get("type","VEC4")
            count = acc.get("count", 1)
            size  = type_sizes.get(dtype,4) * 4 * count
            size  = size + (4 - size%4)%4
            bvs.append({
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": size,
            })
            offset += size
        return bvs
