"""
Continuous memory profiling for production monitoring.
Tracks per-session, per-job, and per-component memory usage.
"""
import os
import gc
import sys
import time
import threading
import psutil
import tracemalloc as tm
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from contextlib import contextmanager
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Point-in-time memory measurement."""
    timestamp: float
    label: str
    
    # Process-level
    rss_mb: float              # Resident Set Size
    vms_mb: float              # Virtual Memory Size
    shared_mb: float           # Shared memory
    private_mb: float          # Private memory
    available_mb: float        # System available
    
    # Python-level (tracemalloc)
    py_current_mb: float       # Current Python allocated
    py_peak_mb: float          # Peak Python allocated
    py_objects: int            # Tracked objects count
    
    # System
    cpu_percent: float
    thread_count: int
    fd_count: int              # Open file descriptors
    
    # GC stats
    gc_gen0: int
    gc_gen1: int
    gc_gen2: int
    gc_collected: tuple
    
    @classmethod
    def capture(cls, label: str = "snapshot") -> "MemorySnapshot":
        """Capture current memory state."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        
        # System memory
        sys_mem = psutil.virtual_memory()
        
        # CPU
        cpu_pct = process.cpu_percent(interval=0.0)
        
        # FDs
        try:
            fd_count = process.num_fds() if hasattr(process, 'num_fds') else 0
        except:
            fd_count = 0
        
        # tracemalloc
        py_current, py_peak = tm.get_traced_memory() if tm.is_tracing() else (0, 0)
        
        # GC
        gc_stats = gc.get_stats()
        gc_counts = gc.get_count()
        
        # Avoid forcing gc in every single snapshot to avoid freezing threads
        gc_collected = (0, 0, 0)
        
        return cls(
            timestamp=time.time(),
            label=label,
            rss_mb=mem_info.rss / 1024 / 1024,
            vms_mb=mem_info.vms / 1024 / 1024,
            shared_mb=getattr(mem_info, 'shared', 0) / 1024 / 1024,
            private_mb=mem_info.rss / 1024 / 1024,  # Approximation
            available_mb=sys_mem.available / 1024 / 1024,
            py_current_mb=py_current / 1024 / 1024,
            py_peak_mb=py_peak / 1024 / 1024,
            py_objects=len(gc.get_objects()),
            cpu_percent=cpu_pct,
            thread_count=process.num_threads(),
            fd_count=fd_count,
            gc_gen0=gc_counts[0] if len(gc_counts) > 0 else 0,
            gc_gen1=gc_counts[1] if len(gc_counts) > 1 else 0,
            gc_gen2=gc_counts[2] if len(gc_counts) > 2 else 0,
            gc_collected=gc_collected,
        )
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ComponentMemory:
    """Track memory for a specific component (model, session, job)."""
    name: str
    component_type: str           # "model" | "session" | "job" | "stream" | "request"
    
    initial_mb: float
    current_mb: float
    peak_mb: float
    last_update: float
    
    # Allocation tracking
    total_allocations: int = 0
    total_deallocations: int = 0
    net_allocations: int = 0
    
    def update(self, current_mb: float):
        """Update memory reading."""
        self.current_mb = current_mb
        self.peak_mb = max(self.peak_mb, current_mb)
        self.last_update = time.time()
    
    def to_dict(self) -> dict:
        return asdict(self)


