"""
Security tests verifying authorization, authentication, and role checks.
"""
import pytest
from fastapi import HTTPException, status
from unittest.mock import MagicMock
from fastapi.security import HTTPAuthorizationCredentials
from backend.security.auth import (
    get_current_user, create_jwt_token, verify_api_key, hash_api_key,
    revoke_token, is_token_revoked
)


@pytest.mark.security
class TestAuthSecurity:
    """Verifies authentication and authorization constraints."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_jwt(self):
        """Should accept valid JWT token."""
        token = create_jwt_token(user_id="alice", role="user")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(request=MagicMock(), credentials=creds)
        assert user["user_id"] == "alice"
        assert user["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_current_user_revoked_jwt(self):
        """Should reject revoked JTI tokens."""
        token = create_jwt_token(user_id="bob", role="user")
        
        # Revoke it
        import jwt
        from backend.security.auth import JWT_SECRET, JWT_ALGORITHM
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        revoke_token(payload["jti"])
        
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=MagicMock(), credentials=creds)
        assert exc.value.status_code == 401
        assert "revoked" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_jwt(self):
        """Should reject malformed/signature-invalid tokens."""
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token-value")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=MagicMock(), credentials=creds)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_valid_api_key(self):
        """Should accept a valid API key passed as bearer token."""
        # Valid key from VALID_API_KEYS: "demo-key-1234"
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="demo-key-1234")
        user = await get_current_user(request=MagicMock(), credentials=creds)
        assert user["user_id"] == "api_key"
        assert user["role"] == "admin"

    @pytest.mark.asyncio
    async def test_get_current_user_missing_credentials(self):
        """Should reject requests with missing credentials."""
        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=MagicMock(), credentials=None)
        assert exc.value.status_code == 401
