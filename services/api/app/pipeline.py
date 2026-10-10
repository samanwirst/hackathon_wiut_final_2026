"""Background video-processing pipeline.

Video -> frame sampling -> YOLO detection + ByteTrack -> zone event engines
(one per enabled workflow) -> event persistence -> evidence JPEG -> action.

Runs in a daemon thread per source; one run per source at a time. All
timestamps are video time (frame_idx / fps) so results are reproducible.
"""

from __future__ import annotations

import logging
import threading

import cv2

from app import config
from app.actions import execute_action
from app.db import (
    ActionExecution,
    TrackEvent,
    VideoSource,
    Workflow,
    Zone as ZoneRow,
    get_session,
)
from visionflow_vision.detector import BaseDetectorTracker
from visionflow_vision.events import EventType, ZoneEventEngine
from visionflow_vision.zones import Zone

logger = logging.getLogger("visionflow.pipeline")

_running: set[int] = set()
_running_lock = threading.Lock()

_detector: BaseDetectorTracker | None = None
_detector_lock = threading.Lock()

# Serializes a complete processing session (detector reset + every frame call)
# so concurrent sources cannot reset or contaminate each other's shared tracker
# state. This also keeps CPU/RAM use sequential, which suits the M1 target.
_session_lock = threading.Lock()

# Tests may replace this factory to inject a deterministic stub detector.
# Production always builds the real YOLO detector.
detector_factory = None


def _get_detector() -> BaseDetectorTracker:
    global _detector
    with _detector_lock:
        if _detector is None:
            if detector_factory is not None:
                _detector = detector_factory()
            else:
                from visionflow_vision.detector import YoloByteTrackDetector

                _detector = YoloByteTrackDetector(
                    model_name=config.DETECTOR_MODEL,
                    confidence=config.DETECTOR_CONFIDENCE,
                    device=config.DETECTOR_DEVICE,
                )
        return _detector


def start_processing(source_id: int) -> bool:
    """Start processing a source in a background thread. False if already running."""
    with _running_lock:
        if source_id in _running:
            return False
        _running.add(source_id)
    thread = threading.Thread(target=_process_source, args=(source_id,), daemon=True)
    thread.start()
    return True


def is_running(source_id: int) -> bool:
    with _running_lock:
        return source_id in _running


def recover_interrupted_sources() -> int:
    """Mark sources stuck in 'processing' (from a crash/restart) as failed so
    they can be retried. Single-worker model: on startup nothing is running, so
    any persisted 'processing' row represents an interrupted run. Returns the
    number of rows recovered."""
    session = get_session()
    try:
        stale = (
            session.query(VideoSource)
            .filter(VideoSource.status == "processing")
            .all()
        )
        count = 0
        for source in stale:
            if is_running(source.id):
                continue
            source.status = "failed"
            source.error = "processing interrupted by restart; retry to reprocess"
            count += 1
        if count:
            session.commit()
            logger.info("recovered %d interrupted processing source(s)", count)
        return count
    finally:
        session.close()


def _workflow_enabled(workflow_id: int) -> bool:
    """Authoritative, fresh read of a workflow's current enabled state.

    Uses its own short-lived session so a disable committed by the API during
    an active run is observed immediately (no stale worker-session snapshot)."""
    session = get_session()
    try:
        return bool(
            session.query(Workflow.enabled)
            .filter(Workflow.id == workflow_id)
            .scalar()
        )
    finally:
        session.close()