class MemoryTracker:
    """
    Continuous memory tracker for production.
    """
    
    def __init__(
        self,
        snapshot_interval: float = 5.0,
        max_history: int = 720,        # 1 hour at 5s intervals
        leak_detection_window: int = 60,  # Compare against window of N snapshots
        leak_growth_threshold_mb: float = 100.0,  # Alert if growth > 100MB
    ):
        self.snapshot_interval = snapshot_interval
        self.max_history = max_history
        self.leak_detection_window = leak_detection_window
        self.leak_growth_threshold_mb = leak_growth_threshold_mb
        
        # Storage
        self.snapshots: deque = deque(maxlen=max_history)
        self.components: Dict[str, ComponentMemory] = {}
        self.alerts: List[Dict] = []
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Process reference
        self._process = psutil.Process(os.getpid())
        self._start_time = time.time()
    
    def start(self):
        """Start background memory monitoring."""
        if self._running:
            return
        self._running = True
        
        # Start tracemalloc only when background monitoring starts
        if not tm.is_tracing():
            tm.start(1)
            
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="MemoryTracker"
        )
        self._thread.start()
        logger.info(f"Memory tracker started (interval={self.snapshot_interval}s)")
    
    def stop(self):
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        
        # Stop tracemalloc on shutdown to free resources
        if tm.is_tracing():
            tm.stop()
            
        logger.info("Memory tracker stopped")
    
    def _monitor_loop(self):
        """Background thread: periodic snapshots + leak detection."""
        while self._running:
            try:
                # Capture snapshot
                snapshot = MemorySnapshot.capture(label="periodic")
                
                with self._lock:
                    self.snapshots.append(snapshot)
                    
                    # Update component memory from tracemalloc
                    self._update_components_from_tracemalloc()
                    
                    # Leak detection
                    self._detect_leaks()
                
                time.sleep(self.snapshot_interval)
            except Exception as e:
                logger.error(f"Memory monitor error: {e}")
                time.sleep(self.snapshot_interval)
    
    def _update_components_from_tracemalloc(self):
        """Get current allocation sizes from tracemalloc."""
        if not tm.is_tracing():
            return
        
        try:
            snapshot = tm.take_snapshot()
            
            # Group by component
            for stat in snapshot.statistics('filename')[:20]:
                filename = stat.traceback.format()[0] if stat.traceback else ""
                component = self._identify_component(filename)
                
                if component:
                    size_mb = stat.size / 1024 / 1024
                    if component not in self.components:
                        self.register_component(component, "model")
                    self.components[component].update(size_mb)
        except Exception as e:
            pass
    
    def _identify_component(self, filename: str) -> Optional[str]:
        """Map filename to component name."""
        if "perception" in filename or "holistic" in filename:
            return "perception_model"
        if "yolo" in filename.lower() or "ultralytics" in filename:
            return "yolo_model"
        if "depth" in filename or "midas" in filename:
            return "depth_model"
        if "export" in filename:
            return "exporter"
        return None
    
    def _detect_leaks(self):
        """Detect potential memory leaks by analyzing growth trend."""
        with self._lock:
            if len(self.snapshots) < self.leak_detection_window:
                return
            
            recent = list(self.snapshots)[-self.leak_detection_window:]
            rss_values = [s.rss_mb for s in recent]
            
            n = len(rss_values)
            x_mean = (n - 1) / 2
            y_mean = sum(rss_values) / n
            
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            if denominator < 1e-6:
                return
                
            slope = sum((i - x_mean) * (rss_values[i] - y_mean) for i in range(n)) / denominator
            growth = slope * n
            
            if growth > self.leak_growth_threshold_mb:
                alert = {
                    "type": "MEMORY_LEAK",
                    "severity": "WARNING" if growth < self.leak_growth_threshold_mb * 2 else "CRITICAL",
                    "growth_mb": growth,
                    "window_seconds": self.leak_detection_window * self.snapshot_interval,
                    "rss_now_mb": rss_values[-1],
                    "rss_then_mb": rss_values[0],
                    "message": f"Memory grew {growth:.1f}MB in last {self.leak_detection_window * self.snapshot_interval:.0f}s",
                    "timestamp": time.time(),
                }
                self.alerts.append(alert)
                logger.warning(f"⚠️ MEMORY LEAK DETECTED: {alert['message']}")
    
    def register_component(self, name: str, component_type: str) -> ComponentMemory:
        """Register a component for memory tracking."""
        with self._lock:
            if name in self.components:
                return self.components[name]
            comp = ComponentMemory(
                name=name,
                component_type=component_type,
                initial_mb=0.0,
                current_mb=0.0,
                peak_mb=0.0,
                last_update=time.time(),
            )
            self.components[name] = comp
            return comp
    
    def get_snapshot(self) -> MemorySnapshot:
        """Get current memory state immediately."""
        return MemorySnapshot.capture(label="manual")
    
    def get_timeline(self, last_n: int = 60) -> List[Dict]:
        """Get memory timeline (last N snapshots)."""
        with self._lock:
            snapshots = list(self.snapshots)[-last_n:]
            return [s.to_dict() for s in snapshots]
    
    def get_components(self) -> List[Dict]:
        """Get all tracked components."""
        with self._lock:
            return [c.to_dict() for c in self.components.values()]
    
    def get_alerts(self, since: float = 0) -> List[Dict]:
        """Get alerts since timestamp."""
        with self._lock:
            return [a for a in self.alerts if a["timestamp"] > since]
    
    def get_summary(self) -> Dict:
        """Get overall summary statistics."""
        with self._lock:
            if not self.snapshots:
                # Capture a quick snapshot to avoid empty results
                self.snapshots.append(MemorySnapshot.capture(label="periodic"))
                
            rss_values = [s.rss_mb for s in self.snapshots]
            cpu_values = [s.cpu_percent for s in self.snapshots]
            
            return {
                "uptime_seconds": time.time() - self._start_time,
                "snapshot_count": len(self.snapshots),
                "process": {
                    "rss_mb": {
                        "current": rss_values[-1],
                        "min": min(rss_values),
                        "max": max(rss_values),
                        "mean": sum(rss_values) / len(rss_values),
                    },
                    "cpu_percent": {
                        "current": cpu_values[-1] if cpu_values else 0.0,
                        "mean": sum(cpu_values) / len(cpu_values) if cpu_values else 0.0,
                    },
                },
                "components": {
                    "count": len(self.components),
                    "peak_total_mb": sum(c.peak_mb for c in self.components.values()),
                },
                "alerts": {
                    "total": len(self.alerts),
                    "recent": len([a for a in self.alerts if time.time() - a["timestamp"] < 3600]),
                },
            }


# Singleton instance
memory_tracker = MemoryTracker(
    snapshot_interval=5.0,
    max_history=720,
    leak_detection_window=60,
    leak_growth_threshold_mb=100.0,
)
