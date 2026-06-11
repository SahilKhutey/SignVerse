"""
Unit tests for BVH writer.
"""
import pytest
import tempfile
from pathlib import Path
from backend.services.kinematics.bvh_writer import BVHWriter, write_bvh, write_bvh_file


@pytest.mark.unit
class TestBVHWriter:
    """Tests for BVHWriter and helper functions."""
    
    def test_write_bvh_format(self):
        """Should output correct BVH format headers and channels."""
        kin_frames = [
            {
                "euler_deg": {
                    "root": [0.0, 0.0, 0.0],
                    "spine": [0.0, 10.0, 0.0],
                }
            }
        ]
        
        bvh_str = write_bvh(kin_frames, fps=30.0, session_name="test")
        
        assert "HIERARCHY" in bvh_str
        assert "ROOT Hips" in bvh_str
        assert "CHANNELS 6" in bvh_str
        assert "MOTION" in bvh_str
        assert "Frames: 1" in bvh_str
        assert "Frame Time: 0.033333" in bvh_str
    
    def test_bvh_writer_class(self):
        """BVHWriter.generate should compute and save landmarks into a file."""
        # 33 landmarks for 2 frames
        frame1 = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(33)]
        frame1[11] = {"x": 0.0, "y": 0.0, "z": 0.0}
        frame1[13] = {"x": 0.0, "y": 1.0, "z": 0.0}
        
        frame2 = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(33)]
        frame2[11] = {"x": 0.0, "y": 0.0, "z": 0.0}
        frame2[13] = {"x": 0.1, "y": 1.0, "z": 0.0}
        
        frames_landmarks = [frame1, frame2]
        
        with tempfile.TemporaryDirectory() as tempdir:
            out_file = Path(tempdir) / "motion.bvh"
            writer = BVHWriter(fps=30)
            writer.generate(frames_landmarks, str(out_file))
            
            assert out_file.exists()
            content = out_file.read_text()
            assert "HIERARCHY" in content
            assert "MOTION" in content
            assert "Frames: 2" in content
