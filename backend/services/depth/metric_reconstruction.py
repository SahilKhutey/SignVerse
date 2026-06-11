"""
metric_reconstruction.py
========================
Reconstructs metric 3D coordinates from monocular depth and perception landmarks.
Performs pinhole back-projection and scale recovery to output coordinates in meters.
"""

from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .depth_estimator import DepthEstimator, DepthModel, DepthResult
from .metric_scaler import MetricScaleRecovery, ScaleAnchor
from .camera_intrinsics import CameraIntrinsics, CameraIntrinsicsEstimator

logger = logging.getLogger(__name__)

@dataclass
class MetricFrame:
    """
    Container for the reconstructed metric 3D data of a single frame.
    
    Attributes
    ----------
    frame_id : int
    timestamp_ms : float
    pose_33_metric : List[List[float]]
        33 joints [x, y, z] in meters (Y is up).
    left_hand_21_metric : List[List[float]]
        21 left hand joints [x, y, z] in meters.
    right_hand_21_metric : List[List[float]]
        21 right hand joints [x, y, z] in meters.
    objects_metric : List[Dict]
        Detected objects with fields: class, label, track_id, position_m, size_m, depth_m.
    depth_map : Optional[np.ndarray]
        2D depth map array.
    scale_factor : float
        Recovered scale factor (meters per normalized depth unit).
    scale_anchors : List[str]
        Names of scale anchors used in this frame.
    depth_confidence : float
        Average confidence score of the depth map.
    person_height_m : Optional[float]
        Estimated person height in meters.
    left_arm_length_m : Optional[float]
        Estimated left arm length in meters.
    right_arm_length_m : Optional[float]
        Estimated right arm length in meters.
    shoulder_width_m : Optional[float]
        Estimated shoulder width in meters.
    camera_intrinsics : Optional[Dict[str, Any]]
        Camera intrinsics dictionary representation.
    inference_time_ms : float
        Inference time for depth estimation.
    """
    frame_id: int
    timestamp_ms: float
    pose_33_metric: List[List[float]] = field(default_factory=list)
    left_hand_21_metric: List[List[float]] = field(default_factory=list)
    right_hand_21_metric: List[List[float]] = field(default_factory=list)
    objects_metric: List[Dict[str, Any]] = field(default_factory=list)
    depth_map: Optional[np.ndarray] = None
    scale_factor: float = 1.0
    scale_anchors: List[str] = field(default_factory=list)
    depth_confidence: float = 1.0
    person_height_m: Optional[float] = None
    left_arm_length_m: Optional[float] = None
    right_arm_length_m: Optional[float] = None
    shoulder_width_m: Optional[float] = None
    camera_intrinsics: Optional[Dict[str, Any]] = None
    inference_time_ms: float = 0.0

    def to_json_dict(self) -> Dict[str, Any]:
        """Convert MetricFrame to a serializable dictionary, excluding numpy arrays."""
        return {
            "frame_id": self.frame_id,
            "timestamp_ms": self.timestamp_ms,
            "pose_33_metric": self.pose_33_metric,
            "left_hand_21_metric": self.left_hand_21_metric,
            "right_hand_21_metric": self.right_hand_21_metric,
            "objects_metric": self.objects_metric,
            "scale_factor": self.scale_factor,
            "scale_anchors": self.scale_anchors,
            "depth_confidence": self.depth_confidence,
            "person_height_m": self.person_height_m,
            "left_arm_length_m": self.left_arm_length_m,
            "right_arm_length_m": self.right_arm_length_m,
            "shoulder_width_m": self.shoulder_width_m,
            "camera_intrinsics": self.camera_intrinsics,
            "inference_time_ms": self.inference_time_ms,
        }

    def measure_joint_distance(self, idx_a: int, idx_b: int) -> Optional[float]:
        """Compute Euclidean distance in meters between two pose joints."""
        if not self.pose_33_metric or idx_a >= len(self.pose_33_metric) or idx_b >= len(self.pose_33_metric):
            return None
        pt_a = self.pose_33_metric[idx_a]
        pt_b = self.pose_33_metric[idx_b]
        if not pt_a or not pt_b:
            return None
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pt_a, pt_b)))


