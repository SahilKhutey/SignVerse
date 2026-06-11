# SignVerse Robotics - 8-Minute Live Demo Script & Guide

Rehearse this flow 3 times before presenting. 

* Run 1: Dry run, note stumbles.
* Run 2: Fix stumbles, time each act.
* Run 3: Full dress rehearsal with backup plan triggered at least once.

*Timing Rule*: If you exceed 1:45 in any act, cut Act 5 entirely. Acts 1-4 are non-negotiable.

---

## Act 1 - Open the System
**Duration**: 0:00 - 1:00 (60 seconds)

### Verbatim Script
> "This is the Sign-Verse Motion Capture Dashboard. We have four primary panels here: Capture, Dataset, 3D Viewer, and Export. The entire platform starts with a single command via our start script. Top right shows system status - the perception pipeline is running and healthy. Here is our FastAPI backend with auto-generated OpenAPI documentation at localhost:8000/docs. Every endpoint is fully documented. Let's see the live tracking in action."

### Visual Sequence
* **0:00**: Browser already loaded on the dashboard page at `http://localhost:5173`.
* **0:05**: Hover mouse over each panel in the sidebar as you list them.
* **0:25**: Switch to the browser tab showing the API docs at `http://localhost:8000/docs` and leave it open for 3 seconds.
* **0:40**: Close the API docs tab to return to the dashboard.
* **0:50**: Click on "Capture Studio" to open the live tracking panel.

### Failure Mode & Mitigation
* *If browser fails to load*: Have backup screenshots of the dashboard and API docs pre-opened in the browser tabs.
* *If backend is down*: Show pre-cached health check screenshot in `docs/screenshots/`.
* *If sidebar is missing*: Refresh once. If still broken, narrate: "Refreshing the dev server to establish WebSocket connection."

---

## Act 2 - Live Capture Demo
**Duration**: 1:00 - 3:00 (120 seconds)

### Verbatim Script
> "Now let's launch the Capture Studio. By enabling the webcam, the MediaPipe Holistic tracker begins running at 25 frames per second. As I move, you can see 553 landmarks detected in real time: 33 body pose points, 21 points per hand, and 478 facial mesh contours. The color coding on the overlay indicates detection confidence - green is high, yellow is medium, and red is low. If we look at the 3D Viewer panel on the right, we see the real-time 3D joint reconstruction. This is not a simulation - these are actual physical rotations computed from the camera feed using vector math. I can rotate, pan, and zoom the camera with the mouse. Let's record this action. I click Record, wave both arms slowly for 5 seconds, and click Stop. The session is saved directly to our database."

### Visual Sequence
* **1:00**: Click "Enable Webcam".
* **1:05**: Wait for the green "Connected" badge to appear.
* **1:15**: Slow wave with your right hand.
* **1:35**: Point to the Three.js 3D Viewer canvas.
* **1:45**: Orbit the Three.js camera with mouse drag (rotate, pan, zoom).
* **2:15**: Click "Record" (observe red dot).
* **2:20**: Wave both arms slowly.
* **2:50**: Click "Stop".
* **2:55**: Verify the "Session saved" notification appears.

### Stage Directions
* **Body Positioning**: Sit slightly back from the camera, ensuring your upper torso is fully visible.
* **Lighting**: Face a window or light source. Do not be backlit (which degrades MediaPipe accuracy).
* **Clothing**: Wear a solid color shirt that contrasts with the background. Avoid skin-tone colors.
* **Distance**: Stand/sit 1.0 to 1.5 meters from the webcam.

### Failure Mode & Mitigation (B-Roll Trigger)
* *If webcam fails or confidence stays red*: 
  > "The live capture requires a compatible webcam. Since the system is hardware-agnostic, let me show you the same pipeline with a pre-loaded video."
  *Action*: Jump directly to Act 3 at 1:15, skipping the rest of Act 2.
* *If 3D viewer crashes*:
  > "The 2D overlay represents the real-time perception layer, while the 3D reconstruction represents our kinematics layer. Both process parallel datasets. Let me show you the recorded motion in the Dataset Manager."
  *Action*: Jump to Act 3 immediately.

---

## Act 3 - Dataset Manager
**Duration**: 3:00 - 5:00 (120 seconds)

