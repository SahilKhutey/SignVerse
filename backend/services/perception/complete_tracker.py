from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import numpy as np

from backend.services.perception_pipeline import PerceptionPipeline

@dataclass
class CompletePerceptionResult:
    frame_id: int
    timestamp_ms: int
    pose_33: List[Dict]
    left_hand_21: List[Dict]
    right_hand_21: List[Dict]
    face_478: List[Dict]
    objects: List[Dict]
    
    # Hand analysis
    hand_gestures: Dict
    
    # Face analysis
    expression: str
    expression_confidence: float
    head_pose: Dict
    gaze: Dict
    
    # Interaction
    interaction_graph: Dict
    person_posture: str
    attention_target: str
    
    # Action
    action_primitives: List[Dict]
    primary_action: str
    
    # Intent
    primary_intent: str
    intent_confidence: float
    intent_evidence: str
    
    # Quality
    pose_confidence: float
    processing_time_ms: float

    # Metric depth extensions
    pose_33_metric: Optional[List[List[float]]] = None
    left_hand_21_metric: Optional[List[List[float]]] = None
    right_hand_21_metric: Optional[List[List[float]]] = None
    objects_metric: Optional[List[Dict]] = None
    depth_map: Optional[np.ndarray] = None
    scale_factor: Optional[float] = None
    person_height_m: Optional[float] = None
    shoulder_width_m: Optional[float] = None
    left_arm_length_m: Optional[float] = None
    right_arm_length_m: Optional[float] = None

class CompleteTracker:
    """
    Wrapper around the PerceptionPipeline.
    Bridges pipeline structures to broadcaster formats.
    """
    def __init__(self):
        self.pipeline = PerceptionPipeline()
        from backend.services.depth.metric_reconstruction import MetricReconstructor
        self.reconstructor = MetricReconstructor(enable_depth_model=True)
        
    def process_frame(self, frame: np.ndarray, frame_id: int = 0, timestamp_ms: int = 0) -> CompletePerceptionResult:
        res = self.pipeline.process_frame(frame, frame_id, timestamp_ms)
        
        prims = res.primitives
        primary_action = prims[0].get("primitive", "IDLE") if prims else "IDLE"
        
        # Convert Landmark dataclasses to dictionaries
        def to_dict_list(landmarks):
            return [{"x": float(l.x), "y": float(l.y), "z": float(l.z), "v": float(l.v)} for l in landmarks]

        pose_33 = to_dict_list(res.pose)
        left_hand_21 = to_dict_list(res.left_hand)
        right_hand_21 = to_dict_list(res.right_hand)
        face_478 = to_dict_list(res.face)
        
        gaze = res.expression.get("gaze", {"direction": "center"})

        # Run metric 3D reconstruction
        metric_res = None
        try:
            metric_res = self.reconstructor.reconstruct_frame(
                frame=frame,
                perception={
                    "pose_33": pose_33,
                    "left_hand_21": left_hand_21,
                    "right_hand_21": right_hand_21,
                    "objects": res.objects
                },
                frame_id=frame_id,
                timestamp_ms=timestamp_ms
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed to run metric reconstruction in tracker: %s", e)
        
        return CompletePerceptionResult(
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            pose_33=pose_33,
            left_hand_21=left_hand_21,
            right_hand_21=right_hand_21,
            face_478=face_478,
            objects=res.objects,
            hand_gestures=res.gestures,
            expression=res.expression.get("expression", "NEUTRAL"),
            expression_confidence=res.expression.get("confidence", 1.0),
            head_pose=res.expression.get("head_pose", {"pitch": 0, "yaw": 0, "roll": 0}),
            gaze=gaze,
            interaction_graph=res.interaction,
            person_posture=res.interaction.get("person_posture", "standing"),
            attention_target=res.interaction.get("attention_target", "scene"),
            action_primitives=prims,
            primary_action=primary_action,
            primary_intent=res.intent,
            intent_confidence=0.85,
            intent_evidence="Calculated from temporal primitives.",
            pose_confidence=float(res.confidence_mean),
            processing_time_ms=self.pipeline.avg_latency_ms,
            
            # Metric depth extensions
            pose_33_metric=metric_res.pose_33_metric if metric_res else None,
            left_hand_21_metric=metric_res.left_hand_21_metric if metric_res else None,
            right_hand_21_metric=metric_res.right_hand_21_metric if metric_res else None,
            objects_metric=metric_res.objects_metric if metric_res else None,
            depth_map=metric_res.depth_map if metric_res else None,
            scale_factor=metric_res.scale_factor if metric_res else None,
            person_height_m=metric_res.person_height_m if metric_res else None,
            shoulder_width_m=metric_res.shoulder_width_m if metric_res else None,
            left_arm_length_m=metric_res.left_arm_length_m if metric_res else None,
            right_arm_length_m=metric_res.right_arm_length_m if metric_res else None
        )
