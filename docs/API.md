# SignVerse Robotics API Reference

The backend of the platform is built using **FastAPI** and serves the following endpoints:

---

## 📹 Capture Routes (`/api/capture`)

### `POST /api/capture/upload`
Uploads a local video file and runs MediaPipe extraction.
* **Form Data**: `file: UploadFile`
* **Response**:
  ```json
  {
    "session_id": "ab12cd34ef56",
    "frames_extracted": 150,
    "status": "ready"
  }
  ```

### `POST /api/capture/youtube`
Downloads a YouTube video clip, clips the motion, and runs perception.
* **JSON Body**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=...",
    "start_time": 0.0,
    "duration": 5.0
  }
  ```
* **Response**: same as upload.

---

## 📂 Dataset Routes (`/api/dataset`)

### `GET /api/dataset/list`
Lists the metadata of up to 50 captured movement sessions.
* **Response**: Array of session objects.

### `GET /api/dataset/{session_id}`
Retrieves details and status of a single session.

### `DELETE /api/dataset/{session_id}`
Deletes a session and its frames from the database.

### `POST /api/dataset/{session_id}/label`
Updates the manual label and notes for a session.
* **JSON Body**:
  ```json
  {
    "action_label": "wave",
    "notes": "Testing standard wave gesture."
  }
  ```

### `GET /api/dataset/{session_id}/bvh`
Compiles and returns a download of a Blender-compatible `.bvh` motion capture file.

### `GET /api/dataset/{session_id}/robot-dataset`
Computes and returns a JSON file of the humanoid robot angular joint trajectories.

---

## 📊 Analytics Routes (`/api/analytics`)

### `POST /api/analytics/segment`
Triggers the rule-based action segmenter to divide the session into distinct movements.
* **JSON Body**:
  ```json
  {
    "session_id": "demo_waving"
  }
  ```
* **Response**:
  ```json
  {
    "session_id": "demo_waving",
    "segment_count": 2,
    "segments": [
      {
        "start_frame": 0,
        "end_frame": 20,
        "action": "idle",
        "confidence": 0.95,
        "description": "Idle/standing still (0.7s)"
      },
      {
        "start_frame": 21,
        "end_frame": 90,
        "action": "wave",
        "confidence": 0.88,
        "description": "Waving gesture (2.3s)"
      }
    ]
  }
  ```

### `GET /api/analytics/segments/{session_id}`
Retrieves previously persisted action segments for a session.

### `GET /api/analytics/dataset`
Aggregates analytics across the entire database.
* **Response**: Summarized counts, action distribution ratios, and source breakdowns.
