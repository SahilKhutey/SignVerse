import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from contextlib import contextmanager
from backend.config import settings

class Database:
    """Manages local SQLite database using the new unified motion_sessions, motion_frames and action_segments tables"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(settings.dataset_dir / "signverse.db")
        import backend.models.database


    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create_session(
        self,
        session_id: str,
        source: str,
        filename: str,
        fps: float,
        frame_count: int,
        duration_sec: float,
        video_path: str = None,
    ) -> str:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO motion_sessions 
                   (id, source_type, name, fps, frame_count, duration_s, 
                    video_path, created_at, status, action_label, avg_confidence, has_metric_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    source,
                    filename,
                    fps,
                    frame_count,
                    duration_sec,
                    video_path,
                    datetime.utcnow().isoformat(),
                    "ready",
                    "unlabeled",
                    0.0,
                    0
                ),
            )
        return session_id

    def update_session_status(self, session_id: str, status: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE motion_sessions SET status = ? WHERE id = ?",
                (status, session_id),
            )

    def update_skeleton_path(self, session_id: str, path: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE motion_sessions SET skeleton_json_path = ?, kinematics_path = ? WHERE id = ?",
                (path, path, session_id),
            )

    def label_session(self, session_id: str, label: str, notes: str = ""):
        with self._conn() as conn:
            conn.execute(
                "UPDATE motion_sessions SET action_label = ?, notes = ? WHERE id = ?",
                (label, notes, session_id),
            )

    def delete_session(self, session_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM motion_sessions WHERE id = ?", (session_id,))
            conn.execute("DELETE FROM motion_frames WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM action_segments WHERE session_id = ?", (session_id,))
            return cur.rowcount > 0

    def get_session(self, session_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM motion_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_sessions(self, limit: int = 100) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM motion_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def count_sessions(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM motion_sessions").fetchone()[0]

    def stats(self) -> Dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM motion_sessions").fetchone()[0]
            total_frames = conn.execute(
                "SELECT COALESCE(SUM(frame_count), 0) FROM motion_sessions"
            ).fetchone()[0]
            total_duration = conn.execute(
                "SELECT COALESCE(SUM(duration_s), 0) FROM motion_sessions"
            ).fetchone()[0]
            labeled = conn.execute(
                "SELECT COUNT(*) FROM motion_sessions WHERE action_label != 'unlabeled'"
            ).fetchone()[0]
            by_source = conn.execute(
                "SELECT source_type, COUNT(*) as c FROM motion_sessions GROUP BY source_type"
            ).fetchall()
            
        return {
            "total_sessions": total,
            "total_frames": int(total_frames),
            "total_duration_sec": float(total_duration),
            "labeled_sessions": labeled,
            "by_source": {r["source_type"]: r["c"] for r in by_source},
        }

    def save_segments(self, session_id: str, segments: List[Dict]):
        """Persist action segments for a session."""
        with self._conn() as conn:
            conn.execute("DELETE FROM action_segments WHERE session_id = ?", (session_id,))
            for seg in segments:
                conn.execute(
                    """INSERT INTO action_segments 
                       (session_id, start_frame, end_frame, action, confidence)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        seg["start_frame"],
                        seg["end_frame"],
                        seg["action"],
                        seg["confidence"],
                    ),
                )

    def get_segments(self, session_id: str) -> List[Dict]:
        """Get action segments for a session."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM action_segments WHERE session_id = ? ORDER BY start_frame",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Translates motion_sessions table row to legacy database dictionary format."""
        d = dict(row)
        # Map back to old keys
        d["session_id"] = d.get("id")
        d["filename"] = d.get("name")
        d["source"] = d.get("source_type")
        d["duration_sec"] = d.get("duration_s")
        return d

# Singleton Instance
db = Database()
