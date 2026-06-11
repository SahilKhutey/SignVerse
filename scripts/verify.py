"""Verify installation + system health."""
import sys
import os
from pathlib import Path


def check_python_deps():
    """Check Python packages are installed."""
    required = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("mediapipe", "mediapipe"),
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("yt_dlp", "yt-dlp"),
        ("sqlalchemy", "sqlalchemy"),
    ]
    missing = []
    for mod, pkg in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[Check] Missing Python packages: {', '.join(missing)}")
        print(f"   Run: pip install -r requirements.txt")
        return False
    print(f"[Check] Python dependencies OK ({len(required)} packages)")
    return True


def check_node_deps():
    """Check Node packages installed."""
    if not os.path.exists("frontend/node_modules/three"):
        print("[Check] Frontend deps missing. Run: cd frontend && npm install")
        return False
    print("[Check] Node dependencies OK")
    return True


def check_directories():
    """Check required directories exist."""
    dirs = ["data/uploads", "exports", "datasets", "frontend"]
    for d in dirs:
        if not Path(d).exists():
            print(f"[Check] Missing directory: {d}")
            return False
    print("[Check] All directories present")
    return True


def check_backend_health():
    """Try to import backend modules."""
    try:
        sys.path.insert(0, str(Path(__file__).parents[1].resolve()))
        from backend.services.kinematics.kinematics import Kinematics
        from backend.services.kinematics.bvh_writer import BVHWriter
        from backend.core.database import db
        print("[Check] Backend import health check OK")
        return True
    except Exception as e:
        print(f"[Check] Backend imports failed: {e}")
        return False


def main():
    print("========================================")
    print("  SignVerse Robotics Verification Tool")
    print("========================================")
    
    # Create necessary dirs
    Path("data/uploads").mkdir(parents=True, exist_ok=True)
    Path("exports").mkdir(parents=True, exist_ok=True)
    Path("datasets").mkdir(parents=True, exist_ok=True)
    
    h1 = check_python_deps()
    h2 = check_node_deps()
    h3 = check_directories()
    h4 = check_backend_health()
    
    if h1 and h2 and h3 and h4:
        print("\n[Check] All checks passed! System is ready.")
        sys.exit(0)
    else:
        print("\n[Check] Verification failed. Check requirements.")
        sys.exit(1)


if __name__ == "__main__":
    main()
