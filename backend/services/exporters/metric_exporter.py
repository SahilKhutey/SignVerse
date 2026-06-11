"""
metric_exporter.py
==================
Exports 3D metric skeletal reconstruction data to JSON and CSV formats.
Features session statistics aggregation and biomechanical measurements logging.
"""

from __future__ import annotations
import csv
import io
import logging
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

class MetricExporter:
    """
    Export pipeline for metric 3D data.
    Provides standard JSON and CSV format outputs of joints and measurements.
    """
    @staticmethod
    def compute_session_measurements(metric_frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate biomechanical measurements across all frames to get statistical summary.
        """
        heights = []
        l_arms = []
        r_arms = []
        shoulders = []
        scales = []

        for f in metric_frames:
            h = f.get("person_height_m")
            la = f.get("left_arm_length_m") or f.get("left_arm_m")
            ra = f.get("right_arm_length_m") or f.get("right_arm_m")
            sh = f.get("shoulder_width_m") or f.get("shoulder_m")
            sc = f.get("scale_factor")

            if h is not None: heights.append(h)
            if la is not None: l_arms.append(la)
            if ra is not None: r_arms.append(ra)
            if sh is not None: shoulders.append(sh)
            if sc is not None: scales.append(sc)

        def get_stats(vals: List[float]) -> Dict[str, float]:
            if not vals:
                return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
            arr = np.array(vals, dtype=np.float64)
            return {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr))
            }

        return {
            "person_height_m": get_stats(heights),
            "left_arm_m": get_stats(l_arms),
            "right_arm_m": get_stats(r_arms),
            "shoulder_width_m": get_stats(shoulders),
            "scale_factor": get_stats(scales)
        }

    @staticmethod
    def export_metric_json(session_name: str, metric_frames: List[Dict[str, Any]], session_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate structured JSON export for the entire metric session.
        """
        measurements = MetricExporter.compute_session_measurements(metric_frames)
        
        # Calculate scale stability
        history_std = measurements["scale_factor"]["std"]
        stability_score = 1.0 / (history_std + 0.01)

        # Standard session details
        fps = float(session_stats.get("fps", 30.0)) if session_stats else 30.0
        frame_count = len(metric_frames)
        duration_s = round(frame_count / fps, 2) if fps > 0 else 0.0

        # Export list of frames with minimal/clean keys
        clean_frames = []
        for f in metric_frames:
            clean_frames.append({
                "frame_id": f.get("frame_id", 0),
                "timestamp_ms": f.get("timestamp_ms", 0.0),
                "pose_33_metric": f.get("pose_33_metric", []),
                "left_hand_21_metric": f.get("left_hand_21_metric", []),
                "right_hand_21_metric": f.get("right_hand_21_metric", []),
                "objects_metric": f.get("objects_metric", []),
                "scale_factor": f.get("scale_factor", 1.0)
            })

        return {
            "session": {
                "name": session_name,
                "frame_count": frame_count,
                "fps": fps,
                "duration_s": duration_s,
                "person_height_m": measurements["person_height_m"]["mean"],
                "scale_factor": measurements["scale_factor"]["mean"]
            },
            "measurements": {
                "person_height_m": measurements["person_height_m"],
                "left_arm_m": measurements["left_arm_m"],
                "right_arm_m": measurements["right_arm_m"],
                "shoulder_width_m": measurements["shoulder_width_m"],
                "scale_stability": stability_score
            },
            "frames": clean_frames
        }

    @staticmethod
    def export_csv_metric(metric_frames: List[Dict[str, Any]]) -> str:
        """
        Generate a CSV string with frame IDs, timestamps, and joint X,Y,Z coords (33 joints).
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Build CSV Header
        header = ["frame_id", "timestamp_ms"]
        for i in range(33):
            header.extend([f"joint_{i}_x", f"joint_{i}_y", f"joint_{i}_z"])
        writer.writerow(header)

        for f in metric_frames:
            row = [f.get("frame_id", 0), f.get("timestamp_ms", 0.0)]
            pose = f.get("pose_33_metric", [])
            
            # Fill landmarks
            for i in range(33):
                if i < len(pose) and pose[i]:
                    row.extend([pose[i][0], pose[i][1], pose[i][2]])
                else:
                    row.extend([0.0, 0.0, 0.0])
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_measurements_csv(metric_frames: List[Dict[str, Any]]) -> str:
        """
        Generate a CSV string compiling the session measurements per frame.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "frame_id",
            "person_height_m",
            "left_arm_m",
            "right_arm_m",
            "shoulder_width_m",
            "scale_factor"
        ])

        for f in metric_frames:
            la = f.get("left_arm_length_m") or f.get("left_arm_m") or 0.0
            ra = f.get("right_arm_length_m") or f.get("right_arm_m") or 0.0
            sh = f.get("shoulder_width_m") or f.get("shoulder_m") or 0.0
            writer.writerow([
                f.get("frame_id", 0),
                f.get("person_height_m", 0.0),
                la,
                ra,
                sh,
                f.get("scale_factor", 1.0)
            ])

        return output.getvalue()
