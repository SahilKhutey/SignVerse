import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text,
    DateTime, ForeignKey, Boolean, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from backend.config import settings

Base = declarative_base()


class MotionSession(Base):
    __tablename__ = "motion_sessions"

    id             = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name           = Column(String(255), nullable=False)
    source_type    = Column(String(50), nullable=False)
    fps            = Column(Float, nullable=False, default=30.0)
    frame_count    = Column(Integer, nullable=False, default=0)
    duration_s     = Column(Float, nullable=False, default=0.0)
    action_label   = Column(String(100), nullable=False, default="unlabeled")
    thumbnail_path = Column(String(512), nullable=True)
    kinematics_path= Column(String(512), nullable=True)
    avg_confidence = Column(Float, nullable=False, default=0.0)
    created_at     = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Compatibility columns
    notes          = Column(Text, nullable=True, default="")
    status         = Column(String(50), nullable=False, default="ready")
    video_path     = Column(String(512), nullable=True)
    skeleton_json_path = Column(String(512), nullable=True)

    # HOI metadata
    unique_objects     = Column(Text, nullable=True)   # JSON list of unique class names seen
    object_count       = Column(Integer, nullable=True, default=0)
    interaction_count  = Column(Integer, nullable=True, default=0)
    primary_object     = Column(String(100), nullable=True)   # Most-interacted object class

    # ── Metric / Depth metadata ──
    person_height_m     = Column(Float, nullable=True)   # Estimated person height (metres)
    scale_factor_mean   = Column(Float, nullable=True)   # Mean scale factor across session
    scale_factor_std    = Column(Float, nullable=True)   # Scale stability indicator
    camera_intrinsics_json = Column(Text, nullable=True) # {fx, fy, cx, cy, fov_x, fov_y}
    depth_model_used    = Column(String(100), nullable=True, default="midas_small")
    has_metric_data     = Column(Boolean, nullable=False, default=False)

    frames       = relationship("MotionFrame",                back_populates="session", cascade="all, delete-orphan")
    obj_traj     = relationship("ObjectTrajectory",           back_populates="session", cascade="all, delete-orphan")
    hoi_records  = relationship("HandObjectInteractionRecord",back_populates="session", cascade="all, delete-orphan")


class MotionFrame(Base):
    __tablename__ = "motion_frames"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id      = Column(String(36), ForeignKey("motion_sessions.id", ondelete="CASCADE"), nullable=False)
    frame_idx       = Column(Integer, nullable=False)
    timestamp_ms    = Column(Float, nullable=False)
    perception_json = Column(Text, nullable=False)   # pose, hands, face, objects (with 3D)
    kinematics_json = Column(Text, nullable=False)   # angles, quats, velocities
    confidence_mean = Column(Float, nullable=False, default=0.0)
    # ── Metric depth fields ──
    metric_json     = Column(Text, nullable=True)    # {pose_33_metric, objects_metric, scale_factor, ...}
    scale_factor    = Column(Float, nullable=True)   # m/unit conversion used this frame
    depth_confidence= Column(Float, nullable=True)   # 0–1 average depth confidence

    session = relationship("MotionSession", back_populates="frames")


class ActionSegment(Base):
    __tablename__ = "action_segments"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(String(36), ForeignKey("motion_sessions.id", ondelete="CASCADE"), nullable=False)
    start_frame = Column(Integer, nullable=False)
    end_frame   = Column(Integer, nullable=False)
    action      = Column(String(100), nullable=False)
    confidence  = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)


class ObjectTrajectory(Base):
    """
    One row = one object detection in one frame.
    Accumulates into full per-object trajectory over the session.
    """
    __tablename__ = "object_trajectories"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(String(36), ForeignKey("motion_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_id     = Column(Integer, nullable=False, index=True)
    timestamp_ms = Column(Float, nullable=False)

    # Detection identity
    track_id    = Column(Integer, nullable=False, index=True)
    class_name  = Column(String(100), nullable=False, index=True)
    class_id    = Column(Integer, nullable=True)
    confidence  = Column(Float, nullable=True)

    # 2D bounding box (pixels)
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)
    bbox_x2 = Column(Float, nullable=True)
    bbox_y2 = Column(Float, nullable=True)

    # 3D world position (metres, camera-relative)
    pos_x   = Column(Float, nullable=True)   # left/right
    pos_y   = Column(Float, nullable=True)   # up/down (Y-up)
    pos_z   = Column(Float, nullable=True)   # depth (distance from camera)
    depth_m = Column(Float, nullable=True)   # explicit depth

    # 3D velocity (metres/second)
    vel_x = Column(Float, nullable=True, default=0.0)
    vel_y = Column(Float, nullable=True, default=0.0)
    vel_z = Column(Float, nullable=True, default=0.0)

    # Age in frames (for filtering out short false positives)
    age_frames = Column(Integer, nullable=True, default=0)

    session = relationship("MotionSession", back_populates="obj_traj")


class HandObjectInteractionRecord(Base):
    """
    One row = one (hand, object) HOI pair that was active in one frame.
    """
    __tablename__ = "hand_object_interactions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(String(36), ForeignKey("motion_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_id     = Column(Integer, nullable=False, index=True)
    timestamp_ms = Column(Float, nullable=False)

    # Hand
    hand         = Column(String(10), nullable=True)   # "left" | "right"
    hand_gesture = Column(String(50), nullable=True)

    # Object
    object_track_id = Column(Integer, nullable=True, index=True)
    object_class    = Column(String(100), nullable=True, index=True)

    # Interaction
    interaction_type  = Column(String(50), nullable=True, index=True)
    confidence        = Column(Float, nullable=True)
    distance_3d       = Column(Float, nullable=True)   # metres
    distance_2d       = Column(Float, nullable=True)   # pixels
    duration_frames   = Column(Integer, nullable=True, default=1)

    # Contact point in 3D (where hand touches object)
    contact_x = Column(Float, nullable=True)
    contact_y = Column(Float, nullable=True)
    contact_z = Column(Float, nullable=True)

    # Object position at moment of interaction
    obj_pos_x = Column(Float, nullable=True)
    obj_pos_y = Column(Float, nullable=True)
    obj_pos_z = Column(Float, nullable=True)

    # Temporal span of this interaction event
    first_frame = Column(Integer, nullable=True)
    last_frame  = Column(Integer, nullable=True)

    session = relationship("MotionSession", back_populates="hoi_records")


# ── Composite indexes for fast timeline queries ───────────────────
Index("ix_obj_traj_session_track",  ObjectTrajectory.session_id, ObjectTrajectory.track_id)
Index("ix_hoi_session_frame",       HandObjectInteractionRecord.session_id, HandObjectInteractionRecord.frame_id)
Index("ix_hoi_session_type",        HandObjectInteractionRecord.session_id, HandObjectInteractionRecord.interaction_type)

# ── Engine ────────────────────────────────────────────────────────
db_path = settings.dataset_dir / "signverse.db"
engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables (including new ones; existing tables are untouched)
Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
