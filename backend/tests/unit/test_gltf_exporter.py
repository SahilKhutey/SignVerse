"""
Unit tests for GLTF exporter.
"""
import pytest
import json
from backend.services.exporters.gltf_exporter import GLTFExporter, GLTFSceneExporter


@pytest.mark.unit
class TestGLTFExporter:
    """Tests for GLTFExporter."""
    
    def test_export_generates_valid_gltf(self, sample_motion_data):
        """Should generate valid GLTF JSON dictionary and binary buffers."""
        exporter = GLTFExporter()
        gltf_dict, buf_bytes = exporter.export(sample_motion_data, embed_binary=False)
        
        assert "asset" in gltf_dict
        assert "nodes" in gltf_dict
        assert "skins" in gltf_dict
        assert "animations" in gltf_dict
        assert len(buf_bytes) > 0
        
        # Check node naming matches canonical joints
        node_names = [n["name"] for n in gltf_dict["nodes"]]
        assert "Hips" in node_names
        assert "Spine" in node_names
        assert "LeftHand" in node_names
        
        # Check inverse bind matrices accessor index
        skin = gltf_dict["skins"][0]
        assert "inverseBindMatrices" in skin
        assert len(skin["joints"]) == len(node_names)
        
        # Check embedded binary buffer option
        gltf_embedded, _ = exporter.export(sample_motion_data, embed_binary=True)
        assert gltf_embedded["buffers"][0]["uri"].startswith("data:application/octet-stream;base64,")


@pytest.mark.unit
class TestGLTFSceneExporter:
    """Tests for GLTFSceneExporter."""
    
    def test_export_scene_empty(self, sample_motion_data):
        """Should export scene with human skeleton and metadata."""
        exporter = GLTFSceneExporter()
        
        # Mock SceneData
        class MockScene:
            def __init__(self, motion_data):
                self.motion_data = motion_data
                self.scene_objects = []
                self.session_id = "sess_1"
                self.unique_classes = []
                self.num_objects = 0
        
        scene = MockScene(sample_motion_data)
        gltf_dict, buf_bytes = exporter.export_scene(scene, embed_binary=False)
        
        assert "extras" in gltf_dict
        assert gltf_dict["extras"]["signverse_session"] == "sess_1"
        assert len(gltf_dict["nodes"]) >= len(sample_motion_data.joint_names)
