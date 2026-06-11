"""
Run memory_profiler on specific functions in development.
Only enabled when MEMORY_PROFILE=true env var.
"""
import os
import functools
import logging

logger = logging.getLogger(__name__)


def memory_profile(track_increment: bool = True):
    """
    Decorator to profile memory usage of a function.
    Only active when MEMORY_PROFILE=true.
    
    Usage:
        @memory_profile()
        def heavy_function():
            ...
    """
    def decorator(func):
        if not os.getenv("MEMORY_PROFILE", "false").lower() == "true":
            return func
        
        try:
            from memory_profiler import profile
            return profile(func, precision=4)
        except ImportError:
            logger.warning("memory_profiler not installed, skipping profiling")
            return func
    return decorator


def profile_block(label: str = "block"):
    """
    Context manager to profile a block of code.
    
    Usage:
        with profile_block("loading_model"):
            model = load_heavy_model()
    """
    if not os.getenv("MEMORY_PROFILE", "false").lower() == "true":
        from contextlib import nullcontext
        return nullcontext()
    
    try:
        from memory_profiler import profile
        @profile(precision=4)
        def _do_profile():
            yield
        return _do_profile()
    except ImportError:
        from contextlib import nullcontext
        return nullcontext()
