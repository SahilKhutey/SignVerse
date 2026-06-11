"""
ObjectDetector3D — YOLOv8 + ByteTrack + monocular depth estimation.

Upgrades over the original object_detector.py:
  • 3D world position [x, y, z] per detection (pinhole + object-size prior)
  • Depth estimate in metres
  • Per-frame velocity [vx, vy, vz] in m/s
  • Object age (frames tracked)
  • Last-N trajectory stored internally

Backward-compatible: output dict still contains 'class', 'confidence',
'bbox', 'track_id' — plus new keys 'position_3d', 'depth_m',
'velocity_3d', 'age_frames'.
"""
import numpy as np
import torch
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from ultralytics import YOLO


# ── Real-world object dimensions (metres): (width, height, depth) ── #
OBJECT_SIZES: Dict[str, Tuple[float, float, float]] = {
    "person":        (0.50, 1.70, 0.30),
    "bicycle":       (0.70, 1.10, 1.70),
    "car":           (1.80, 1.50, 4.50),
    "motorcycle":    (0.80, 1.10, 2.20),
    "airplane":      (30.0, 5.00, 35.0),
    "bus":           (2.50, 3.00, 12.0),
    "train":         (3.00, 4.00, 20.0),
    "truck":         (2.50, 3.00, 8.00),
    "boat":          (3.00, 1.50, 6.00),
    "traffic light": (0.30, 0.80, 0.30),
    "fire hydrant":  (0.25, 0.70, 0.25),
    "stop sign":     (0.60, 0.60, 0.05),
    "parking meter": (0.20, 1.20, 0.20),
    "bench":         (1.50, 0.80, 0.60),
    "bird":          (0.20, 0.20, 0.30),
    "cat":           (0.35, 0.25, 0.45),
    "dog":           (0.50, 0.40, 0.70),
    "horse":         (1.50, 1.60, 2.40),
    "sheep":         (0.90, 0.90, 1.20),
    "cow":           (1.50, 1.40, 2.40),
    "elephant":      (2.50, 3.30, 5.50),
    "bear":          (1.20, 1.20, 2.00),
    "zebra":         (1.50, 1.50, 2.40),
    "giraffe":       (1.80, 5.50, 2.00),
    "backpack":      (0.35, 0.50, 0.20),
    "umbrella":      (0.10, 0.90, 0.10),
    "handbag":       (0.35, 0.30, 0.15),
    "tie":           (0.10, 0.50, 0.02),
    "suitcase":      (0.50, 0.70, 0.30),
    "frisbee":       (0.27, 0.27, 0.02),
    "skis":          (0.12, 1.80, 0.12),
    "snowboard":     (0.30, 1.50, 0.10),
    "sports ball":   (0.22, 0.22, 0.22),
    "kite":          (1.00, 0.80, 0.01),
    "baseball bat":  (0.07, 1.07, 0.07),
    "baseball glove":(0.28, 0.25, 0.10),
    "skateboard":    (0.20, 0.10, 0.80),
    "surfboard":     (0.55, 0.10, 2.00),
    "tennis racket": (0.28, 0.68, 0.05),
    "bottle":        (0.07, 0.25, 0.07),
    "wine glass":    (0.07, 0.20, 0.07),
    "cup":           (0.08, 0.10, 0.08),
    "fork":          (0.02, 0.20, 0.01),
    "knife":         (0.02, 0.22, 0.01),
    "spoon":         (0.04, 0.18, 0.01),
    "bowl":          (0.15, 0.08, 0.15),
    "banana":        (0.04, 0.20, 0.04),
    "apple":         (0.08, 0.08, 0.08),
    "sandwich":      (0.12, 0.05, 0.12),
    "orange":        (0.08, 0.08, 0.08),
    "broccoli":      (0.15, 0.20, 0.15),
    "carrot":        (0.03, 0.20, 0.03),
    "hot dog":       (0.04, 0.15, 0.04),
    "pizza":         (0.35, 0.03, 0.35),
    "donut":         (0.10, 0.04, 0.10),
    "cake":          (0.25, 0.12, 0.25),
    "chair":         (0.50, 1.00, 0.50),
    "couch":         (2.00, 0.90, 0.90),
    "potted plant":  (0.30, 0.50, 0.30),
    "bed":           (1.60, 0.60, 2.10),
    "dining table":  (1.50, 0.75, 0.90),
    "toilet":        (0.40, 0.80, 0.65),
    "tv":            (1.00, 0.60, 0.05),
    "laptop":        (0.35, 0.02, 0.25),
    "mouse":         (0.06, 0.03, 0.10),
    "remote":        (0.05, 0.02, 0.20),
    "keyboard":      (0.45, 0.02, 0.15),
    "cell phone":    (0.07, 0.15, 0.01),
    "microwave":     (0.50, 0.35, 0.40),
    "oven":          (0.60, 0.90, 0.60),
    "toaster":       (0.28, 0.20, 0.20),
    "sink":          (0.60, 0.25, 0.50),
    "refrigerator":  (0.70, 1.80, 0.70),
    "book":          (0.20, 0.03, 0.15),
    "clock":         (0.30, 0.30, 0.05),
    "vase":          (0.15, 0.30, 0.15),
    "scissors":      (0.08, 0.02, 0.15),
    "teddy bear":    (0.30, 0.40, 0.25),
    "hair drier":    (0.08, 0.25, 0.08),
    "toothbrush":    (0.02, 0.20, 0.02),
}


