"""Pre-recorded VIDEO inference pipeline (OWNER PIVOT).

The public demo ingests an uploaded MP4 rather than a live camera stream. A room
owner uploads a clip (bounded, decode-validated, stored at an opaque path); a
per-room background job then decodes it frame-by-frame, runs the SAME real YOLO
detector + tracker and the SAME temporal ``ZoneEventEngine`` as the live worker,
and publishes annotated frames, events, evidence and local notifications.

Temporal CLOCK: the dwell/cooldown timeline uses the SOURCE video clock
(frame_index / fps), never processing wall-time, so a 1.25s dwell means 1.25s of
footage regardless of how fast or slow the CPU decodes it. Wall latency is
measured separately and never presented as "real-time".

A fresh detector/tracker and fresh engines are built for every job, so a rerun
(different request on the same video, or re-enable) starts from a clean state. A
version guard drops any event whose task version was replaced/disabled while the
job was running, so stale work can never publish after an acknowledged control.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from app.live import config, rooms, worker

logger = logging.getLogger("visionflow.live.video")

_jobs: dict[str, "VideoJob"] = {}
_jobs_lock = threading.Lock()


class VideoError(ValueError):
    """Raised for an unusable / out-of-bounds uploaded clip (cleanly rejected)."""


def probe(path: Path) -> dict:
    """Decode-validate an uploaded clip and return its real properties, or raise
    VideoError. Enforces fps / frame-count / dimension / duration bounds against
    the ACTUAL decoded stream — declared container metadata is never trusted to
    bypass a bound, and at least one frame must genuinely decode."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise VideoError("file is not a decodable video")
        ok, frame = cap.read()
        if not ok or frame is None:
            raise VideoError("no decodable frames in video")
        h, w = frame.shape[:2]
        long_edge = max(w, h)
        if long_edge > config.MAX_VIDEO_LONG_EDGE or min(w, h) < config.MIN_VIDEO_LONG_EDGE:
            raise VideoError(f"frame dimensions {w}x{h} out of bounds")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if not (config.MIN_VIDEO_FPS <= fps <= config.MAX_VIDEO_FPS):
            # Fall back to a safe default when the container lies about fps, so the
            # video clock still advances; clamp into the allowed band.
            fps = max(config.MIN_VIDEO_FPS, min(config.MAX_VIDEO_FPS, 25.0))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count <= 0:
            # Count by scanning (bounded) when the container omits the count.
            frame_count = 1
            while frame_count <= config.MAX_VIDEO_FRAMES and cap.grab():
                frame_count += 1
        if frame_count > config.MAX_VIDEO_FRAMES:
            raise VideoError(f"too many frames ({frame_count} > {config.MAX_VIDEO_FRAMES})")
        duration = frame_count / fps if fps else 0.0
        if duration > config.MAX_VIDEO_DURATION_SECONDS:
            raise VideoError(f"duration {duration:.1f}s exceeds limit")
        return {
            "fps": round(fps, 4), "frame_count": frame_count,
            "w": w, "h": h, "duration_seconds": round(duration, 3),
        }
    finally:
        cap.release()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_detector():
    """A FRESH detector/tracker per job (clean tracking identity on every rerun)."""
    if worker.detector_factory is not None:
        return worker.detector_factory()
    from visionflow_vision.detector import YoloByteTrackDetector
    import app.config as app_config

    return YoloByteTrackDetector(
        model_name=app_config.DETECTOR_MODEL,
        confidence=app_config.DETECTOR_CONFIDENCE,
        device=app_config.DETECTOR_DEVICE,
    )


def _model_identity(detector) -> str:
    name = getattr(detector, "model_name", None) or type(detector).__name__
    return str(name)