class MetricReconstructor:
    """
    Main reconstruction engine combining depth estimation, intrinsics estimation,
    and scale recovery.
    """
    def __init__(
        self,
        enable_depth_model: bool = True,
        depth_model_name: str = "MiDaS_small",
        use_ensemble: bool = False
    ) -> None:
        self.enable_depth_model = enable_depth_model
        self.depth_model_name = depth_model_name
        self.use_ensemble = use_ensemble

        self._depth_estimator: Optional[DepthEstimator] = None
        if self.enable_depth_model:
            try:
                # Find matching DepthModel enum value
                enum_model = DepthModel.MIDAS_SMALL
                for m in DepthModel:
                    if m.value.lower() == depth_model_name.lower():
                        enum_model = m
                        break
                self._depth_estimator = DepthEstimator.get_instance(
                    model=enum_model,
                    enable_ensemble=self.use_ensemble
                )
            except Exception as e:
                logger.error("Failed to load depth estimator: %s. Proceeding without depth model.", e)
                self._depth_estimator = None

        self._scale_recovery = MetricScaleRecovery()
        self._intrinsics_estimator = CameraIntrinsicsEstimator()
        self._current_intrinsics: Optional[CameraIntrinsics] = None
        self._frame_count = 0

    def reconstruct_frame(
        self,
        frame: np.ndarray,
        perception: Any,
        frame_id: int = 0,
        timestamp_ms: float = 0.0
    ) -> MetricFrame:
        """
        Reconstruct a single frame's metric coordinate data.
        
        Parameters
        ----------
        frame : np.ndarray
            BGR image frame (H, W, 3).
        perception : Any
            Perception data (CompletePerceptionResult or dict) containing pose, hands, objects.
        frame_id : int
        timestamp_ms : float
        """
        h, w = (720, 1280)
        if frame is not None:
            h, w = frame.shape[:2]

        # 1. Depth Estimation
        depth_map = None
        depth_confidence = 1.0
        inference_time_ms = 0.0
        
        if self._depth_estimator is not None and frame is not None:
            try:
                depth_res = self._depth_estimator.estimate(frame)
                depth_map = depth_res.depth_map
                depth_confidence = float(np.mean(depth_res.confidence_map))
                inference_time_ms = depth_res.inference_time_ms
            except Exception as e:
                logger.error("Error running depth estimation: %s", e)

        # 2. Extract perception elements
        if hasattr(perception, "pose_33"):
            pose_33 = perception.pose_33
            left_hand = perception.left_hand_21
            right_hand = perception.right_hand_21
            objects = perception.objects
        elif isinstance(perception, dict):
            pose_33 = perception.get("pose_33", [])
            left_hand = perception.get("left_hand_21", [])
            right_hand = perception.get("right_hand_21", [])
            objects = perception.get("objects", [])
        else:
            pose_33 = getattr(perception, "pose", [])
            left_hand = getattr(perception, "left_hand", [])
            right_hand = getattr(perception, "right_hand", [])
            objects = getattr(perception, "objects", [])

        # Normalize formats: MediaPipe pose list or dict list
        pose_dicts = []
        for i, lm in enumerate(pose_33):
            if isinstance(lm, dict):
                pose_dicts.append(lm)
            else:
                pose_dicts.append({
                    "x": getattr(lm, "x", 0.0),
                    "y": getattr(lm, "y", 0.0),
                    "z": getattr(lm, "z", 0.0),
                    "visibility": getattr(lm, "visibility", getattr(lm, "v", 1.0))
                })

        # 3. Update Camera Intrinsics
        if self._current_intrinsics is None:
            self._intrinsics_estimator.width = w
            self._intrinsics_estimator.height = h
            self._current_intrinsics = self._intrinsics_estimator.default_webcam()

        if pose_dicts:
            self._current_intrinsics = self._intrinsics_estimator.update_from_new_frame(
                pose_dicts, person_height_m=1.70
            )

        # 4. Compute Scale Factor
        # Fallback depth_map if none produced
        if depth_map is None:
            depth_map = np.ones((h, w), dtype=np.float32) * 0.5

        scale, anchors = self._scale_recovery.compute_scale(
            depth_map=depth_map,
            pose_landmarks=self._convert_to_mp_format(pose_dicts),
            objects=objects,
            image_height=h,
            image_width=w
        )

        anchor_names = [a.name for a in anchors]

        # 5. Lift Landmarks to 3D Metric Coordinates
        pose_metric = self._lift_landmarks(pose_dicts, depth_map, self._current_intrinsics, scale, w, h)
        left_hand_metric = self._lift_landmarks(left_hand, depth_map, self._current_intrinsics, scale, w, h)
        right_hand_metric = self._lift_landmarks(right_hand, depth_map, self._current_intrinsics, scale, w, h)
        objects_metric = self._lift_objects(objects, depth_map, self._current_intrinsics, scale, w, h)

        # 6. Measure person biomechanics
        height_m = self._measure_height(pose_metric)
        left_arm_m = self._measure_arm(pose_metric, side="left")
        right_arm_m = self._measure_arm(pose_metric, side="right")
        shoulder_m = self._measure_shoulder_width(pose_metric)

        self._frame_count += 1

        return MetricFrame(
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            pose_33_metric=pose_metric,
            left_hand_21_metric=left_hand_metric,
            right_hand_21_metric=right_hand_metric,
            objects_metric=objects_metric,
            depth_map=depth_map,
            scale_factor=scale,
            scale_anchors=anchor_names,
            depth_confidence=depth_confidence,
            person_height_m=height_m,
            left_arm_length_m=left_arm_m,
            right_arm_length_m=right_arm_m,
            shoulder_width_m=shoulder_m,
            camera_intrinsics=self._current_intrinsics.to_dict() if self._current_intrinsics else None,
            inference_time_ms=inference_time_ms
        )

    def _convert_to_mp_format(self, pose_dicts: List[Dict[str, float]]) -> List[Any]:
        """Convert standard dict landmarks to mock objects with .x, .y, .visibility for MetricScaleRecovery."""
        class MockLandmark:
            def __init__(self, x, y, z, v):
                self.x = x
                self.y = y
                self.z = z
                self.visibility = v
        return [MockLandmark(lm.get("x", 0.0), lm.get("y", 0.0), lm.get("z", 0.0), lm.get("visibility", lm.get("v", 1.0))) for lm in pose_dicts]

    def _lift_landmarks(
        self,
        landmarks: List[Any],
        depth_map: np.ndarray,
        intrinsics: CameraIntrinsics,
        scale: float,
        width: int,
        height: int
    ) -> List[List[float]]:
        """
        Pinhole reprojection to back-project 2D points to 3D metric space.
        """
        metric_points = []
        fx, fy = intrinsics.fx, intrinsics.fy
        cx, cy = intrinsics.cx, intrinsics.cy

        for lm in landmarks:
            # Handle both dicts and class instances
            if isinstance(lm, dict):
                x_norm, y_norm = lm.get("x", 0.0), lm.get("y", 0.0)
                z_mp = lm.get("z", 0.0)
            else:
                x_norm = getattr(lm, "x", 0.0)
                y_norm = getattr(lm, "y", 0.0)
                z_mp = getattr(lm, "z", 0.0)

            # Convert to pixel coordinates
            px = int(np.clip(x_norm * width, 0, width - 1))
            py = int(np.clip(y_norm * height, 0, height - 1))

            # Sample absolute depth from depth map
            depth_z_rel = float(depth_map[py, px])
            depth_z = depth_z_rel * scale

            # Blend with MediaPipe relative Z to preserve local skeletal detail
            # MediaPipe Z is normalized relative to hips, so scaling it aligns it.
            z_final = 0.7 * depth_z + 0.3 * (depth_z + z_mp * scale)
            z_final = float(np.clip(z_final, 0.1, 15.0))

            # Reproject to 3D (Y up, standard coordinate system)
            x_m = (px - cx) * z_final / fx
            y_m = -(py - cy) * z_final / fy

            metric_points.append([x_m, y_m, z_final])

        return metric_points

    def _lift_objects(
        self,
        objects: List[Dict[str, Any]],
        depth_map: np.ndarray,
        intrinsics: CameraIntrinsics,
        scale: float,
        width: int,
        height: int
    ) -> List[Dict[str, Any]]:
        """
        Estimate 3D position and size of detected objects.
        """
        lifted_objects = []
        fx, fy = intrinsics.fx, intrinsics.fy
        cx, cy = intrinsics.cx, intrinsics.cy

        for obj in objects:
            bbox = obj.get("bbox")
            if bbox is None or len(bbox) < 4:
                continue

            bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]

            # 1. Determine depth using median value in bbox region
            x_min = int(np.clip(bx, 0, width - 1))
            y_min = int(np.clip(by, 0, height - 1))
            x_max = int(np.clip(bx + bw, 0, width - 1))
            y_max = int(np.clip(by + bh, 0, height - 1))

            if x_max > x_min and y_max > y_min:
                crop = depth_map[y_min:y_max, x_min:x_max]
                depth_z_rel = float(np.median(crop))
            else:
                depth_z_rel = 0.5

            depth_z = depth_z_rel * scale
            depth_z = float(np.clip(depth_z, 0.1, 15.0))

            # 2. Compute 3D position
            box_cx = bx + bw / 2.0
            box_cy = by + bh / 2.0
            x_m = (box_cx - cx) * depth_z / fx
            y_m = -(box_cy - cy) * depth_z / fy

            # 3. Compute metric size
            size_w = bw * depth_z / fx
            size_h = bh * depth_z / fy
            # Assume depth of object is average of width and height as prior
            size_d = (size_w + size_h) / 2.0

            lifted_objects.append({
                "class": obj.get("class", obj.get("label", "unknown")),
                "label": obj.get("label", obj.get("class", "unknown")),
                "track_id": obj.get("track_id", -1),
                "position_m": [x_m, y_m, depth_z],
                "size_m": [size_w, size_h, size_d],
                "depth_m": depth_z,
                "confidence": obj.get("score", obj.get("confidence", 1.0))
            })

        return lifted_objects

    def _measure_height(self, pose_3d: List[List[float]]) -> Optional[float]:
        """Nose-to-midpoint-of-ankles distance + 0.12m head offset."""
        if len(pose_3d) < 33:
            return None
        
        nose = pose_3d[0]
        l_ankle = pose_3d[27]
        r_ankle = pose_3d[28]

        if not nose or not l_ankle or not r_ankle:
            return None

        mid_ankle_x = 0.5 * (l_ankle[0] + r_ankle[0])
        mid_ankle_y = 0.5 * (l_ankle[1] + r_ankle[1])
        mid_ankle_z = 0.5 * (l_ankle[2] + r_ankle[2])

        dist = math.sqrt(
            (nose[0] - mid_ankle_x) ** 2 +
            (nose[1] - mid_ankle_y) ** 2 +
            (nose[2] - mid_ankle_z) ** 2
        )
        return float(dist + 0.12)  # NASA MSIS standard head offset from nose to crown

    def _measure_arm(self, pose_3d: List[List[float]], side: str = "right") -> Optional[float]:
        """Shoulder-to-wrist distance."""
        if len(pose_3d) < 33:
            return None
        
        if side == "left":
            shoulder = pose_3d[11]
            elbow = pose_3d[13]
            wrist = pose_3d[15]
        else:
            shoulder = pose_3d[12]
            elbow = pose_3d[14]
            wrist = pose_3d[16]

        if not shoulder or not elbow or not wrist:
            return None

        upper_arm = math.sqrt(sum((a - b) ** 2 for a, b in zip(shoulder, elbow)))
        forearm = math.sqrt(sum((a - b) ** 2 for a, b in zip(elbow, wrist)))
        return float(upper_arm + forearm)

    def _measure_shoulder_width(self, pose_3d: List[List[float]]) -> Optional[float]:
        """Distance between left and right shoulder."""
        if len(pose_3d) < 33:
            return None
        
        l_shoulder = pose_3d[11]
        r_shoulder = pose_3d[12]

        if not l_shoulder or not r_shoulder:
            return None

        return float(math.sqrt(sum((a - b) ** 2 for a, b in zip(l_shoulder, r_shoulder))))

    def get_session_stats(self) -> Dict[str, Any]:
        """Retrieve metrics stability statistics."""
        return self._scale_recovery.get_stats()

    def reset(self) -> None:
        """Reset scale recovery and current frame stats."""
        self._scale_recovery.reset()
        self._current_intrinsics = None
        self._frame_count = 0
