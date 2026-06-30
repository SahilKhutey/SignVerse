import cv2
import numpy as np
import os
import time
from pathlib import Path
import yt_dlp
from typing import Optional, List

class InputManager:
    """Manages all media ingestion sources: file uploads, YouTube, and local camera feeds"""
    
    def __init__(self, cache_dir: str = "data/uploads"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def from_upload(self, uploaded_file) -> str:
        """Saves an uploaded Streamlit file buffer to disk and returns the path"""
        # Clean filename to avoid OS path injection issues
        safe_name = "".join([c for c in uploaded_file.name if c.isalnum() or c in "._-"])
        if not safe_name:
            safe_name = f"upload_{int(time.time())}.mp4"
            
        file_path = self.cache_dir / safe_name
        with open(file_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        return str(file_path.resolve())
        
    def from_youtube(self, url: str) -> str:
        """Downloads a video from YouTube at low resolution to conserve bandwidth and returns filepath"""
        # Save file with title template inside our uploads folder
        output_template = str(self.cache_dir / "yt_%(id)s.%(ext)s")
        
        ydl_opts = {
            'format': 'best[height<=480]/best',  # cap at 480p for high-speed download
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Ensure the filename extension matches what was downloaded (e.g. if requested format changes extension)
                if not os.path.exists(filename):
                    # Fallback lookup in directory
                    yt_id = info.get('id')
                    for f in os.listdir(self.cache_dir):
                        if yt_id in f:
                            return str((self.cache_dir / f).resolve())
                return str(Path(filename).resolve())
            except Exception as e:
                raise RuntimeError(f"YouTube download failed: {str(e)}")
                
    def from_camera(self, camera_id: int = 0, duration_sec: int = 5) -> Optional[str]:
        """Captures a video sequence from a local webcam device and writes it to an MP4 file"""
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise RuntimeError(f"Webcam with ID {camera_id} could not be initialized.")
            
        # Target properties
        fps = 30
        frames = []
        
        # Determine capture resolution
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        
        start_time = time.time()
        # Cap frames to avoid infinite loop
        max_frame_count = fps * duration_sec
        
        while (time.time() - start_time) < duration_sec and len(frames) < max_frame_count:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            # Short sleep to match FPS target approximately
            time.sleep(1.0 / fps)
            
        cap.release()
        
        if not frames:
            return None
            
        output_path = self.cache_dir / f"camera_{int(time.time())}.mp4"
        
        # Write out captured video using standard MP4 codec
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))
        
        for f in frames:
            out.write(f)
        out.release()
        
        return str(output_path.resolve())
        
    def extract_frames(self, video_path: str, max_frames: int = 300) -> List[np.ndarray]:
        """Utility method to read a video file and extract individual frame arrays"""
        cap = cv2.VideoCapture(video_path)
        frames = []
        if not cap.isOpened():
            return frames
            
        while len(frames) < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            
        cap.release()
        return frames
