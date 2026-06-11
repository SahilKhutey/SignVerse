import numpy as np

def segment_actions(kin_frames, fps):
    """
    Scans kin_frames using velocity thresholds to segment them into action windows.
    Rules:
    - wrist_vel > 0.15 -> GESTURE
    - hip_y_vel > 0.08 -> SIT_STAND
    - foot_cyclic (foot velocity > 0.12) -> WALK
    - else -> IDLE
    """
    if not kin_frames:
        return []

    labels = []
    for fr in kin_frames:
        bone_vecs = fr.get("bone_vectors", {})
        
        # Get wrist velocities
        l_wrist_vel = np.linalg.norm(bone_vecs.get("l_wrist", {}).get("vel", [0, 0, 0]))
        r_wrist_vel = np.linalg.norm(bone_vecs.get("r_wrist", {}).get("vel", [0, 0, 0]))
        wrist_vel = max(l_wrist_vel, r_wrist_vel)

        # Get hip velocities
        l_hip_vel = np.linalg.norm(bone_vecs.get("l_hip", {}).get("vel", [0, 0, 0]))
        r_hip_vel = np.linalg.norm(bone_vecs.get("r_hip", {}).get("vel", [0, 0, 0]))
        hip_vel = max(l_hip_vel, r_hip_vel)

        # Get ankle (foot) velocities
        l_ankle_vel = np.linalg.norm(bone_vecs.get("l_ankle", {}).get("vel", [0, 0, 0]))
        r_ankle_vel = np.linalg.norm(bone_vecs.get("r_ankle", {}).get("vel", [0, 0, 0]))
        foot_vel = max(l_ankle_vel, r_ankle_vel)

        # Determine action classification
        if hip_vel > 0.08:
            labels.append("SIT_STAND")
        elif foot_vel > 0.12:
            labels.append("WALK")
        elif wrist_vel > 0.15:
            labels.append("GESTURE")
        else:
            labels.append("IDLE")

    # Group frame labels into contiguous segments
    segments = []
    if not labels:
        return segments

    curr_label = labels[0]
    start_idx = 0
    for idx, lbl in enumerate(labels):
        if lbl != curr_label:
            segments.append({
                "action": curr_label,
                "start_frame": start_idx,
                "end_frame": idx - 1
            })
            curr_label = lbl
            start_idx = idx

    # Append the trailing segment
    segments.append({
        "action": curr_label,
        "start_frame": start_idx,
        "end_frame": len(labels) - 1
    })

    return segments
