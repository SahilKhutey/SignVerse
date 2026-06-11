"""
Unit tests for export formats.
"""
import pytest
from backend.services.exporters.bvh_exporter import BVHExporter


@pytest.mark.unit
class TestExporters:
    """Tests for export engines."""
    
    def test_generates_valid_bvh(self, sample_motion_data):
        """BVH output should have valid structure."""
        exporter = BVHExporter()
        bvh = exporter.export(sample_motion_data)
        
        assert "HIERARCHY" in bvh
        assert "MOTION" in bvh
        assert "ROOT Hips" in bvh
        assert "JOINT Spine" in bvh
        assert f"Frames: {sample_motion_data.num_frames}" in bvh
