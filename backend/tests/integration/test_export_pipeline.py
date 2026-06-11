"""
Integration tests for the multi-format motion exporter pipeline API.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.database import get_db


@pytest.fixture(autouse=True)
def override_db(db_session):
    """Override get_db dependency."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestExportPipelineIntegration:
    """Verifies retrieval of export metadata and file downloads in multiple formats."""

    def test_list_formats(self, client, sample_session):
        """Should list all available export formats and their capabilities."""
        response = client.get(f"/api/exporters/{sample_session.id}/formats")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == sample_session.id
        assert "available_formats" in data
        assert len(data["available_formats"]) > 0

    def test_export_bvh(self, client, sample_frames_in_db):
        """Should export session to BVH text format."""
        session_id = sample_frames_in_db.id
        response = client.get(f"/api/exporters/{session_id}/export?format=bvh")
        assert response.status_code == 200
        assert "HIERARCHY" in response.text
        assert "MOTION" in response.text

    def test_export_gltf(self, client, sample_frames_in_db):
        """Should export session to GLTF JSON format."""
        session_id = sample_frames_in_db.id
        response = client.get(f"/api/exporters/{session_id}/export?format=gltf")
        assert response.status_code == 200
        data = response.json()
        assert "asset" in data
        assert "scenes" in data

    def test_export_mujoco(self, client, sample_frames_in_db):
        """Should export session to MuJoCo XML configuration."""
        session_id = sample_frames_in_db.id
        response = client.get(f"/api/exporters/{session_id}/export?format=mujoco")
        assert response.status_code == 200
        assert "<mujoco" in response.text

    def test_export_urdf(self, client, sample_frames_in_db):
        """Should export session to URDF robot XML description."""
        session_id = sample_frames_in_db.id
        response = client.get(f"/api/exporters/{session_id}/export?format=urdf")
        assert response.status_code == 200
        assert "<robot" in response.text

    def test_export_invalid_format(self, client, sample_frames_in_db):
        """Should return 400 Bad Request for unsupported format."""
        session_id = sample_frames_in_db.id
        response = client.get(f"/api/exporters/{session_id}/export?format=invalid_format_name")
        assert response.status_code == 400
        assert "unsupported format" in response.json()["detail"].lower()
