"""
SignVerse Depth Estimation Package
===================================
Monocular depth → metric 3D reconstruction pipeline.

Sub-modules
-----------
depth_estimator      : Neural-network based monocular depth estimation
                       (MiDaS, DPT, Depth-Anything).
metric_scaler        : Recovers the unknown scale factor that converts
                       relative depth into metric (SI) units using
                       human-body proportions and COCO object priors.
camera_intrinsics    : Focal-length / principal-point estimation from
                       EXIF data, known sensor sizes, or heuristics.
metric_reconstruction: Combines depth map + intrinsics + scale to
                       produce metric 3-D point clouds.
"""

from .depth_estimator import DepthEstimator, DepthResult, DepthModel
from .metric_scaler import (
    MetricScaleRecovery,
    ScaleAnchor,
    ADULT_HUMAN_PROPORTIONS,
    OBJECT_REFERENCE_SIZES,
)
from .camera_intrinsics import CameraIntrinsics, CameraIntrinsicsEstimator
from .metric_reconstruction import MetricReconstructor, MetricFrame

__all__ = [
    # depth_estimator
    "DepthEstimator",
    "DepthResult",
    "DepthModel",
    # metric_scaler
    "MetricScaleRecovery",
    "ScaleAnchor",
    "ADULT_HUMAN_PROPORTIONS",
    "OBJECT_REFERENCE_SIZES",
    # camera_intrinsics
    "CameraIntrinsics",
    "CameraIntrinsicsEstimator",
    # metric_reconstruction
    "MetricReconstructor",
    "MetricFrame",
]
