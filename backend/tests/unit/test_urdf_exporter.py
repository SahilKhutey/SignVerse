"""
Unit tests for URDF exporter.
"""
import pytest
import json
import yaml
from backend.services.exporters.urdf_exporter import URDFExporter


@pytest.mark.unit
class TestURDFExporter:
    """Tests for URDFExporter."""
    
    def test_export_urdf(self, sample_motion_data):
        """Should generate valid URDF XML format."""
        exporter = URDFExporter()
        urdf_str = exporter.export_urdf(sample_motion_data)
        
        assert "<robot name=\"signverse_humanoid\">" in urdf_str
        assert "<link name=\"base_link\">" in urdf_str
        assert "<joint name=\"hips_joint\" type=\"floating\">" in urdf_str
        
        # Check links
        assert "link name=\"hips\"" in urdf_str
        assert "link name=\"spine\"" in urdf_str
        assert "joint name=\"left_shoulder_joint\"" in urdf_str
    
    def test_export_ros2_trajectory(self, sample_motion_data):
        """Should generate valid ROS2 JointTrajectory YAML."""
        exporter = URDFExporter()
        yaml_str = exporter.export_ros2_trajectory(sample_motion_data)
        
        assert "joint_trajectory:" in yaml_str
        assert "joint_names:" in yaml_str
        assert "points:" in yaml_str
        
        # Parse YAML to verify structure
        parsed = yaml.safe_load(yaml_str)
        assert "joint_trajectory" in parsed
        traj = parsed["joint_trajectory"]
        assert len(traj["joint_names"]) > 0
        assert len(traj["points"]) == sample_motion_data.num_frames
    
    def test_export_csv(self, sample_motion_data):
        """Should generate valid CSV content."""
        exporter = URDFExporter()
        csv_str = exporter.export_csv(sample_motion_data)
        
        assert "frame_idx" in csv_str
        assert "timestamp_ms" in csv_str
        assert "Hips_rad_x" in csv_str
        assert "Spine_deg_x" in csv_str
        
        # Count lines (1 header + 10 data frames)
        lines = csv_str.strip().split("\n")
        assert len(lines) == 11
    
    def test_export_pinocchio(self, sample_motion_data):
        """Should generate valid Pinocchio JSON dict."""
        exporter = URDFExporter()
        p_dict = exporter.export_pinocchio(sample_motion_data)
        
        assert p_dict["schema"] == "signverse-pinocchio-v1"
        assert p_dict["session_id"] == "test_123"
        assert len(p_dict["frames"]) == sample_motion_data.num_frames
        assert "base_pos" in p_dict["frames"][0]
        assert "base_quat_wxyz" in p_dict["frames"][0]
        assert "q" in p_dict["frames"][0]
    
    def test_export_blender_script(self, sample_motion_data):
        """Should generate executable Blender python code."""
        exporter = URDFExporter()
        script_str = exporter.export_blender_script(sample_motion_data)
        
        assert "import bpy" in script_str
        assert "bpy.ops.wm.read_factory_settings" in script_str
        assert "SignVerseArmature" in script_str
        assert "ANIM_DATA" in script_str