def _build_engines(session, source: VideoSource) -> list[tuple[Workflow, ZoneEventEngine]]:
    engines: list[tuple[Workflow, ZoneEventEngine]] = []
    workflows = (
        session.query(Workflow)
        .filter(Workflow.source_id == source.id, Workflow.enabled.is_(True))
        .all()
    )
    for wf in workflows:
        dsl = wf.dsl
        zone_row = session.get(ZoneRow, dsl["trigger"]["zone_id"])
        if zone_row is None or zone_row.source_id != source.id:
            logger.warning("workflow %s references missing zone; skipping", wf.id)
            continue
        zone = Zone(
            id=zone_row.id,
            name=zone_row.name,
            polygon=tuple((float(x), float(y)) for x, y in zone_row.polygon),
        )
        engine = ZoneEventEngine(
            zone=zone,
            object_class=dsl["object_class"],
            event_type=EventType(dsl["trigger"]["type"]),
            frame_w=source.width or 1,
            frame_h=source.height or 1,
            dwell_seconds=dsl["trigger"].get("duration_seconds") or 0.0,
            count_threshold=dsl["trigger"].get("threshold") or 0,
            cooldown_seconds=dsl.get("cooldown_seconds", 10.0),
            rule_key=f"src{source.id}-wf{wf.id}",
        )
        engines.append((wf, engine))
    return engines


