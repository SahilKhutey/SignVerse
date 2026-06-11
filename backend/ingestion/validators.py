"""
Validate all input at the boundary.
Nothing unsafe gets past this layer.
"""
import os
import re
import magic
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from fastapi import UploadFile, HTTPException

from backend.config import settings


# Allowed MIME types
ALLOWED_VIDEO_MIME = {
    "video/mp4", "video/avi", "video/x-msvideo", "video/quicktime",
    "video/webm", "video/x-matroska", "video/3gpp",
}

ALLOWED_IMAGE_MIME = {
    "image/jpeg", "image/png", "image/webp",
}

# File extensions
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".3gp"}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class ValidatedFile:
    """Result of file validation."""
    is_valid: bool
    file_path: Optional[Path] = None
    file_size: int = 0
    mime_type: str = ""
    sha256: str = ""
    error: Optional[str] = None
    metadata: dict = None


def validate_uploaded_file(
    file: UploadFile,
    max_size_mb: int = None,
    allowed_kinds: set = None,
) -> ValidatedFile:
    """
    Validate uploaded file at the boundary.
    Checks: size, MIME, magic bytes, filename safety.
    """
    max_size_mb = max_size_mb or settings.max_upload_mb
    allowed_kinds = allowed_kinds or {"video", "image"}
    allowed_mime = set()
    if "video" in allowed_kinds:
        allowed_mime |= ALLOWED_VIDEO_MIME
    if "image" in allowed_kinds:
        allowed_mime |= ALLOWED_IMAGE_MIME
    
    # 1. Check filename safety
    if not file.filename:
        return ValidatedFile(is_valid=False, error="No filename")
    
    safe_name = _sanitize_filename(file.filename)
    if not safe_name:
        return ValidatedFile(is_valid=False, error="Invalid filename")
    
    # 2. Check file size (we read in chunks to avoid loading huge files)
    #    But also need full content for hash — so we save to temp first
    ext = Path(safe_name).suffix.lower()
    if ext not in (ALLOWED_VIDEO_EXT | ALLOWED_IMAGE_EXT):
        return ValidatedFile(is_valid=False, error=f"Extension {ext} not allowed")
    
    # 3. Save to temp location with safe name
    safe_path = _get_safe_storage_path(safe_name)
    
    sha256 = hashlib.sha256()
    total_size = 0
    
    try:
        with open(safe_path, "wb") as f:
            while chunk := file.file.read(1024 * 64):  # 64KB chunks
                total_size += len(chunk)
                if total_size > max_size_mb * 1024 * 1024:
                    f.close()
                    safe_path.unlink()
                    return ValidatedFile(
                        is_valid=False,
                        error=f"File exceeds {max_size_mb}MB limit"
                    )
                sha256.update(chunk)
                f.write(chunk)
    except Exception as e:
        if safe_path.exists():
            safe_path.unlink()
        return ValidatedFile(is_valid=False, error=f"Save failed: {e}")
    
    # 4. Verify magic bytes (actual file content, not just extension)
    detected_mime = _detect_mime(safe_path)
    if detected_mime not in allowed_mime:
        safe_path.unlink()
        return ValidatedFile(
            is_valid=False,
            error=f"File content doesn't match allowed types. Detected: {detected_mime}"
        )
    
    # 5. Extract metadata
    metadata = _extract_metadata(safe_path, detected_mime)
    
    return ValidatedFile(
        is_valid=True,
        file_path=safe_path,
        file_size=total_size,
        mime_type=detected_mime,
        sha256=sha256.hexdigest(),
        metadata=metadata,
    )


def _sanitize_filename(filename: str) -> Optional[str]:
    """
    Sanitize filename: prevent path traversal, null bytes, control chars.
    """
    if not filename:
        return None
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Reject if contains path separators or null bytes
    if any(c in filename for c in ['/', '\\', '\0']):
        return None
    
    # Reject control characters
    if any(ord(c) < 32 for c in filename):
        return None
    
    # Limit length
    if len(filename) > 255:
        return None
    
    # Only allow safe characters
    if not re.match(r'^[a-zA-Z0-9._\- ()]+$', filename):
        return None
    
    return filename


def _get_safe_storage_path(filename: str) -> Path:
    """Generate a safe storage path with UUID prefix to prevent collisions."""
    import uuid
    unique_prefix = uuid.uuid4().hex[:12]
    safe_name = f"{unique_prefix}_{filename}"
    return settings.upload_dir / safe_name


def _detect_mime(path: Path) -> str:
    """Detect actual MIME type from file content (magic bytes)."""
    try:
        # python-magic for accurate detection
        m = magic.Magic(mime=True)
        detected = m.from_file(str(path))
        return detected
    except Exception:
        # Fallback: guess from extension
        mime, _ = mimetypes.guess_type(str(path))
        return mime or "application/octet-stream"


def _extract_metadata(path: Path, mime: str) -> dict:
    """Extract media metadata (duration, dimensions, codec, etc.)."""
    metadata = {"mime": mime}
    
    try:
        if mime.startswith("video/"):
            import cv2
            cap = cv2.VideoCapture(str(path))
            metadata.update({
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "duration_s": (
                    int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) /
                    max(cap.get(cv2.CAP_PROP_FPS), 1)
                ),
            })
            cap.release()
        elif mime.startswith("image/"):
            from PIL import Image
            with Image.open(path) as img:
                metadata.update({
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                })
    except Exception as e:
        metadata["extraction_error"] = str(e)
    
    return metadata


def validate_url(url: str, allowed_domains: set = None) -> Tuple[bool, str]:
    """
    Validate URL: format, scheme, optional domain allowlist.
    """
    from urllib.parse import urlparse
    
    if not url or len(url) > 2048:
        return False, "URL too long or empty"
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"
    
    if parsed.scheme not in ("http", "https"):
        return False, "Only http/https URLs allowed"
    
    if not parsed.netloc:
        return False, "No host in URL"
    
    # Check for SSRF attempts (private IPs, localhost)
    hostname = parsed.hostname
    if hostname:
        clean_host = hostname.strip("[]").lower()
        if clean_host == "localhost":
            return False, "Internal URLs not allowed"
        
        # Try parsing as an IP address to check CIDR ranges securely
        import ipaddress
        try:
            ip = ipaddress.ip_address(clean_host)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified:
                return False, "Internal URLs not allowed"
        except ValueError:
            # Not a raw IP address (it's a domain hostname like google.com)
            pass
    
    if allowed_domains and parsed.netloc not in allowed_domains:
        return False, f"Domain not in allowlist"
    
    return True, "OK"
