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
    """Classifies user intention using context heuristics."""

    def classify(self, interaction_graph: Dict, primitives: List[Dict]) -> str:
        """
        Classifies intent based on interaction state and action primitives.
        """
        posture = interaction_graph.get("person_posture", "unknown")
        attention = interaction_graph.get("attention_target", "scene")
        
        prims = [p["primitive"] for p in primitives]
        ho_interactions = interaction_graph.get("hand_object_interactions", [])
        
        objects_held = [i["object_class"] for i in ho_interactions if i["interaction_type"] in ("HOLDING", "GRASPING")]
        objects_near = [i["object_class"] for i in ho_interactions if i["interaction_type"] == "NEAR"]

        # 1. Food & Drink Heuristics
        if "cup" in objects_held or "bottle" in objects_held:
            if "LIFT" in prims or attention in ("gaze_up", "cup", "bottle"):
                return Intent.DRINK.value
            return Intent.PICK_UP.value
            
        if any(food in objects_held for food in ["banana", "apple", "sandwich", "orange"]):
            if "LIFT" in prims or attention == "scene":
                return Intent.EAT.value
            return Intent.PICK_UP.value

        # 2. Writing / Reading / Office work
        if "keyboard" in objects_near or "laptop" in objects_near:
            if posture == "sitting":
                return Intent.TYPING.value
                
        if "cell phone" in objects_held:
            if "LIFT" in prims:
                return Intent.PHONE_CALL.value
            return Intent.TEXTING.value
            
        if "book" in objects_held:
            return Intent.READ.value

        # 3. Work tool heuristics
        if any(tool in objects_held for tool in ["scissors", "knife", "toothbrush"]):
            return Intent.USE_TOOL.value

        # 4. Movement / Posture intentions
        if posture == "sitting" and not objects_held:
            return Intent.SIT.value
        if posture == "standing" and not objects_held:
            if "WALK" in prims:
                return Intent.WALK.value
            return Intent.STAND

        # 5. General primitive fallbacks
        if "GRASP" in prims:
            return Intent.PICK_UP.value
        if "PLACE" in prims:
            return Intent.PUT_DOWN.value

        return Intent.IDLE.value
