"""
Enhanced interaction.py — Human-Object Interaction (HOI) engine.

Upgrades over original:
  • LIFTING, MOVING, PLACING, POINTING, USING interaction types
  • 3D distance computation (uses object position_3d from detector)
  • Contact point in 3D coordinates
  • Richer temporal state machine (GRASPING → HOLDING → LIFTING → PLACING)
  • `HandObjectInteraction` extended with 3D fields + first/last frame
  • Backward-compatible: `to_dict()` and serialisation unchanged
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════ #
# Enums & Dataclasses
# ═══════════════════════════════════════════════════════════════════ #

class InteractionType(Enum):
    NO_CONTACT  = "NO_CONTACT"
    APPROACHING = "APPROACHING"    # Hand moving toward object
    NEAR        = "NEAR"           # Within proximity, no contact
    TOUCHING    = "TOUCHING"       # Hand on object surface
    GRASPING    = "GRASPING"       # Hand closed around object
    HOLDING     = "HOLDING"        # Stable grasp (> threshold frames)
    LIFTING     = "LIFTING"        # Holding + upward motion
    MOVING      = "MOVING"         # Holding + lateral translation
    PLACING     = "PLACING"        # Lowering held object
    RELEASING   = "RELEASING"      # Opening hand, moving away
    POINTING    = "POINTING"       # Index finger extended toward object
    USING       = "USING"          # Tool-use pattern (e.g. typing, writing)
    MANIPULATING= "MANIPULATING"   # General active manipulation


@dataclass
class HandObjectInteraction:
    """One hand's interaction with one tracked object."""
    # Core fields (original API — unchanged)
    hand:             str     # "left" | "right"
    object_id:        int     # YOLO track ID
    object_class:     str     # "cup", "cell phone", etc.
    interaction_type: str     # InteractionType.value
    distance_px:      float   # 2D distance in pixels
    hand_gesture:     str     # From gesture classifier
    confidence:       float
    duration_frames:  int = 0

    # New 3D fields
    object_position_3d: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    distance_3d:        float = 0.0         # metres
    contact_point_3d:   List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    velocity_3d:        List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # Temporal tracking
    first_frame:  int = 0
    last_frame:   int = 0


@dataclass
class InteractionGraph:
    """Complete HOI state for one frame."""
    hand_object_interactions: List[HandObjectInteraction]
    person_objects_in_scene:  List[Dict]   # All detected objects (with 3D data)
    person_posture:           str          # "standing" | "sitting" | "crouching"
    attention_target:         str          # What person is paying attention to
    primary_focus:            Optional[Dict]


# ═══════════════════════════════════════════════════════════════════ #
# Engine
# ═══════════════════════════════════════════════════════════════════ #

