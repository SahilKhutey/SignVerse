"""
FBX exporter using ASCII FBX 7.4 format.
ASCII FBX is widely compatible and human-debuggable.

Output: Single FBX file with embedded skeleton + animation.
Compatible with: Unity, Unreal Engine, Maya, Blender, MotionBuilder.
"""
import struct
import json
from typing import List
from .data_loader import UnifiedMotionData


class FBXExporter:
    """Generates ASCII FBX 7.4 format files."""

    FBX_HEADER = """; FBX 7.4.0 project file
; Created by SignVerse Robotics
; ----------------------------------------------------

FBXHeaderExtension:  {{
    FBXHeaderVersion: 1003
    FBXVersion: 7400
    CreationTimeStamp:  {{
        Version: 1000
        Year: 2026
        Month: 6
        Day: 10
        Hour: 8
        Minute: 0
        Second: 0
        Millisecond: 0
    }}
    Creator: "SignVerse FBX Exporter"
}}
GlobalSettings:  {{
    Version: 1000
    Properties70:  {{
        P: "UpAxis", "int", "Integer", "",1
        P: "UpAxisSign", "int", "Integer", "",1
        P: "FrontAxis", "int", "Integer", "",2
        P: "FrontAxisSign", "int", "Integer", "",1
        P: "CoordAxis", "int", "Integer", "",0
        P: "CoordAxisSign", "int", "Integer", "",1
        P: "OriginalUpAxis", "int", "Integer", "",-1
        P: "OriginalUpAxisSign", "int", "Integer", "",1
        P: "UnitScaleFactor", "double", "Number", "",100
        P: "OriginalUnitScaleFactor", "double", "Number", "",1
        P: "AmbientColor", "ColorRGB", "Color", "",0,0,0
        P: "DefaultCamera", "KString", "", "", "Producer Perspective"
        P: "TimeMode", "enum", "", "",11
        P: "TimeProtocol", "enum", "", "",2
        P: "SnapOnFrameMode", "enum", "", "",0
        P: "TimeSpanStart", "KTime", "Time", "",0
        P: "TimeSpanStop", "KTime", "Time", "",{stop_time}
        P: "CustomFrameRate", "double", "Number", "",{fps}
    }}
}}
"""

    # Parent mapping: joint -> parent
    FBX_PARENTS = {
        "Hips": None,
        "Spine": "Hips",
        "Chest": "Spine",
        "Neck": "Chest",
        "Head": "Neck",
        "LeftShoulder": "Chest",
        "LeftArm": "LeftShoulder",
        "LeftForeArm": "LeftArm",
        "LeftHand": "LeftForeArm",
        "RightShoulder": "Chest",
        "RightArm": "RightShoulder",
        "RightForeArm": "RightArm",
        "RightHand": "RightForeArm",
        "LeftUpLeg": "Hips",
        "LeftLeg": "LeftUpLeg",
        "LeftFoot": "LeftLeg",
        "RightUpLeg": "Hips",
        "RightLeg": "RightUpLeg",
        "RightFoot": "RightLeg",
    }

    def export(self, data: UnifiedMotionData) -> str:
        """Generate FBX file content."""
        fbx_time_per_frame = 46186158000  # FBX time units (1/46186158000 sec)
        stop_time = int(data.num_frames * fbx_time_per_frame / data.fps)

        output = self.FBX_HEADER.format(
            stop_time=stop_time,
            fps=int(data.fps),
        )

        output += self._build_documents(data)
        output += self._build_references()
        output += self._build_definitions(data)
        output += self._build_objects(data)
        output += self._build_connections(data)
        output += self._build_takes(data)

        return output

    def _build_documents(self, data):
        return """
Documents:  {
    Count: 1
    Document: {
        Name: ""
        Properties70:  {
            P: "SourceObject", "object", "", ""
            P: "ActiveAnimStackName", "KString", "", "", "Take 001"
        }
        RootNode:  {
        }
    }
}
"""

    def _build_references(self):
        return """
References:  {
}
"""

    def _build_definitions(self, data):
        num_models = len(data.joint_names)
        num_curve_nodes = num_models + 1  # 1 rotation node per joint + 1 root translation node
        num_curves = num_models * 3 + 3   # 3 curves per rotation node + 3 curves for root translation

        return f"""
Definitions:  {{
    Version: 100
    Count: 5

    ObjectType: "Model" {{
        Count: {num_models}
    }}

    ObjectType: "AnimationStack" {{
        Count: 1
        PropertyTemplate: "FbxAnimStack" {{
            Properties70:  {{
                P: "Description", "KString", "", "", ""
                P: "LocalStart", "KTime", "Time", "",0
                P: "LocalStop", "KTime", "Time", "",0
                P: "ReferenceStart", "KTime", "Time", "",0
                P: "ReferenceStop", "KTime", "Time", "",0
            }}
        }}
    }}

    ObjectType: "AnimationLayer" {{
        Count: 1
        PropertyTemplate: "FbxAnimLayer" {{
            Properties70:  {{
                P: "Weight", "Number", "", "Number",100
            }}
        }}
    }}

    ObjectType: "AnimationCurveNode" {{
        Count: {num_curve_nodes}
    }}

    ObjectType: "AnimationCurve" {{
        Count: {num_curves}
    }}
}}
"""

    def _build_objects(self, data):
        out = ["Objects:  {"]

        # Build skeleton models
        for i, joint_name in enumerate(data.joint_names):
            out.append(self._build_model_node(joint_name, i, data))

        # Animation stack
        out.append("""
    AnimationStack: 100000, "AnimStack::Take 001", "AnimStack" {
        Properties70:  {
            P: "Description", "KString", "", "", "SignVerse Motion"
        }
    }""")

        # Animation layer
        out.append("""
    AnimationLayer: 200000, "AnimLayer::BaseLayer", "AnimLayer" {
    }""")

        # Animation curve nodes
        for i, joint_name in enumerate(data.joint_names):
            rot_node_id = 3000 + i
            out.append(f"""
    AnimationCurveNode: {rot_node_id}, "AnimCurveNode::Lcl Rotation", "Lcl Rotation" {{
        Properties70:  {{
            P: "d", "Compound", "", ""
        }}
    }}""")

            if joint_name == "Hips":
                trans_node_id = 4000 + i
                out.append(f"""
    AnimationCurveNode: {trans_node_id}, "AnimCurveNode::Lcl Translation", "Lcl Translation" {{
        Properties70:  {{
            P: "d", "Compound", "", ""
        }}
    }}""")

        # Animation curves
        out.append(self._build_animation_curves(data))

        out.append("}")
        return "\n".join(out)

    def _build_model_node(self, name, idx, data):
        """Build a model node for a joint with parent-relative translation."""
        pos = [0.0, 0.0, 0.0]
        if data.joint_positions_3d:
            pos = data.joint_positions_3d[0].get(name, [0.0, 0.0, 0.0])

        parent_name = self.FBX_PARENTS.get(name)
        if parent_name and data.joint_positions_3d:
            parent_pos = data.joint_positions_3d[0].get(parent_name, [0.0, 0.0, 0.0])
            rel_pos = [pos[0] - parent_pos[0], pos[1] - parent_pos[1], pos[2] - parent_pos[2]]
        else:
            rel_pos = pos

        # Multiply positions by 100 to convert to cm (standard FBX units)
        rel_pos = [p * 100.0 for p in rel_pos]

        return f"""
    Model: {1000 + idx}, "Model::{name}", "LimbNode" {{
        Version: 232
        Properties70:  {{
            P: "Lcl Translation", "Lcl Translation", "", "A",{rel_pos[0]:.4f},{rel_pos[1]:.4f},{rel_pos[2]:.4f}
            P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0
            P: "Lcl Scaling", "Lcl Scaling", "", "A",100,100,100
            P: "DefaultAttributeIndex", "int", "Integer", "",0
            P: "InheritType", "enum", "", "",1
        }}
        MultiLayer: 0
        MultiTake: 0
        Shading: Y
        Culling: "CullingOff"
    }}"""

    def _build_animation_curves(self, data):
        curves = []

        # For each joint, export rotation curves
        for i, joint_name in enumerate(data.joint_names):
            for channel_idx, channel_name in enumerate(["X", "Y", "Z"]):
                channel_data = []
                for frame_idx in range(data.num_frames):
                    t = frame_idx / data.fps
                    angles = data.joint_angles_deg[frame_idx].get(joint_name, [0.0, 0.0, 0.0])
                    val = angles[channel_idx]
                    channel_data.append((t, val))

                key_times = ";".join(f"{t * 46186158000:.0f}" for t, _ in channel_data)
                key_values = ";".join(f"{v:.4f}" for _, v in channel_data)
                curve_id = 5000 + i * 6 + channel_idx

                curves.append(f"""
    AnimationCurve: {curve_id}, "AnimCurve::{joint_name}_Rot_{channel_name}", "AnimCurve" {{
        Default: 0
        KeyVer: 4008
        KeyTime: *{len(channel_data)} {{
            a: {key_times}
        }}
        KeyValueFloat: *{len(channel_data)} {{
            a: {key_values}
        }}
        KeyAttrFlags: *1 {{
            a: 24840
        }}
        KeyAttrRefCount: *1 {{
            a: {len(channel_data)}
        }}
    }}""")

            # For Hips, also export root translation curves
            if joint_name == "Hips":
                for channel_idx, channel_name in enumerate(["X", "Y", "Z"]):
                    channel_data = []
                    for frame_idx in range(data.num_frames):
                        t = frame_idx / data.fps
                        root_pos = data.root_positions[frame_idx]
                        val = root_pos[channel_idx] * 100.0  # to cm
                        channel_data.append((t, val))

                    key_times = ";".join(f"{t * 46186158000:.0f}" for t, _ in channel_data)
                    key_values = ";".join(f"{v:.4f}" for _, v in channel_data)
                    curve_id = 5000 + i * 6 + 3 + channel_idx

                    curves.append(f"""
    AnimationCurve: {curve_id}, "AnimCurve::{joint_name}_Trans_{channel_name}", "AnimCurve" {{
        Default: 0
        KeyVer: 4008
        KeyTime: *{len(channel_data)} {{
            a: {key_times}
        }}
        KeyValueFloat: *{len(channel_data)} {{
            a: {key_values}
        }}
        KeyAttrFlags: *1 {{
            a: 24840
        }}
        KeyAttrRefCount: *1 {{
            a: {len(channel_data)}
        }}
    }}""")

        return "\n".join(curves)

    def _build_connections(self, data):
        out = ["Connections:  {"]

        # Connect Model joints hierarchical tree
        for i, joint_name in enumerate(data.joint_names):
            model_id = 1000 + i
            parent_name = self.FBX_PARENTS.get(joint_name)
            if parent_name:
                parent_idx = data.joint_names.index(parent_name)
                parent_id = 1000 + parent_idx
                out.append(f"    C: \"OO\",{model_id},{parent_id}")
            else:
                out.append(f"    C: \"OO\",{model_id},0")

        # Connect CurveNodes to Models and AnimationLayer
        for i, joint_name in enumerate(data.joint_names):
            model_id = 1000 + i
            rot_node_id = 3000 + i
            # Connect rotation node to model rotation property
            out.append(f"    C: \"OP\",{rot_node_id},{model_id},\"Lcl Rotation\"")
            # Connect rotation node to animation layer
            out.append(f"    C: \"OO\",{rot_node_id},200000")

            # Connect rotation channels (X, Y, Z) to rotation node
            out.append(f"    C: \"OP\",{5000 + i * 6},{rot_node_id},\"d|X\"")
            out.append(f"    C: \"OP\",{5000 + i * 6 + 1},{rot_node_id},\"d|Y\"")
            out.append(f"    C: \"OP\",{5000 + i * 6 + 2},{rot_node_id},\"d|Z\"")

            if joint_name == "Hips":
                trans_node_id = 4000 + i
                # Connect translation node to model translation property
                out.append(f"    C: \"OP\",{trans_node_id},{model_id},\"Lcl Translation\"")
                # Connect translation node to animation layer
                out.append(f"    C: \"OO\",{trans_node_id},200000")

                # Connect translation channels (X, Y, Z) to translation node
                out.append(f"    C: \"OP\",{5000 + i * 6 + 3},{trans_node_id},\"d|X\"")
                out.append(f"    C: \"OP\",{5000 + i * 6 + 4},{trans_node_id},\"d|Y\"")
                out.append(f"    C: \"OP\",{5000 + i * 6 + 5},{trans_node_id},\"d|Z\"")

        # Connect AnimationLayer to AnimationStack
        out.append("    C: \"OO\",200000,100000")

        out.append("}")
        return "\n".join(out)

    def _build_takes(self, data):
        fbx_time_per_frame = 46186158000
        stop_time = int(data.num_frames * fbx_time_per_frame / data.fps)
        return f"""
Takes:  {{
    Current: "Take 001"
    Take: "Take 001" {{
        FileName: "Take_001.tak"
        LocalTime: 0,{stop_time}
        ReferenceTime: 0,{stop_time}
    }}
}}
"""
