import time
from typing import Dict, List, Any
from dataclasses import dataclass, field, asdict
import threading

@dataclass
class RouteMetrics:
    path: str
    method: str
    count: int = 0
    total_time_s: float = 0.0
    max_time_s: float = 0.0
    min_time_s: float = 9999.0
    status_2xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0

    def record_request(self, duration_s: float, status_code: int):
        self.count += 1
        self.total_time_s += duration_s
        self.max_time_s = max(self.max_time_s, duration_s)
        self.min_time_s = min(self.min_time_s, duration_s)
        
        if 200 <= status_code < 300:
            self.status_2xx += 1
        elif 400 <= status_code < 500:
            self.status_4xx += 1
        elif 500 <= status_code < 600:
            self.status_5xx += 1

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "method": self.method,
            "count": self.count,
            "mean_latency_ms": round((self.total_time_s / self.count) * 1000, 2) if self.count > 0 else 0.0,
            "max_latency_ms": round(self.max_time_s * 1000, 2) if self.count > 0 else 0.0,
            "min_latency_ms": round(self.min_time_s * 1000, 2) if self.count > 0 and self.min_time_s != 9999.0 else 0.0,
            "status_2xx": self.status_2xx,
            "status_4xx": self.status_4xx,
            "status_5xx": self.status_5xx,
            "error_rate_percent": round(((self.status_5xx) / self.count) * 100, 2) if self.count > 0 else 0.0
        }

class TelemetryManager:
    """
    Manages global telemetry operations:
    - Route latencies
    - WebSocket packet metrics
    - Thread-safe statistics
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.route_metrics: Dict[str, RouteMetrics] = {}
        
        # WebSocket metrics
        self.ws_active_connections = 0
        self.ws_total_frames_received = 0
        self.ws_total_frames_processed = 0
        self.ws_processing_time_total = 0.0
        self.ws_peak_processing_time = 0.0

    def record_route_latency(self, path: str, method: str, duration_s: float, status_code: int):
        key = f"{method}:{path}"
        with self._lock:
            if key not in self.route_metrics:
                self.route_metrics[key] = RouteMetrics(path=path, method=method)
            self.route_metrics[key].record_request(duration_s, status_code)

    def record_ws_connect(self):
        with self._lock:
            self.ws_active_connections += 1

    def record_ws_disconnect(self):
        with self._lock:
            self.ws_active_connections = max(0, self.ws_active_connections - 1)

    def record_ws_frame(self, duration_s: float, processed: bool = True):
        with self._lock:
            self.ws_total_frames_received += 1
            if processed:
                self.ws_total_frames_processed += 1
                self.ws_processing_time_total += duration_s
                self.ws_peak_processing_time = max(self.ws_peak_processing_time, duration_s)

    def get_api_metrics(self) -> List[dict]:
        with self._lock:
            return [m.to_dict() for m in self.route_metrics.values()]

    def get_ws_metrics(self) -> dict:
        with self._lock:
            mean_time_ms = (self.ws_processing_time_total / self.ws_total_frames_processed) * 1000 if self.ws_total_frames_processed > 0 else 0.0
            return {
                "active_connections": self.ws_active_connections,
                "total_frames_received": self.ws_total_frames_received,
                "total_frames_processed": self.ws_total_frames_processed,
                "mean_frame_latency_ms": round(mean_time_ms, 2),
                "peak_frame_latency_ms": round(self.ws_peak_processing_time * 1000, 2),
            }

# Global singleton
telemetry_manager = TelemetryManager()
