import pytest
import time
from backend.services.profiling.telemetry_manager import TelemetryManager

@pytest.mark.unit
class TestTelemetryManager:
    """Unit tests for TelemetryManager operational stats."""
    
    def test_record_route_latency(self):
        tm = TelemetryManager()
        tm.record_route_latency("/api/test", "GET", 0.150, 200)
        tm.record_route_latency("/api/test", "GET", 0.050, 200)
        tm.record_route_latency("/api/test", "GET", 0.200, 500)
        
        metrics = tm.get_api_metrics()
        assert len(metrics) == 1
        m = metrics[0]
        assert m["path"] == "/api/test"
        assert m["method"] == "GET"
        assert m["count"] == 3
        assert m["mean_latency_ms"] == 133.33  # (150+50+200)/3
        assert m["max_latency_ms"] == 200.0
        assert m["min_latency_ms"] == 50.0
        assert m["status_2xx"] == 2
        assert m["status_5xx"] == 1
        assert m["error_rate_percent"] == 33.33

    def test_websocket_metrics(self):
        tm = TelemetryManager()
        tm.record_ws_connect()
        tm.record_ws_connect()
        assert tm.get_ws_metrics()["active_connections"] == 2
        
        tm.record_ws_disconnect()
        assert tm.get_ws_metrics()["active_connections"] == 1
        
        tm.record_ws_frame(0.012)
        tm.record_ws_frame(0.008)
        
        ws = tm.get_ws_metrics()
        assert ws["total_frames_received"] == 2
        assert ws["total_frames_processed"] == 2
        assert ws["mean_frame_latency_ms"] == 10.0  # (12+8)/2
        assert ws["peak_frame_latency_ms"] == 12.0
