"""
Classifies the person's work intention from current state.
Combines: action primitives + object class + context → intent label.
"""
from typing import List, Dict, Optional
from enum import Enum


class Intent(Enum):
    """Recognized work intentions."""
    IDLE = "IDLE"
    UNKNOWN = "UNKNOWN"

    # Food & drink
    DRINK = "DRINK"                    # Lifting cup/bottle to face
    EAT = "EAT"                        # Bringing food to mouth
    POUR = "POUR"                      # Tilted container
    COOK = "COOK"                      # Manipulating utensils in cooking area

    # Communication
    TYPING = "TYPING"                  # Hands on keyboard
    PHONE_CALL = "PHONE_CALL"          # Phone to ear
    TEXTING = "TEXTING"                # Phone in front, thumbs moving
    READ = "READ"                      # Holding book/tablet, looking at it
    WRITE = "WRITE"                    # Holding pen, writing motion

    # Object manipulation
    PICK_UP = "PICK_UP"                # Generic grasp + lift
    PUT_DOWN = "PUT_DOWN"              # Generic place
    CLEAN = "CLEAN"                    # Wiping motion with cloth
    OPEN = "OPEN"                      # Opening container/door
    CLOSE = "CLOSE"                    # Closing container/door
    ASSEMBLE = "ASSEMBLE"              # Joining two objects

    # Body movement
    WALK = "WALK"
    SIT = "SIT"
    STAND = "STAND"
    REACH_HIGH = "REACH_HIGH"          # Arm above shoulder
    REACH_LOW = "REACH_LOW"            # Bending down
    GESTURE = "GESTURE"                # Communicative hand movement
    WAVE = "WAVE"                      # Greeting gesture

    # Tools
    USE_TOOL = "USE_TOOL"              # Hammer, scissors, knife, etc.


class IntentClassifier:
    """Classifies user intention using context heuristics and temporal sequence tracking."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the temporal state history."""
        # Stores dicts of frame state details for sequence recognition
        self.history = []
        self.max_history_len = 60  # ~2 seconds at 30 fps

    def classify(self, interaction_graph: Dict, primitives: List[Dict]) -> str:
        """
        Classifies intent based on interaction state, action primitives, and temporal history.
        """
        # Append current frame state to history
        self.history.append({
            "interaction_graph": interaction_graph,
            "primitives": primitives
        })
        if len(self.history) > self.max_history_len:
            self.history.pop(0)

        # Extract recent active primitives across history
        recent_prims = []
        for frame in self.history:
            for p in frame["primitives"]:
                recent_prims.append(p["primitive"])

        posture = interaction_graph.get("person_posture", "unknown")
        attention = interaction_graph.get("attention_target", "scene")
        
        ho_interactions = interaction_graph.get("hand_object_interactions", [])
        
        objects_held = [i["object_class"] for i in ho_interactions if i["interaction_type"] in ("HOLDING", "GRASPING")]
        objects_near = [i["object_class"] for i in ho_interactions if i["interaction_type"] == "NEAR"]
        prims = [p["primitive"] for p in primitives]

        # 1. Food & Drink Heuristics (DRINK / EAT)
        if "cup" in objects_held or "bottle" in objects_held:
            # If bringing towards face or looking up to drink
            if "LIFT" in prims or attention in ("gaze_up", "cup", "bottle", "mouth", "face"):
                if attention not in ("table", "desk", "bowl", "sink"):
                    return Intent.DRINK.value

        if any(food in objects_held for food in ["banana", "apple", "sandwich", "orange"]):
            if "LIFT" in prims or attention in ("scene", "mouth", "face"):
                return Intent.EAT.value

        # 2. Compound Sequence - POUR Heuristic:
        # Hand holding container (cup or bottle) + pouring target nearby + not drinking
        if any(c in objects_held for c in ("cup", "bottle")):
            has_lifted = any(p in ("LIFT", "GRASP") for p in recent_prims[-30:]) or len(self.history) < 5
            if has_lifted and attention in ("table", "desk", "bowl", "sink", "scene"):
                # Check if another object or table surface is near/touching
                other_targets = [i for i in ho_interactions if i["object_class"] in ("cup", "bowl", "sink", "table", "desk") and i["interaction_type"] in ("NEAR", "TOUCHING")]
                if other_targets:
                    return Intent.POUR.value

        # 3. Compound Sequence - CLEAN Heuristic:
        # Hand wiping a table/desk surface repeatedly (back-and-forth movement primitives)
        table_contacts = [
            any(i["object_class"] in ("table", "desk") and i["interaction_type"] in ("TOUCHING", "NEAR") for i in f["interaction_graph"].get("hand_object_interactions", []))
            for f in self.history[-30:]
        ]
        if sum(table_contacts) > 10:  # Active table contact in history
            if any(p in ("PUSH", "PULL", "PLACE") for p in recent_prims[-30:]):
                return Intent.CLEAN.value

        # 4. Compound Sequence - ASSEMBLE Heuristic:
        # Both hands holding objects and bringing them together
        left_held = [i for i in ho_interactions if i["hand"] == "left" and i["interaction_type"] in ("HOLDING", "GRASPING")]
        right_held = [i for i in ho_interactions if i["hand"] == "right" and i["interaction_type"] in ("HOLDING", "GRASPING")]
        if left_held and right_held:
            return Intent.ASSEMBLE.value

        # 5. Writing / Reading / Office work
        if "keyboard" in objects_near or "laptop" in objects_near:
            if posture == "sitting":
                return Intent.TYPING.value
                
        if "cell phone" in objects_held:
            if "LIFT" in prims:
                return Intent.PHONE_CALL.value
            return Intent.TEXTING.value
            
        if "book" in objects_held:
            return Intent.READ.value

        # 6. Work tool heuristics
        if any(tool in objects_held for tool in ["scissors", "knife", "toothbrush"]):
            return Intent.USE_TOOL.value

        # 7. Movement / Posture intentions
        if posture == "sitting" and not objects_held:
            return Intent.SIT.value
        if posture == "standing" and not objects_held:
            if "WALK" in prims:
                return Intent.WALK.value
            return Intent.STAND.value

        # 8. General primitive fallbacks
        if "GRASP" in prims:
            return Intent.PICK_UP.value
        if "PLACE" in prims:
            return Intent.PUT_DOWN.value

        return Intent.IDLE.value

