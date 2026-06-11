import numpy as np

def compute_bone_vectors(pose, prev_vecs=None):
    """
    Computes direction vectors, length, and temporal velocities for a custom joint map.
    Matches the schema requirements for kinematics frame JSON.
    """
    if prev_vecs is None:
        prev_vecs = {}

    def get_coord(lm):
        if hasattr(lm, 'x'):
            return np.array([lm.x, lm.y, lm.z])
        elif isinstance(lm, dict):
            return np.array([lm.get('x', 0.0), lm.get('y', 0.0), lm.get('z', 0.0)])
        else:
            return np.array([0.0, 0.0, 0.0])

    if len(pose) < 33:
        return {}

    # Standard landmarks
    l_shoulder = get_coord(pose[11])
    r_shoulder = get_coord(pose[12])
    l_elbow = get_coord(pose[13])
    r_elbow = get_coord(pose[14])
    l_wrist = get_coord(pose[15])
    r_wrist = get_coord(pose[16])
    l_hip = get_coord(pose[23])
    r_hip = get_coord(pose[24])
    l_knee = get_coord(pose[25])
    r_knee = get_coord(pose[26])
    l_ankle = get_coord(pose[27])
    r_ankle = get_coord(pose[28])
    nose = get_coord(pose[0])

    # Left/Right indices for hand/foot direction vectors
    l_index = get_coord(pose[19]) if len(pose) > 19 else l_wrist
    r_index = get_coord(pose[20]) if len(pose) > 20 else r_wrist
    l_heel = get_coord(pose[29]) if len(pose) > 29 else l_ankle
    r_heel = get_coord(pose[30]) if len(pose) > 30 else r_ankle

    root = (l_hip + r_hip) / 2.0
    shoulder_center = (l_shoulder + r_shoulder) / 2.0
    mid_torso = (root + shoulder_center) / 2.0

    # Define bones as (parent_pos, child_pos)
    bone_joints = {
        "spine": (root, mid_torso),
        "chest": (mid_torso, shoulder_center),
        "neck": (shoulder_center, nose),
        "l_shoulder": (l_shoulder, l_elbow),
        "l_elbow": (l_elbow, l_wrist),
        "l_wrist": (l_wrist, l_index),
        "r_shoulder": (r_shoulder, r_elbow),
        "r_elbow": (r_elbow, r_wrist),
        "r_wrist": (r_wrist, r_index),
        "l_hip": (l_hip, l_knee),
        "l_knee": (l_knee, l_ankle),
        "l_ankle": (l_ankle, l_heel),
        "r_hip": (r_hip, r_knee),
        "r_knee": (r_knee, r_ankle),
        "r_ankle": (r_ankle, r_heel),
    }

    bone_vectors = {}
    for bone_name, (p_pos, c_pos) in bone_joints.items():
        vec = c_pos - p_pos
        length = float(np.linalg.norm(vec))
        direction = vec / (length + 1e-8)

        # Compute velocity relative to previous direction vector
        prev_dir = prev_vecs.get(bone_name, {}).get("dir", direction)
        vel = list(direction - prev_dir)

        bone_vectors[bone_name] = {
            "dir": list(direction),
            "len": length,
            "vel": vel
        }

    return bone_vectors
