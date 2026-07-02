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

    def test_pour_intent_sequence(self):
        """cup held + POUR target near + LIFT primitive + POUR attention = POUR."""
        clf = IntentClassifier()
        # Feed 10 frames to build history
        for i in range(10):
            graph = make_interaction_graph(objects_held=["cup"], objects_near=["bowl"], attention="table")
            result = clf.classify(
                interaction_graph=graph,
                primitives=[{"primitive": "LIFT", "confidence": 0.9}]
            )
        assert result == Intent.POUR.value

    def test_clean_intent_sequence(self):
        """Table contact + repetitive PUSH/PULL primitives = CLEAN."""
        clf = IntentClassifier()
        # Feed 15 frames of table contacts
        for i in range(15):
            graph = make_interaction_graph(objects_near=["table"], posture="standing")
            # Set the hand contact explicitly to TOUCHING
            graph["hand_object_interactions"][0]["interaction_type"] = "TOUCHING"
            result = clf.classify(
                interaction_graph=graph,
                primitives=[{"primitive": "PUSH", "confidence": 0.8}]
            )
        assert result == Intent.CLEAN.value

    def test_assemble_intent_sequence(self):
        """Holding items in both hands = ASSEMBLE."""
        clf = IntentClassifier()
        # Create graph with both hands holding something
        graph = {
            "hand_object_interactions": [
                {
                    "hand": "left",
                    "object_id": 1,
                    "object_class": "block",
                    "interaction_type": "HOLDING",
                },
                {
                    "hand": "right",
                    "object_id": 2,
                    "object_class": "box",
                    "interaction_type": "HOLDING",
                }
            ],
            "person_posture": "standing",
            "attention_target": "scene",
        }
        result = clf.classify(interaction_graph=graph, primitives=[])
        assert result == Intent.ASSEMBLE.value

