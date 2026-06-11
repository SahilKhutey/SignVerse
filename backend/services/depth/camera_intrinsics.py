"""
camera_intrinsics.py
===================
Camera intrinsics representation and estimation for SignVerse depth pipeline.
Tracks focal lengths (fx, fy), principal points (cx, cy), and image size.
Includes heuristics for estimating intrinsics from visible people or objects when EXIF is missing.
"""

from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning("OpenCV not found in camera_intrinsics. Calibration functionality will be disabled.")

@dataclass
class CameraIntrinsics:
    """
    Representation of camera intrinsic parameters.
    
    Attributes
    ----------
    fx, fy : float
        Focal lengths in pixels along x and y axes.
    cx, cy : float
        Principal point coordinates in pixels (usually image center).
    width, height : int
        Image dimensions in pixels.
    distortion : Optional[np.ndarray]
        Distortion coefficients (k1, k2, p1, p2, k3).
    """
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    distortion: Optional[np.ndarray] = None

    @property
    def fov_x_deg(self) -> float:
        """Horizontal Field of View in degrees."""
        return 2 * math.degrees(math.atan2(self.width / 2.0, self.fx))

    @property
    def fov_y_deg(self) -> float:
        """Vertical Field of View in degrees."""
        return 2 * math.degrees(math.atan2(self.height / 2.0, self.fy))

    @property
    def K(self) -> np.ndarray:
        """3x3 Intrinsic Camera Matrix."""
        return np.array([
            [self.fx, 0.0, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0]
        ], dtype=np.float32)

    def depth_from_pixel_size(self, pixel_size: float, real_size_m: float) -> float:
        """
        Estimate depth Z of an object of known size.
        Z = fx * real_size_m / pixel_size
        """
        if pixel_size < 1e-5:
            return 0.0
        return (self.fx * real_size_m) / pixel_size

    def project_3d_to_2d(self, xyz: np.ndarray) -> Tuple[float, float]:
        """
        Project 3D point (meters) in camera coordinate system to 2D pixel coordinates.
        Uses standard pinhole model.
        """
        x, y, z = xyz[0], xyz[1], xyz[2]
        if abs(z) < 1e-5:
            z = 1e-5 if z >= 0 else -1e-5
        px = (x * self.fx) / z + self.cx
        py = (y * self.fy) / z + self.cy
        return (float(px), float(py))

    def unproject_2d_to_3d(self, px: float, py: float, depth_m: float) -> np.ndarray:
        """
        Back-project 2D pixel coordinate to 3D point in camera coordinate system.
        """
        x = (px - self.cx) * depth_m / self.fx
        y = (py - self.cy) * depth_m / self.fy
        return np.array([x, y, depth_m], dtype=np.float32)

    def to_dict(self) -> Dict[str, Any]:
        """Convert intrinsics to a serializable dictionary."""
        return {
            "fx": self.fx,
            "fy": self.fy,
            "cx": self.cx,
            "cy": self.cy,
            "width": self.width,
            "height": self.height,
            "distortion": self.distortion.tolist() if self.distortion is not None else None
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CameraIntrinsics:
        """Create CameraIntrinsics from dictionary representation."""
        dist = np.array(d["distortion"], dtype=np.float32) if d.get("distortion") is not None else None
        return cls(
            fx=float(d["fx"]),
            fy=float(d["fy"]),
            cx=float(d["cx"]),
            cy=float(d["cy"]),
            width=int(d["width"]),
            height=int(d["height"]),
            distortion=dist
        )


class CameraIntrinsicsEstimator:
    """
    Estimator class to refine/determine camera intrinsics dynamically.
    """
    def __init__(self, image_width: int = 1280, image_height: int = 720) -> None:
        self.width = image_width
        self.height = image_height
        
        # Initialize with standard webcam heuristic (fov ~ 70 deg)
        self.current_intrinsics = self.default_webcam()

    def default_webcam(self) -> CameraIntrinsics:
        """Returns default webcam intrinsics (fx = fy = width * 0.9)."""
        fx = self.width * 0.9
        fy = self.height * 0.9 if self.height > 0 else fx
        return CameraIntrinsics(
            fx=fx,
            fy=fy,
            cx=self.width / 2.0,
            cy=self.height / 2.0,
            width=self.width,
            height=self.height
        )

    def default_phone(self) -> CameraIntrinsics:
        """Returns typical mobile phone camera intrinsics (fx = fy = width * 1.2)."""
        fx = self.width * 1.2
        fy = self.height * 1.2 if self.height > 0 else fx
        return CameraIntrinsics(
            fx=fx,
            fy=fy,
            cx=self.width / 2.0,
            cy=self.height / 2.0,
            width=self.width,
            height=self.height
        )

    def estimate_from_person(self, landmarks: List[Dict[str, float]], person_height_m: float = 1.70, assumed_depth_m: float = 2.5) -> CameraIntrinsics:
        """
        Estimate focal length from the vertical pixel height of a visible person.
        
        Parameters
        ----------
        landmarks : List[Dict[str, float]]
            List of 33 normalized MediaPipe landmarks, e.g. [{"x":..., "y":..., "z":..., "visibility":...}]
        person_height_m : float
            Assumed real-world height of the person in meters.
        assumed_depth_m : float
            Assumed average depth of the person from the camera in meters.
        """
        if len(landmarks) < 33:
            return self.current_intrinsics

        # Use crown/nose to ankle/foot vertical span.
        # MediaPipe nose is index 0. Ankle index 27, 28.
        # Find vertical pixel coordinates.
        y_coords = [lm["y"] * self.height for lm in landmarks if "y" in lm]
        if not y_coords:
            return self.current_intrinsics

        # Alternatively, find the bounding box of all visible landmarks (excluding hands/feet if preferred,
        # but vertical extent works well).
        # We want to measure crown to foot. Crown is above nose. Nose is index 0, eyes 1-6, ears 7-8.
        # Let's take the difference between minimum y (top of head/shoulders) and maximum y (ankles/heels).
        y_min = min(y_coords)
        y_max = max(y_coords)
        pixel_height = y_max - y_min

        if pixel_height < 50.0:
            return self.current_intrinsics  # person too small/distant or invalid

        # fy = pixel_height * assumed_depth_m / person_height_m
        fy = (pixel_height * assumed_depth_m) / person_height_m
        fx = fy  # assume square pixels

        return CameraIntrinsics(
            fx=fx,
            fy=fy,
            cx=self.width / 2.0,
            cy=self.height / 2.0,
            width=self.width,
            height=self.height
        )

    def estimate_from_object(self, bbox: List[float], real_height_m: float, assumed_depth_m: float = 1.5) -> CameraIntrinsics:
        """
        Estimate focal length from the bounding box height of an object of known height.
        bbox is [x, y, w, h] in pixels.
        """
        if len(bbox) < 4:
            return self.current_intrinsics
        
        pixel_height = bbox[3]
        if pixel_height < 10.0:
            return self.current_intrinsics
        
        fy = (pixel_height * assumed_depth_m) / real_height_m
        fx = fy

        return CameraIntrinsics(
            fx=fx,
            fy=fy,
            cx=self.width / 2.0,
            cy=self.height / 2.0,
            width=self.width,
            height=self.height
        )

    def calibrate_from_checkerboard(self, images: List[np.ndarray], board_size: Tuple[int, int] = (9, 6), square_m: float = 0.025) -> CameraIntrinsics:
        """
        Calibrate camera using standard OpenCV chessboard calibration method.
        """
        if not _CV2_AVAILABLE:
            logger.warning("calibrated_from_checkerboard failed: OpenCV is not available.")
            return self.current_intrinsics

        objpoints = []
        imgpoints = []

        # 3D points in real space
        objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2) * square_m

        gray_shape = None
        for img in images:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            gray_shape = gray.shape[::-1]
            ret, corners = cv2.findChessboardCorners(gray, board_size, None)
            if ret:
                objpoints.append(objp)
                imgpoints.append(corners)

        if not imgpoints or gray_shape is None:
            logger.warning("Chessboard corners not found in any input images. Calibration skipped.")
            return self.current_intrinsics

        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            objpoints, imgpoints, gray_shape, None, None
        )

        if ret:
            logger.info("Camera calibration successful!")
            return CameraIntrinsics(
                fx=float(mtx[0, 0]),
                fy=float(mtx[1, 1]),
                cx=float(mtx[0, 2]),
                cy=float(mtx[1, 2]),
                width=gray_shape[0],
                height=gray_shape[1],
                distortion=dist
            )
        else:
            logger.warning("Camera calibration algorithm failed. Using current estimate.")
            return self.current_intrinsics

    def update_from_new_frame(self, landmarks: List[Dict[str, float]], person_height_m: float = 1.70) -> CameraIntrinsics:
        """
        Refine the camera intrinsics estimate using exponential moving average (EMA)
        over landmarks detected in a new frame.
        """
        if len(landmarks) < 33:
            return self.current_intrinsics
        
        # Extent vertical height in pixels
        y_coords = [lm["y"] * self.height for lm in landmarks if "y" in lm and lm.get("visibility", 0) > 0.5]
        if not y_coords:
            return self.current_intrinsics

        y_min = min(y_coords)
        y_max = max(y_coords)
        pixel_height = y_max - y_min

        # Only update if pixel height is reasonable/stable (> 150px)
        if pixel_height < 150.0:
            return self.current_intrinsics

        # Assume distance is around 2.5 meters
        target_depth = 2.5
        estimated_fy = (pixel_height * target_depth) / person_height_m
        estimated_fx = estimated_fy

        # EMA update
        alpha = 0.1
        new_fx = alpha * estimated_fx + (1.0 - alpha) * self.current_intrinsics.fx
        new_fy = alpha * estimated_fy + (1.0 - alpha) * self.current_intrinsics.fy

        self.current_intrinsics = CameraIntrinsics(
            fx=new_fx,
            fy=new_fy,
            cx=self.width / 2.0,
            cy=self.height / 2.0,
            width=self.width,
            height=self.height,
            distortion=self.current_intrinsics.distortion
        )
        return self.current_intrinsics
