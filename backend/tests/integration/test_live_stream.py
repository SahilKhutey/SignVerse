"""
Integration tests for the live stream REST control controllers.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from backend.main import app
from backend.services.perception.complete_tracker import CompletePerceptionResult


class MockVideoCapture:
    def __init__(self, *args, **kwargs):
        self.opened = True

    def isOpened(self):
        return self.opened

    def read(self):
        return True, np.zeros((240, 320, 3), dtype=np.uint8)

    def set(self, prop, val):
        pass

    def release(self):
        self.opened = False


@pytest.fixture
def mock_camera():
    """Patch cv2.VideoCapture to return MockVideoCapture."""
    with patch("cv2.VideoCapture", side_effect=MockVideoCapture) as mock:
        yield mock


@pytest.fixture
def mock_tracker():
    """Patch CompleteTracker.process_frame."""
    dummy_res = CompletePerceptionResult(
        frame_id=42,
        timestamp_ms=1000,
        pose_33=[],
        left_hand_21=[],
        right_hand_21=[],
        face_478=[],
        objects=[],
        hand_gestures={},
        expression="HAPPY",
        expression_confidence=0.95,
        head_pose={},
        gaze={},
        interaction_graph={},
        person_posture="standing",
        attention_target="scene",
        action_primitives=[],
        primary_action="WAVING",
        primary_intent="GREETING",
        intent_confidence=0.85,
        intent_evidence="none",
        pose_confidence=0.9,
        processing_time_ms=5.0
    )
    with patch("backend.services.live_broadcaster.CompleteTracker.process_frame", return_value=dummy_res) as mock:
        yield mock


@pytest.mark.integration
class TestLiveStreamIntegration:
    """Verifies live stream HTTP APIs and broadcaster transitions."""

    def test_live_stream_lifecycle(self, client, mock_camera, mock_tracker):
        """Should start stream, check status, stop stream, and verify snapshot returns latest perception."""
        # 1. Stop stream initially
        client.post("/api/live/stop")
        
        response = client.get("/api/live/status")
        assert response.status_code == 200
        assert response.json()["is_streaming"] is False

        # 2. Start stream
        response = client.post("/api/live/start?camera_id=0")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

        # 3. Check status (will be streaming)
        response = client.get("/api/live/status")
        assert response.status_code == 200
        assert response.json()["is_streaming"] is True

        # 4. Trigger one frame run (broadcaster reads frame and populates latest_result)
        from backend.services.live_broadcaster import broadcaster
        # Directly mock/simulate frame loop step for the test
        broadcaster.latest_result = mock_tracker.return_value
        
        # 5. Check status populated with latest results
        response = client.get("/api/live/status")
        assert response.status_code == 200
        data = response.json()
        assert data["latest_frame_id"] == 42
        assert data["latest_action"] == "WAVING"

        # 6. Verify snapshot endpoint
        response = client.get("/api/live/snapshot")
        assert response.status_code == 200
        snap_data = response.json()
        assert snap_data["type"] == "frame"
        assert snap_data["data"]["expression"] == "HAPPY"

        # 7. Stop stream
        response = client.post("/api/live/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"

        response = client.get("/api/live/status")
        assert response.json()["is_streaming"] is False
