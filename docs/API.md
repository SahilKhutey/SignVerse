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

---

## 🌐 Live WebSockets (`/ws/live`)

### `WebSocket /ws/live`
Real-time JSON perception streaming connection.
* **Client Control Action**: `{"action": "ping"}` or `{"action": "stop"}`
* **Server Payload**:
  ```json
  {
    "type": "frame",
    "data": {
      "frame_id": 42,
      "timestamp_ms": 1781156251000,
      "pose_33": [{"x": 0.5, "y": 0.3, "z": 0.0, "v": 0.95}, ...],
      "left_hand_21": [],
      "right_hand_21": [],
      "face_478": [],
      "objects": [{"class": "bottle", "bbox": [100, 120, 180, 320], "confidence": 0.88}],
      "hand_gestures": {"left_hand": "NONE", "right_hand": "NONE"},
      "expression": "NEUTRAL",
      "expression_confidence": 0.98,
      "head_pose": {"pitch": 1.2, "yaw": -0.5, "roll": 0.1},
      "gaze": {"direction": "center"},
      "interaction_graph": {"hands": [], "attention_target": "scene", "person_posture": "standing"},
      "primary_action": "IDLE",
      "primary_intent": "STAND",
      "intent_confidence": 0.85,
      "pose_confidence": 0.95,
      "processing_time_ms": 28.5
    },
    "meta": {
      "server_fps": 30.0,
      "subscriber_count": 1
    }
  }
  ```

### `WebSocket /ws/live/video`
High-speed raw camera feed streaming connection.
* **Server Payload**: Raw binary JPEG image frames (uint8 arraybuffer) formatted to exactly `640x480` and letterboxed to align with the visual perception canvas.

---

## 📦 Multi-Format Exporters (`/api/exporters`)

### `GET /api/exporters/{session_id}/export?format={fmt}`
Generates and downloads kinematic coordinate conversions for a capture session.
* **Supported Formats**:
  * **Person-only (`format=`)**:
    * `bvh` — Biovision Hierarchy skeleton file.
    * `fbx` — ASCII FBX 7.4 animation node.
    * `gltf` / `glb` — GLTF 2.0 animated skin.
    * `mujoco` — Humanoid body MuJoCo XML.
    * `urdf` — Humanoid URDF link file.
    * `ros2` — ROS2 JointTrajectory YAML.
    * `csv` — Joint coordinate time-series CSV.
    * `pinocchio` — Pinocchio rigid-body JSON.
    * `blender` — Import script for Blender bpy.
  * **Scene-level (`format=`)**:
    * `gltf_scene` / `glb_scene` — GLTF scene containing the person armature alongside independent, animated object meshes.
    * `bvh_scene` — BVH including objects as virtual root joints.
    * `mujoco_scene` — MuJoCo XML compiling body structure with target object geometries.
    * `usd_scene` — Pixar USD (.usda) ascii stage representation.

---

## 🤝 Human-Object Interaction (`/api/hoi`)

### `GET /api/hoi/{session_id}/timeline`
Retrieves chronological lists of HOI contact events.
* **Response**: Detailed logs containing frame references, contact coordinates, gestures, and distance thresholds.

### `GET /api/hoi/{session_id}/objects`
Returns unique objects tracked during the session along with their 3D path trajectory logs.

### `GET /api/hoi/{session_id}/stats`
Retrieves aggregated statistics (hold durations, interaction frequencies, and hand contact matrices).

### `GET /api/hoi/{session_id}/summary`
Retrieves a high-level summary card of the session (object count, interaction indicators, and available exports).

---

## 📊 System Profiling & Diagnostics (`/api/profiling`)

### `GET /api/profiling/memory/snapshot`
Exposes the active process's memory footprint (RSS, VMS, shared RAM, and heap statistics).

### `GET /api/profiling/memory/timeline`
Retrieves historical snapshots of memory usage (e.g., last 60 minutes) to visualize memory leaks.

### `GET /api/profiling/memory/components`
Exposes memory allocation details grouped by component (MediaPipe extractors, YOLO engines, database connection pools).

### `GET /api/profiling/memory/alerts`
Returns memory leak warning indicators detected by the least-squares regression tracker.

### `POST /api/profiling/memory/gc`
Forces Python's garbage collection and returns reclaimed MBs.

### `GET /api/profiling/memory/report`
Generates a comprehensive diagnostic report containing summary statistics, timelines, and actionable optimization advice.
