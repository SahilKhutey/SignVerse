from pathlib import Path

# Joint hierarchy: (name, parent, T-pose-offset, is_root)
BVH_JOINTS = [
    ("Hips",        None,            (0.00, 0.00, 0.00),  True),
    ("Spine",       "Hips",          (0.00, 10.00, 0.00), False),
    ("Chest",       "Spine",         (0.00, 25.00, 0.00), False),
    ("Neck",        "Chest",         (0.00, 20.00, 0.00), False),
    ("Head",        "Neck",          (0.00, 10.00, 0.00), False),
    ("LeftShoulder","Chest",         (-15.0, 0.00, 0.00), False),
    ("LeftArm",     "LeftShoulder",  (-10.0, 0.00, 0.00), False),
    ("LeftForeArm", "LeftArm",       (-28.0, 0.00, 0.00), False),
    ("LeftHand",    "LeftForeArm",   (-25.0, 0.00, 0.00), False),
    ("RightShoulder","Chest",        (15.0, 0.00, 0.00),  False),
    ("RightArm",    "RightShoulder", (10.0, 0.00, 0.00),  False),
    ("RightForeArm","RightArm",      (28.0, 0.00, 0.00),  False),
    ("RightHand",   "RightForeArm",  (25.0, 0.00, 0.00),  False),
    ("LeftUpLeg",   "Hips",          (-10.0, 0.00, 0.00), False),
    ("LeftLeg",     "LeftUpLeg",     (0.00, -42.0, 0.00), False),
    ("LeftFoot",    "LeftLeg",       (0.00, -38.0, 0.00), False),
    ("RightUpLeg",  "Hips",          (10.0, 0.00, 0.00),  False),
    ("RightLeg",    "RightUpLeg",    (0.00, -42.0, 0.00), False),
    ("RightFoot",   "RightLeg",      (0.00, -38.0, 0.00), False),
]

BVH_ORDER = [j[0] for j in BVH_JOINTS]

# Map BVH joint names → bone names in kinematics data
JOINT_BONE_MAP = {
    "Hips": "root", "Spine": "spine", "Chest": "chest",
    "Neck": "neck", "Head": "neck",
    "LeftArm": "l_shoulder", "LeftForeArm": "l_elbow", "LeftHand": "l_wrist",
    "RightArm": "r_shoulder", "RightForeArm": "r_elbow", "RightHand": "r_wrist",
    "LeftUpLeg": "l_hip", "LeftLeg": "l_knee", "LeftFoot": "l_ankle",
    "RightUpLeg": "r_hip", "RightLeg": "r_knee", "RightFoot": "r_ankle",
}

# Bone parent map for kinematic chain
_BONE_PARENTS = {
    "spine": "root", "chest": "spine", "neck": "chest",
    "l_shoulder": "chest", "l_elbow": "l_shoulder", "l_wrist": "l_elbow",
    "r_shoulder": "chest", "r_elbow": "r_shoulder", "r_wrist": "r_elbow",
    "l_hip": "root", "l_knee": "l_hip", "l_ankle": "l_knee",
    "r_hip": "root", "r_knee": "r_hip", "r_ankle": "r_knee",
}

def _write_hierarchy(lines, joints, parent=None, indent=0):
    """Recursively write the HIERARCHY section."""
    for jname, jparent, offset, is_root in joints:
        if jparent != parent:
            continue
        pad = "  " * indent
        has_children = any(j[1] == jname for j in joints)

        if is_root:
            lines.append(f"{pad}ROOT {jname}")
        else:
            lines.append(f"{pad}JOINT {jname}")

        lines.append(f"{pad}{{")
        lines.append(f"{pad}  OFFSET {offset[0]:.2f} {offset[1]:.2f} {offset[2]:.2f}")

        if is_root:
            lines.append(f"{pad}  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation")
        else:
            lines.append(f"{pad}  CHANNELS 3 Zrotation Yrotation Xrotation")

        if has_children:
            _write_hierarchy(lines, joints, jname, indent + 1)
        else:
            lines.append(f"{pad}  End Site")
            lines.append(f"{pad}  {{")
            lines.append(f"{pad}    OFFSET 0.00 5.00 0.00")
            lines.append(f"{pad}  }}")

        lines.append(f"{pad}}}")

def write_bvh(kin_frames: list, fps: float, session_name: str = "motion") -> str:
    """
    Generate BVH file content from kinematics frames.

    Args:
        kin_frames: list of frame dicts with 'euler_deg' field
        fps: frames per second
        session_name: name for the motion

    Returns:
        BVH file content as string
    """
    lines = ["HIERARCHY"]
    _write_hierarchy(lines, BVH_JOINTS, None, 0)
    lines.append("MOTION")
    lines.append(f"Frames: {len(kin_frames)}")
    lines.append(f"Frame Time: {1.0 / fps:.6f}")

    for fr in kin_frames:
        ed = fr.get("euler_deg", {})
        row = [0.0, 0.0, 0.0]  # root XYZ position

        for jname in BVH_ORDER:
            bone = JOINT_BONE_MAP.get(jname)
            angles = ed.get(bone, [0.0, 0.0, 0.0])
            row.extend([round(a, 4) for a in angles])

        lines.append(" ".join(map(str, row)))

    return "\n".join(lines)

def write_bvh_file(kin_frames, fps, path: str, session_name: str = "motion"):
    """Write BVH content directly to file."""
    bvh_str = write_bvh(kin_frames, fps, session_name)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(bvh_str)
    return path

class BVHWriter:
    """Backward compatibility class for scripts/verify.py and older routes."""
    def __init__(self, fps: int = 30):
        self.fps = fps

    def generate(self, frames_landmarks, output_path):
        from backend.services.kinematics.bone_vectors import compute_bone_vectors
        from backend.services.kinematics.euler_angles import bone_to_euler
        
        kin_frames = []
        prev_vecs = {}
        for idx, landmarks in enumerate(frames_landmarks):
            # Support formats like Landmark object, dict, or list
            lms_parsed = []
            for lm in landmarks:
                if hasattr(lm, 'x'):
                    lms_parsed.append(lm)
                elif isinstance(lm, dict):
                    lms_parsed.append(lm)
                else:
                    lms_parsed.append({"x": lm[0], "y": lm[1], "z": lm[2]})
                    
            bone_vecs = compute_bone_vectors(lms_parsed, prev_vecs)
            prev_vecs = bone_vecs
            
            euler_deg = {}
            for bone, bv in bone_vecs.items():
                parent_name = _BONE_PARENTS.get(bone)
                parent = bone_vecs.get(parent_name)
                _, e_deg = bone_to_euler(bv['dir'], parent['dir'] if parent else None)
                euler_deg[bone] = e_deg
                
            kin_frames.append({"euler_deg": euler_deg})
            
        write_bvh_file(kin_frames, self.fps, output_path)
        return output_path
