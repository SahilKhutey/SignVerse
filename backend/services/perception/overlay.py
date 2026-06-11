import cv2
import numpy as np
import mediapipe as mp
from backend.services.perception.holistic_extractor import PerceptionResult

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


def draw_pose_overlay(frame: np.ndarray, result: PerceptionResult) -> np.ndarray:
    """
    Draw MediaPipe pose/hands/face and YOLO bounding boxes on frame.
    Returns annotated frame.
    """
    annotated = frame.copy()
    h, w = frame.shape[:2]
    
    # 1. Convert normalized landmarks back to mediapipe format for drawing
    if result.pose:
        pose_proto = _landmarks_to_proto(result.pose, w, h)
        mp_drawing.draw_landmarks(
            annotated,
            pose_proto,
            mp.solutions.holistic.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
        )
    
    if result.left_hand:
        lh_proto = _landmarks_to_proto(result.left_hand, w, h)
        mp_drawing.draw_landmarks(
            annotated, lh_proto, mp.solutions.holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style(),
        )
    
    if result.right_hand:
        rh_proto = _landmarks_to_proto(result.right_hand, w, h)
        mp_drawing.draw_landmarks(
            annotated, rh_proto, mp.solutions.holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style(),
        )
        
    # 2. Draw YOLO Object Detection Bounding Boxes
    if result.objects:
        for obj in result.objects:
            bbox = obj["bbox"] # [x1, y1, x2, y2]
            cls_name = obj["class"]
            conf = obj["confidence"]
            track_id = obj.get("track_id")
            
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            
            # Draw box
            color = (0, 255, 255) # Yellow/Cyan
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Label text
            label = f"{cls_name} ({conf:.2f})"
            if track_id is not None:
                label = f"#{track_id} {label}"
                
            cv2.putText(
                annotated, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )
    
    # HUD overlay
    cv2.putText(
        annotated,
        f"Conf: {result.confidence_mean:.2f} | Frame: {result.frame_id}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
    )
    
    return annotated


def _landmarks_to_proto(landmarks, w: int, h: int):
    """Convert our Landmark list back to MediaPipe NormalizedLandmarkList."""
    proto = mp.framework.formats.landmark_pb2.NormalizedLandmarkList()
    for lm in landmarks:
        # Re-scale from actual pixels to normalized [0, 1] relative to drawing size
        proto.landmark.add(
            x=lm.x / w,
            y=lm.y / h,
            z=lm.z / w,
            visibility=lm.v,
        )
    return proto
