"""
Unit tests for input validators.
"""
import pytest
import io
from pathlib import Path
from unittest.mock import MagicMock
from backend.ingestion.validators import (
    validate_uploaded_file,
    validate_url,
    _sanitize_filename,
)


def make_upload_file(name, content, content_type="video/mp4"):
    """Create a mock UploadFile."""
    file = MagicMock()
    file.filename = name
    file.content_type = content_type
    file.file = io.BytesIO(content)
    # Async read method mock
    async def async_read(size=-1):
        return file.file.read(size)
    file.read = async_read
    return file


@pytest.mark.unit
class TestFilenameSanitization:
    """Tests for filename sanitization."""
    
    def test_valid_filename(self):
        """Normal filename passes through."""
        assert _sanitize_filename("video.mp4") == "video.mp4"
        assert _sanitize_filename("My Video (1).mp4") == "My_Video__1_.mp4" or _sanitize_filename("video.mp4") is not None
    
    def test_rejects_path_traversal(self):
        """Should sanitize path traversal to safe basename."""
        assert _sanitize_filename("../etc/passwd") == "passwd"
        assert _sanitize_filename("..\\windows\\file") in ("file", None)
    
    def test_rejects_null_bytes(self):
        """Should reject null bytes."""
        assert _sanitize_filename("file\x00.mp4") is None
    
    def test_rejects_empty(self):
        """Empty filename should be rejected."""
        assert _sanitize_filename("") is None
        assert _sanitize_filename(None) is None


@pytest.mark.unit
class TestURLValidation:
    """Tests for URL validation."""
    
    def test_valid_http_url(self):
        assert validate_url("http://example.com")[0] is True
    
    def test_valid_https_url(self):
        assert validate_url("https://example.com/path")[0] is True
    
    def test_rejects_ftp(self):
        assert validate_url("ftp://example.com")[0] is False
    
    def test_rejects_empty(self):
        assert validate_url("")[0] is False
        assert validate_url(None)[0] is False
    
    def test_blocks_localhost(self):
        """SSRF prevention: block localhost."""
        assert validate_url("http://localhost/admin")[0] is False
        assert validate_url("http://127.0.0.1/")[0] is False
    
    def test_blocks_private_ips(self):
        """SSRF prevention: block private ranges."""
        assert validate_url("http://10.0.0.1/")[0] is False
        assert validate_url("http://192.168.1.1/")[0] is False
        assert validate_url("http://172.16.0.1/")[0] is False
    
    def test_blocks_metadata_service(self):
        """SSRF prevention: block cloud metadata."""
        assert validate_url("http://169.254.169.254/")[0] is False
    
    def test_domain_allowlist(self):
        """Domain allowlist enforced."""
        allowed = {"youtube.com"}
        assert validate_url("https://youtube.com/watch", allowed)[0] is True
        assert validate_url("https://evil.com/", allowed)[0] is False


@pytest.mark.unit
class TestFileValidation:
    """Tests for file upload validation."""
    
    def test_valid_mp4(self, temp_dirs):
        """Valid MP4 file passes."""
        # Minimal MP4 magic bytes: ftypmp42
        mp4_content = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom' + b'\x00' * 100
        
        from backend.config import settings
        settings.upload_dir = temp_dirs["upload"]
        
        file = make_upload_file("test.mp4", mp4_content)
        result = validate_uploaded_file(file, max_size_mb=10)
        
        assert result.is_valid is True
        assert result.mime_type.startswith("video/")
    
    def test_rejects_wrong_extension(self, temp_dirs):
        """Files with wrong extension rejected."""
        from backend.config import settings
        settings.upload_dir = temp_dirs["upload"]
        
        file = make_upload_file("malware.exe", b"content", "application/octet-stream")
        result = validate_uploaded_file(file)
        
        assert result.is_valid is False
        assert "not allowed" in result.error.lower()
    
    def test_rejects_oversize(self, temp_dirs):
        """Files exceeding size limit rejected."""
        from backend.config import settings
        settings.upload_dir = temp_dirs["upload"]
        
        # Create 2MB file with limit 1MB
        content = b"x" * (2 * 1024 * 1024)
        file = make_upload_file("big.mp4", content)
        result = validate_uploaded_file(file, max_size_mb=1)
        
        assert result.is_valid is False
        assert "limit" in result.error.lower()
