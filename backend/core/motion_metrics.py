"""
Dataset analytics: aggregate metrics across all sessions.
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
from collections import Counter
from .database import db
from .action_segmenter import ActionSegmenter


class MotionMetrics:
    """Compute analytics across the full dataset."""

    def __init__(self):
        self.segmenter = ActionSegmenter()

    def compute_full_analytics(self) -> Dict:
        """Compute comprehensive dataset analytics."""
        sessions = db.list_sessions(limit=1000)
        if not sessions:
            return {"empty": True}

        # Per-session analytics
        session_analytics = []
        all_actions = []
        motion_intensities = []
        bone_lengths = []

        for s in sessions:
            s_analytics = self._analyze_session(s)
            session_analytics.append(s_analytics)
            all_actions.extend(s_analytics.get("actions", []))
            motion_intensities.append(s_analytics.get("avg_motion", 0))
            bone_lengths.extend(s_analytics.get("bone_lengths", []))

        # Aggregate
        action_dist = Counter(all_actions)
        avg_intensity = float(np.mean(motion_intensities)) if motion_intensities else 0

        return {
            "summary": {
                "total_sessions": len(sessions),
                "total_frames": sum(s["frame_count"] for s in sessions),
                "total_duration_sec": sum(s["duration_sec"] for s in sessions),
                "avg_motion_intensity": round(avg_intensity, 2),
                "sources": dict(Counter(s["source"] for s in sessions)),
                "labels": dict(Counter(s["action_label"] for s in sessions)),
            },
            "action_distribution": dict(action_dist),
            "top_actions": action_dist.most_common(10),
            "sessions": session_analytics,
        }

    def _analyze_session(self, session: Dict) -> Dict:
        """Analyze a single session in detail."""
        skeleton_path = session.get("skeleton_json_path")
        result = {
            "session_id": session["session_id"],
            "filename": session.get("filename"),
            "frame_count": session.get("frame_count", 0),
            "duration_sec": session.get("duration_sec", 0),
            "source": session.get("source"),
            "action_label": session.get("action_label"),
            "actions": [],
            "avg_motion": 0,
            "bone_lengths": [],
        }

        if not skeleton_path or not Path(skeleton_path).exists():
            return result

        try:
            with open(skeleton_path) as f:
                data = json.load(f)
            frames = data.get("frames", [])
            if not frames:
                return result

            # Extract landmarks
            landmarks_seq = [f.get("pose_33", []) for f in frames]

            # Action segmentation
            segments = self.segmenter.segment_sequence(landmarks_seq)
            result["actions"] = [s.action for s in segments]
            result["segments"] = [s.to_dict() for s in segments]

            # Motion intensity (variance of landmark positions)
            if landmarks_seq and landmarks_seq[0]:
                all_x = []
                all_y = []
                for lms in landmarks_seq:
                    for lm in lms:
                        all_x.append(lm.get("x", 0))
                        all_y.append(lm.get("y", 0))
                result["avg_motion"] = float(np.std(all_x) + np.std(all_y))

            # Bone lengths (sample)
            if landmarks_seq and len(landmarks_seq[0]) >= 33:
                from .skeleton_graph import SkeletonGraph
                from .kinematics import Kinematics
                graph = SkeletonGraph()
                kin = Kinematics()
                lengths = kin.compute_bone_lengths(landmarks_seq[0])
                result["bone_lengths"] = list(lengths.values())[:10]

        except Exception as e:
            result["error"] = str(e)

        return result
