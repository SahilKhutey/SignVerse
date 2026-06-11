import pytest
import numpy as np
from backend.services.perception.holistic_extractor import HolisticExtractor, PerceptionResult
from backend.services.motion_fusion.kalman_smoother import TemporalSmoother

@pytest.fixture
def dummy_frame():
    """Create a blank BGR frame."""
    return np.zeros((480, 640, 3), dtype=np.uint8)

def test_holistic_extractor_runs(dummy_frame):
    extractor = HolisticExtractor()
    pose = extractor.extract(dummy_frame, frame_id=0, timestamp_ms=0)
    assert pose.frame_id == 0
    assert isinstance(pose.confidence_mean, float)

def test_kalman_smoother_smooths():
    smoother = TemporalSmoother()
    
    # Create fake perception result to smooth
    from backend.services.perception.holistic_extractor import Landmark
    lms = [Landmark(x=100.0, y=200.0, z=0.0, v=1.0)] * 33
    res = PerceptionResult(pose=lms, frame_id=0)
    
    out = smoother.smooth(res)
    assert len(out.pose) == 33
    assert out.pose[0].x == 100.0