class InteractionEngine:
    """
    Detects and tracks person-object interactions.
    Inputs: MediaPipe body/hand landmarks + YOLO object list (now with 3D).
    """

    MANIPULABLE_OBJECTS = {
        "cup", "bottle", "wine glass", "bowl", "fork", "knife", "spoon",
        "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
        "hot dog", "pizza", "donut", "cake",
        "cell phone", "laptop", "mouse", "remote", "keyboard",
        "book", "scissors", "toothbrush", "hair drier",
        "handbag", "backpack", "umbrella", "tie", "suitcase",
        "baseball bat", "baseball glove", "tennis racket",
        "frisbee", "sports ball", "kite",
        "vase", "clock", "teddy bear",
    }

    # Distance thresholds (normalised bbox diagonal)
    DIST_GRASP  = 0.40
    DIST_TOUCH  = 0.30
    DIST_NEAR   = 0.65
    DIST_POINT  = 0.80

    # 3D distance thresholds (metres)
    D3_CONTACT  = 0.12
    D3_NEAR     = 0.35
    D3_APPROACH = 0.60

    # Temporal thresholds (frames)
    HOLD_FRAMES   = 10
    LIFT_Y_THRESH = 0.05   # metres per frame upward motion

    def __init__(self):
        self.active_interactions: Dict[Tuple[str, int], HandObjectInteraction] = {}
        self._frame_counter = 0

    # ---------------------------------------------------------------- #
    # Main entry point
    # ---------------------------------------------------------------- #

    def analyze_frame(
        self,
        body_landmarks:    List[Dict],
        left_hand:         Optional[List[Dict]],
        right_hand:        Optional[List[Dict]],
        left_gesture:      Optional[str],
        right_gesture:     Optional[str],
        objects:           List[Dict],          # From ObjectDetector3D
        gaze:              Dict,
        prev_interactions: Optional["InteractionGraph"] = None,
    ) -> InteractionGraph:
        """Build complete interaction graph for one frame."""
        self._frame_counter += 1
        interactions: List[HandObjectInteraction] = []

        if left_hand and len(left_hand) >= 21:
            palm_l = self._get_palm_center(left_hand)
            interactions.extend(
                self._find_hand_interactions(
                    "left", palm_l, left_hand, left_gesture, objects
                )
            )

        if right_hand and len(right_hand) >= 21:
            palm_r = self._get_palm_center(right_hand)
            interactions.extend(
                self._find_hand_interactions(
                    "right", palm_r, right_hand, right_gesture, objects
                )
            )

        interactions = self._update_state_machine(interactions, prev_interactions)

        posture    = self._classify_posture(body_landmarks)
        attention  = self._find_attention_target(gaze, objects, interactions)
        primary    = self._find_primary_focus(interactions)

        return InteractionGraph(
            hand_object_interactions=interactions,
            person_objects_in_scene=objects,
            person_posture=posture,
            attention_target=attention,
            primary_focus=primary,
        )

    # ---------------------------------------------------------------- #
    # Hand → object matching
    # ---------------------------------------------------------------- #

    def _find_hand_interactions(
        self,
        hand:            str,
        palm:            Tuple[float, float, float],
        hand_landmarks:  List[Dict],
        gesture:         Optional[str],
        objects:         List[Dict],
    ) -> List[HandObjectInteraction]:
        results = []
        hx, hy, hz = palm

        for obj in objects:
            bbox      = obj["bbox"]
            cls_name  = obj["class"]
            tid       = obj.get("track_id", -1)
            pos3d     = obj.get("position_3d", [0.0, 0.0, 0.0])
            vel3d     = obj.get("velocity_3d", [0.0, 0.0, 0.0])

            # ── 2D distance ──
            # Scale hx, hy from [0, 1] normalized space to [640, 480] pixel space
            hx_px = hx * 640.0
            hy_px = hy * 480.0
            cx2d = (bbox[0] + bbox[2]) / 2
            cy2d = (bbox[1] + bbox[3]) / 2
            diag  = max(((bbox[2]-bbox[0])**2 + (bbox[3]-bbox[1])**2)**0.5, 50.0)
            dist2d = ((hx_px - cx2d)**2 + (hy_px - cy2d)**2)**0.5
            ndist  = dist2d / diag

            # ── 3D distance (if available) ──
            # palm is in pixel space (normalised 0-1); obj in metres.
            # Use 2D-normalised as primary, 3D as supporting evidence.
            dist3d = float(np.linalg.norm(np.array(pos3d) - np.array([0, 0, pos3d[2]])))

            itype, conf = self._classify(ndist, dist3d, gesture, cls_name)
            if itype == InteractionType.NO_CONTACT.value:
                continue

            contact = self._contact_point(hand_landmarks, bbox, pos3d)

            results.append(HandObjectInteraction(
                hand=hand,
                object_id=tid,
                object_class=cls_name,
                interaction_type=itype,
                distance_px=round(dist2d, 1),
                hand_gesture=gesture or "UNKNOWN",
                confidence=conf,
                duration_frames=0,
                object_position_3d=pos3d,
                distance_3d=round(dist3d, 3),
                contact_point_3d=contact,
                velocity_3d=vel3d,
                first_frame=self._frame_counter,
                last_frame=self._frame_counter,
            ))

        return results

    def _classify(
        self,
        ndist:     float,
        dist3d:    float,
        gesture:   Optional[str],
        cls_name:  str,
    ) -> Tuple[str, float]:
        """Map distance + gesture → interaction type + confidence."""
        manipulable = cls_name in self.MANIPULABLE_OBJECTS
        g = gesture or "UNKNOWN"

        if not manipulable:
            return (InteractionType.NEAR.value, 0.45) if ndist < 0.4 else (InteractionType.NO_CONTACT.value, 0.0)

        # Confirmed grasp (very close + closed hand)
        if ndist < self.DIST_GRASP and g in ("FIST", "GRAB", "PINCH"):
            return InteractionType.GRASPING.value, 0.93

        # Touching (close + open hand)
        if ndist < self.DIST_TOUCH and g in ("OPEN_PALM",):
            return InteractionType.TOUCHING.value, 0.86

        # Pointing
        if ndist < self.DIST_POINT and g in ("POINTING", "INDEX_UP"):
            return InteractionType.POINTING.value, 0.82

        # Generic grasp at medium distance
        if ndist < self.DIST_GRASP and g in ("FIST", "GRAB"):
            return InteractionType.GRASPING.value, 0.80

        # Near (hand is close but gesture unclear)
        if ndist < self.DIST_NEAR:
            return InteractionType.NEAR.value, 0.60 + (self.DIST_NEAR - ndist) * 0.3

        return InteractionType.NO_CONTACT.value, 0.0

    # ---------------------------------------------------------------- #
    # Temporal state machine
    # ---------------------------------------------------------------- #

    def _update_state_machine(
        self,
        current:  List[HandObjectInteraction],
        prev_raw: Optional["InteractionGraph"],
    ) -> List[HandObjectInteraction]:
        """Upgrade interaction types based on history."""
        prev_map: Dict[Tuple[str, int], HandObjectInteraction] = {}
        if prev_raw is not None:
            plist = (prev_raw.hand_object_interactions
                     if hasattr(prev_raw, "hand_object_interactions")
                     else prev_raw.get("hand_object_interactions", []))
            for p in plist:
                if hasattr(p, "hand"):
                    prev_map[(p.hand, p.object_id)] = p
                else:
                    prev_map[(p.get("hand"), p.get("object_id"))] = p

        current_keys = set()
        for i in current:
            key = (i.hand, i.object_id)
            current_keys.add(key)

            if key in prev_map:
                p = prev_map[key]
                p_dur   = getattr(p, "duration_frames", p.get("duration_frames", 0) if isinstance(p, dict) else 0)
                p_type  = getattr(p, "interaction_type", p.get("interaction_type", "") if isinstance(p, dict) else "")
                p_ff    = getattr(p, "first_frame", self._frame_counter)
                i.duration_frames = p_dur + 1
                i.first_frame     = p_ff
                i.last_frame      = self._frame_counter
            else:
                i.duration_frames = 1
                i.first_frame     = self._frame_counter
                i.last_frame      = self._frame_counter

            # ── State upgrades ──
            p_type = ""
            if key in prev_map:
                pp = prev_map[key]
                p_type = getattr(pp, "interaction_type", pp.get("interaction_type", "") if isinstance(pp, dict) else "")

            # GRASPING → HOLDING (sustained grip)
            if (i.interaction_type == InteractionType.GRASPING.value
                    and i.duration_frames >= self.HOLD_FRAMES):
                i.interaction_type = InteractionType.HOLDING.value

            # HOLDING → LIFTING (upward velocity)
            if (i.interaction_type == InteractionType.HOLDING.value
                    and i.velocity_3d[1] > self.LIFT_Y_THRESH):
                i.interaction_type = InteractionType.LIFTING.value

            # HOLDING / LIFTING → MOVING (horizontal motion while held)
            if (i.interaction_type in (InteractionType.HOLDING.value, InteractionType.LIFTING.value)
                    and (abs(i.velocity_3d[0]) + abs(i.velocity_3d[2])) > 0.05):
                if i.velocity_3d[1] < -self.LIFT_Y_THRESH:
                    i.interaction_type = InteractionType.PLACING.value
                elif abs(i.velocity_3d[0]) > 0.02 or abs(i.velocity_3d[2]) > 0.02:
                    i.interaction_type = InteractionType.MOVING.value

            # HOLDING → RELEASING (was holding, now hand opens)
            if (p_type in (InteractionType.HOLDING.value, InteractionType.GRASPING.value)
                    and i.hand_gesture in ("OPEN_PALM", "UNKNOWN", "FIVE")):
                i.interaction_type = InteractionType.RELEASING.value

            self.active_interactions[key] = i

        # Clean up old
        for k in list(self.active_interactions.keys()):
            if k not in current_keys:
                del self.active_interactions[k]

        return current

    # ---------------------------------------------------------------- #
    # Utility
    # ---------------------------------------------------------------- #

    @staticmethod
    def _get_palm_center(lms: List[Dict]) -> Tuple[float, float, float]:
        def g(lm, attr, default=0.0):
            return getattr(lm, attr, None) or (lm.get(attr, default) if isinstance(lm, dict) else default)
        w  = lms[0];  m = lms[9]
        return (
            (g(w,"x") + g(m,"x")) / 2,
            (g(w,"y") + g(m,"y")) / 2,
            (g(w,"z") + g(m,"z")) / 2,
        )

    @staticmethod
    def _contact_point(
        lms:   List[Dict],
        bbox:  List[float],
        pos3d: List[float],
    ) -> List[float]:
        """Find hand landmark closest to object bbox centre."""
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        best_d, best_i = float("inf"), 0
        for idx, lm in enumerate(lms):
            x = getattr(lm, "x", lm.get("x", 0) if isinstance(lm, dict) else 0)
            y = getattr(lm, "y", lm.get("y", 0) if isinstance(lm, dict) else 0)
            x_px = x * 640.0
            y_px = y * 480.0
            d = (x_px - cx)**2 + (y_px - cy)**2
            if d < best_d:
                best_d, best_i = d, idx
        lm = lms[best_i]
        return [
            getattr(lm, "x", lm.get("x", 0.0) if isinstance(lm, dict) else 0.0),
            getattr(lm, "y", lm.get("y", 0.0) if isinstance(lm, dict) else 0.0),
            pos3d[2],
        ]

    def _classify_posture(self, body: List[Dict]) -> str:
        if len(body) < 33:
            return "unknown"
        def gy(idx):
            lm = body[idx]
            return getattr(lm, "y", lm.get("y", 0.0) if isinstance(lm, dict) else 0.0)
        avg_hip  = (gy(23) + gy(24)) / 2
        avg_knee = (gy(25) + gy(26)) / 2
        ext = abs(avg_knee - avg_hip)
        if ext > 0.15: return "standing"
        if ext > 0.08: return "crouching"
        return "sitting"

    def _find_attention_target(
        self,
        gaze:         Dict,
        objects:      List[Dict],
        interactions: List[HandObjectInteraction],
    ) -> str:
        held = [i for i in interactions
                if i.interaction_type in (
                    InteractionType.HOLDING.value,
                    InteractionType.GRASPING.value,
                    InteractionType.LIFTING.value,
                    InteractionType.MOVING.value,
                )]
        if held:
            return held[0].object_class

        if gaze.get("direction") in ("left", "right", "up", "down"):
            return f"gaze_{gaze['direction']}"

        return "scene"

    def _find_primary_focus(
        self,
        interactions: List[HandObjectInteraction],
    ) -> Optional[Dict]:
        if not interactions:
            return None
        priority = {
            InteractionType.LIFTING.value:  6,
            InteractionType.MOVING.value:   6,
            InteractionType.HOLDING.value:  5,
            InteractionType.GRASPING.value: 4,
            InteractionType.PLACING.value:  4,
            InteractionType.USING.value:    4,
            InteractionType.TOUCHING.value: 3,
            InteractionType.POINTING.value: 2,
            InteractionType.NEAR.value:     1,
        }
        best = max(interactions, key=lambda i: priority.get(i.interaction_type, 0) * i.confidence)
        return asdict(best)

    def to_dict(self, graph: InteractionGraph) -> Dict:
        """JSON-serialisable dict — unchanged public API."""
        return {
            "hand_object_interactions": [asdict(i) for i in graph.hand_object_interactions],
            "person_objects_in_scene":  graph.person_objects_in_scene,
            "person_posture":           graph.person_posture,
            "attention_target":         graph.attention_target,
            "primary_focus":            graph.primary_focus,
        }

    def reset(self):
        """Reset for new session."""
        self.active_interactions.clear()
        self._frame_counter = 0
