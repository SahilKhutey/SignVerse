import json
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from backend.models.database import MotionSession, MotionFrame


@dataclass
class UnifiedMotionData:
    """
    Complete, normalized representation of a motion session.
    All exporters consume this. Decouples DB schema from export format.
    v6: Extended with metric (real-world meter) fields from depth estimation.
    """
    # Metadata
    session_id: str
    session_name: str
    fps: float
    frame_count: int
    duration_s: float
    source_type: str
    action_label: str
    intent: str
    created_at: str

    # Joint names (canonical order)
    joint_names: List[str] = field(default_factory=list)

    # Per-frame data (parallel arrays, index = frame)
    timestamps_ms: List[float] = field(default_factory=list)
    root_positions: List[List[float]] = field(default_factory=list)  # [x,y,z] per frame
    joint_angles_rad: List[Dict[str, List[float]]] = field(default_factory=list)  # joint → [rx,ry,rz]
    joint_angles_deg: List[Dict[str, List[float]]] = field(default_factory=list)
    joint_angles_quat: List[Dict[str, List[float]]] = field(default_factory=list)  # joint → [w,x,y,z]
    joint_positions_3d: List[Dict[str, List[float]]] = field(default_factory=list)  # joint → [x,y,z] (normalized)
    bone_lengths: Dict[str, float] = field(default_factory=dict)  # Reference T-pose lengths (normalized)
    confidence_per_frame: List[float] = field(default_factory=list)

    # Rich context (per frame)
    actions_per_frame: List[str] = field(default_factory=list)  # Action primitive per frame
    intents_per_frame: List[str] = field(default_factory=list)
    interactions_per_frame: List[Dict] = field(default_factory=list)  # Hand-object contacts

    # ── Metric (real-world) fields ── populated if depth estimation was run
    metric_positions_3d: List[Dict[str, List[float]]] = field(default_factory=list)  # joint → [x,y,z] in metres
    metric_pose_33: List[List[List[float]]] = field(default_factory=list)            # 33 lm × [x,y,z] metres
    metric_objects: List[List[Dict]] = field(default_factory=list)                   # per-frame object metrics
    bone_lengths_metric: Dict[str, float] = field(default_factory=dict)              # bone lengths in metres
    person_height_m: Optional[float] = None
    left_arm_length_m: Optional[float] = None
    right_arm_length_m: Optional[float] = None
    shoulder_width_m: Optional[float] = None
    scale_factor_mean: Optional[float] = None
    scale_factor_std: Optional[float] = None
    camera_intrinsics: Optional[Dict] = None   # {fx, fy, cx, cy, fov_x_deg, fov_y_deg}
    has_metric_data: bool = False

    @property
    def num_frames(self) -> int:
        return len(self.timestamps_ms)

    def get_joint_trajectory(self, joint_name: str, representation: str = "rad") -> np.ndarray:
        """Get a single joint's full trajectory as numpy array."""
        if representation == "rad":
            return np.array([f[joint_name] for f in self.joint_angles_rad])
        elif representation == "deg":
            return np.array([f[joint_name] for f in self.joint_angles_deg])
        elif representation == "quat":
            return np.array([f[joint_name] for f in self.joint_angles_quat])
        elif representation == "pos":
            return np.array([f[joint_name] for f in self.joint_positions_3d])
        elif representation == "metric":
            return np.array([f.get(joint_name, [0,0,0]) for f in self.metric_positions_3d])
        raise ValueError(f"Unknown representation: {representation}")

    def get_bone_length_m(self, bone_name: str) -> float:
        """Return bone length in metres. Falls back to normalized * scale if no metric data."""
        if bone_name in self.bone_lengths_metric:
            return self.bone_lengths_metric[bone_name]
        if self.scale_factor_mean and bone_name in self.bone_lengths:
            return self.bone_lengths[bone_name] * self.scale_factor_mean
        return 0.0



# Canonical 19-joint skeleton (BVH-compatible)
CANONICAL_JOINTS = [
    "Hips",
    "Spine", "Chest", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot",
    "RightUpLeg", "RightLeg", "RightFoot",
]


