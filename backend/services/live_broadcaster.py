"""
Central pub/sub hub for live perception data.
Multiple WebSocket clients can subscribe to the same live stream.
"""
import asyncio
import json
import time
from typing import Dict, Set, Optional
from dataclasses import asdict
import numpy as np

from backend.services.perception.complete_tracker import CompleteTracker, CompletePerceptionResult


class LiveBroadcaster:
    """
    Singleton broadcaster that:
    1. Owns one CompleteTracker instance
    2. Reads from webcam continuously
    3. Broadcasts result to all connected WebSocket clients
    """

    _instance: Optional['LiveBroadcaster'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _initialize(self):
        self.tracker = CompleteTracker()
        self.clients: Set[asyncio.Queue] = set()
        self.is_streaming = False
        self.stream_task: Optional[asyncio.Task] = None
        self.latest_result: Optional[CompletePerceptionResult] = None
        self.fps_counter = {"frames": 0, "last_time": time.time(), "fps": 0.0}
        self.frame_callbacks = []

    def __init__(self):
        if not self._initialized:
            self._initialize()
            self._initialized = True

    def subscribe(self) -> asyncio.Queue:
        """Add a new subscriber; returns their queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=2)  # Drop old frames if slow
        self.clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscriber."""
        self.clients.discard(q)

    def add_frame_callback(self, callback):
        """Register a callback for every processed frame (for stats/log)."""
        self.frame_callbacks.append(callback)

    async def start_streaming(self, camera_id: int = 0):
        """Start the live capture + perception loop."""
        if self.is_streaming:
            return

        import cv2
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}")

        # Set camera to 720p if possible
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.is_streaming = True
        self.stream_task = asyncio.create_task(self._stream_loop())

    async def stop_streaming(self):
        """Stop the live capture loop."""
        self.is_streaming = False
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
        if hasattr(self, 'cap'):
            self.cap.release()

    async def _stream_loop(self):
        """
        Main loop: read frame → perceive → broadcast.
        Target 30 FPS.
        """
        frame_id = 0
        loop = asyncio.get_event_loop()

        while self.is_streaming:
            loop_start = time.time()

            # Read frame in executor (OpenCV is blocking)
            ret, frame = await loop.run_in_executor(None, self.cap.read)
            if not ret:
                await asyncio.sleep(0.01)
                continue

            timestamp_ms = int(time.time() * 1000)

            # Run perception in executor (CPU-heavy)
            result = await loop.run_in_executor(
                None,
                self.tracker.process_frame,
                frame,
                frame_id,
                timestamp_ms
            )

            # Cache latest
            self.latest_result = result

            # Update FPS
            self.fps_counter["frames"] += 1
            now = time.time()
            if now - self.fps_counter["last_time"] >= 1.0:
                self.fps_counter["fps"] = self.fps_counter["frames"] / (now - self.fps_counter["last_time"])
                self.fps_counter["frames"] = 0
                self.fps_counter["last_time"] = now

            # Broadcast to all subscribers
            await self._broadcast(result)

            # Call registered callbacks (sync)
            for cb in self.frame_callbacks:
                try:
                    cb(result)
                except Exception as e:
                    print(f"Callback error: {e}")

            frame_id += 1

            # Frame rate control
            elapsed = time.time() - loop_start
            sleep_time = max(0, (1.0 / 30) - elapsed)
            await asyncio.sleep(sleep_time)

    async def _broadcast(self, result: CompletePerceptionResult):
        """Send result to all subscriber queues (non-blocking)."""
        # Convert to JSON-serializable dict
        message = self._serialize_result(result)

        # Snapshot the client set to avoid mutation during iteration
        for q in list(self.clients):
            try:
                # Non-blocking put; drop frame if queue is full (client too slow)
                q.put_nowait(message)
            except asyncio.QueueFull:
                # Remove slowest clients
                try:
                    q.get_nowait()
                    q.put_nowait(message)
                except Exception:
                    self.unsubscribe(q)

    def _serialize_result(self, result: CompletePerceptionResult) -> Dict:
        """Convert CompletePerceptionResult to JSON-safe dict."""
        return {
            "type": "frame",
            "data": {
                "frame_id": result.frame_id,
                "timestamp_ms": result.timestamp_ms,

                # Raw detection
                "pose_33": result.pose_33,
                "left_hand_21": result.left_hand_21,
                "right_hand_21": result.right_hand_21,
                "face_478": result.face_478,
                "objects": result.objects,

                # Hand analysis
                "hand_gestures": result.hand_gestures,

                # Face analysis
                "expression": result.expression,
                "expression_confidence": result.expression_confidence,
                "head_pose": result.head_pose,
                "gaze": result.gaze,

                # Interaction
                "interaction_graph": result.interaction_graph,
                "person_posture": result.person_posture,
                "attention_target": result.attention_target,

                # Action
                "action_primitives": result.action_primitives,
                "primary_action": result.primary_action,

                # Intent
                "primary_intent": result.primary_intent,
                "intent_confidence": result.intent_confidence,
                "intent_evidence": result.intent_evidence,

                # Quality
                "pose_confidence": result.pose_confidence,
                "processing_time_ms": result.processing_time_ms,
            },
            "meta": {
                "server_fps": round(self.fps_counter["fps"], 1),
                "subscriber_count": len(self.clients),
            }
        }


# Global singleton
broadcaster = LiveBroadcaster()