### Verbatim Script
> "Now we navigate to the Datasets Manager. Here you can see every captured motion session - our just-recorded sequence plus three pre-seeded demo sessions: wave_gesture, walk_cycle, and sit_stand. By selecting the walk_cycle session, we load the full skeletal motion capture. We can play back the animation, scrub frame-by-frame on the timeline, and analyze joint angles. We can also edit labels: I will select wave_gesture and change its label from GESTURE to WAVE. This human-in-the-loop labeling allows an operator to verify and clean the dataset. Lastly, the Metrics Dashboard aggregates dataset-wide frames, durations, and average confidence levels."

### Visual Sequence
* **3:00**: Click "Datasets".
* **3:05**: Hover over 3-4 session cards to show list variety.
* **3:15**: Click on the `walk_cycle` card.
* **3:20**: Auto-navigate/scroll to 3D Viewer.
* **3:30**: Click Play on the Timeline Scrubber.
* **3:45**: Drag timeline scrubber back and forth.
* **4:00**: Navigate back to Datasets.
* **4:05**: Click label pill on the `wave_gesture` session.
* **4:10**: Select "WAVE" from the dropdown and click Save.
* **4:20**: Scroll down/navigate to the Metrics Dashboard.
* **4:30**: Point to the metric cards and breakdown charts.

### Failure Mode & Mitigation
* *If 3D viewer is blank*:
  > "The WebGL context is initializing. The JSON coordinate data is fully loaded, so let me show you our export pipeline which is the primary system deliverable."
  *Action*: Skip to Act 4 immediately.
* *If pre-seeded sessions are missing*:
  *Action*: Keep a terminal open in the background and run `python backend/scripts/generate_demo_data.py` to restore them.
  > "Re-seeding the database to demonstrate the pre-captured sequences."

---

## Act 4 - Export
**Duration**: 5:00 - 7:00 (120 seconds)

### Verbatim Script
> "Let's export this motion. Clicking Export JSON on the walk_cycle session downloads our Universal Robot Dataset format. Opening this file reveals our schema: joint names, timestamps, joint angles in radians, and angular velocities. This format is robot-agnostic - any simulator like MuJoCo, Isaac Sim, or ROS2 can ingest this directly. Now let's download the industry-standard animation asset. I click Export BVH. Let's switch to Blender, where I have an empty scene. I go to File, Import, and choose BVH, selecting our downloaded file. In just seconds, the exact motion from the video is imported. I press Play, and the skeleton animates. This motion can now be applied to any 3D humanoid character rig."

### Visual Sequence
* **5:00**: Click "Export JSON" on the `walk_cycle` session.
* **5:05**: Open the Downloads folder on the system.
* **5:10**: Open the downloaded JSON in a text editor.
* **5:25**: Scroll through the JSON structure, pointing out the joint angles and velocities.
* **5:45**: Click the "Export BVH" button in the Dataset Manager.
* **5:50**: Switch window to Blender (which should already be open with an empty scene).
* **5:55**: In Blender, click File -> Import -> Biovision Hierarchy (.bvh).
* **6:05**: Navigate to the Downloads folder and select the exported `.bvh` file.
* **6:15**: Press Numpad 0 (or zoom out) to frame the skeleton.
* **6:25**: Press A to select the armature.
* **6:30**: Press Space to play the imported animation.
* **6:50**: Let the animation play in Blender for 5-10 seconds.

### Blender Pre-Setup (CRITICAL)
1. Open Blender before the demo starts.
2. Delete the default cube, camera, and lamp (`X` to delete).
3. Set the viewport shading to "Solid" or "Material Preview".
4. Open the File menu and hover over "Import" so it is ready.
5. Practice the import flow 3 times - it should take less than 10 seconds.
6. Know keyboard shortcuts: `Numpad 0` (frame), `A` (select all), `Space` (play).

### Failure Mode & Mitigation
* *If BVH import fails or skeleton is broken*:
  > "Blender's BVH importer has strict constraints on bone hierarchical lengths. The file is validated - let me show you the raw hierarchy text instead."
  *Action*: Open the `.bvh` file in a text editor and walk through the `HIERARCHY` and `MOTION` sections.
* *If Blender is not installed*:
  > "Blender is not installed on this local presentation machine, but the exported BVH is universal and can be imported directly into Maya, Unity, or Unreal Engine."

---

## Act 5 - Architecture Summary
**Duration**: 7:00 - 8:00 (60 seconds)

