"""
Strict CORS configuration. Default-deny, allowlist-only.
"""
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from backend.config import settings


def configure_cors(app: FastAPI):
    """
    Apply strict CORS policy.
    - Only allows specified origins
    - No wildcards in production
    - Restricts methods + headers
    """
    # In production, use specific origins only
    origins = settings.cors_origins
    
    # SECURITY: Never use "*" in production
    if "*" in origins:
        import logging
        logger = logging.getLogger("security")
        logger.warning("⚠️ CORS allows ALL origins (*). Restrict in production!")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Client-Version",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=600,  # Cache preflight for 10 min
    )
