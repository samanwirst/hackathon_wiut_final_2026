"""Integration tests for M1 defect fixes M1-003/004/005.

All use clearly-disclosed test-only stub detectors (not real inference).
"""

import threading
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import pipeline
from app.db import VideoSource, get_session
from app.main import app
from visionflow_vision.detector import BaseDetectorTracker
from visionflow_vision.events import TrackedObject


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def video_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "fix.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (320, 240))
    for _ in range(60):  # 2 seconds @30fps -> 10 sampled frames @5fps
        writer.write(np.full((240, 320, 3), 40, dtype=np.uint8))
    writer.release()
    return path


def _upload(client, video_path, name):
    with open(video_path, "rb") as f:
        r = client.post("/api/sources/upload", files={"file": (name, f, "video/mp4")})
    assert r.status_code == 201, r.text
    return r.json()


def _right_half_zone(client, source_id):
    return client.post(
        "/api/zones",
        json={
            "source_id": source_id,
            "name": "bay",
            "polygon": [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]],
        },
    ).json()


def _enter_workflow(client, source_id, zone_id):
    wf = client.post(
        "/api/workflows",
        json={
            "name": "car enter",
            "source_id": source_id,
            "object_class": "car",
            "trigger": {"type": "object_entered_zone", "zone_id": zone_id},
            "action": {"type": "create_notification", "config": {"title": "bay"}},
            "cooldown_seconds": 1,
        },
    ).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    return wf


def _wait_status(client, source_id, target=("processed", "failed"), timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/sources/{source_id}").json()["status"]
        if status in target:
            return status
        time.sleep(0.1)
    return client.get(f"/api/sources/{source_id}").json()["status"]


def _use_detector(det):
    pipeline.detector_factory = lambda: det
    pipeline._detector = None


def _reset_detector():
    pipeline.detector_factory = None
    pipeline._detector = None


# -------------------------------------------------------------- M1-003


class GatedCarDetector(BaseDetectorTracker):
    """Blocks on the first frame so the test can disable mid-run, then always
    reports one car inside the right-half zone."""

    def __init__(self):
        self.last_inference_ms = 0.1
        self.reached = threading.Event()
        self.release = threading.Event()
        self._first = True

    def reset(self):
        self._first = True

    def track_frame(self, frame, timestamp):
        if self._first:
            self._first = False
            self.reached.set()
            self.release.wait(timeout=10)
        h, w = frame.shape[:2]
        cx = 0.8 * w
        return [TrackedObject(1, "car", 0.95, cx - 10, 100, cx + 10, 140)]


def test_disable_during_processing_revokes_actions(client, video_path):
    det = GatedCarDetector()
    _use_detector(det)
    try:
        source = _upload(client, video_path, "m1003.mp4")
        zone = _right_half_zone(client, source["id"])
        wf = _enter_workflow(client, source["id"], zone["id"])

        assert client.post(f"/api/sources/{source['id']}/process").status_code == 202
        assert det.reached.wait(timeout=10), "worker never reached the detector"

        # Disable while the worker is paused before its first result.
        r = client.post(f"/api/workflows/{wf['id']}/disable")
        assert r.status_code == 200 and r.json()["enabled"] is False

        det.release.set()
        assert _wait_status(client, source["id"]) == "processed"

        events = client.get("/api/events", params={"source_id": source["id"]}).json()
        assert events == [], f"disabled workflow still produced events: {events}"
    finally:
        det.release.set()
        _reset_detector()


# -------------------------------------------------------------- M1-004


class SerialProbeDetector(BaseDetectorTracker):
    """Shared across sources; records reset/track ordering and blocks on the
    first track call so the test can prove sessions are serialized, not
    interleaved. Reports no objects (ordering is what matters here)."""

    def __init__(self):
        self.last_inference_ms = 0.1
        self.log: list[str] = []
        self._lock = threading.Lock()
        self.reached = threading.Event()
        self.release = threading.Event()
        self._block_next = True

    def reset(self):
        with self._lock:
            self.log.append("reset")

    def track_frame(self, frame, timestamp):
        with self._lock:
            self.log.append("t")
            first = self._block_next
            if first:
                self._block_next = False
        if first:
            self.reached.set()
            self.release.wait(timeout=10)
        return []


def test_concurrent_sources_are_serialized(client, video_path):
    det = SerialProbeDetector()
    _use_detector(det)
    try:
        a = _upload(client, video_path, "m1004a.mp4")
        b = _upload(client, video_path, "m1004b.mp4")

        assert client.post(f"/api/sources/{a['id']}/process").status_code == 202
        assert det.reached.wait(timeout=10), "source A never reached the detector"

        # Source A holds the session lock (paused in track_frame). Start B.
        assert client.post(f"/api/sources/{b['id']}/process").status_code == 202

        # Give B a chance to (incorrectly) reset the shared detector.
        time.sleep(0.5)
        assert det.log.count("reset") == 1, (
            f"B reset the shared tracker while A was active: {det.log}"
        )

        det.release.set()
        assert _wait_status(client, a["id"]) == "processed"
        assert _wait_status(client, b["id"]) == "processed"

        # Exactly two resets total, one per isolated session.
        assert det.log.count("reset") == 2, det.log
    finally:
        det.release.set()
        _reset_detector()


# -------------------------------------------------------------- M1-005


class NoopDetector(BaseDetectorTracker):
    def __init__(self):
        self.last_inference_ms = 0.1

    def reset(self):
        pass

    def track_frame(self, frame, timestamp):
        return []


def test_interrupted_processing_recovered_and_retryable(client, video_path):
    det = NoopDetector()
    _use_detector(det)
    try:
        source = _upload(client, video_path, "m1005.mp4")

        # Simulate an interrupted run: a persisted 'processing' row, no worker.
        session = get_session()
        try:
            row = session.get(VideoSource, source["id"])
            row.status = "processing"
            session.commit()
        finally:
            session.close()

        # Startup recovery (as runs on restart).
        recovered = pipeline.recover_interrupted_sources()
        assert recovered >= 1

        got = client.get(f"/api/sources/{source['id']}").json()
        assert got["status"] == "failed"
        assert "interrupt" in (got["error"] or "").lower()

        # Retry is now permitted (not 409).
        assert client.post(f"/api/sources/{source['id']}/process").status_code == 202
        assert _wait_status(client, source["id"]) == "processed"
    finally:
        _reset_detector()