class VideoJob:
    def __init__(self, room: rooms.RoomState, version: int):
        self.room = room
        self.version = version
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"video-{room.room_id}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def cancel(self) -> None:
        self.stop.set()

    def _run(self) -> None:
        room = self.room
        path = room.video_path
        if path is None or not path.exists():
            self._fail("source video missing")
            return
        detector = _make_detector()
        model_id = _model_identity(detector)
        source_sha = room.video_sha256 or ""
        fps = float(room.video_meta.get("fps") or 25.0)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            self._fail("could not open source video")
            return
        with room.lock:
            room.job_status = "running"
            room.job_processed = 0
            room.job_total = int(room.video_meta.get("frame_count") or 0)
            room.job_error = None
            room.job_version = self.version
            room.frames_received = 0
            room.frames_inferred = 0
            room.events.clear()
            room.notifications.clear()
        idx = 0
        try:
            while not self.stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                video_ts = idx / fps if fps else float(idx)
                self._process_frame(frame, idx, video_ts, source_sha, model_id, detector)
                idx += 1
                with room.lock:
                    room.job_processed = idx
                    room.frames_received = idx
            final = "cancelled" if self.stop.is_set() else "done"
        except Exception as exc:  # noqa: BLE001 — a bad frame must not crash the server
            logger.warning("video job room=%s failed: %s", room.room_id, exc)
            final = "error"
            with room.lock:
                room.job_error = str(exc)[:200]
        finally:
            cap.release()
            with room.lock:
                if room.job_version == self.version:
                    room.job_status = final
            with _jobs_lock:
                if _jobs.get(room.room_id) is self:
                    _jobs.pop(room.room_id, None)

    def _fail(self, msg: str) -> None:
        with self.room.lock:
            self.room.job_status = "error"
            self.room.job_error = msg
        with _jobs_lock:
            if _jobs.get(self.room.room_id) is self:
                _jobs.pop(self.room.room_id, None)

    def _process_frame(self, frame, idx, video_ts, source_sha, model_id, detector) -> None:
        room = self.room
        recv_ts = time.time()
        frame_h, frame_w = frame.shape[:2]
        t0 = time.perf_counter()
        objects = detector.track_frame(frame, video_ts)
        inference_ms = (time.perf_counter() - t0) * 1000.0

        with room.lock:
            version = room.task_version
            enabled = room.task_enabled and not room.task_paused
            task = room.task
            engines = list(room.engines)
            room.latest_meta = {"w": frame_w, "h": frame_h}

        emitted = []
        if enabled and task is not None and engines and version == self.version:
            for engine in engines:
                engine.frame_w = frame_w
                engine.frame_h = frame_h
                emitted.extend(engine.update(objects, video_ts))

        annotated = worker._annotate(frame, objects, task, emitted, None)
        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with room.lock:
            room.frames_inferred += 1
            room.last_inference_ms = inference_ms
            if ok:
                room.annotated_jpeg = bytes(buf)
                room.annotated_meta = {
                    "ts": time.time(), "frame_index": idx,
                    "video_ts": round(video_ts, 3), "object_count": len(objects),
                }
            cur_version = room.task_version
            cur_enabled = room.task_enabled and not room.task_paused

        if not emitted:
            return
        # Version/generation guard: a task replaced/disabled during this frame (or a
        # job superseded by a newer rerun) must not publish events/evidence.
        if cur_version != version or not cur_enabled or self.version != cur_version:
            return
        for ev in emitted:
            self._handle_event(ev, frame, objects, task, version, idx, video_ts,
                               recv_ts, inference_ms, source_sha, model_id)

    def _handle_event(self, ev, frame, objects, task, version, idx, video_ts,
                      recv_ts, inference_ms, source_sha, model_id) -> None:
        room = self.room
        # Frame-provenance hash over the RAW decoded frame bytes (not annotated).
        ok, raw = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        frame_hash = hashlib.sha256(bytes(raw)).hexdigest() if ok else None
        now = time.time()
        evidence_file = self._save_evidence(frame, objects, task, ev, version, idx)
        provenance = {
            "source_sha256": source_sha,
            "frame_index": idx,
            "video_ts_seconds": round(video_ts, 3),
            "source_fps": room.video_meta.get("fps"),
            "recv_ts": recv_ts,
            "processing_ts": now,
            "processing_latency_ms": round(inference_ms, 2),
            "frame_sha256": frame_hash,
            "detector_model": model_id,
            "workflow_version": version,
        }
        with room.lock:
            # Re-check the generation under lock before committing.
            if (room.task_version != version
                    or not (room.task_enabled and not room.task_paused)
                    or self.version != room.task_version):
                return
            eid = room.next_event_id()
            live_ev = rooms.LiveEvent(
                id=eid, type=ev.type.value, class_name=ev.class_name, track_id=ev.track_id,
                detail=ev.detail, confidence=ev.confidence,
                capture_ts=round(video_ts, 3), recv_ts=recv_ts, event_ts=now,
                task_version=version, evidence_file=evidence_file,
                visual_observation=None, action_status="done", provenance=provenance,
            )
            room.events.append(live_ev)
            title = (task.get("name") or "VisionFlow") if task else "VisionFlow"
            room.notifications.append({
                "id": eid, "event_id": eid, "title": title[:120],
                "message": ev.detail, "created_at": now,
                "video_ts_seconds": round(video_ts, 3),
            })
        logger.info("room %s video event %s @frame %s (t=%.3fs): %s",
                    room.room_id, eid, idx, video_ts, ev.detail)

    def _save_evidence(self, frame, objects, task, ev, version, idx) -> str | None:
        annotated = worker._annotate(frame, objects, task, [ev], ev.track_id)
        rooms.LIVE_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"room_{self.room.room_id}_ev{version}_f{idx}_{int(time.time()*1000)}.jpg"
        path = rooms.LIVE_EVIDENCE_DIR / fname
        if not cv2.imwrite(str(path), annotated):
            logger.warning("failed to write live evidence %s", path)
            return None
        self.room.record_evidence(path)
        return fname


def start_job(room: rooms.RoomState) -> None:
    """Cancel any running job for this room and start a FRESH one from frame 0 for
    the room's current task version (fresh detector/tracker/engine state)."""
    with _jobs_lock:
        old = _jobs.get(room.room_id)
        if old is not None:
            old.cancel()
        running = sum(1 for j in _jobs.values() if j is not old and not j.stop.is_set())
        if running >= config.MAX_CONCURRENT_VIDEO_JOBS:
            raise RuntimeError("video job capacity reached")
        with room.lock:
            version = room.task_version
        job = VideoJob(room, version)
        _jobs[room.room_id] = job
    job.start()


def cancel_job(room_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(room_id)
    if job is not None:
        job.cancel()


def job_running(room_id: str) -> bool:
    with _jobs_lock:
        job = _jobs.get(room_id)
    return bool(job and not job.stop.is_set() and job.thread.is_alive())


def _reset_for_tests() -> None:
    with _jobs_lock:
        for job in _jobs.values():
            job.cancel()
        _jobs.clear()
