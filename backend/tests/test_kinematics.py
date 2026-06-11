import pytest
import numpy as np
from backend.core.skeleton_graph import SkeletonGraph, MP
from backend.services.kinematics.kinematics import Kinematics
from backend.services.kinematics.bvh_writer import BVHWriter
from backend.services.kinematics.retargeter import RobotRetargeter

def make_fake_landmarks():
    """Generates synthetic landmarks for testing"""
    lms = []
    for i in range(33):
        lms.append({"x": float(i * 5), "y": float(i * 10), "z": 0.0, "v": 1.0})
        
    # Setup specific positions for joint pairs
    lms[MP.LEFT_SHOULDER] = {"x": 100.0, "y": 200.0, "z": 0.0, "v": 1.0}
    lms[MP.RIGHT_SHOULDER] = {"x": 200.0, "y": 200.0, "z": 0.0, "v": 1.0}
    lms[MP.LEFT_ELBOW] = {"x": 100.0, "y": 250.0, "z": 0.0, "v": 1.0}
    lms[MP.RIGHT_ELBOW] = {"x": 200.0, "y": 250.0, "z": 0.0, "v": 1.0}
    lms[MP.LEFT_WRIST] = {"x": 100.0, "y": 300.0, "z": 0.0, "v": 1.0}
    lms[MP.RIGHT_WRIST] = {"x": 200.0, "y": 300.0, "z": 0.0, "v": 1.0}
    
    lms[MP.LEFT_HIP] = {"x": 120.0, "y": 400.0, "z": 0.0, "v": 1.0}
    lms[MP.RIGHT_HIP] = {"x": 180.0, "y": 400.0, "z": 0.0, "v": 1.0}
    lms[MP.LEFT_KNEE] = {"x": 120.0, "y": 480.0, "z": 0.0, "v": 1.0}
    lms[MP.RIGHT_KNEE] = {"x": 180.0, "y": 480.0, "z": 0.0, "v": 1.0}
    lms[MP.LEFT_ANKLE] = {"x": 120.0, "y": 560.0, "z": 0.0, "v": 1.0}
    lms[MP.RIGHT_ANKLE] = {"x": 180.0, "y": 560.0, "z": 0.0, "v": 1.0}
    
    return lms

def test_skeleton_graph():
    graph = SkeletonGraph()
    assert "hips" in graph.joints
    assert "left_shoulder" in graph.joints
    assert "right_foot" in graph.joints
    
    # Check that hierarchy traversal works
    chain = graph.get_chain_to_root("left_hand")
    assert "left_hand" in chain
    assert "hips" in chain
    
    # Check bone connections
    bones = graph.get_bones()
    assert len(bones) > 0
    assert len(bones[0]) == 4

def test_kinematics_vector_math():
    kin = Kinematics()
    v1 = np.array([0.0, 1.0, 0.0])
    v2 = np.array([1.0, 0.0, 0.0])
    
    # test quaternion calculation
    q = kin.vector_to_quaternion(v1, v2)
    assert np.allclose(np.linalg.norm(q), 1.0)
    
    # test euler conversion
    euler = kin.quaternion_to_euler(q)
    assert len(euler) == 3
    
    # test dummy landmarks calculations
    lms = make_fake_landmarks()
    bones = kin.extract_all_bones(lms)
    assert len(bones) > 0
    
    # test normalization
    norm_lms = kin.normalize_landmarks(lms, target_height=2.0)
    assert len(norm_lms) == 33
    assert norm_lms[MP.LEFT_HIP]["y"] == 0.0  # shifted root to origin Y

def test_bvh_writer(tmp_path):
    writer = BVHWriter(fps=30)
    lms = make_fake_landmarks()
    frames = [lms] * 5  # 5 frames
    
    output_file = tmp_path / "test_motion.bvh"
    writer.generate(frames, str(output_file))
    
    assert output_file.exists()
    content = output_file.read_text()
    assert "HIERARCHY" in content
    assert "MOTION" in content
    assert "Frames: 5" in content

def test_robot_retargeter():
    retargeter = RobotRetargeter()
    lms = make_fake_landmarks()
    
    # frame retargeting
    q = retargeter.retarget_frame(lms)
    assert len(q) == len(retargeter.ROBOT_JOINT_NAMES)
    
    # sequence retargeting
    frames = [lms] * 10
    dataset = retargeter.retarget_sequence(frames, fps=30)
    assert "metadata" in dataset
    assert "trajectory" in dataset
    assert len(dataset["trajectory"]["joint_angles_rad"]) == 10
    assert len(dataset["trajectory"]["velocities_rad_per_sec"]) == 10
    assert len(dataset["trajectory"]["accelerations_rad_per_sec2"]) == 10
