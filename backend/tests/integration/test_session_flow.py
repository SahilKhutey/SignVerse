"""
Integration tests for the session management FastAPI flow.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.database import get_db, MotionSession


@pytest.fixture(autouse=True)
def override_db(db_session):
    """Override get_db with transactional test database session."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestSessionFlowIntegration:
    """Verifies end-to-end HTTP lifecycle for dataset sessions API endpoints."""

    def test_list_and_get_sessions(self, client, sample_session):
        """Should list all sessions and retrieve details for a single session."""
        # 1. List sessions
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(item["id"] == sample_session.id for item in data)

        # 2. Get specific session
        response = client.get(f"/api/sessions/{sample_session.id}")
        assert response.status_code == 200
        sess_data = response.json()
        assert sess_data["name"] == sample_session.name
        assert sess_data["fps"] == sample_session.fps

        # 3. Get non-existent session
        response = client.get("/api/sessions/nonexistent")
        assert response.status_code == 404

    def test_update_label(self, client, sample_session):
        """Should update session action label."""
        payload = {"label": "WAVING"}
        response = client.patch(f"/api/sessions/{sample_session.id}/label", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["label"] == "WAVING"

        # Verify in DB/GET request
        response = client.get(f"/api/sessions/{sample_session.id}")
        assert response.json()["action_label"] == "WAVING"

    def test_delete_session(self, client, sample_session):
        """Should delete session."""
        response = client.delete(f"/api/sessions/{sample_session.id}")
        assert response.status_code == 200
        assert response.json()["ok"] is True

        # Verify not found
        response = client.get(f"/api/sessions/{sample_session.id}")
        assert response.status_code == 404