def _save_evidence(frame, objects, zone: Zone, event, frame_w: int, frame_h: int) -> str:
    """Draw zone + boxes on the frame and save a JPEG. Returns relative path."""
    img = frame.copy()
    import numpy as np

    pts = np.array(
        [[int(x * frame_w), int(y * frame_h)] for x, y in zone.polygon], dtype=np.int32
    )
    cv2.polylines(img, [pts], isClosed=True, color=(0, 200, 255), thickness=2)
    for obj in objects:
        color = (0, 0, 255) if obj.track_id == event.track_id else (0, 255, 0)
        cv2.rectangle(img, (int(obj.x1), int(obj.y1)), (int(obj.x2), int(obj.y2)), color, 2)
        cv2.putText(
            img,
            f"{obj.class_name} #{obj.track_id}",
            (int(obj.x1), max(15, int(obj.y1) - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )
    cv2.putText(
        img, event.detail[:80], (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    fname = f"event_{event.dedupe_key.replace(':', '_').replace('/', '_')}.jpg"
    out_path = config.EVIDENCE_DIR / fname
    # cv2.imwrite returns False (never raises) on an unwritable/full destination.
    # Surface it so we never publish an evidence URL that 404s (M1-009).
    if not cv2.imwrite(str(out_path), img):
        raise RuntimeError(f"failed to write evidence image: {out_path}")
    return f"evidence/{fname}"


def _record_source_failure(session, source_id: int, message: str) -> None:
    """Mark a source failed after an exception. The worker's session may be in a
    broken/aborted transaction (e.g. SQLite rejected a bad value at commit), so
    roll it back first; if it still cannot persist, use a fresh session. This
    guarantees an interrupted run never leaves the source stuck in 'processing'
    with no visible error (M1-008)."""
    try:
        session.rollback()
    except Exception:  # noqa: BLE001
        pass
    try:
        source = session.get(VideoSource, source_id)
        if source is not None:
            source.status = "failed"
            source.error = message
            session.commit()
            return
    except Exception:  # noqa: BLE001
        logger.exception("failed to record source failure on worker session; retrying fresh")
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
    fresh = get_session()
    try:
        source = fresh.get(VideoSource, source_id)
        if source is not None:
            source.status = "failed"
            source.error = message
            fresh.commit()
    except Exception:  # noqa: BLE001
        logger.exception("could not record source failure even with a fresh session")
    finally:
        fresh.close()


def _dispatch_action(session, wf: Workflow, event: TrackEvent) -> None:
    """Run the workflow's action for one persisted event."""
    execute_action(
        session, event, wf.dsl["action"]["type"], wf.dsl["action"].get("config", {})
    )


def _resume_pending_event(session, wf: Workflow, existing: TrackEvent) -> bool:
    """If a previously committed event never had its action dispatched (e.g. the
    process was interrupted between the event commit and action dispatch),
    complete it now instead of silently skipping (M1-007).

    Returns True if the event was handled as a resume (completed or already
    complete), so the caller treats this dedupe key as done. Completed events
    (action_status != 'pending' or an existing ActionExecution row) are left
    untouched to preserve idempotent deduplication."""
    has_execution = (
        session.query(ActionExecution.id)
        .filter(ActionExecution.event_id == existing.id)
        .first()
        is not None
    )
    if existing.action_status != "pending" or has_execution:
        return True  # already dispatched; keep dedupe, do not re-run
    logger.info("resuming undispatched action for event %s", existing.id)
    _dispatch_action(session, wf, existing)
    return True


def _process_source(source_id: int) -> None:
    session = get_session()
    session_locked = False
    try:
        source = session.get(VideoSource, source_id)
        if source is None:
            return
        source.status = "processing"
        source.frames_processed = 0
        source.error = None
        session.commit()

        cap = cv2.VideoCapture(source.path)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video: {source.path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if fps <= 0:
            fps = 30.0
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or None
        source.fps, source.width, source.height, source.frame_count = fps, frame_w, frame_h, total
        session.commit()

        engines = _build_engines(session, source)
        if not engines:
            logger.info("source %s: no enabled workflows; detection-only pass", source_id)

        # Serialize the whole session: reset + every frame call must be
        # isolated from any other source so tracker identities cannot be
        # contaminated by a concurrent reset (M1-004).
        _session_lock.acquire()
        session_locked = True
        detector = _get_detector()
        detector.reset()

        step = max(1, round(fps / config.PROCESS_FPS))
        frame_idx = 0
        processed = 0
        inference_ms_total = 0.0

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step != 0:
                frame_idx += 1
                continue
            timestamp = frame_idx / fps
            objects = detector.track_frame(frame, timestamp)
            inference_ms_total += getattr(detector, "last_inference_ms", 0.0)
            processed += 1

            for wf, engine in engines:
                # Advance the engine exactly once per frame to keep debounce /
                # cooldown state consistent.
                emitted = engine.update(objects, timestamp)
                for ev in emitted:
                    # Re-check authoritative enabled state before EACH event so a
                    # disable committed by the API mid-frame (e.g. between two
                    # events emitted on the same frame) revokes the remaining
                    # events and actions (M1-003).
                    if not _workflow_enabled(wf.id):
                        break
                    existing = (
                        session.query(TrackEvent)
                        .filter(TrackEvent.dedupe_key == ev.dedupe_key)
                        .first()
                    )
                    if existing is not None:
                        _resume_pending_event(session, wf, existing)
                        continue
                    row = TrackEvent(
                        source_id=source.id,
                        workflow_id=wf.id,
                        track_id=ev.track_id,
                        type=ev.type.value,
                        class_name=ev.class_name,
                        video_timestamp=ev.timestamp,
                        confidence=ev.confidence,
                        detail=ev.detail,
                        dedupe_key=ev.dedupe_key,
                    )
                    session.add(row)
                    session.flush()
                    # Evidence must be written before we commit the event so an
                    # unwritable destination rolls back the whole event instead
                    # of publishing a dangling evidence URL (M1-009).
                    row.evidence_path = _save_evidence(
                        frame, objects, engine.zone, row, frame_w, frame_h
                    )
                    session.commit()
                    _dispatch_action(session, wf, row)
                    logger.info("event %s: %s", row.id, ev.detail)

            if processed % 25 == 0:
                source.frames_processed = processed
                session.commit()
            frame_idx += 1

        cap.release()
        source.frames_processed = processed
        source.avg_inference_ms = inference_ms_total / processed if processed else None
        source.status = "processed"
        session.commit()
        logger.info(
            "source %s done: %d frames analyzed, avg inference %.1f ms",
            source_id, processed, source.avg_inference_ms or 0,
        )
    except Exception as exc:  # noqa: BLE001 — surface failure on the source row
        logger.exception("processing failed for source %s", source_id)
        _record_source_failure(session, source_id, str(exc)[:1000])
    finally:
        if session_locked:
            _session_lock.release()
        session.close()
        with _running_lock:
            _running.discard(source_id)
