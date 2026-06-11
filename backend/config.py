from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App Info
    app_name: str = "SignVerse-MVP"
    app_version: str = "1.0.0"
    debug: bool = True

    # Server Address
    host: str = "0.0.0.0"
    port: int = 8000

    # Paths Setup
    upload_dir: Path = Path("./data/uploads")
    export_dir: Path = Path("./exports")
    dataset_dir: Path = Path("./datasets")

    # Restrictions
    max_upload_mb: int = 200
    max_frames_per_session: int = 5000

    # Allowed CORS Origins
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # MediaPipe Parameters
    mp_model_complexity: int = 1
    mp_min_detection_confidence: float = 0.5
    mp_min_tracking_confidence: float = 0.5

    # Frequency Configs
    target_fps: int = 30
    enable_smoothing: bool = True

settings = Settings()

# Bootstrap Dirs
for d in [settings.upload_dir, settings.export_dir, settings.dataset_dir]:
    d.mkdir(parents=True, exist_ok=True)
