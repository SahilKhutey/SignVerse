"""
Security tests verifying input validation, filename sanitization, and path traversal blocks.
"""
import pytest
from backend.ingestion.validators import _sanitize_filename, _detect_mime


@pytest.mark.security
class TestInputValidation:
    """Verifies that user inputs are sanitized and blocked from path traversal attacks."""

    def test_path_traversal_prevention(self):
        """Filenames attempting path traversal must be sanitized to a safe basename or rejected."""
        traversal_attempts = [
            "../../etc/passwd",
            "..\\..\\windows\\win.ini",
            "/absolute/path/to/malicious.py",
            "C:\\System32\\cmd.exe",
            "video.mp4/../../../etc/passwd",
            "video.mp4\x00.exe"  # Null-byte injection
        ]
        for attempt in traversal_attempts:
            res = _sanitize_filename(attempt)
            if res is not None:
                assert '/' not in res
                assert '\\' not in res
                assert '..' not in res

    def test_filename_size_limit(self):
        """Extremely long filenames must be rejected (return None)."""
        long_name = "a" * 300 + ".mp4"
        assert _sanitize_filename(long_name) is None

    def test_valid_mime_detection(self, temp_dirs):
        """Should detect correct MIME type for valid headers."""
        # Minimal MP4 magic bytes header
        mp4_header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom'
        temp_file = temp_dirs["upload"] / "temp_detect.mp4"
        with open(temp_file, "wb") as f:
            f.write(mp4_header)
        
        mime = _detect_mime(temp_file)
        assert mime == "video/mp4"

        # Invalid/random binary should be generic stream
        unknown_bytes = b'\x01\x02\x03\x04' * 10
        mime = _detect_mime(unknown_bytes)
        assert mime == "application/octet-stream"
