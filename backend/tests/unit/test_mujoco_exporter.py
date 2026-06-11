"""
Unit tests for MuJoCo exporter.
"""
import pytest
from backend.services.exporters.mujoco_exporter import MuJoCoExporter


@pytest.mark.unit
class TestMuJoCoExporter:
    """Tests for MuJoCoExporter."""
    
    def test_export_generates_valid_xml(self, sample_motion_data):
        """Should generate valid MuJoCo XML with worldbody and joint limits."""
        exporter = MuJoCoExporter()
        xml_str = exporter.export(sample_motion_data)
        
        assert "<mujoco" in xml_str
        assert "<worldbody>" in xml_str
        assert "body name=\"torso\"" in xml_str
        assert "joint name=\"root\" type=\"free\"" in xml_str
        
        # Check standard joint chains
        assert "body name=\"left_shoulder_body\"" in xml_str
        assert "body name=\"right_shoulder_body\"" in xml_str
        assert "body name=\"left_hip_body\"" in xml_str
        assert "body name=\"right_hip_body\"" in xml_str
        
        # Check coordinates and limits
        assert "type=\"capsule\"" in xml_str
        assert "integrator=\"RK4\"" in xml_str
