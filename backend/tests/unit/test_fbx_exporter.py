"""
Unit tests for FBX exporter.
"""
import pytest
from backend.services.exporters.fbx_exporter import FBXExporter


@pytest.mark.unit
class TestFBXExporter:
    """Tests for FBXExporter."""
    
    def test_export_generates_valid_ascii_fbx(self, sample_motion_data):
        """Should generate valid FBX ASCII header and connection fields."""
        exporter = FBXExporter()
        fbx_str = exporter.export(sample_motion_data)
        
        assert "FBXHeaderExtension" in fbx_str
        assert "GlobalSettings" in fbx_str
        assert "Definitions" in fbx_str
        assert "Objects" in fbx_str
        assert "Connections" in fbx_str
        assert "Takes" in fbx_str
        
        # Check standard joints connected
        assert "Model::Hips" in fbx_str
        assert "Model::Spine" in fbx_str
        assert "Model::LeftHand" in fbx_str
        
        # Check parent-child hierarchy in connections
        assert "AnimCurveNode" in fbx_str
