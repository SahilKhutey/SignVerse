"""
Unit tests for the profiling and memory tracking services.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.profiling.memory_tracker import memory_tracker, MemorySnapshot


@pytest.mark.unit
class TestMemoryTracker:
    """Tests for MemoryTracker and MemorySnapshot."""
    
    def test_capture_snapshot(self):
        """Should capture a valid MemorySnapshot with all metrics."""
        snapshot = MemorySnapshot.capture("test_label")
        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.label == "test_label"
        assert snapshot.rss_mb > 0.0
        assert snapshot.cpu_percent >= 0.0
        assert snapshot.thread_count >= 1
        
        # Test serialization
        d = snapshot.to_dict()
        assert d["label"] == "test_label"
        assert "rss_mb" in d
        assert "cpu_percent" in d

    def test_register_and_update_component(self):
        """Should register components and record updates."""
        comp = memory_tracker.register_component("test_comp", "model")
        assert comp.name == "test_comp"
        assert comp.component_type == "model"
        
        comp.update(128.5)
        assert comp.current_mb == 128.5
        assert comp.peak_mb == 128.5
        
        comp.update(96.0)
        assert comp.current_mb == 96.0
        assert comp.peak_mb == 128.5  # Peak remains high


@pytest.mark.unit
class TestProfilingEndpoints:
    """Tests for the profiling endpoints and middleware."""
    
    def test_profiling_headers_appended(self):
        """Requests should get custom timing, CPU, and memory headers."""
        client = TestClient(app)
        # Query root or system stats (which is within profile_paths)
        response = client.get("/api/system/stats")
        assert response.status_code == 200
        assert "X-Profiling-Time-Ms" in response.headers
        assert "X-Profiling-Memory-Delta-Mb" in response.headers
        assert "X-Profiling-CPU-Percent" in response.headers
        
        # Verify values can be parsed as float
        assert float(response.headers["X-Profiling-Time-Ms"]) >= 0.0

    def test_memory_snapshot_endpoint(self):
        """GET /api/profiling/memory/snapshot should return current snapshot."""
        client = TestClient(app)
        response = client.get("/api/profiling/memory/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert "rss_mb" in data
        assert "py_objects" in data
        assert data["label"] == "manual"

    def test_memory_summary_endpoint(self):
        """GET /api/profiling/memory/summary should return stats summary."""
        client = TestClient(app)
        response = client.get("/api/profiling/memory/summary")
        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert "process" in data
        assert "rss_mb" in data["process"]

    def test_force_gc_endpoint(self):
        """POST /api/profiling/memory/gc should run garbage collection."""
        client = TestClient(app)
        response = client.post("/api/profiling/memory/gc")
        assert response.status_code == 200
        data = response.json()
        assert "objects_collected" in data
        assert "freed_mb" in data
        assert data["objects_collected"] >= 0

    def test_telemetry_metrics_endpoint(self):
        """GET /api/profiling/metrics should return API and WebSocket metrics."""
        client = TestClient(app)
        
        # Hit some routes to register telemetry
        client.get("/api/system/stats")
        
        response = client.get("/api/profiling/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "api" in data
        assert "websockets" in data
        
        # Ensure the hit was recorded
        api_metrics = data["api"]
        assert len(api_metrics) > 0
        hits = [m for m in api_metrics if "/api/system/stats" in m["path"]]
        assert len(hits) > 0
        assert hits[0]["count"] >= 1

