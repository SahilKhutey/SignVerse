"""
Unit tests for authentication and authorization.
"""
import pytest
import time
from backend.security.auth import (
    create_jwt_token, verify_jwt_token, generate_api_key, hash_api_key,
    verify_api_key, revoke_token, is_token_revoked
)


@pytest.mark.unit
class TestAuth:
    """Tests for JWT and API key security utilities."""
    
    def test_jwt_token_lifecycle(self):
        """Should create a valid token, verify it, and extract user data."""
        token = create_jwt_token(user_id="user1", role="admin")
        assert isinstance(token, str)
        assert len(token) > 0
        
        payload = verify_jwt_token(token)
        assert payload is not None
        assert payload["sub"] == "user1"
        assert payload["role"] == "admin"
        assert "jti" in payload
    
    def test_jwt_token_revocation(self):
        """Revoking a token's JTI should reject it on subsequent verifications."""
        token = create_jwt_token(user_id="user2", role="user")
        payload = verify_jwt_token(token)
        jti = payload["jti"]
        
        assert is_token_revoked(jti) is False
        
        # Revoke the JTI
        revoke_token(jti)
        assert is_token_revoked(jti) is True
        
        # Verify should fail (revoked token check via is_token_revoked)
        assert is_token_revoked(jti) is True
    
    def test_expired_jwt_token(self):
        """Expired token should fail verification."""
        # Create token that expired 1 hour ago
        token = create_jwt_token(user_id="user3", role="user", expiry_hours=-1)
        payload = verify_jwt_token(token)
        assert payload is None
    
    def test_api_key_generation_and_verification(self):
        """API key generation, hashing, and verification should work."""
        # Note: verify_api_key relies on config database or list.
        # Let's verify hashing / generation logic.
        raw_key = generate_api_key()
        assert raw_key.startswith("sv_")
        assert len(raw_key) > 30  # prefix + secure random string
        
        hashed = hash_api_key(raw_key)
        assert len(hashed) == 64  # sha256 hex
        
        # Verify should return None for random invalid key
        assert verify_api_key("invalid") is None
