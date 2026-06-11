"""
Unit tests for SkeletonGraph.
"""
import pytest
from backend.core.skeleton_graph import SkeletonGraph, Joint


@pytest.mark.unit
class TestSkeletonGraph:
    """Tests for SkeletonGraph class."""
    
    def test_initialization(self):
        """Should build the joint graph hierarchy correctly."""
        graph = SkeletonGraph()
        assert "hips" in graph.joints
        assert "spine" in graph.joints
        assert "left_hand" in graph.joints
        
        # Check parents
        assert graph.joints["hips"].parent is None
        assert graph.joints["spine"].parent == "hips"
        assert graph.joints["left_hand"].parent == "left_lower_arm"
        
        # Check children wired up
        assert "spine" in graph.joints["hips"].children
        assert "left_hip" in graph.joints["hips"].children
        assert "left_upper_arm" in graph.joints["left_shoulder"].children
    
    def test_get_chain_to_root(self):
        """Should return list of parents up to the root."""
        graph = SkeletonGraph()
        chain = graph.get_chain_to_root("left_hand")
        assert chain[0] == "left_hand"
        assert chain[-1] == "hips"
        assert "left_lower_arm" in chain
        assert "left_upper_arm" in chain
        assert "left_shoulder" in chain
        assert "chest" in chain
        assert "spine" in chain
    
    def test_get_bones(self):
        """Should return bone segments with indices."""
        graph = SkeletonGraph()
        bones = graph.get_bones()
        assert len(bones) > 0
        
        # Check specific bone segment
        # format: (parent_name, child_name, parent_index, child_index)
        spine_bone = [b for b in bones if b[0] == "hips" and b[1] == "spine"]
        assert len(spine_bone) == 1
        
        left_arm_bone = [b for b in bones if b[0] == "left_upper_arm" and b[1] == "left_lower_arm"]
        assert len(left_arm_bone) == 1
    
    def test_get_ordered_joints(self):
        """Should return DFS ordered joints starting at hips."""
        graph = SkeletonGraph()
        ordered = graph.get_ordered_joints()
        assert len(ordered) == len(graph.joints)
        assert ordered[0].name == "hips"
        
        # Verify parent comes before child in DFS order
        names = [j.name for j in ordered]
        assert names.index("hips") < names.index("spine")
        assert names.index("spine") < names.index("chest")
