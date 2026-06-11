"""
Authentication and authorization.
Supports: API keys, JWT tokens, session cookies.
"""
import secrets
import hashlib
import hmac
import time
import jwt
from typing import Optional, Dict, List
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass
from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.config import settings

# === Configuration ===
JWT_SECRET = getattr(settings, 'jwt_secret', None) or secrets.token_urlsafe(64)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# API keys (in production: hash + store in DB)
VALID_API_KEYS: Dict[str, Dict] = {
    # Format: "key_hash": {"name": "...", "role": "admin" | "user", "rate_limit": 100}
    hashlib.sha256(b"demo-key-1234").hexdigest(): {
        "name": "Demo Key",
        "role": "admin",
        "rate_limit_per_min": 1000,
    },
}

# CORS allowlist
ALLOWED_ORIGINS = settings.cors_origins

# === Security helpers ===

def hash_api_key(key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new secure API key."""
    return f"sv_{secrets.token_urlsafe(32)}"


def create_jwt_token(user_id: str, role: str = "user", expiry_hours: int = JWT_EXPIRY_HOURS) -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": user_id,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expiry_hours),
        "jti": secrets.token_urlsafe(16),  # Unique token ID (for revocation)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[Dict]:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_api_key(api_key: str) -> Optional[Dict]:
    """Verify an API key. Returns key metadata or None."""
    key_hash = hash_api_key(api_key)
    return VALID_API_KEYS.get(key_hash)


# === Token blacklist (for logout/revocation) ===
_TOKEN_BLACKLIST: set = set()

def revoke_token(jti: str):
    """Revoke a JWT by its JTI."""
    _TOKEN_BLACKLIST.add(jti)


def is_token_revoked(jti: str) -> bool:
    return jti in _TOKEN_BLACKLIST


# === FastAPI dependencies ===

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict:
    """
    Authenticate request via JWT or API key.
    Returns user dict {user_id, role} or raises 401.
    """
    # Try JWT first
    if credentials and credentials.scheme == "Bearer":
        token = credentials.credentials
        payload = verify_jwt_token(token)
        if payload:
            if is_token_revoked(payload.get("jti", "")):
                raise HTTPException(401, "Token revoked")
            return {"user_id": payload["sub"], "role": payload["role"]}
        
        # Try as API key
        key_info = verify_api_key(token)
        if key_info:
            return {"user_id": "api_key", "role": key_info["role"]}
    
    # No credentials or invalid
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(*allowed_roles: str):
    """Decorator factory: require specific role(s) to access endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("current_user")
            if not user or user.get("role") not in allowed_roles:
                raise HTTPException(403, "Insufficient permissions")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# === Login endpoint ===

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str


async def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate user. In production, check against DB with hashed passwords.
    For demo: simple check.
    """
    # DEMO ONLY - replace with real auth in production
    DEMO_USERS = {
        "admin": hashlib.sha256(b"admin123").hexdigest(),
        "demo": hashlib.sha256(b"demo123").hexdigest(),
    }
    
    expected_hash = DEMO_USERS.get(username)
    if not expected_hash:
        return None
    
    if hmac.compare_digest(expected_hash, hashlib.sha256(password.encode()).hexdigest()):
        return {"user_id": username, "role": "admin" if username == "admin" else "user"}
    return None
