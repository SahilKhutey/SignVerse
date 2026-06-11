"""
Integration tests for miscellaneous FastAPI endpoints (health, root, and system stats).
"""
import pytest
from backend.main import app


@pytest.mark.integration
class TestAPIEndpointsIntegration:
    """Verifies response structure for system, health, and metadata endpoints."""

    def test_root_endpoint(self, client):
        """Root endpoint should return app metadata and features list."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert "features" in data
        assert len(data["features"]) > 0

    def test_health_endpoint(self, client):
        """Health endpoint should return status healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_system_stats_endpoint(self, client):
        """System stats should return message bus stats and circuit breakers state."""
        response = client.get("/api/system/stats")
        assert response.status_code == 200
        data = response.json()
        assert "bus" in data
        assert "breakers" in data
        assert "messages_published" in data["bus"]
