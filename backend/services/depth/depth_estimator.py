"""
depth_estimator.py
==================
Production-grade monocular depth estimator for the SignVerse pipeline.

Supported back-ends
-------------------
* MiDaS Small    – fastest, CPU-friendly, good for real-time pipelines.
* DPT Hybrid     – Vision Transformer backbone, higher quality, needs GPU.
* Depth Anything Small / Base – state-of-the-art relative depth, best
  generalization across indoor/outdoor scenes.

The estimator
-------------
* Auto-selects CUDA / CPU.
* Falls back to MiDaS Small on any load failure.
* Optionally blends two models (ensemble mode).
* Thread-safe: a ``threading.Lock`` serializes all inference calls.
* Singleton: ``DepthEstimator.get_instance()`` returns the shared instance.
* Returns zero-depth maps rather than raising on any runtime error.

Dependencies (install as needed)
---------------------------------
    pip install torch torchvision timm
    pip install transformers          # for Depth Anything
    pip install opencv-python-headless numpy
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports – never crash at module level
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn.functional as F

    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TORCH_AVAILABLE = False
    logger.warning("PyTorch not found. DepthEstimator will return zero maps.")

try:
    import cv2 as _cv2

    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CV2_AVAILABLE = False
    logger.warning("OpenCV not found. Frame preprocessing will use numpy only.")

try:
    from transformers import pipeline as _hf_pipeline

    _TRANSFORMERS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TRANSFORMERS_AVAILABLE = False
    logger.info("transformers not installed – Depth Anything will fall back to MiDaS.")


# ---------------------------------------------------------------------------
# Public enums / dataclasses
# ---------------------------------------------------------------------------


class DepthModel(str, Enum):
    """Enumeration of supported depth estimation back-ends."""

    MIDAS_SMALL = "MiDaS_small"
    DPT_HYBRID = "DPT_Hybrid"
    DEPTH_ANYTHING_SMALL = "depth_anything_small"
    DEPTH_ANYTHING_BASE = "depth_anything_base"


@dataclass
class DepthResult:
    """
    Container for one depth estimation result.

    Attributes
    ----------
    depth_map : np.ndarray
        H×W float32 array, values in [0, 1] (0 = near, 1 = far) after
        normalisation, OR raw relative depth if ``scale_factor`` != 1.
    confidence_map : np.ndarray
        H×W float32 array in [0, 1].  Derived from local gradient
        magnitude; regions with sharp depth gradients → low confidence.
    model_used : str
        Human-readable name of the model that produced this result.
    inference_time_ms : float
        Wall-clock inference duration in milliseconds.
    scale_factor : float
        Metric scale applied to ``depth_map`` (metres per unit).
        Defaults to 1.0 (unscaled / relative depth).
    """

    depth_map: np.ndarray
    confidence_map: np.ndarray
    model_used: str
    inference_time_ms: float
    scale_factor: float = 1.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _zero_result(h: int, w: int, model: str = "none", t_ms: float = 0.0) -> DepthResult:
    """Return a safe all-zero result for the given frame dimensions."""
    return DepthResult(
        depth_map=np.zeros((h, w), dtype=np.float32),
        confidence_map=np.zeros((h, w), dtype=np.float32),
        model_used=model,
        inference_time_ms=t_ms,
        scale_factor=1.0,
    )


def _bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    """Convert a BGR uint8 frame to float32 RGB in [0, 1]."""
    if _CV2_AVAILABLE:
        rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
    else:
        rgb = frame[:, :, ::-1].copy()
    return rgb.astype(np.float32) / 255.0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class DepthEstimator:
    """
    Thread-safe, singleton monocular depth estimator.

    Parameters
    ----------
    model : DepthModel
        Which model back-end to load as the primary estimator.
    device : str | None
        ``'cuda'``, ``'cpu'``, or ``None`` (auto-detect).
    enable_ensemble : bool
        When True, run a secondary model and blend the outputs
        (primary weight 0.6, secondary weight 0.4).

    Examples
    --------
    >>> est = DepthEstimator.get_instance(model=DepthModel.MIDAS_SMALL)
    >>> result = est.estimate(frame)          # frame: BGR uint8 np.ndarray
    >>> depth_img = (result.depth_map * 255).astype(np.uint8)
    """

    # ------------------------------------------------------------------
    # Singleton bookkeeping
    # ------------------------------------------------------------------
    _instance: Optional["DepthEstimator"] = None
    _instance_lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        model: DepthModel = DepthModel.MIDAS_SMALL,
        device: Optional[str] = None,
        enable_ensemble: bool = False,
    ) -> None:
        self.requested_model = model
        self.enable_ensemble = enable_ensemble

        # Device selection ─────────────────────────────────────────────
        if device is not None:
            self.device = device
        elif _TORCH_AVAILABLE and torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        logger.info("DepthEstimator: device=%s  model=%s", self.device, model.value)

        # Inference lock ────────────────────────────────────────────────
        self._lock: threading.Lock = threading.Lock()

        # Model storage ─────────────────────────────────────────────────
        self._primary: Dict = {}     # keys: 'model', 'transform', 'type'
        self._secondary: Dict = {}
        self._model_name: str = model.value

        # Load models ────────────────────────────────────────────────────
        self._load_model()

    # ------------------------------------------------------------------
    # Singleton factory
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(
        cls,
        model: DepthModel = DepthModel.MIDAS_SMALL,
        device: Optional[str] = None,
        enable_ensemble: bool = False,
    ) -> "DepthEstimator":
        """
        Return (or create) the global ``DepthEstimator`` singleton.

        Thread-safe via a class-level lock.
        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(model=model, device=device, enable_ensemble=enable_ensemble)
        return cls._instance

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """
        Load the primary (and optionally secondary) model.

        Falls back to ``MiDaS_small`` on any error so the pipeline
        never hard-crashes at start-up.
        """
        if not _TORCH_AVAILABLE:
            logger.warning("_load_model: torch unavailable – using zero-depth mode.")
            return

        # --- Primary ─────────────────────────────────────────────────
        try:
            self._primary = self._load_single(self.requested_model)
            self._model_name = self.requested_model.value
            logger.info("Primary model loaded: %s", self._model_name)
        except Exception as exc:
            logger.error(
                "Failed to load primary model %s (%s). Falling back to MiDaS_small.",
                self.requested_model.value,
                exc,
            )
            try:
                self._primary = self._load_single(DepthModel.MIDAS_SMALL)
                self._model_name = DepthModel.MIDAS_SMALL.value + " (fallback)"
                logger.info("Fallback model loaded: MiDaS_small")
            except Exception as exc2:
                logger.critical("Fallback model also failed: %s. Running in zero-depth mode.", exc2)
                self._primary = {}

        # --- Secondary (ensemble only) ──────────────────────────────
        if self.enable_ensemble and self._primary:
            secondary_model = (
                DepthModel.DPT_HYBRID
                if self.requested_model == DepthModel.MIDAS_SMALL
                else DepthModel.MIDAS_SMALL
            )
            try:
                self._secondary = self._load_single(secondary_model)
                logger.info("Secondary (ensemble) model loaded: %s", secondary_model.value)
            except Exception as exc:
                logger.warning(
                    "Secondary model %s failed to load (%s). Ensemble disabled.",
                    secondary_model.value,
                    exc,
                )
                self.enable_ensemble = False

    def _load_single(self, model: DepthModel) -> Dict:
        """
        Load one model and return a model-dict understood by the runner helpers.

        Returns
        -------
        dict with keys:
            ``'type'``      – ``'midas'`` | ``'depth_anything'``
            ``'model'``     – the nn.Module or HuggingFace pipeline
            ``'transform'`` – MiDaS transform (None for Depth Anything)
        """
        if model in (DepthModel.DEPTH_ANYTHING_SMALL, DepthModel.DEPTH_ANYTHING_BASE):
            return self._load_depth_anything(model)
        return self._load_midas(model)

    def _load_midas(self, model: DepthModel) -> Dict:
        """Load a MiDaS / DPT model via ``torch.hub``."""
        hub_name = model.value  # e.g. 'MiDaS_small', 'DPT_Hybrid'
        logger.debug("Loading MiDaS hub model: %s", hub_name)

        midas = torch.hub.load("intel-isl/MiDaS", hub_name, pretrained=True)
        midas.to(self.device).eval()

        transforms_hub = torch.hub.load("intel-isl/MiDaS", "transforms")
        if hub_name == "MiDaS_small":
            transform = transforms_hub.small_transform
        elif hub_name == "DPT_Hybrid":
            transform = transforms_hub.dpt_transform
        else:
            transform = transforms_hub.default_transform

        return {"type": "midas", "model": midas, "transform": transform}

    def _load_depth_anything(self, model: DepthModel) -> Dict:
        """
        Load a Depth Anything model.

        Tries HuggingFace ``transformers`` first, then falls back to a
        MiDaS model so the pipeline always has something to run.
        """
        if not _TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers library is not installed.")

        model_id = (
            "LiheYoung/depth-anything-small-hf"
            if model == DepthModel.DEPTH_ANYTHING_SMALL
            else "LiheYoung/depth-anything-base-hf"
        )
        logger.debug("Loading Depth Anything via transformers: %s", model_id)

        pipe = _hf_pipeline(
            task="depth-estimation",
            model=model_id,
            device=0 if self.device == "cuda" else -1,
        )
        return {"type": "depth_anything", "model": pipe, "transform": None}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(self, frame: np.ndarray) -> DepthResult:
        """
        Estimate depth for a single BGR frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR uint8 image of shape (H, W, 3).

        Returns
        -------
        DepthResult
            Normalised depth map, confidence map, and metadata.
            Returns a zero-depth result on any error rather than raising.
        """
        if frame is None or frame.size == 0:
            logger.warning("estimate: received empty/None frame.")
            return _zero_result(1, 1, self._model_name)

        h, w = frame.shape[:2]

        if not _TORCH_AVAILABLE or not self._primary:
            return _zero_result(h, w, self._model_name)

        t_start = time.perf_counter()
        try:
            with self._lock:
                rgb = _bgr_to_rgb(frame)
                depth = self._infer_primary(rgb)

                if self.enable_ensemble and self._secondary:
                    depth_sec = self._infer_secondary(rgb)
                    depth = 0.6 * depth + 0.4 * depth_sec

                # Resize to input resolution
                depth = self._resize_to(depth, h, w)
                depth_norm = self._normalize_depth(depth)
                confidence = self._compute_confidence(depth_norm)

        except Exception as exc:  # noqa: BLE001
            logger.error("estimate: inference failed: %s", exc, exc_info=True)
            return _zero_result(h, w, self._model_name)

        t_ms = (time.perf_counter() - t_start) * 1000.0
        return DepthResult(
            depth_map=depth_norm,
            confidence_map=confidence,
            model_used=self._model_name,
            inference_time_ms=t_ms,
        )

    def estimate_batch(self, frames: List[np.ndarray]) -> List[DepthResult]:
        """
        Estimate depth for a list of BGR frames.

        Frames are processed sequentially (the lock serialises inference).
        For true parallel GPU batching, override ``_infer_primary`` with a
        batched forward pass.

        Parameters
        ----------
        frames : list of np.ndarray
            Each element is a BGR uint8 image.

        Returns
        -------
        list of DepthResult
            One result per input frame, in the same order.
        """
        return [self.estimate(f) for f in frames]

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def _infer_primary(self, rgb: np.ndarray) -> np.ndarray:
        """Run inference on the primary model; returns raw float32 depth array."""
        m = self._primary
        if m["type"] == "midas":
            return self._run_midas(rgb, m)
        return self._run_depth_anything(rgb, m["model"])

    def _infer_secondary(self, rgb: np.ndarray) -> np.ndarray:
        """Run inference on the secondary (ensemble) model."""
        m = self._secondary
        if m["type"] == "midas":
            return self._run_midas(rgb, m)
        return self._run_depth_anything(rgb, m["model"])

    def _run_midas(self, rgb: np.ndarray, model_dict: Dict) -> np.ndarray:
        """
        Execute a MiDaS or DPT forward pass.

        Parameters
        ----------
        rgb : np.ndarray
            Float32 H×W×3 image in [0, 1].
        model_dict : dict
            Dict returned by ``_load_midas`` with keys ``'model'``
            and ``'transform'``.

        Returns
        -------
        np.ndarray
            Raw relative depth as a 2-D float32 array.
        """
        # MiDaS transforms expect uint8-like float in [0, 255] or a PIL image.
        img_uint8 = (rgb * 255.0).astype(np.uint8)

        inp = model_dict["transform"](img_uint8).to(self.device)  # adds batch dim

        with torch.no_grad():
            prediction = model_dict["model"](inp)
            # DPT outputs (B, H', W'); MiDaS small outputs (B, H', W')
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=rgb.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        return prediction.cpu().numpy().astype(np.float32)

    def _run_depth_anything(self, rgb: np.ndarray, model) -> np.ndarray:
        """
        Execute a Depth Anything HuggingFace pipeline pass.

        Parameters
        ----------
        rgb : np.ndarray
            Float32 H×W×3 image in [0, 1].
        model : transformers pipeline
            The loaded HuggingFace depth-estimation pipeline.

        Returns
        -------
        np.ndarray
            Raw relative depth as a 2-D float32 array.
        """
        from PIL import Image as _PILImage  # imported lazily

        img_pil = _PILImage.fromarray((rgb * 255).astype(np.uint8))
        result = model(img_pil)
        depth_arr = np.array(result["depth"], dtype=np.float32)
        return depth_arr

    # ------------------------------------------------------------------
    # Post-processing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resize_to(depth: np.ndarray, h: int, w: int) -> np.ndarray:
        """
        Resize a depth array to (h, w) using bicubic interpolation.

        Falls back to nearest-neighbour if OpenCV is unavailable.
        """
        if depth.shape == (h, w):
            return depth
        if _CV2_AVAILABLE:
            return _cv2.resize(depth, (w, h), interpolation=_cv2.INTER_CUBIC).astype(np.float32)
        # Numpy fallback (nearest)
        from PIL import Image as _PILImage

        pil = _PILImage.fromarray(depth)
        return np.array(pil.resize((w, h), resample=0), dtype=np.float32)

    @staticmethod
    def _normalize_depth(depth: np.ndarray) -> np.ndarray:
        """
        Linearly normalise a depth array to [0, 1].

        Parameters
        ----------
        depth : np.ndarray
            Raw relative depth (any range, float32).

        Returns
        -------
        np.ndarray
            Same shape, values in [0, 1].  Returns zeros if depth is
            constant (avoids division by zero).
        """
        d_min, d_max = float(depth.min()), float(depth.max())
        span = d_max - d_min
        if span < 1e-8:
            return np.zeros_like(depth, dtype=np.float32)
        return ((depth - d_min) / span).astype(np.float32)

    @staticmethod
    def _compute_confidence(depth_norm: np.ndarray) -> np.ndarray:
        """
        Compute a per-pixel confidence map from the normalised depth.

        Strategy: regions with high local depth *gradient magnitude* are
        likely near depth discontinuities or noisy estimates, so they get
        lower confidence.  The map is smoothed with a small Gaussian to
        reduce salt-and-pepper artifacts.

        Parameters
        ----------
        depth_norm : np.ndarray
            H×W float32 depth in [0, 1].

        Returns
        -------
        np.ndarray
            H×W float32 confidence in [0, 1].
        """
        if _CV2_AVAILABLE:
            # Sobel gradient magnitude
            sx = _cv2.Sobel(depth_norm, _cv2.CV_32F, 1, 0, ksize=3)
            sy = _cv2.Sobel(depth_norm, _cv2.CV_32F, 0, 1, ksize=3)
            grad = np.sqrt(sx ** 2 + sy ** 2)
            # Smooth the gradient
            grad_smooth = _cv2.GaussianBlur(grad, (5, 5), 0)
        else:
            # Pure-numpy Sobel approximation
            ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
            kx = ky.T
            pad = np.pad(depth_norm, 1, mode="edge")
            grad = np.sqrt(
                sum(
                    (
                        (
                            pad[:-2, :-2] * k[0, 0]
                            + pad[:-2, 1:-1] * k[0, 1]
                            + pad[:-2, 2:] * k[0, 2]
                            + pad[1:-1, :-2] * k[1, 0]
                            + pad[1:-1, 1:-1] * k[1, 1]
                            + pad[1:-1, 2:] * k[1, 2]
                            + pad[2:, :-2] * k[2, 0]
                            + pad[2:, 1:-1] * k[2, 1]
                            + pad[2:, 2:] * k[2, 2]
                        )
                        ** 2
                    )
                    for k in (kx, ky)
                )
            )
            grad_smooth = grad

        # Normalise gradient and invert so low-gradient → high-confidence
        g_max = float(grad_smooth.max())
        if g_max < 1e-8:
            return np.ones_like(depth_norm, dtype=np.float32)
        confidence = 1.0 - (grad_smooth / g_max)
        return confidence.astype(np.float32)
