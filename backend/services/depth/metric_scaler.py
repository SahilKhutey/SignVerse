"""
metric_scaler.py
================
Metric scale recovery for the SignVerse depth estimation pipeline.

Problem statement
-----------------
Monocular depth networks output *relative* depth – the absolute scale
(metres per unit) is unknown.  This module recovers that scale by
exploiting two kinds of prior knowledge:

1. **Human body proportions** – When a person is visible in the frame,
   landmark pairs (shoulders, head-top/ankle, …) have known real-world
   lengths per NASA Man-Systems Integration Standards (MSIS-3000).

2. **COCO object sizes** – Common objects detected in the scene have
   well-characterised typical dimensions; the ratio of detected pixel
   span to known metric span gives a scale estimate.

Multiple anchors are combined via **weighted least squares** followed by
**outlier rejection** (drop any anchor whose implied scale deviates more
than 2 standard deviations from the mean).  An **exponential moving
average** then smooths scale estimates across video frames.

Usage
-----
::

    scaler = MetricScaleRecovery(use_ema=True, ema_alpha=0.15)
    scale, anchors = scaler.compute_scale(
        depth_map,
        pose_landmarks=mp_results.pose_landmarks.landmark,
        image_height=480,
        image_width=640,
    )
    metric_depth = depth_map * scale   # approximate depth in metres

Dependencies
------------
    numpy (always available)
    mediapipe (optional – only needed when pose_landmarks are supplied)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NASA MSIS-3000  (50th-percentile male/female average, metres)
# ---------------------------------------------------------------------------

ADULT_HUMAN_PROPORTIONS: Dict[str, float] = {
    # Vertical segments
    "total_height": 1.70,      # crown → floor
    "head_height": 0.23,       # crown → chin
    "neck": 0.05,              # chin → acromion
    "torso": 0.50,             # acromion → iliac crest (standing trunk)
    "upper_arm": 0.28,         # shoulder joint → elbow
    "forearm": 0.27,           # elbow → wrist
    "hand": 0.19,              # wrist → fingertip (middle)
    "thigh": 0.42,             # hip joint → knee
    "shin": 0.41,              # knee → ankle
    "foot": 0.26,              # heel → toe-tip
    # Lateral spans
    "shoulder_width": 0.40,    # left acromion → right acromion
    "hip_width": 0.32,         # left ASIS → right ASIS
    "head_width": 0.16,        # temporal bone L → R
}

# ---------------------------------------------------------------------------
# COCO category reference dimensions  (width_m, height_m, depth_m)
# ---------------------------------------------------------------------------
# Sources: standard product specs, ergonomics databases, and measurement surveys.
# Dimensions are typical adult / common-size values.

OBJECT_REFERENCE_SIZES: Dict[str, Tuple[float, float, float]] = {
    # Person (shoulder width, standing height, body depth)
    "person": (0.40, 1.70, 0.25),
    # Vehicles
    "bicycle": (0.60, 1.00, 1.70),
    "car": (1.80, 1.45, 4.40),
    "motorcycle": (0.90, 1.15, 2.10),
    "bus": (2.55, 3.10, 12.00),
    "truck": (2.50, 3.60, 8.00),
    "train": (3.10, 3.80, 20.00),
    "airplane": (34.0, 12.0, 37.0),
    "boat": (3.50, 1.20, 7.50),
    # Outdoor furniture / signage
    "traffic light": (0.35, 0.90, 0.20),
    "fire hydrant": (0.30, 0.65, 0.30),
    "stop sign": (0.75, 0.75, 0.05),
    "parking meter": (0.18, 1.20, 0.18),
    "bench": (1.80, 0.85, 0.55),
    # Animals
    "bird": (0.15, 0.20, 0.25),
    "cat": (0.22, 0.28, 0.45),
    "dog": (0.35, 0.55, 0.70),
    "horse": (0.55, 1.60, 2.20),
    "sheep": (0.50, 0.80, 1.10),
    "cow": (0.80, 1.45, 2.20),
    "elephant": (2.50, 3.30, 5.50),
    "bear": (1.10, 1.20, 2.30),
    "zebra": (0.80, 1.45, 2.20),
    "giraffe": (1.80, 5.50, 2.80),
    # Kitchen / household
    "bottle": (0.08, 0.25, 0.08),
    "wine glass": (0.08, 0.22, 0.08),
    "cup": (0.08, 0.10, 0.08),
    "fork": (0.02, 0.18, 0.01),
    "knife": (0.02, 0.22, 0.01),
    "spoon": (0.02, 0.17, 0.01),
    "bowl": (0.16, 0.07, 0.16),
    "banana": (0.03, 0.17, 0.03),
    "apple": (0.08, 0.08, 0.08),
    "sandwich": (0.12, 0.06, 0.12),
    "orange": (0.08, 0.08, 0.08),
    "broccoli": (0.15, 0.18, 0.15),
    "carrot": (0.03, 0.18, 0.03),
    "hot dog": (0.04, 0.14, 0.04),
    "pizza": (0.30, 0.03, 0.30),
    "donut": (0.09, 0.04, 0.09),
    "cake": (0.22, 0.12, 0.22),
    # Furniture / indoors
    "chair": (0.55, 0.87, 0.55),
    "couch": (2.00, 0.88, 0.88),
    "potted plant": (0.30, 0.45, 0.30),
    "bed": (1.60, 0.50, 2.00),
    "dining table": (1.50, 0.76, 0.90),
    "toilet": (0.46, 0.78, 0.70),
    "tv": (1.10, 0.65, 0.08),
    "laptop": (0.35, 0.02, 0.25),
    "mouse": (0.06, 0.04, 0.12),
    "remote": (0.05, 0.02, 0.18),
    "keyboard": (0.45, 0.02, 0.14),
    "cell phone": (0.07, 0.01, 0.15),
    "microwave": (0.54, 0.33, 0.46),
    "oven": (0.60, 0.60, 0.60),
    "toaster": (0.30, 0.22, 0.18),
    "sink": (0.56, 0.22, 0.50),
    "refrigerator": (0.70, 1.78, 0.70),
    "book": (0.14, 0.02, 0.22),
    "clock": (0.30, 0.30, 0.05),
    "vase": (0.16, 0.28, 0.16),
    "scissors": (0.06, 0.18, 0.01),
    "teddy bear": (0.25, 0.35, 0.15),
    "hair drier": (0.08, 0.22, 0.14),
    "toothbrush": (0.02, 0.18, 0.02),
    # Sports
    "frisbee": (0.27, 0.03, 0.27),
    "skis": (0.10, 0.01, 1.60),
    "snowboard": (0.30, 0.02, 1.55),
    "sports ball": (0.22, 0.22, 0.22),
    "kite": (0.65, 0.02, 0.65),
    "baseball bat": (0.04, 0.01, 0.86),
    "baseball glove": (0.22, 0.22, 0.04),
    "skateboard": (0.20, 0.05, 0.80),
    "surfboard": (0.55, 0.06, 1.80),
    "tennis racket": (0.28, 0.03, 0.65),
    # Accessories / misc
    "backpack": (0.28, 0.42, 0.15),
    "umbrella": (0.90, 0.30, 0.90),
    "handbag": (0.30, 0.22, 0.12),
    "tie": (0.08, 0.01, 0.65),
    "suitcase": (0.48, 0.68, 0.24),
}

# ---------------------------------------------------------------------------
# MediaPipe landmark index constants
# ---------------------------------------------------------------------------

MP_INDICES: Dict[str, int] = {
    "NOSE": 0,
    "LEFT_EYE_INNER": 1,
    "LEFT_EYE": 2,
    "LEFT_EYE_OUTER": 3,
    "RIGHT_EYE_INNER": 4,
    "RIGHT_EYE": 5,
    "RIGHT_EYE_OUTER": 6,
    "LEFT_EAR": 7,
    "RIGHT_EAR": 8,
    "MOUTH_LEFT": 9,
    "MOUTH_RIGHT": 10,
    "LEFT_SHOULDER": 11,
    "RIGHT_SHOULDER": 12,
    "LEFT_ELBOW": 13,
    "RIGHT_ELBOW": 14,
    "LEFT_WRIST": 15,
    "RIGHT_WRIST": 16,
    "LEFT_PINKY": 17,
    "RIGHT_PINKY": 18,
    "LEFT_INDEX": 19,
    "RIGHT_INDEX": 20,
    "LEFT_THUMB": 21,
    "RIGHT_THUMB": 22,
    "LEFT_HIP": 23,
    "RIGHT_HIP": 24,
    "LEFT_KNEE": 25,
    "RIGHT_KNEE": 26,
    "LEFT_ANKLE": 27,
    "RIGHT_ANKLE": 28,
    "LEFT_HEEL": 29,
    "RIGHT_HEEL": 30,
    "LEFT_FOOT_INDEX": 31,
    "RIGHT_FOOT_INDEX": 32,
}


# ---------------------------------------------------------------------------
# ScaleAnchor dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScaleAnchor:
    """
    A single measurement that ties pixel distance to a real-world size.

    Attributes
    ----------
    name : str
        Human-readable label, e.g. ``'shoulder_width'`` or ``'bottle'``.
    pixel_size : float
        Observed size in pixels (e.g., Euclidean distance between two
        landmarks, or bounding-box height).
    real_size_m : float
        Corresponding real-world size in metres.
    confidence : float
        Weight in [0, 1] used during weighted least-squares combination.
        Higher → this anchor has more influence on the final scale.
    source : str
        ``'pose'``, ``'object'``, or ``'unknown'``.
    depth_sample : float
        Normalised depth value (0–1) sampled at the anchor's location.
        Not directly used by ``compute_scale`` but useful for debugging.
    """

    name: str
    pixel_size: float
    real_size_m: float
    confidence: float = 1.0
    source: str = "unknown"
    depth_sample: float = 0.5

    @property
    def implied_scale(self) -> float:
        """
        The metric scale implied by this anchor alone (metres per pixel).

        Returns ``0.0`` if ``pixel_size`` is near zero.
        """
        if self.pixel_size < 1e-6:
            return 0.0
        return self.real_size_m / self.pixel_size


# ---------------------------------------------------------------------------
# MetricScaleRecovery
# ---------------------------------------------------------------------------


class MetricScaleRecovery:
    """
    Recovers the metric scale factor that converts normalised depth to metres.

    Parameters
    ----------
    use_ema : bool
        Whether to apply exponential-moving-average smoothing across frames.
    ema_alpha : float
        Smoothing coefficient ∈ (0, 1].  Smaller = more smoothing/lag;
        larger = faster adaptation.  Typical range: 0.1 – 0.3.

    Notes
    -----
    The default scale of ``5.0`` is a reasonable starting guess for an
    indoor scene viewed from ~2 m distance, matching common depth-network
    output ranges.
    """

    _DEFAULT_SCALE: float = 5.0

    def __init__(self, use_ema: bool = True, ema_alpha: float = 0.2) -> None:
        self.use_ema = use_ema
        self.ema_alpha = float(np.clip(ema_alpha, 1e-4, 1.0))

        self._scale_history: List[float] = []
        self._ema_scale: float = self._DEFAULT_SCALE

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def compute_scale(
        self,
        depth_map: np.ndarray,
        pose_landmarks: Optional[Any] = None,
        objects: Optional[List[Dict]] = None,
        image_height: int = 480,
        image_width: int = 640,
    ) -> Tuple[float, List[ScaleAnchor]]:
        """
        Compute the metric scale for the current frame.

        Parameters
        ----------
        depth_map : np.ndarray
            H×W float32 normalised depth map in [0, 1].
        pose_landmarks : sequence of MediaPipe NormalizedLandmark | None
            If provided, used to extract body-proportion anchors.
        objects : list of dict | None
            Each dict should have at least:
            ``{'label': str, 'bbox': [x, y, w, h]}``
            where bbox values are in pixels.
        image_height : int
        image_width : int

        Returns
        -------
        scale : float
            Smoothed metric scale (metres per normalised-depth unit).
        anchors_used : list of ScaleAnchor
            The anchors that survived outlier rejection.
        """
        anchors: List[ScaleAnchor] = []

        # --- Gather anchors ──────────────────────────────────────────
        if pose_landmarks is not None:
            try:
                anchors.extend(
                    self._compute_person_anchors(pose_landmarks, image_height, image_width)
                )
            except Exception as exc:
                logger.warning("compute_scale: person anchors failed: %s", exc)

        if objects:
            try:
                anchors.extend(
                    self._compute_object_anchors(objects, image_height, image_width)
                )
            except Exception as exc:
                logger.warning("compute_scale: object anchors failed: %s", exc)

        if not anchors:
            logger.debug("compute_scale: no anchors found – returning default %.2f", self._ema_scale)
            return self._ema_scale, []

        # --- Filter anchors with valid implied scale ─────────────────
        valid = [a for a in anchors if a.implied_scale > 1e-6]
        if not valid:
            return self._ema_scale, []

        # --- Outlier rejection ───────────────────────────────────────
        valid = self._reject_outliers(valid)
        if not valid:
            return self._ema_scale, []

        # --- Weighted least squares ───────────────────────────────────
        raw_scale = self._weighted_average(valid)

        # --- EMA smoothing ────────────────────────────────────────────
        if self.use_ema:
            self._ema_scale = self.ema_alpha * raw_scale + (1.0 - self.ema_alpha) * self._ema_scale
            smoothed = self._ema_scale
        else:
            smoothed = raw_scale

        self._scale_history.append(smoothed)
        logger.debug(
            "compute_scale: raw=%.3f  smoothed=%.3f  n_anchors=%d",
            raw_scale, smoothed, len(valid),
        )
        return smoothed, valid

    # ------------------------------------------------------------------
    # Anchor builders
    # ------------------------------------------------------------------

    def _compute_person_anchors(
        self,
        landmarks: Any,
        image_height: int,
        image_width: int,
    ) -> List[ScaleAnchor]:
        """
        Build ``ScaleAnchor`` objects from MediaPipe pose landmarks.

        Extracts the following body segments (when both endpoints have
        sufficient visibility):

        * shoulder width
        * torso height (shoulder mid → hip mid)
        * upper arm (shoulder → elbow, left and right)
        * thigh (hip → knee, left and right)
        * full height approximation (nose → ankle)

        Parameters
        ----------
        landmarks : sequence of MediaPipe NormalizedLandmark
            Access via ``landmarks[i].x``, ``.y``, ``.visibility``.
        image_height, image_width : int

        Returns
        -------
        list of ScaleAnchor
        """
        if landmarks is None or len(landmarks) < 33:
            return []
            
        anchors: List[ScaleAnchor] = []
        lm = landmarks  # shorthand

        def to_px(idx: int) -> Dict[str, float]:
            """Convert a normalised landmark to pixel coordinates dict."""
            l = lm[idx]  # noqa: E741
            return {"x": l.x * image_width, "y": l.y * image_height}

        def vis(idx: int) -> float:
            """Return landmark visibility (0–1); 0 if attribute missing."""
            try:
                return float(lm[idx].visibility)
            except AttributeError:
                return 0.0

        # Minimum visibility threshold to trust a landmark
        _VIS_MIN = 0.5

        # -- Shoulder width ────────────────────────────────────────────
        ls, rs = MP_INDICES["LEFT_SHOULDER"], MP_INDICES["RIGHT_SHOULDER"]
        if vis(ls) >= _VIS_MIN and vis(rs) >= _VIS_MIN:
            d = self._pixel_dist_2d(to_px(ls), to_px(rs))
            if d > 5.0:
                anchors.append(
                    ScaleAnchor(
                        name="shoulder_width",
                        pixel_size=d,
                        real_size_m=ADULT_HUMAN_PROPORTIONS["shoulder_width"],
                        confidence=min(vis(ls), vis(rs)),
                        source="pose",
                    )
                )

        # -- Torso height (shoulder-mid → hip-mid) ─────────────────────
        lh, rh = MP_INDICES["LEFT_HIP"], MP_INDICES["RIGHT_HIP"]
        if all(vis(i) >= _VIS_MIN for i in (ls, rs, lh, rh)):
            shoulder_mid = {
                "x": 0.5 * (to_px(ls)["x"] + to_px(rs)["x"]),
                "y": 0.5 * (to_px(ls)["y"] + to_px(rs)["y"]),
            }
            hip_mid = {
                "x": 0.5 * (to_px(lh)["x"] + to_px(rh)["x"]),
                "y": 0.5 * (to_px(lh)["y"] + to_px(rh)["y"]),
            }
            d = self._pixel_dist_2d(shoulder_mid, hip_mid)
            if d > 5.0:
                anchors.append(
                    ScaleAnchor(
                        name="torso",
                        pixel_size=d,
                        real_size_m=ADULT_HUMAN_PROPORTIONS["torso"],
                        confidence=min(vis(ls), vis(rs), vis(lh), vis(rh)),
                        source="pose",
                    )
                )

        # -- Upper arms (left + right) ─────────────────────────────────
        for side, s_idx, e_idx in (
            ("left", MP_INDICES["LEFT_SHOULDER"], MP_INDICES["LEFT_ELBOW"]),
            ("right", MP_INDICES["RIGHT_SHOULDER"], MP_INDICES["RIGHT_ELBOW"]),
        ):
            if vis(s_idx) >= _VIS_MIN and vis(e_idx) >= _VIS_MIN:
                d = self._pixel_dist_2d(to_px(s_idx), to_px(e_idx))
                if d > 3.0:
                    anchors.append(
                        ScaleAnchor(
                            name=f"{side}_upper_arm",
                            pixel_size=d,
                            real_size_m=ADULT_HUMAN_PROPORTIONS["upper_arm"],
                            confidence=min(vis(s_idx), vis(e_idx)) * 0.85,  # arms foreshorten
                            source="pose",
                        )
                    )

        # -- Thighs (left + right) ─────────────────────────────────────
        for side, h_idx, k_idx in (
            ("left", MP_INDICES["LEFT_HIP"], MP_INDICES["LEFT_KNEE"]),
            ("right", MP_INDICES["RIGHT_HIP"], MP_INDICES["RIGHT_KNEE"]),
        ):
            if vis(h_idx) >= _VIS_MIN and vis(k_idx) >= _VIS_MIN:
                d = self._pixel_dist_2d(to_px(h_idx), to_px(k_idx))
                if d > 3.0:
                    anchors.append(
                        ScaleAnchor(
                            name=f"{side}_thigh",
                            pixel_size=d,
                            real_size_m=ADULT_HUMAN_PROPORTIONS["thigh"],
                            confidence=min(vis(h_idx), vis(k_idx)) * 0.85,
                            source="pose",
                        )
                    )

        # -- Full-height approximation (nose → ankle) ──────────────────
        nose_idx = MP_INDICES["NOSE"]
        la_idx, ra_idx = MP_INDICES["LEFT_ANKLE"], MP_INDICES["RIGHT_ANKLE"]
        for ankle_idx in (la_idx, ra_idx):
            if vis(nose_idx) >= _VIS_MIN and vis(ankle_idx) >= _VIS_MIN:
                d = self._pixel_dist_2d(to_px(nose_idx), to_px(ankle_idx))
                # Nose-to-ankle ≈ total_height - head_height/2
                real = ADULT_HUMAN_PROPORTIONS["total_height"] - 0.12
                if d > 20.0:
                    anchors.append(
                        ScaleAnchor(
                            name="full_height_approx",
                            pixel_size=d,
                            real_size_m=real,
                            confidence=min(vis(nose_idx), vis(ankle_idx)) * 0.75,
                            source="pose",
                        )
                    )
                break  # use only one ankle (first visible)

        return anchors

    def _compute_object_anchors(
        self,
        objects: List[Dict],
        image_height: int,
        image_width: int,
    ) -> List[ScaleAnchor]:
        """
        Build ``ScaleAnchor`` objects from detected COCO-style objects.

        Parameters
        ----------
        objects : list of dict
            Each dict must have:
            - ``'label'``: COCO category name (str)
            - ``'bbox'``:  [x, y, w, h] in pixels (list/tuple of 4 floats)
            - ``'score'``: detection confidence ∈ [0, 1] (optional, defaults 1.0)
        image_height, image_width : int
            Frame dimensions (used for sanity-checking bbox bounds).

        Returns
        -------
        list of ScaleAnchor
        """
        anchors: List[ScaleAnchor] = []

        for obj in objects:
            label = obj.get("label", "").lower().strip()
            if label not in OBJECT_REFERENCE_SIZES:
                continue

            bbox = obj.get("bbox")
            if bbox is None or len(bbox) < 4:
                continue

            x, y, bw, bh = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            score = float(obj.get("score", 1.0))

            if bw < 5 or bh < 5:
                continue  # bbox too small to be reliable

            real_w, real_h, _ = OBJECT_REFERENCE_SIZES[label]

            # Use the dimension (height or width) whose aspect ratio better
            # matches the reference, giving preference to height for tall objects.
            aspect_real = real_h / max(real_w, 1e-6)
            aspect_px = bh / max(bw, 1e-6)

            if abs(aspect_px - aspect_real) / max(aspect_real, 1e-6) < 0.4:
                # Aspect ratios are consistent: use height
                pixel_size = bh
                real_size = real_h
                dim = "height"
            else:
                # Use width instead (object may be rotated / partially occluded)
                pixel_size = bw
                real_size = real_w
                dim = "width"

            anchors.append(
                ScaleAnchor(
                    name=f"{label}_{dim}",
                    pixel_size=pixel_size,
                    real_size_m=real_size,
                    confidence=score * 0.8,   # objects are less reliable than body landmarks
                    source="object",
                )
            )

        return anchors

    # ------------------------------------------------------------------
    # Statistical helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pixel_dist_2d(a: Dict[str, float], b: Dict[str, float]) -> float:
        """
        Euclidean distance between two landmark dicts with ``'x'`` and ``'y'`` keys.

        Parameters
        ----------
        a, b : dict with float values ``'x'`` and ``'y'``

        Returns
        -------
        float
        """
        dx = a["x"] - b["x"]
        dy = a["y"] - b["y"]
        return math.sqrt(dx * dx + dy * dy)

    @staticmethod
    def _weighted_average(anchors: List[ScaleAnchor]) -> float:
        """
        Weighted mean of implied scales.

        ``scale = Σ(w_i * s_i) / Σ(w_i)``

        where ``w_i = anchor.confidence`` and ``s_i = anchor.implied_scale``.
        """
        total_w = sum(a.confidence for a in anchors)
        if total_w < 1e-9:
            return MetricScaleRecovery._DEFAULT_SCALE
        return sum(a.confidence * a.implied_scale for a in anchors) / total_w

    @staticmethod
    def _reject_outliers(anchors: List[ScaleAnchor], n_sigma: float = 2.0) -> List[ScaleAnchor]:
        """
        Remove anchors whose implied scale deviates more than ``n_sigma``
        standard deviations from the unweighted mean.

        Parameters
        ----------
        anchors : list of ScaleAnchor
            Input anchors with valid (> 0) ``implied_scale``.
        n_sigma : float
            Threshold in standard deviations.

        Returns
        -------
        list of ScaleAnchor
            Filtered list.  Returns ``anchors`` unchanged if fewer than
            3 anchors are provided (not enough data to estimate spread).
        """
        if len(anchors) < 3:
            return anchors

        scales = np.array([a.implied_scale for a in anchors], dtype=np.float64)
        mu = float(scales.mean())
        sigma = float(scales.std())

        if sigma < 1e-8:
            return anchors  # all identical – nothing to reject

        kept = [
            a for a, s in zip(anchors, scales)
            if abs(s - mu) <= n_sigma * sigma
        ]
        n_dropped = len(anchors) - len(kept)
        if n_dropped:
            logger.debug("_reject_outliers: dropped %d anchor(s)", n_dropped)
        return kept if kept else anchors  # never return empty

    # ------------------------------------------------------------------
    # Management / diagnostics
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """
        Clear scale history and reset the EMA to the default value.

        Call this when switching scenes or cameras.
        """
        self._scale_history.clear()
        self._ema_scale = self._DEFAULT_SCALE
        logger.debug("MetricScaleRecovery: state reset.")

    def get_stability_score(self) -> float:
        """
        Return a scalar ∈ (0, ∞) indicating scale stability.

        A higher score means the estimated scale has been stable across
        recent frames.  Computed as ``1 / (std(history) + 0.01)``.

        Returns
        -------
        float
            ``100.0`` (maximum) when fewer than 2 samples have been
            collected.
        """
        if len(self._scale_history) < 2:
            return 100.0
        return 1.0 / (float(np.std(self._scale_history)) + 0.01)

    def get_stats(self) -> Dict[str, float]:
        """
        Return descriptive statistics about the collected scale history.

        Returns
        -------
        dict with keys ``'mean'``, ``'std'``, ``'min'``, ``'max'``, ``'n_frames'``,
        ``'ema_scale'``, ``'stability'``.
        """
        h = self._scale_history
        if not h:
            return {
                "mean": self._DEFAULT_SCALE,
                "std": 0.0,
                "min": self._DEFAULT_SCALE,
                "max": self._DEFAULT_SCALE,
                "n_frames": 0,
                "ema_scale": self._ema_scale,
                "stability": 100.0,
            }
        arr = np.array(h, dtype=np.float64)
        return {
            "mean": float(arr.mean()),
            "std": float(arr.std()),
            "min": float(arr.min()),
            "max": float(arr.max()),
            "n_frames": len(h),
            "ema_scale": self._ema_scale,
            "stability": self.get_stability_score(),
        }