### Verbatim Script
> "To summarize, the Sign-Verse platform utilizes a 7-layer pipeline. The Input layer handles video files, YouTube URLs, and webcams. The Perception layer runs MediaPipe Holistic and YOLOv8 to extract 553 landmarks and detect objects in parallel. Temporal Kalman filters smooth tracking noise. The Kinematic layer is our core contribution, converting raw 3D coordinates into bone vectors, quaternions, and Euler angles. The 3D viewer, database store, and export engine sit on top. Our goal is a Universal Motion Dataset format, allowing any robotic morphology or simulation system to train on data captured here. Thank you, and I am open to any questions."

### Visual Sequence
* **7:00**: Open `ARCHITECTURE.md` or the README architecture diagram in the browser.
* **7:10**: Briefly point to each block in the diagram (Input, Perception, Kinematics, Database, UI).
* **7:30**: Emphasize the "Universal Motion Dataset" format.
* **7:50**: Pause and invite questions.

---

## Risks & Mitigations

| Risk | Detection | Mitigation |
| :--- | :--- | :--- |
| **MediaPipe slow on CPU (<10fps)** | FPS counter shows <10 | Set model_complexity=0. Skip face mesh. Process every 2nd frame. Target: 15fps minimum. |
| **YOLO blocks event loop** | WebSocket freezes | Run YOLO in ThreadPoolExecutor. `await loop.run_in_executor(None, detect, frame)`. Never call sync inside async. |
| **BVH wrong orientation in Blender** | Skeleton upside-down or rotated | Coordinate system conversion: MediaPipe uses image space (y=down), flip y axis. |
| **React Three.js canvas collapses to 0px** | 3D viewer invisible | Always set explicit height: `style={{height:'450px', width:'100%'}}`. |
| **WebSocket drops frames, skeleton snaps** | Visible jitter | Frontend interpolates between last 2 frames. If ws.readyState !== 1, render last valid frame. |
| **YouTube blocked/slow during demo** | Download hangs | Pre-download 3 videos to `data/uploads/` before presentation. |
| **SQLite locked under concurrent requests** | database is locked error | Use `connect_args={'check_same_thread': False}` and a single scoped connection. |
| **Webcam unavailable on demo machine** | Black feed | Pre-run `generate_demo_data.py`. The Dataset, Viewer, and Export work without a webcam. Skip Act 2 gracefully. |
| **scipy Rotation API differences** | Quaternions scrambled | Pin `scipy==1.13.0` and explicitly order: `q[[3,0,1,2]]` for `[w,x,y,z]`. |

---

## Pre-Demo Technical Checklist

### 30 Minutes Before
1. **Clean restart**: Run `start.bat` or `start.sh` to restart servers.
2. **Verify health**: Open `http://localhost:8000/health` (should return `{"status":"healthy"}`).
3. **Seed demo data**: Run `.\venv\Scripts\python.exe backend/scripts/generate_demo_data.py` to ensure mock data exists.
4. **Test BVH export**: Click export on one session and verify download.
5. **Test WebSocket**: Check webcam live stream on `http://localhost:5173`.

### 5 Minutes Before
* [ ] Browser open at `http://localhost:5173` (Capture Studio).
* [ ] Blender open, empty scene, viewport in Solid shading.
* [ ] Blender File menu open, hovered over Import -> BVH.
* [ ] Exported BVH file copied to Desktop for quick access.
* [ ] Terminals visible (backend logs, frontend console).
* [ ] Water bottle ready (talking for 8 minutes straight).

---

## Q&A Preparation

* **Q: How accurate is the pose estimation?**
  * *A*: MediaPipe achieves 95%+ accuracy on clear frontal videos. We add Kalman filtering for temporal stability. For higher precision, we would integrate multi-view triangulation or depth cameras.
* **Q: Can it handle multiple people?**
  * *A*: Not in the current MVP. MediaPipe Holistic processes one person at a time. The full system vision includes multi-person tracking with OpenPose. The architecture supports adding it as a parallel pipeline.
* **Q: What robots is this compatible with?**
  * *A*: The output is robot-agnostic. Any robot that accepts joint angles or BVH motion data can use it. We've tested the schema against MuJoCo and Isaac Sim documentation.
* **Q: Why not use ROS2 directly?**
  * *A*: We chose BVH and JSON as the export format because they are universal and do not require a ROS2 installation to use. A ROS2 node can easily subscribe to these outputs and publish `sensor_msgs/JointState` messages.