class ObjectDetector3D:
    """
    Singleton YOLOv8 + ByteTrack detector with monocular 3D position estimation.
    Backward-compatible with the original ObjectDetector.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _initialize(self, model_size: str = "yolov8n.pt"):
        if self._initialized:
            return
        self.model = YOLO(model_size)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.imgsz = 320 if self.device == "cpu" else 640
        print(f"[ObjectDetector3D] device={self.device} imgsz={self.imgsz}")

        # Per-track state
        self._history:    Dict[int, List[List[float]]] = defaultdict(list)
        self._prev_pos:   Dict[int, List[float]] = {}
        self._track_age:  Dict[int, int] = defaultdict(int)
        self._velocities: Dict[int, List[float]] = {}
        self._initialized = True

    def __init__(self, model_size: str = "yolov8n.pt"):
        self._initialize(model_size)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def detect(
        self,
        frame: np.ndarray,
        camera_matrix: Optional[np.ndarray] = None,
        frame_rate: float = 30.0,
        persist: bool = True,
    ) -> List[Dict]:
        """
        Detect + track objects in one BGR frame.

        Returns list of dicts with keys:
          class, confidence, bbox, track_id          ← original keys
          position_3d, depth_m, velocity_3d,         ← new 3D keys
          age_frames, trajectory                      ← tracking metadata
        """
        h, w = frame.shape[:2]
        K = camera_matrix if camera_matrix is not None else self._default_K(w, h)

        try:
            results = self.model.track(
                frame, persist=persist,
                tracker="bytetrack.yaml",
                verbose=False, device=self.device,
                imgsz=self.imgsz
            )
        except Exception:
            try:
                results = self.model.predict(frame, verbose=False, device=self.device, imgsz=self.imgsz)
            except Exception:
                return []

        if not results or results[0].boxes is None:
            return []

        boxes = results[0].boxes
        output = []
        current_ids: set = set()

        for i in range(len(boxes)):
            xyxy   = boxes.xyxy[i].cpu().numpy().tolist()
            conf   = float(boxes.conf[i].cpu())
            cls_id = int(boxes.cls[i].cpu())
            name   = self.model.names[cls_id]
            tid    = int(boxes.id[i].cpu()) if boxes.id is not None else -1

            # 3D estimation
            pos3d, depth = self._estimate_3d(xyxy, name, K, w, h)

            # Track state
            current_ids.add(tid)
            self._track_age[tid] += 1
            age = self._track_age[tid]

            # Velocity
            if tid in self._prev_pos:
                dp = np.array(pos3d) - np.array(self._prev_pos[tid])
                vel = (dp * frame_rate).tolist()
                vel = [round(v, 4) for v in vel]
            else:
                vel = [0.0, 0.0, 0.0]
            self._velocities[tid] = vel
            self._prev_pos[tid] = pos3d

            # Trajectory buffer (last 60 frames)
            self._history[tid].append(pos3d)
            if len(self._history[tid]) > 60:
                self._history[tid] = self._history[tid][-60:]

            output.append({
                # ── Original keys (backward-compatible) ──
                "class":       name,
                "class_id":    cls_id,
                "confidence":  round(conf, 3),
                "bbox":        [round(v, 1) for v in xyxy],
                "track_id":    tid,
                # ── New 3D keys ──
                "position_3d": [round(v, 4) for v in pos3d],
                "depth_m":     round(depth, 3),
                "velocity_3d": vel,
                "age_frames":  age,
                "trajectory":  self._history[tid][-10:],  # last 10 positions
            })

        self._prune_stale(current_ids)
        return output

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _default_K(w: int, h: int) -> np.ndarray:
        """Estimate intrinsic matrix assuming focal length ≈ image width."""
        fx = fy = float(w)
        return np.array([[fx, 0, w / 2],
                         [0, fy, h / 2],
                         [0,  0,     1]], dtype=np.float64)

    def _estimate_3d(
        self,
        xyxy: List[float],
        class_name: str,
        K: np.ndarray,
        img_w: int,
        img_h: int,
    ) -> Tuple[List[float], float]:
        """Pinhole + object-size prior → 3D world position (metres)."""
        x1, y1, x2, y2 = xyxy
        bw = max(x2 - x1, 1.0)
        bh = max(y2 - y1, 1.0)
        cx_px = (x1 + x2) / 2.0
        cy_px = (y1 + y2) / 2.0

        fx = K[0, 0];  fy = K[1, 1]
        cx = K[0, 2];  cy = K[1, 2]

        rw, rh, _ = OBJECT_SIZES.get(class_name, (0.20, 0.20, 0.20))

        # depth from each dimension independently
        d_w = fx * rw / bw if bw > 5 else 5.0
        d_h = fy * rh / bh if bh > 5 else 5.0

        # Weight by how "square" the box is (more reliable dim)
        aspect = bw / bh
        if 0.5 < aspect < 2.0:
            depth = (d_w + d_h) / 2.0
        elif aspect >= 2.0:
            depth = d_w  # wide object → width more reliable
        else:
            depth = d_h  # tall object → height more reliable

        depth = float(np.clip(depth, 0.10, 12.0))

        # Back-project centre to world X/Y
        wx =  (cx_px - cx) * depth / fx
        wy = -(cy_px - cy) * depth / fy   # flip Y upright
        wz =  depth

        return [wx, wy, wz], depth

    def _prune_stale(self, active: set, keep_frames: int = 30):
        """Remove tracks absent for > keep_frames frames."""
        for tid in list(self._track_age.keys()):
            if tid not in active:
                self._track_age[tid] -= 1
                if self._track_age[tid] <= 0:
                    for store in (self._history, self._prev_pos,
                                  self._velocities, self._track_age):
                        store.pop(tid, None)

    def get_trajectory(self, track_id: int) -> List[List[float]]:
        """Return full stored trajectory for a track."""
        return self._history.get(track_id, [])

    def reset(self):
        """Clear all tracking state."""
        self._history.clear()
        self._prev_pos.clear()
        self._track_age.clear()
        self._velocities.clear()
