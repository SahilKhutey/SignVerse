"""
E2E integration test simulating a live demo scenario:
1. Check stream initial state (stopped).
2. Start live streaming via POST /api/live/start.
3. Poll stream status via GET /api/live/status.
4. Stop stream via POST /api/live/stop.
5. Verify status returns stopped.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.live_broadcaster import broadcaster


@pytest.fixture(autouse=True)
def clean_broadcaster():
    """Ensure broadcaster starts clean."""
    broadcaster.is_streaming = False
    if broadcaster.stream_task:
        broadcaster.stream_task.cancel()
        broadcaster.stream_task = None
    broadcaster.clients.clear()
    broadcaster.latest_result = None
    yield
    broadcaster.is_streaming = False
    if broadcaster.stream_task:
        broadcaster.stream_task.cancel()
        broadcaster.stream_task = None


@pytest.mark.e2e
class TestDemoScenarioE2E:
    """Verifies live streaming control loop and status updates."""

    @patch("cv2.VideoCapture")
    def test_live_demo_flow(self, mock_cv2_cap):
        """Test complete live demo cycle from starting stream to stopping it."""
        client = TestClient(app)

        # Mock VideoCapture to start successfully
        cap_instance = MagicMock()
        cap_instance.isOpened.return_value = True
        import numpy as np
        cap_instance.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cv2_cap.return_value = cap_instance

        # Mock the pipeline processing
        from backend.services.live_broadcaster import CompleteTracker, CompletePerceptionResult
        dummy_res = CompletePerceptionResult(
            frame_id=42,
            timestamp_ms=5000,
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
            person_posture="sitting",
            attention_target="screen",
            action_primitives=[],
            primary_action="TYPING",
            primary_intent="WORK",
            intent_confidence=0.9,
            intent_evidence="keyboard typing",
            pose_confidence=0.95,
            processing_time_ms=2.0
        )
        
        # 1. CHECK INITIAL STATUS
        status_resp = client.get("/api/live/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["is_streaming"] is False
        assert status_resp.json()["latest_intent"] == "UNKNOWN"

        # 2. START THE LIVE STREAM
        # We patch start_streaming to set states synchronously for reliability in TestClient
        with patch.object(broadcaster, "start_streaming") as mock_start:
            async def dummy_start(*args, **kwargs):
                broadcaster.is_streaming = True
                broadcaster.latest_result = dummy_res
            mock_start.side_effect = dummy_start
            
            start_resp = client.post("/api/live/start?camera_id=0")
            assert start_resp.status_code == 200
            assert start_resp.json()["status"] == "started"
            
        # 3. GET UPDATED STATUS AND SNAPSHOT
        status_resp = client.get("/api/live/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["is_streaming"] is True
        assert status_resp.json()["latest_frame_id"] == 42
        assert status_resp.json()["latest_intent"] == "WORK"
        assert status_resp.json()["latest_action"] == "TYPING"
        assert status_resp.json()["latest_expression"] == "HAPPY"

        # Check snapshot polling fallback
        snapshot_resp = client.get("/api/live/snapshot")
        assert snapshot_resp.status_code == 200
        snapshot_data = snapshot_resp.json()["data"]
        assert snapshot_data["frame_id"] == 42
        assert snapshot_data["primary_intent"] == "WORK"

        # 4. STOP STREAMING
        with patch.object(broadcaster, "stop_streaming") as mock_stop:
            async def dummy_stop(*args, **kwargs):
                broadcaster.is_streaming = False
                broadcaster.latest_result = None
            mock_stop.side_effect = dummy_stop

            stop_resp = client.post("/api/live/stop")
            assert stop_resp.status_code == 200
            assert stop_resp.json()["status"] == "stopped"

        # 5. VERIFY FINAL STATUS IS STOPPED
        status_resp = client.get("/api/live/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["is_streaming"] is False
        assert status_resp.json()["latest_intent"] == "UNKNOWN"
