"""
Integration tests for the database dataset builder/persistence layer.
"""
import json
import pytest
from datetime import datetime
from backend.models.database import MotionSession, MotionFrame


@pytest.mark.integration
class TestDatasetBuilderIntegration:
    """Verifies that SQLite session and frame persistence functions work transactionally."""

    def test_session_lifecycle(self, db_session):
        """Should insert, read, update, and delete a MotionSession."""
        # 1. Create a session
        session = MotionSession(
            id="sess_lifecycle",
            name="Lifecycle Test Session",
            source_type="upload",
            fps=30.0,
            frame_count=0,
            duration_s=0.0,
            action_label="gesture",
            avg_confidence=0.9,
            created_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # 2. Retrieve session
        retrieved = db_session.query(MotionSession).filter_by(id="sess_lifecycle").first()
        assert retrieved is not None
        assert retrieved.name == "Lifecycle Test Session"
        assert retrieved.fps == 30.0
        assert retrieved.frame_count == 0

        # 3. Update session
        retrieved.frame_count = 100
        retrieved.duration_s = 3.33
        db_session.commit()

        updated = db_session.query(MotionSession).filter_by(id="sess_lifecycle").first()
        assert updated.frame_count == 100
        assert updated.duration_s == 3.33

        # 4. Delete session
        db_session.delete(updated)
        db_session.commit()

        deleted = db_session.query(MotionSession).filter_by(id="sess_lifecycle").first()
        assert deleted is None

    def test_session_frame_relations(self, db_session):
        """Should persist frames linked to session and verify cascade delete."""
        # 1. Add session
        session = MotionSession(
            id="sess_rel",
            name="Relationship Session",
            source_type="live",
            fps=30.0,
            frame_count=2,
            duration_s=0.066,
            action_label="sign",
            avg_confidence=0.95,
            created_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # 2. Add frames linked to session
        frame1 = MotionFrame(
            id="f1_rel",
            session_id="sess_rel",
            frame_idx=0,
            timestamp_ms=0.0,
            perception_json=json.dumps({"pose_33": [{"x": 0.1, "y": 0.2}]}),
            kinematics_json=json.dumps({"euler_deg": {"Hips": [0, 10, 0]}}),
            confidence_mean=0.94
        )
        frame2 = MotionFrame(
            id="f2_rel",
            session_id="sess_rel",
            frame_idx=1,
            timestamp_ms=33.3,
            perception_json=json.dumps({"pose_33": [{"x": 0.12, "y": 0.22}]}),
            kinematics_json=json.dumps({"euler_deg": {"Hips": [0, 12, 0]}}),
            confidence_mean=0.96
        )
        db_session.add(frame1)
        db_session.add(frame2)
        db_session.commit()

        # 3. Verify relations
        sess_db = db_session.query(MotionSession).filter_by(id="sess_rel").first()
        assert sess_db is not None
        assert len(sess_db.frames) == 2
        
        # Verify JSON decoding
        f1_db = db_session.query(MotionFrame).filter_by(id="f1_rel").first()
        perception = json.loads(f1_db.perception_json)
        assert perception["pose_33"][0]["x"] == 0.1
        
        # 4. Verify cascade deletion
        db_session.delete(sess_db)
        db_session.commit()

        # Frames should be cascade-deleted
        frames_db = db_session.query(MotionFrame).filter_by(session_id="sess_rel").all()
        assert len(frames_db) == 0
