import re
import yt_dlp
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?'
    r'(youtube\.com/watch\?v=|youtu\.be/)'
    r'([\w-]{11})'
)

executor = ThreadPoolExecutor(max_workers=2)


def validate_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube video URL."""
    return bool(YOUTUBE_REGEX.match(url))


def download_youtube_sync(url: str, output_path: str, progress_callback=None) -> str:
    """Synchronous YouTube download (run in threadpool)."""
    
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [progress_callback] if progress_callback else [],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        actual_path = ydl.prepare_filename(info)
        return actual_path


async def download_youtube(url: str, job_id: str, progress_queue: asyncio.Queue = None):
    """Async wrapper for YouTube download."""
    # Use standard downloads directory or output directory
    output_path = f"data/uploads/youtube_{job_id}.%(ext)s"
    
    def progress_hook(d):
        if progress_queue and d['status'] == 'downloading':
            try:
                pct = d.get('_percent_str', '0%').replace('%', '').strip()
                progress_queue.put_nowait({
                    'type': 'youtube_progress',
                    'percent': float(pct),
                })
            except Exception:
                pass
    
    loop = asyncio.get_event_loop()
    actual_path = await loop.run_in_executor(
        executor,
        download_youtube_sync,
        url,
        output_path,
        progress_hook
    )
    
    return actual_path
