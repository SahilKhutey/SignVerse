import yt_dlp
from pathlib import Path
from backend.config import settings

def download_youtube(url: str) -> Path:
    """Download YouTube video at 480p resolution to expedite pipeline analysis processing time"""
    output_template = str(settings.upload_dir / "yt_%(id)s.%(ext)s")
    ydl_opts = {
        "format": "best[height<=480]/best[height<=720]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return Path(filename)
        except Exception as e:
            raise RuntimeError(f"yt-dlp extraction failed: {str(e)}")
