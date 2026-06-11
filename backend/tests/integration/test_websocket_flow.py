"""
Integration tests for WebSocket live streams and control flows.
"""
import pytest
import numpy as np
import cv2
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.perception.complete_tracker import CompletePerceptionResult


class MockVideoCapture:
    """Mock for cv2.VideoCapture."""
    def __init__(self, *args, **kwargs):
        self.opened = True

    def isOpened(self):
        return self.opened

    def read(self):
        # Return a small blank BGR frame
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
        frame_id=0,
        timestamp_ms=1000,
        pose_33=[],
        left_hand_21=[],
        right_hand_21=[],
        face_478=[],
        objects=[],
        hand_gestures={},
        expression="NEUTRAL",
        expression_confidence=0.9,
        head_pose={},
        gaze={},
        interaction_graph={},
        person_posture="standing",
        attention_target="scene",
        action_primitives=[],
        primary_action="IDLE",
        primary_intent="IDLE",
        intent_confidence=0.8,
        intent_evidence="none",
        pose_confidence=0.9,
        processing_time_ms=5.0
    )
    with patch("backend.services.live_broadcaster.CompleteTracker.process_frame", return_value=dummy_res) as mock:
        yield mock


@pytest.mark.integration
class TestWebSocketFlowIntegration:
    """Verifies that Websocket live perception and video streams broadcast correct frames."""

    def test_live_perception_socket(self, client, mock_camera, mock_tracker):
        """Should connect to live perception socket, accept ready state, pong, and disconnect."""
        # Start and clean up streaming broadcaster state
        from backend.services.live_broadcaster import broadcaster
        broadcaster.is_streaming = False
        if broadcaster.stream_task:
            broadcaster.stream_task.cancel()

        with client.websocket_connect("/ws/live") as websocket:
            # 1. Check greeting/ready message
            greeting = websocket.receive_json()
            assert greeting["type"] == "ready"

            # 2. Receive a broadcasted frame
            frame_data = websocket.receive_json()
            assert frame_data["type"] == "frame"
            assert frame_data["data"]["primary_action"] == "IDLE"

            # 3. Send client control ping
            websocket.send_json({"action": "ping"})
            pong = None
            for _ in range(10):
                msg = websocket.receive_json()
                if msg.get("type") == "pong":
                    pong = msg
                    break
            assert pong is not None
            assert pong["type"] == "pong"

            # 4. Stop stream
            websocket.send_json({"action": "stop"})

    def test_live_camera_socket(self, client, mock_camera):
        """Should connect to raw camera socket and receive binary JPEG frames."""
        with client.websocket_connect("/ws/camera") as websocket:
            # Receive binary frame (JPEG bytes)
            bytes_data = websocket.receive_bytes()
            assert len(bytes_data) > 0
            
            # Check magic bytes for JPEG (0xFFD8)
            assert bytes_data[0] == 0xFF
            assert bytes_data[1] == 0xD8
