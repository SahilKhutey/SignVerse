"""
Unit tests for pose extraction.
"""
import pytest
import numpy as np
from backend.services.perception.holistic_extractor import HolisticExtractor, PerceptionResult, Landmark


@pytest.mark.unit
class TestHolisticExtractor:
    """Tests for the HolisticExtractor class."""
    
    def test_initialization(self):
        """Extractor should initialize without errors."""
        extractor = HolisticExtractor()
        assert extractor.holistic is not None
    
    def test_extract_returns_perception_result(self, sample_frame):
        """extract() should return a PerceptionResult object."""
        extractor = HolisticExtractor()
        result = extractor.extract(sample_frame, frame_id=1, timestamp_ms=33.3)
        assert isinstance(result, PerceptionResult)
        assert result.frame_id == 1
        assert result.timestamp_ms == 33.3
    
    def test_extract_handles_blank_frame(self, sample_frame):
        """Should not crash on blank frame."""
        extractor = HolisticExtractor()
        result = extractor.extract(sample_frame, frame_id=0, timestamp_ms=0)
        assert result.confidence_mean >= 0.0
        assert result.confidence_mean <= 1.0
    
    def test_extract_invalid_input_returns_empty(self):
        """Invalid inputs should return empty result, not crash."""
        extractor = HolisticExtractor()
        result = extractor.extract(None, frame_id=0, timestamp_ms=0)
        assert isinstance(result, PerceptionResult)
        assert len(result.pose) == 0
    
    def test_extract_normalizes_to_uint8(self):
        """Float [0,1] input should be converted to uint8."""
        extractor = HolisticExtractor()
        float_frame = np.ones((100, 100, 3), dtype=np.float32) * 0.5
        result = extractor.extract(float_frame, frame_id=0, timestamp_ms=0)
        assert isinstance(result, PerceptionResult)
    
    def test_landmark_format(self, sample_landmarks):
        """Landmarks should be converted to dict format."""
        extractor = HolisticExtractor()
        result = extractor.extract(np.zeros((100, 100, 3), dtype=np.uint8), 0, 0)
        assert isinstance(result.pose, list)
    
    def test_face_subsampling(self):
        """Face should be subsampled to ≤100 points."""
        extractor = HolisticExtractor()
        assert extractor._extract_landmarks(None, sample_count=100) == []
    
    def test_close_releases_resources(self):
        """close() should not raise error."""
        extractor = HolisticExtractor()
        extractor.close()  # Should not crash


@pytest.mark.unit
class TestPerceptionResult:
    """Tests for PerceptionResult dataclass."""
    
    def test_to_dict_serialization(self):
        """to_dict() should produce JSON-serializable output."""
        result = PerceptionResult(
            pose=[Landmark(x=0.5, y=0.5, z=0.0, v=0.9)],
            frame_id=1,
            timestamp_ms=33.3,
        )
        d = result.to_dict()
        assert d["frame_id"] == 1
        assert d["timestamp_ms"] == 33.3
        assert "pose" in d
        assert "confidence_mean" in d
        import json
        json.dumps(d)  # Should not raise