class SessionDataLoader:
    """Loads session data from DB and builds UnifiedMotionData."""

    def load(self, session_id: str, db: Session) -> UnifiedMotionData:
        """Load and normalize a session into UnifiedMotionData."""
        session = db.query(MotionSession).filter_by(id=session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        frames_db = (db.query(MotionFrame)
                     .filter_by(session_id=session_id)
                     .order_by(MotionFrame.frame_idx)
                     .all())

        if not frames_db:
            raise ValueError(f"No frames in session {session_id}")

        data = UnifiedMotionData(
            session_id=session.id,
            session_name=session.name,
            fps=session.fps or 30.0,
            frame_count=session.frame_count,
            duration_s=session.duration_s or 0.0,
            source_type=session.source_type,
            action_label=session.action_label,
            intent=getattr(session, 'primary_intent', 'UNKNOWN'),
            created_at=session.created_at.isoformat() if session.created_at else "",
            joint_names=CANONICAL_JOINTS.copy(),
        )

        for f in frames_db:
            kin = json.loads(f.kinematics_json) if f.kinematics_json else {}
            perc = json.loads(f.perception_json) if f.perception_json else {}
            met = json.loads(f.metric_json) if getattr(f, 'metric_json', None) else {}

            data.timestamps_ms.append(f.timestamp_ms)
            data.confidence_per_frame.append(f.confidence_mean or 0.0)

            # Extract per-joint angles
            angles_rad = {}
            angles_deg = {}
            angles_quat = {}
            positions_3d = {}

            # Map kinematics data to canonical joints
            joint_map = self._build_joint_map(kin, perc)

            for joint_name in CANONICAL_JOINTS:
                key = joint_map.get(joint_name, joint_name)
                angles_rad[joint_name] = kin.get("euler_rad", {}).get(key, [0.0, 0.0, 0.0])
                angles_deg[joint_name] = kin.get("euler_deg", {}).get(key, [0.0, 0.0, 0.0])
                angles_quat[joint_name] = kin.get("quaternions", {}).get(key, [1.0, 0.0, 0.0, 0.0])
                positions_3d[joint_name] = [0.0, 0.0, 0.0]

            # Reconstruct 3D joint positions from perception landmarks
            pose = perc.get("pose", [])
            if len(pose) >= 33:
                # Compute hip center
                l_hip_lm = pose[23]
                r_hip_lm = pose[24]
                hip_center_x = (l_hip_lm.get("x", 0.0) + r_hip_lm.get("x", 0.0)) / 2.0
                hip_center_y = (l_hip_lm.get("y", 0.0) + r_hip_lm.get("y", 0.0)) / 2.0
                hip_center_z = (l_hip_lm.get("z", 0.0) + r_hip_lm.get("z", 0.0)) / 2.0
                
                # Torso height normalization (so hips to nose is approx 1.0 unit)
                nose = pose[0]
                height = abs(hip_center_y - nose.get("y", 0.0)) + 1e-6
                scale = 1.0 / height
                
                # Scale and center all pose landmarks
                pose_scaled = []
                for lm in pose:
                    pose_scaled.append({
                        "x": (lm.get("x", 0.0) - hip_center_x) * scale,
                        "y": -(lm.get("y", 0.0) - hip_center_y) * scale,  # Flip upright
                        "z": (lm.get("z", 0.0) - hip_center_z) * scale
                    })
                
                # Midpoints
                hips_pos = [0.0, 0.0, 0.0]
                l_sh = [pose_scaled[11]["x"], pose_scaled[11]["y"], pose_scaled[11]["z"]]
                r_sh = [pose_scaled[12]["x"], pose_scaled[12]["y"], pose_scaled[12]["z"]]
                chest_pos = [
                    (l_sh[0] + r_sh[0]) / 2.0,
                    (l_sh[1] + r_sh[1]) / 2.0,
                    (l_sh[2] + r_sh[2]) / 2.0
                ]
                spine_pos = [
                    (hips_pos[0] + chest_pos[0]) / 2.0,
                    (hips_pos[1] + chest_pos[1]) / 2.0,
                    (hips_pos[2] + chest_pos[2]) / 2.0
                ]
                neck_pos = [
                    chest_pos[0],
                    chest_pos[1] + 0.1,
                    chest_pos[2]
                ]
                
                def get_p(idx):
                    lm = pose_scaled[idx]
                    return [lm["x"], lm["y"], lm["z"]]
                
                positions_3d = {
                    "Hips": hips_pos,
                    "Spine": spine_pos,
                    "Chest": chest_pos,
                    "Neck": neck_pos,
                    "Head": get_p(0),
                    "LeftShoulder": get_p(11),
                    "LeftArm": get_p(13),
                    "LeftForeArm": get_p(15),
                    "LeftHand": get_p(19) if len(pose_scaled) > 19 else get_p(15),
                    "RightShoulder": get_p(12),
                    "RightArm": get_p(14),
                    "RightForeArm": get_p(16),
                    "RightHand": get_p(20) if len(pose_scaled) > 20 else get_p(16),
                    "LeftUpLeg": get_p(23),
                    "LeftLeg": get_p(25),
                    "LeftFoot": get_p(27),
                    "RightUpLeg": get_p(24),
                    "RightLeg": get_p(26),
                    "RightFoot": get_p(28),
                }
            else:
                # Default T-pose positions
                positions_3d = {
                    "Hips": [0.0, 0.0, 0.0],
                    "Spine": [0.0, 0.2, 0.0],
                    "Chest": [0.0, 0.4, 0.0],
                    "Neck": [0.0, 0.5, 0.0],
                    "Head": [0.0, 0.6, 0.0],
                    "LeftShoulder": [-0.15, 0.4, 0.0],
                    "LeftArm": [-0.35, 0.4, 0.0],
                    "LeftForeArm": [-0.55, 0.4, 0.0],
                    "LeftHand": [-0.65, 0.4, 0.0],
                    "RightShoulder": [0.15, 0.4, 0.0],
                    "RightArm": [0.35, 0.4, 0.0],
                    "RightForeArm": [0.55, 0.4, 0.0],
                    "RightHand": [0.65, 0.4, 0.0],
                    "LeftUpLeg": [-0.1, -0.1, 0.0],
                    "LeftLeg": [-0.1, -0.5, 0.0],
                    "LeftFoot": [-0.1, -0.8, 0.0],
                    "RightUpLeg": [0.1, -0.1, 0.0],
                    "RightLeg": [0.1, -0.5, 0.0],
                    "RightFoot": [0.1, -0.8, 0.0],
                }

            data.joint_angles_rad.append(angles_rad)
            data.joint_angles_deg.append(angles_deg)
            data.joint_angles_quat.append(angles_quat)
            data.joint_positions_3d.append(positions_3d)

            # Root position
            # If not in kin, default to the translated hips position (hips_pos is centered, so we can use [0,0,0])
            root_pos = kin.get("root_position", [0.0, 0.0, 0.0])
            data.root_positions.append(root_pos)

            # Per-frame context
            data.actions_per_frame.append(kin.get("primary_action", session.action_label or "IDLE"))
            data.intents_per_frame.append(kin.get("primary_intent", perc.get("intent", "UNKNOWN")))

            # Interaction graph
            if "interaction_graph" in kin:
                data.interactions_per_frame.append(kin["interaction_graph"])
            elif "objects" in perc:
                data.interactions_per_frame.append({"objects": perc["objects"]})
            else:
                data.interactions_per_frame.append({})

        # Compute reference bone lengths (T-pose) from first valid frame
        if data.joint_positions_3d:
            first_frame = data.joint_positions_3d[0]
            for joint_name, pos in first_frame.items():
                data.bone_lengths[joint_name] = float(np.linalg.norm(np.array(pos)))

        # ── Load metric data from session-level columns (if available) ──
        data.has_metric_data = bool(getattr(session, 'has_metric_data', False))
        if data.has_metric_data:
            data.person_height_m  = getattr(session, 'person_height_m', None)
            data.scale_factor_mean = getattr(session, 'scale_factor_mean', None)
            data.scale_factor_std  = getattr(session, 'scale_factor_std', None)
            intr_json = getattr(session, 'camera_intrinsics_json', None)
            if intr_json:
                try:
                    data.camera_intrinsics = json.loads(intr_json)
                except Exception:
                    pass

        # ── Load per-frame metric data from metric_json column ──
        metric_heights = []
        for i, f in enumerate(frames_db):
            raw = getattr(f, 'metric_json', None)
            if not raw:
                continue
            try:
                met = json.loads(raw)
            except Exception:
                continue

            # 33-landmark metric positions
            if "pose_33_metric" in met:
                data.metric_pose_33.append(met["pose_33_metric"])

            # Canonical joint map from metric 33 landmarks
            mp33 = met.get("pose_33_metric", [])
            if len(mp33) >= 29:
                # Build canonical joint positions in metric space
                _lm = lambda idx: mp33[idx] if idx < len(mp33) else [0.0, 0.0, 0.0]
                hip_m = [
                    (_lm(23)[0] + _lm(24)[0]) / 2,
                    (_lm(23)[1] + _lm(24)[1]) / 2,
                    (_lm(23)[2] + _lm(24)[2]) / 2,
                ]
                chest_m = [
                    (_lm(11)[0] + _lm(12)[0]) / 2,
                    (_lm(11)[1] + _lm(12)[1]) / 2,
                    (_lm(11)[2] + _lm(12)[2]) / 2,
                ]
                metric_joint_pos = {
                    "Hips":          hip_m,
                    "Spine":         [hip_m[i]*0.5 + chest_m[i]*0.5 for i in range(3)],
                    "Chest":         chest_m,
                    "Neck":          [chest_m[0], chest_m[1] + 0.05, chest_m[2]],
                    "Head":          _lm(0),
                    "LeftShoulder":  _lm(11),
                    "LeftArm":       _lm(13),
                    "LeftForeArm":   _lm(15),
                    "LeftHand":      _lm(19) if len(mp33) > 19 else _lm(15),
                    "RightShoulder": _lm(12),
                    "RightArm":      _lm(14),
                    "RightForeArm":  _lm(16),
                    "RightHand":     _lm(20) if len(mp33) > 20 else _lm(16),
                    "LeftUpLeg":     _lm(23),
                    "LeftLeg":       _lm(25),
                    "LeftFoot":      _lm(27),
                    "RightUpLeg":    _lm(24),
                    "RightLeg":      _lm(26),
                    "RightFoot":     _lm(28),
                }
                data.metric_positions_3d.append(metric_joint_pos)

            # Objects
            if "objects_metric" in met:
                data.metric_objects.append(met["objects_metric"])

            # Height
            h_m = met.get("person_height_m")
            if h_m:
                metric_heights.append(h_m)

        # Aggregate session measurements
        if metric_heights:
            data.person_height_m = float(np.median(metric_heights))

        # Compute metric bone lengths from first valid metric frame
        if data.metric_positions_3d:
            mf = data.metric_positions_3d[0]
            joints_list = list(CANONICAL_JOINTS)
            for j, joint in enumerate(joints_list[:-1]):
                next_j = joints_list[j + 1]
                if joint in mf and next_j in mf:
                    p0 = np.array(mf[joint])
                    p1 = np.array(mf[next_j])
                    data.bone_lengths_metric[f"{joint}_{next_j}"] = round(float(np.linalg.norm(p0 - p1)), 4)

        return data

    def _build_joint_map(self, kin: Dict, perc: Dict) -> Dict[str, str]:
        """Map our internal joint names to kinematics data keys."""
        return {
            "Hips": "hips",
            "Spine": "spine", "Chest": "chest", "Neck": "neck", "Head": "head",
            "LeftShoulder": "l_shoulder", "LeftArm": "l_elbow",
            "LeftForeArm": "l_wrist", "LeftHand": "l_wrist",
            "RightShoulder": "r_shoulder", "RightArm": "r_elbow",
            "RightForeArm": "r_wrist", "RightHand": "r_wrist",
            "LeftUpLeg": "l_hip", "LeftLeg": "l_knee", "LeftFoot": "l_ankle",
            "RightUpLeg": "r_hip", "RightLeg": "r_knee", "RightFoot": "r_ankle",
        }
