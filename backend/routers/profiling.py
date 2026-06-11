"""
Endpoints to expose profiling data.
"""
from fastapi import APIRouter, Query
from typing import Optional, List, Dict
import gc
import time

from backend.services.profiling.memory_tracker import memory_tracker

router = APIRouter(prefix="/api/profiling", tags=["profiling"])


@router.get("/memory/snapshot")
async def get_memory_snapshot():
    """Get current memory state."""
    snapshot = memory_tracker.get_snapshot()
    return snapshot.to_dict()


@router.get("/memory/timeline")
async def get_memory_timeline(
    last_n: int = Query(60, ge=1, le=720),
):
    """Get memory timeline (last N snapshots, default 5 min)."""
    return memory_tracker.get_timeline(last_n=last_n)


@router.get("/memory/components")
async def get_memory_components():
    """Get memory usage by component."""
    return memory_tracker.get_components()


@router.get("/memory/summary")
async def get_memory_summary():
    """Get aggregate memory statistics."""
    return memory_tracker.get_summary()


@router.get("/memory/alerts")
async def get_memory_alerts(
    since_seconds: int = Query(3600, ge=0),
):
    """Get memory-related alerts from last N seconds."""
    since = time.time() - since_seconds
    return memory_tracker.get_alerts(since=since)


@router.post("/memory/gc")
async def force_garbage_collection():
    """Force garbage collection and return memory delta."""
    before = memory_tracker.get_snapshot()
    collected = gc.collect()
    after = memory_tracker.get_snapshot()
    
    return {
        "objects_collected": collected,
        "memory_before_mb": before.rss_mb,
        "memory_after_mb": after.rss_mb,
        "freed_mb": max(0.0, before.rss_mb - after.rss_mb),
    }


@router.get("/memory/report")
async def get_memory_report():
    """Generate comprehensive memory report."""
    summary = memory_tracker.get_summary()
    timeline = memory_tracker.get_timeline(last_n=60)
    components = memory_tracker.get_components()
    alerts = memory_tracker.get_alerts()
    current = memory_tracker.get_snapshot().to_dict()
    
    return {
        "current": current,
        "summary": summary,
        "timeline_5min": timeline,
        "components": components,
        "alerts": alerts,
        "recommendations": _generate_recommendations(summary, alerts, components),
    }


def _generate_recommendations(summary: dict, alerts: list, components: list) -> list:
    """Generate actionable recommendations based on profiling data."""
    recs = []
    
    rss_max = summary.get("process", {}).get("rss_mb", {}).get("max", 0.0)
    
    if rss_max > 4096:
        recs.append({
            "severity": "HIGH",
            "issue": "Peak memory > 4GB",
            "suggestion": "Consider horizontal scaling with multiple workers",
        })
    elif rss_max > 2048:
        recs.append({
            "severity": "MEDIUM",
            "issue": "Peak memory > 2GB",
            "suggestion": "Monitor closely, may need optimization",
        })
    
    leak_alerts = [a for a in alerts if a.get("type") == "MEMORY_LEAK"]
    if leak_alerts:
        recs.append({
            "severity": "HIGH",
            "issue": f"{len(leak_alerts)} memory leak alerts",
            "suggestion": "Investigate using py-spy or memory_profiler",
        })
    
    for comp in components:
        if comp.get("peak_mb", 0.0) > 500:
            recs.append({
                "severity": "MEDIUM",
                "issue": f"Component '{comp['name']}' peaked at {comp['peak_mb']:.0f}MB",
                "suggestion": "Consider lazy loading or unloading after use",
            })
    
    if not recs:
        recs.append({
            "severity": "INFO",
            "issue": "All metrics within healthy ranges",
            "suggestion": "Continue monitoring",
        })
    
    return recs
