# 🤖 SignVerse Robotics Studio

### Universal Human Motion → Robot Intelligence and Kinematic Transfer Pipeline

SignVerse is a complete, production-hardened platform that translates raw human motion capture sequences (from video uploads, YouTube streams, or live webcam feeds) into smoothed 3D trajectories, local Euler/Quaternion joint rotations, and retargeted joint commands for an 11-DoF humanoid robot model.

---

## 📁 System Architecture Overview

```
SignVerse/
├── backend/
│   ├── api/                      # Ingress controllers & routers
│   ├── communication/            # Priority pub/sub message bus with DLQ
│   ├── ingestion/                # Upload chunking and sanitization validators
│   ├── middleware/               # Timing, memory, and CPU profiling middleware
│   ├── models/                   # SQLAlchemy database schemas
│   ├── resilience/               # Circuit breakers and retry logic
│   ├── routers/                  # API routers (capture, stream, export, depth, profiling)
│   ├── scripts/                  # Production py-spy flame-graph recorders
│   ├── security/                 # JWT tokens, API keys, strict CORS, and rate limiting
│   ├── services/                 # Kinematics solvers, Kalman smoothing, HOI, exporters
│   ├── utils/                    # Common utility helpers
│   ├── main.py                   # App production-hardened entry point
│   └── config.py                 # Pydantic-based settings
├── frontend/
│   ├── dist/                     # Optimized code-split production builds
│   ├── scripts/                  # Bundle analysis tools
│   ├── src/
│   │   ├── api/                  # Axios clients & WS interfaces
│   │   ├── components/           # UI elements (3D Visualizer, Stats, Overlays, Profiling)
│   │   ├── store/                # Zustand global states (auth, live feeds, session)
│   │   └── App.jsx               # Router & lazy-loaded view mounts
│   └── vite.config.js            # Rollup manual chunks & Terser compression
├── docs/
│   ├── ARCHITECTURE.md           # System design specifications
│   ├── API.md                    # Endpoint details
│   ├── DEMO_SCRIPT.md            # 3-minute presentation script
│   └── MATH_PRINCIPLES.md        # Comprehensive mathematical references & equations
└── LICENSE                       # MIT License
```

---

## ✨ Features

- **Multi-Source Data Ingestion**: Supports drag-and-drop local video uploads (MP4/AVI/MOV), remote YouTube stream extraction, and real-time live webcam feeds.
- **Robust Real-Time Tracking**: Combines **MediaPipe Holistic** pose/hands/face mesh and **YOLOv8** + **ByteTrack** object tracking to compute human kinematics and human-object interactions (HOI) concurrently.
- **Temporal Motion Smoothing**: Integrates a multi-group **Temporal Kalman Filter** to smooth coordinate tracking, eliminating high-frequency capture jitter.
- **NASA Biomechanical Metric Scaling**: Recovers absolute scale (meters per pixel) from relative monocular depth maps using NASA MSIS-3000 anthropometric proportions (shoulders, hip spans, heights) and common object dimensions.
- **11-DoF Humanoid Retargeter**: Maps human joint coordinates into command trajectories for an 11-DoF humanoid robot model in radians.
- **Multi-Format Kinematic Exporters**: Exports coordinate animations into **10+ formats** including BVH, FBX, GLTF, GLB, MuJoCo XML, URDF, ROS2 Trajectory YAML, CSV, Pinocchio JSON, and Blender Python scripts.
- **Dynamic Connection Resilience**: Features a custom React Zustand store with dynamic WebSocket scheme/host resolution and auto-reconnecting event listeners that survive network interruptions.
- **System Memory Diagnostics**: Includes a background memory profiling thread and request-level timing middleware with real-time diagnostics charts and alerts directly inside the dashboard.

---

## 🚀 Quick Start

To launch the platform:

1. **Verify Prerequisites**:
   - Python 3.10+
   - Node.js v18+

2. **Setup and Install**:
   ```bash
   # Initialize and activate Python virtual environment
   python -m venv venv
   venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Install frontend dependencies
   cd frontend
   npm install
   cd ..
   ```

3. **Launch Services**:
   Simply run the start script in the root folder:
   - **Windows**: `run.bat` or `start.bat`
   - **Linux/macOS**: `./run.sh` or `./scripts/start.sh`

4. **Production Mode**:
   To build assets and run the production server:
   ```bash
   # Run backend API
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1

   # Compile and serve frontend
   cd frontend
   npm run build
   npx serve dist -p 5173
   ```

---

## ⚙️ Testing and Verification

To run the full backend verification suite containing **175+ tests** (unit, integration, performance, security, and profiling):
```bash
venv\Scripts\python.exe -m pytest backend/tests --basetemp=tmp
```

To run individual verification pipelines:
- Perceptions Pipeline: `python verify_pipeline.py`
- Multi-Format Exporters: `python verify_exporters.py`
- Monocular Depth Pipeline: `python verify_depth_pipeline.py`
- Spatial HOI Pipeline: `python verify_hoi_pipeline.py`
- Security & Resilience: `python verify_security_pipeline.py`

To run the frontend bundle size analyzer:
```bash
cd frontend
npm run build:analyze
```

---

## 📄 Documentation Links

- [System Architecture Specification](file:///c:/Users/User/Documents/SignVerse/docs/ARCHITECTURE.md)
- [FastAPI Endpoints Reference](file:///c:/Users/User/Documents/SignVerse/docs/API.md)
- [3-Minute Live Demo Presentation Script](file:///c:/Users/User/Documents/SignVerse/docs/DEMO_SCRIPT.md)
- [Mathematical Foundations & Verification Metrics Reference](file:///c:/Users/User/Documents/SignVerse/docs/MATH_PRINCIPLES.md)
