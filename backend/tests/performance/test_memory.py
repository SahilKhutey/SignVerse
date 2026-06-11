"""
Performance tests verifying memory usage stability.
Ensures no significant memory leaks or compounding allocations occur during repeated processing loops.
"""
import pytest
import gc
import os
try:
    import psutil
except ImportError:
    psutil = None
from backend.services.perception_pipeline import PerceptionPipeline
import numpy as np


@pytest.mark.performance
class TestMemoryLeak:
    """Verifies memory footprint stability over repeated processing iterations."""

    def test_pipeline_memory_growth(self, sample_frame):
        """Repeated frame processing should not leak memory."""
        pipeline = PerceptionPipeline()
        
        # Warm up
        for _ in range(5):
            pipeline.process_frame(sample_frame)
        
        gc.collect()
        
        # Only assert memory if psutil is installed
        if psutil is not None:
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
            
            # Execute processing loop
            for i in range(50):
                pipeline.process_frame(sample_frame)
                
            gc.collect()
            final_memory = process.memory_info().rss
            
            # Allow for up to 10MB overhead max, but should not grow linearly
            growth_mb = (final_memory - initial_memory) / (1024 * 1024)
            assert growth_mb < 10.0, f"Memory grew by {growth_mb:.2f} MB (leak threshold: 10.0 MB)"
        else:
            # Fallback if psutil is not available (just run to check for crashes)
            for i in range(50):
                pipeline.process_frame(sample_frame)
            assert True
