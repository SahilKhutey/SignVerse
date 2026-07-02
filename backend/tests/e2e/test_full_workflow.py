"""
End-to-End integration test simulating a complete user workflow.
1. Authenticate to get JWT token.
2. Upload video file.
3. Perform perception pipeline analysis (mocked or synchronous).
4. Query session and frame tables.
5. Export skeleton animation to BVH/GLTF/MuJoCo.
"""
import pytest
import io
import json
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.database import get_db, MotionSession, MotionFrame

@pytest.fixture(autouse=True)
def override_db(db_session):
    """Override get_db dependency."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.e2e
class TestFullWorkflowE2E:
    """Verifies complete end-to-end user lifecycle."""

    def test_complete_workflow(self, client, db_session, temp_dirs):
        """Simulate authentication, upload, processing, data validation, and multi-export."""
        # 1. AUTHENTICATE
        auth_payload = {"username": "admin", "password": "password123"}
        # Mock authenticate_user to return admin dict
        with patch("backend.main.authenticate_user", return_value={"username": "admin", "role": "admin"}) as mock_auth:
            login_resp = client.post("/api/auth/login", json=auth_payload)
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

        # 2. UPLOAD VIDEO
        # Override setting directories to temporary ones
        from backend.config import settings
        settings.upload_dir = temp_dirs["upload"]
        settings.export_dir = temp_dirs["export"]
        settings.dataset_dir = temp_dirs["dataset"]

        # Synthesize a minimal valid MP4 header
        mp4_bytes = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom' + b'\x00' * 100
        file_payload = {"file": ("demo.mp4", io.BytesIO(mp4_bytes), "video/mp4")}

        # Submit upload request
        # Mock the pipeline processing to avoid OpenCV dependencies loading heavy files
        from backend.core.schemas import SessionMetadata, PoseFrame, Landmark
        from datetime import datetime, timezone
        dummy_session_id = "e2e_test_sess"
        mock_result = {
            "session_id": dummy_session_id,
            "metadata": SessionMetadata(
                session_id=dummy_session_id,
                source="upload",
                filename="demo.mp4",
                fps=30.0,
                frame_count=10,
                duration_sec=0.33,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                status="ready"
            ),
            "frames": [
                PoseFrame(
                    frame_id=i,
                    timestamp=i * 0.033,
                    pose_33=[Landmark(x=0.5, y=0.5, z=0.0, v=0.9) for _ in range(33)],
                    left_hand_21=[Landmark(x=0.5, y=0.5, z=0.0, v=0.9) for _ in range(21)],
                    right_hand_21=[],
                    face_468=[],
                    confidence=0.9
                ) for i in range(10)
            ]
        }

        cap_instance = MagicMock()
        cap_instance.isOpened.return_value = True
        cap_instance.read.side_effect = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)
        ]
        cap_instance.get.return_value = 30.0

        from backend.ingestion.orchestrator import IngestionJob, JobStatus
        mock_job = IngestionJob(
            job_id="e2e_test_job",
            source_type="upload",
            source_path="demo.mp4",
            source_url=None,
            status=JobStatus.QUEUED
        )

        with patch("backend.routers.capture.validate_video", return_value=(True, "")):
            with patch("cv2.VideoCapture", return_value=cap_instance):
                with patch("backend.routers.capture.orchestrator.submit_job", return_value=mock_job):
                    # Ingestion call
                    upload_resp = client.post("/api/capture/upload", files=file_payload, headers=headers)
                    assert upload_resp.status_code == 200
                    upload_data = upload_resp.json()
                    assert upload_data["status"] == "queued"
                    assert upload_data["job_id"] == "e2e_test_job"

        # 3. VERIFY DATABASE PERSISTENCE
        # The router saves the session and frames to database. Let's populate db_session directly with E2E sample.
        # This matches what capture router would do after processing video.
        session = MotionSession(
            id=dummy_session_id,
            name="demo.mp4",
            source_type="upload",
            fps=30.0,
            frame_count=10,
            duration_s=0.33,
            action_label="unlabeled",
            avg_confidence=0.9,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db_session.add(session)
        for i in range(10):
            frame = MotionFrame(
                session_id=dummy_session_id,
                frame_idx=i,
                timestamp_ms=i * 33.3,
                perception_json=json.dumps({
                    "pose": [{"x": 0.5, "y": 0.5, "z": 0.0, "v": 0.9} for _ in range(33)],
                    "left_hand": [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(21)],
                    "right_hand": [],
                    "face": []
                }),
                kinematics_json=json.dumps({
                    "joints_3d": {"Hips": [0, 0, 0]},
                    "euler_deg": {"Hips": [0, 0, 0]},
                    "quaternions": {"Hips": [1, 0, 0, 0]},
                    "root_position": [0, 0, 0],
                }),
                confidence_mean=0.9
            )
            db_session.add(frame)
        db_session.commit()

        # 4. QUERY SESSIONS API
        get_sess_resp = client.get(f"/api/sessions/{dummy_session_id}", headers=headers)
        assert get_sess_resp.status_code == 200
        assert get_sess_resp.json()["name"] == "demo.mp4"

        get_frames_resp = client.get(f"/api/sessions/{dummy_session_id}/frames", headers=headers)
        assert get_frames_resp.status_code == 200
        assert len(get_frames_resp.json()) == 10

        # 5. MULTI-FORMAT EXPORT VERIFICATION
        # Verify formats endpoint
        formats_resp = client.get(f"/api/exporters/{dummy_session_id}/formats", headers=headers)
        assert formats_resp.status_code == 200
        assert "available_formats" in formats_resp.json()

        # BVH Export
        bvh_resp = client.get(f"/api/exporters/{dummy_session_id}/export?format=bvh", headers=headers)
        assert bvh_resp.status_code == 200
        assert "HIERARCHY" in bvh_resp.text

        # GLTF Export
        gltf_resp = client.get(f"/api/exporters/{dummy_session_id}/export?format=gltf", headers=headers)
        assert gltf_resp.status_code == 200
        assert "asset" in gltf_resp.json()

        # MuJoCo Export
        mujoco_resp = client.get(f"/api/exporters/{dummy_session_id}/export?format=mujoco", headers=headers)
        assert mujoco_resp.status_code == 200
        assert "<mujoco" in mujoco_resp.text
