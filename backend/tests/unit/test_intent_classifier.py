"""
Unit tests for intent classifier.
"""
import pytest
from backend.services.motion_intelligence.intent_classifier import (
    IntentClassifier, Intent
)


def make_interaction_graph(objects_held=None, objects_near=None, posture="standing", attention="scene"):
    return {
        "hand_object_interactions": [
            {
                "hand": "right",
                "object_id": 1,
                "object_class": obj,
                "interaction_type": "HOLDING",
                "distance_px": 20,
                "hand_gesture": "FIST",
                "confidence": 0.9,
            } for obj in (objects_held or [])
        ] + [
            {
                "hand": "right",
                "object_id": 2,
                "object_class": obj,
                "interaction_type": "NEAR",
                "distance_px": 50,
                "hand_gesture": "OPEN_PALM",
                "confidence": 0.9,
            } for obj in (objects_near or [])
        ],
        "person_posture": posture,
        "attention_target": attention,
    }


@pytest.mark.unit
class TestIntentClassifier:
    """Tests for intent classification."""
    
    def test_idle_when_no_interactions(self):
        """No interactions, standing = IDLE or STAND."""
        clf = IntentClassifier()
        result = clf.classify(
            interaction_graph=make_interaction_graph(),
            primitives=[]
        )
        assert result in [
            Intent.IDLE.value, Intent.STAND.value, Intent.STAND
        ]
    
    def test_drink_intent(self):
        """Cup near top of frame + held = DRINK."""
        clf = IntentClassifier()
        graph = make_interaction_graph(objects_held=["cup"], attention="cup")
        result = clf.classify(
            interaction_graph=graph,
            primitives=[{"primitive": "LIFT", "confidence": 0.9}]
        )
        assert result == Intent.DRINK.value
    
    def test_typing_intent(self):
        """Keyboard near + sitting posture = TYPING."""
        clf = IntentClassifier()
        graph = make_interaction_graph(objects_near=["keyboard"], posture="sitting")
        result = clf.classify(
            interaction_graph=graph,
            primitives=[]
        )
        assert result == Intent.TYPING.value
    
    def test_phone_call_intent(self):
        """phone held + LIFT = PHONE_CALL."""
        clf = IntentClassifier()
        graph = make_interaction_graph(objects_held=["cell phone"])
        result = clf.classify(
            interaction_graph=graph,
            primitives=[{"primitive": "LIFT", "confidence": 0.9}]
        )
        assert result == Intent.PHONE_CALL.value
