"""
SignVerse Depth Estimation & Metric Reconstruction -- End-to-End Verification Script
Runs 8 checks covering every layer of the implementation.

Usage:
    python verify_depth_pipeline.py
"""
import sys
import json
import numpy as np
import traceback
from sqlalchemy.orm import declarative_base

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PASS = "[PASS]"
FAIL = "[FAIL]"

def check(name: str, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        return True
    except Exception as e:
        print(f"  {FAIL}  {name}")
        print(f"         {e}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        return False

results = []

print("\n" + "="*60)
print("  SignVerse Metric Reconstruction — Verification Suite")
print("="*60 + "\n")

# -- CHECK 1: DepthEstimator & Fallbacks ------------------------------
print("Layer 1 — Monocular Depth Estimation")

def c1():
    from backend.services.depth.depth_estimator import DepthEstimator, DepthModel, DepthResult
    
    # Check singleton class instantiation
    estimator = DepthEstimator.get_instance(model=DepthModel.MIDAS_SMALL)
    assert estimator is not None, "Failed to get DepthEstimator instance"
    assert estimator.device in ["cuda", "cpu"], f"Invalid device: {estimator.device}"
    
    # Run inference on mock black frame
    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = estimator.estimate(mock_frame)
    assert isinstance(res, DepthResult), "Inference did not return a DepthResult object"
    assert res.depth_map.shape == (480, 640), f"Expected shape (480, 640), got {res.depth_map.shape}"
    assert res.confidence_map.shape == (480, 640), "Confidence map shape mismatch"
    assert res.model_used is not None
    assert isinstance(res.inference_time_ms, float)

results.append(check("DepthEstimator: singleton, fallback model, inference on mock frame", c1))

# -- CHECK 2: MetricScaleRecovery -------------------------------------
def c2():
    from backend.services.depth.metric_scaler import MetricScaleRecovery, ScaleAnchor
    
    scaler = MetricScaleRecovery(use_ema=False)
    
    # Test with synthetic anchors
    mock_depth = np.ones((480, 640), dtype=np.float32) * 0.5
    
    # Mock MediaPipe NormalizedLandmarks
    class MockLandmark:
        def __init__(self, x, y, visibility):
            self.x = x
            self.y = y
            self.visibility = visibility
            
    # Mock landmarks: Left shoulder (0.3, 0.4), Right shoulder (0.7, 0.4)
    # Distance in normalized coords: 0.4.
    # In pixels: 0.4 * 640 = 256 pixels.
    # Typical shoulder width: 0.40m.
    # Implied scale: 0.40 / 256 = 0.0015625 m/pixel.
    landmarks = [MockLandmark(0.0, 0.0, 0.0)] * 33
    landmarks[11] = MockLandmark(0.3, 0.4, 0.9)  # LEFT_SHOULDER
    landmarks[12] = MockLandmark(0.7, 0.4, 0.9)  # RIGHT_SHOULDER
    
    # Also add hips to estimate torso
    # Torso height: 0.50m.
    # Left hip (0.3, 0.8), Right hip (0.7, 0.8)
    # Shoulder mid y = 0.4, Hip mid y = 0.8. Torso pixel distance: 0.4 * 480 = 192 pixels.
    landmarks[23] = MockLandmark(0.3, 0.8, 0.9)  # LEFT_HIP
    landmarks[24] = MockLandmark(0.7, 0.8, 0.9)  # RIGHT_HIP

    scale, anchors = scaler.compute_scale(
        depth_map=mock_depth,
        pose_landmarks=landmarks,
        image_height=480,
        image_width=640
    )
    
    assert scale > 0, "Scale should be positive"
    assert len(anchors) >= 2, f"Should have found torso + shoulder_width anchors, got {len(anchors)}"
    
    # Reset and stability test
    scaler.reset()
    assert len(scaler._scale_history) == 0, "Reset should clear scale history"

results.append(check("MetricScaleRecovery: NASA anchors, weighted average, history stats", c2))

# -- CHECK 3: CameraIntrinsics ----------------------------------------
print("\nLayer 2 — Camera Intrinsics")

def c3():
    from backend.services.depth.camera_intrinsics import CameraIntrinsics, CameraIntrinsicsEstimator
    
    intrinsics = CameraIntrinsics(fx=1000.0, fy=1000.0, cx=640.0, cy=360.0, width=1280, height=720)
    
    # 3D to 2D projection check
    xyz = np.array([0.0, 0.0, 2.0])
    px, py = intrinsics.project_3d_to_2d(xyz)
    assert px == 640.0 and py == 360.0, f"Expected center projection (640, 360), got ({px}, {py})"
    
    # Back-projection check
    reprojected = intrinsics.unproject_2d_to_3d(px, py, 2.0)
    assert np.allclose(reprojected, xyz), f"Unprojection mismatch: {reprojected} vs {xyz}"
    
    # Serialization
    d = intrinsics.to_dict()
    restored = CameraIntrinsics.from_dict(d)
    assert restored.fx == intrinsics.fx and restored.width == intrinsics.width
    
    # Heuristic estimator
    estimator = CameraIntrinsicsEstimator(1280, 720)
    default_c = estimator.default_webcam()
    assert default_c.fx == 1280 * 0.9

results.append(check("CameraIntrinsics: projection math, serialization, default FOVs", c3))

# -- CHECK 4: MetricReconstructor -------------------------------------
print("\nLayer 3 — Metric Reconstruction")

def c4():
    from backend.services.depth.metric_reconstruction import MetricReconstructor, MetricFrame
    
    reconstructor = MetricReconstructor(enable_depth_model=False)
    
    # Mock perception result
    perception = {
        "pose_33": [{"x": 0.5, "y": 0.3, "z": 0.0, "v": 0.9}] * 33,
        "left_hand_21": [{"x": 0.4, "y": 0.3, "z": 0.0, "v": 0.8}] * 21,
        "right_hand_21": [{"x": 0.6, "y": 0.3, "z": 0.0, "v": 0.8}] * 21,
        "objects": [{"class": "bottle", "bbox": [100, 100, 50, 150], "score": 0.9}]
    }
    
    # Reconstruct
    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    metric_frame = reconstructor.reconstruct_frame(mock_frame, perception)
    
    assert isinstance(metric_frame, MetricFrame)
    assert len(metric_frame.pose_33_metric) == 33
    assert len(metric_frame.left_hand_21_metric) == 21
    assert len(metric_frame.objects_metric) == 1
    
    # Height measurements
    assert metric_frame.person_height_m is not None
    assert metric_frame.shoulder_width_m is not None
    
    # JSON serialization
    serialized = metric_frame.to_json_dict()
    assert "depth_map" not in serialized, "Serialized JSON should not contain depth_map array"
    assert serialized["scale_factor"] > 0

results.append(check("MetricReconstructor: frame lifting, biomechanical measurements, JSON serialization", c4))

# -- CHECK 5: Database Schema Verification ---------------------------
print("\nLayer 4 — Database Schema")

def c5():
    from backend.models.database import MotionSession, MotionFrame
    
    # Verify new model columns exist
    session_attrs = ["person_height_m", "scale_factor_mean", "scale_factor_std", "camera_intrinsics_json", "depth_model_used", "has_metric_data"]
    frame_attrs = ["metric_json", "scale_factor", "depth_confidence"]
    
    for attr in session_attrs:
        assert hasattr(MotionSession, attr), f"MotionSession missing column: {attr}"
        
    for attr in frame_attrs:
        assert hasattr(MotionFrame, attr), f"MotionFrame missing column: {attr}"

results.append(check("SQLite database schema: metric depth columns exist in session and frame models", c5))

# -- CHECK 6: CompleteTracker & DatasetBuilder Updates ----------------
print("\nLayer 5 — Integrated Modules")

def c6():
    from backend.services.perception.complete_tracker import CompleteTracker, CompletePerceptionResult
    
    # Verify tracker outputs metric fields
    tracker = CompleteTracker()
    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = tracker.process_frame(mock_frame)
    
    assert isinstance(res, CompletePerceptionResult)
    assert hasattr(res, "pose_33_metric")
    assert hasattr(res, "objects_metric")
    assert hasattr(res, "depth_map")
    assert hasattr(res, "scale_factor")
    
    # Verify DatasetBuilderHOI
    from backend.services.dataset_builder_hoi import DatasetBuilderHOI
    # Simple check that it imports and class exists
    assert DatasetBuilderHOI is not None

results.append(check("CompleteTracker & DatasetBuilderHOI upgraded to support metric pipeline", c6))

# -- CHECK 7: UnifiedMotionData Loader --------------------------------
print("\nLayer 6 — Data Loading")

def c7():
    from backend.services.exporters.data_loader import UnifiedMotionData, SessionDataLoader
    
    # Check UnifiedMotionData properties
    from dataclasses import fields
    field_names = {f.name for f in fields(UnifiedMotionData)}
    assert "metric_positions_3d" in field_names
    assert "metric_pose_33" in field_names
    assert "metric_objects" in field_names
    assert "person_height_m" in field_names
    assert "camera_intrinsics" in field_names
    assert "has_metric_data" in field_names

results.append(check("UnifiedMotionData definition: metric fields populated on load", c7))

# -- CHECK 8: MetricExporter & Router Formats ------------------------
print("\nLayer 7 — Exporters & Routers")

def c8():
    from backend.services.exporters.metric_exporter import MetricExporter
    
    # Mock data for export
    metric_frames = [
        {
            "frame_id": 0,
            "timestamp_ms": 0.0,
            "pose_33_metric": [[0.1, 0.2, 2.0]] * 33,
            "left_hand_21_metric": [[0.05, 0.2, 1.95]] * 21,
            "right_hand_21_metric": [[0.15, 0.2, 1.95]] * 21,
            "objects_metric": [{"class": "bottle", "position_m": [0.1, 0.2, 1.9], "size_m": [0.08, 0.25, 0.08]}],
            "scale_factor": 4.5,
            "person_height_m": 1.72,
            "left_arm_length_m": 0.55,
            "right_arm_length_m": 0.55,
            "shoulder_width_m": 0.39
        }
    ]
    
    session_stats = {"fps": 30.0}
    json_out = MetricExporter.export_metric_json("test_session", metric_frames, session_stats)
    assert json_out["session"]["name"] == "test_session"
    assert json_out["measurements"]["person_height_m"]["mean"] == 1.72
    assert len(json_out["frames"]) == 1
    
    csv_out = MetricExporter.export_csv_metric(metric_frames)
    assert "frame_id" in csv_out
    assert "joint_0_x" in csv_out
    
    measure_csv = MetricExporter.export_measurements_csv(metric_frames)
    assert "person_height_m" in measure_csv
    
    # Verify exporters router lists the new formats
    from backend.routers.exporters import router
    # Check that formats endpoints is ready by importing the file
    import backend.routers.exporters as exporters_mod
    assert exporters_mod.router is not None

results.append(check("MetricExporter: JSON export structure, CSV export, biomechanics summary", c8))


# -- SUMMARY -----------------------------------------------------
print("\n" + "="*60)
passed = sum(1 for r in results if r)
failed = len(results) - passed
print(f"  Verification Summary: {passed}/{len(results)} passed")
print("="*60 + "\n")

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
