"""
Per-request profiling middleware.
Tracks timing, memory delta, and custom metrics.
"""
import time
import psutil
import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import logging

from backend.services.profiling.memory_tracker import memory_tracker

logger = logging.getLogger("profiling")


class ProfilingMiddleware(BaseHTTPMiddleware):
    """
    Adds detailed per-request profiling.
    
    Adds headers to response:
    - X-Profiling-Time-Ms: Total request time
    - X-Profiling-Memory-Delta-Mb: Memory used by this request
    - X-Profiling-CPU-Percent: CPU usage during request
    """
    
    def __init__(self, app, track_all: bool = False):
        super().__init__(app)
        self.track_all = track_all
        self.process = psutil.Process(os.getpid())
    
    async def dispatch(self, request: Request, call_next):
        if not self._should_profile(request):
            return await call_next(request)
        
        # Baseline
        start_time = time.perf_counter()
        start_mem = self.process.memory_info().rss
        start_cpu = self.process.cpu_times()
        
        # Track this session/component if session_id in path
        component = self._extract_component(request)
        comp_tracker = None
        if component:
            comp_tracker = memory_tracker.register_component(
                name=component,
                component_type="request"
            )
        
        # Execute
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise e
        
        # Calculate deltas
        duration_ms = (time.perf_counter() - start_time) * 1000
        end_mem = self.process.memory_info().rss
        end_cpu = self.process.cpu_times()
        
        mem_delta_mb = (end_mem - start_mem) / 1024 / 1024
        user_cpu = (end_cpu.user - start_cpu.user) + (end_cpu.system - start_cpu.system)
        cpu_percent = (user_cpu / (duration_ms / 1000)) * 100 if duration_ms > 0 else 0
        
        # Add profiling headers
        response.headers["X-Profiling-Time-Ms"] = f"{duration_ms:.1f}"
        response.headers["X-Profiling-Memory-Delta-Mb"] = f"{mem_delta_mb:.2f}"
        response.headers["X-Profiling-CPU-Percent"] = f"{cpu_percent:.1f}"
        
        # Update component tracker
        if comp_tracker:
            comp_tracker.update(end_mem / 1024 / 1024)
        
        # Log if request was slow or memory-heavy
        if duration_ms > 1000 or abs(mem_delta_mb) > 50:
            logger.warning(
                f"Slow/heavy request: {request.method} {request.url.path} "
                f"({duration_ms:.0f}ms, {mem_delta_mb:+.1f}MB)"
            )
        
        return response
    
    def _should_profile(self, request: Request) -> bool:
        """Determine if we should profile this request."""
        if self.track_all:
            return True
        
        # Profile only specific endpoints
        profile_paths = [
            "/api/capture",
            "/api/ingest",
            "/api/dataset",
            "/api/export",
            "/api/analytics",
            "/api/system",
            "/api/profiling",
        ]
        return any(request.url.path.startswith(p) for p in profile_paths)
    
    def _extract_component(self, request: Request) -> str:
        """Extract a component name from the request path."""
        path = request.url.path
        
        if "/capture" in path:
            return f"capture_{path.split('/')[-1]}"
        if "/export" in path:
            fmt = request.query_params.get("fmt", "json")
            return f"export_{fmt}"
        if "/dataset" in path:
            return f"dataset_{path.split('/')[-1]}"
        
        return f"request_{request.method}_{path[:30].replace('/', '_')}"
