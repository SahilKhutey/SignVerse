"""
Shared pytest fixtures for the entire test suite.
"""
import asyncio
import os
import shutil
import tempfile
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment BEFORE imports
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "False"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-32-chars-min"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["UPLOAD_DIR"] = "./test_uploads"
os.environ["EXPORT_DIR"] = "./test_exports"
os.environ["DATASET_DIR"] = "./test_datasets"
os.environ["REQUIRE_AUTH"] = "False"
os.environ["CORS_ORIGINS"] = '["http://localhost:5173"]'

from backend.config import settings
from backend.models.database import Base, MotionSession, MotionFrame


# === Event loop ===

@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# === Database ===

@pytest.fixture(scope="function")
def db_engine():
    """In-memory SQLite for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Database session with automatic rollback."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


# === File system ===

@pytest.fixture
def temp_dirs():
    """Create temporary directories for uploads/exports."""
    dirs = {
        "upload": Path(tempfile.mkdtemp(prefix="test_upload_")),
        "export": Path(tempfile.mkdtemp(prefix="test_export_")),
        "dataset": Path(tempfile.mkdtemp(prefix="test_dataset_")),
    }
    yield dirs
    for d in dirs.values():
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


# === Sample data ===

@pytest.fixture
def sample_landmarks():
    """Generate 33 realistic pose landmarks."""
    landmarks = []
    for i in range(33):
        landmarks.append({
            "x": float(160 + i * 10),
            "y": float(240 - i * 5),
            "z": float(i * 0.1),
            "v": 0.95,
        })
    return landmarks


@pytest.fixture
def sample_frame():
    """Generate a blank RGB frame."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_video_frames():
    """Generate 30 frames of a person waving."""
    frames = []
    for i in range(30):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:400, 250:400] = 100 + i * 2
        frames.append(frame)
    return frames


@pytest.fixture
def sample_session(db_session):
    """Create a test session in the database."""
    import uuid
    from datetime import datetime, timezone
    
    session = MotionSession(
        id=str(uuid.uuid4())[:12],
        name="test_session",
        source_type="upload",
        fps=30.0,
        frame_count=10,
        duration_s=1.0,
        action_label="unlabeled",
        avg_confidence=0.85,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture
def sample_frames_in_db(db_session, sample_session):
    """Create 10 test frames for the sample session."""
    import uuid
    for i in range(10):
        frame = MotionFrame(
            id=str(uuid.uuid4()),
            session_id=sample_session.id,
            frame_idx=i,
            timestamp_ms=i * 33.3,
            perception_json=json.dumps({
                "pose_33": [{"x": j * 10, "y": j * 5, "z": 0, "v": 0.9} for j in range(33)],
            }),
            kinematics_json=json.dumps({
                "joints_3d": {"Hips": [0, 0, 0]},
                "euler_deg": {"Hips": [0, 0, 0]},
                "quaternions": {"Hips": [1, 0, 0, 0]},
                "root_position": [0, 0, 0],
            }),
            confidence_mean=0.9,
        )
        db_session.add(frame)
    db_session.commit()
    return sample_session


# === Mock services ===

@pytest.fixture
def mock_mediapipe(monkeypatch):
    """Mock MediaPipe for unit tests."""
    mock = MagicMock()
    mock.solutions.pose.Pose.return_value.process.return_value.pose_landmarks = MagicMock(
        landmark=[MagicMock(x=0.5, y=0.5, z=0.0, visibility=0.9) for _ in range(33)]
    )
    monkeypatch.setattr("mediapipe.solutions.pose", mock.solutions.pose)
    return mock


@pytest.fixture
def mock_yolo(monkeypatch):
    """Mock YOLO for unit tests."""
    from ultralytics import YOLO
    
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxy = [np.array([100, 100, 200, 200])]
    mock_box.conf = [0.9]
    mock_box.cls = [0]
    mock_box.id = [1]
    mock_result.boxes = [mock_box]
    mock_model.track.return_value = [mock_result]
    mock_model.names = {0: "person"}
    
    monkeypatch.setattr(YOLO, "__init__", lambda *a, **k: None)
    monkeypatch.setattr(YOLO, "track", mock_model.track)
    monkeypatch.setattr(YOLO, "names", mock_model.names)
    return mock_model


@pytest.fixture
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


# === Utilities ===

@pytest.fixture
def assert_performance():
    """Helper for performance assertions."""
    def _assert(duration_ms: float, max_ms: float, operation: str):
        assert duration_ms <= max_ms, (
            f"{operation} took {duration_ms:.1f}ms (max: {max_ms}ms)"
        )
    return _assert


@pytest.fixture
def sample_motion_data():
    """Create sample motion data for export tests."""
    from backend.services.exporters.data_loader import UnifiedMotionData, CANONICAL_JOINTS
    
    n_frames = 10
    joint_names = list(CANONICAL_JOINTS)
    
    return UnifiedMotionData(
        session_id="test_123",
        session_name="test_session",
        fps=30.0,
        frame_count=n_frames,
        duration_s=n_frames / 30.0,
        source_type="upload",
        action_label="walk",
        intent="WALK",
        created_at="2024-01-01T00:00:00",
        joint_names=joint_names,
        timestamps_ms=[i * 33.3 for i in range(n_frames)],
        root_positions=[[0.0, 0.0, 0.0] for _ in range(n_frames)],
        joint_angles_rad=[{j: [0.0, 0.0, 0.0] for j in joint_names} for _ in range(n_frames)],
        joint_angles_deg=[{j: [0.0, 0.0, 0.0] for j in joint_names} for _ in range(n_frames)],
        joint_angles_quat=[{j: [1.0, 0.0, 0.0, 0.0] for j in joint_names} for _ in range(n_frames)],
        joint_positions_3d=[{j: [0.0, 0.0, 0.0] for j in joint_names} for _ in range(n_frames)],
        bone_lengths={j: 0.1 for j in joint_names},
        confidence_per_frame=[0.9] * n_frames,
        actions_per_frame=["IDLE"] * n_frames,
        intents_per_frame=["UNKNOWN"] * n_frames,
        interactions_per_frame=[{}] * n_frames,
    )

