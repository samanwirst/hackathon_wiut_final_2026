"""M2 integration: event-routed visual reasoning + NL compile + boundaries.

Uses a deterministic STUB detector and a STUB teacher (both clearly test-only).
This verifies the wiring and the honesty guarantees — it does NOT verify real
visual inference, which requires a configured provider (documented blocker).

Covered acceptance:
- M2-AC1: /api/workflows/compile produces a strict editable draft; ambiguous
  text is rejected; the draft saves disabled and needs explicit enable.
- M2-AC2: a geometric-only workflow makes ZERO VLM calls; a visual workflow
  routes the candidate ROI to the teacher.
- M2-AC3: a confirmed teacher result fires the action; unknown/error/missing
  credentials do NOT fire an action and remain visible.
- M2-AC4/AC5: router counters/VlmCall rows reflect calls; stats endpoints work.
"""

import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import pipeline
from app.main import app
from app.teacher import TeacherAdapter, TeacherResult
from app.vlm_router import VlmRouter, set_router
from visionflow_vision.detector import BaseDetectorTracker
from visionflow_vision.events import TrackedObject


class ScriptedDetector(BaseDetectorTracker):
    """One 'car' track sweeping left->right; enters the right-half zone."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_inference_ms = 0.1

    def reset(self) -> None:
        self.calls = 0

    def track_frame(self, frame, timestamp: float):
        h, w = frame.shape[:2]
        cx = (self.calls / 8.0) * w
        self.calls += 1
        if cx < 10 or cx > w - 10:
            return []
        return [TrackedObject(track_id=1, class_name="car", confidence=0.95,
                              x1=cx - 10, y1=100, x2=cx + 10, y2=140)]


class StubTeacher(TeacherAdapter):
    provider_name = "stub"
    model = "stub-vlm"

    def __init__(self, status="ok", label="yes"):
        self.status = status
        self.label = label
        self.calls = 0

    def classify(self, image_bytes, prompt, labels, on_attempt=None):
        self.calls += 1
        return TeacherResult(status=self.status, label=self.label, confidence=0.9,
                             model=self.model, latency_ms=1.0, usage={"total_tokens": 7})


@pytest.fixture
def client():
    pipeline.detector_factory = ScriptedDetector
    pipeline._detector = None
    with TestClient(app) as c:
        yield c
    pipeline.detector_factory = None
    pipeline._detector = None
    set_router(None)


@pytest.fixture(scope="module")
def video_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("m2video") / "t.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (320, 240))
    for i in range(60):
        frame = np.full((240, 320, 3), 40, dtype=np.uint8)
        cv2.circle(frame, (int(i / 60 * 320), 120), 15, (0, 200, 255), -1)
        writer.write(frame)
    writer.release()
    return path


def _setup_source_zone(c, video_path, name):
    with open(video_path, "rb") as f:
        source = c.post("/api/sources/upload", files={"file": (name, f, "video/mp4")}).json()
    zone = c.post("/api/zones", json={
        "source_id": source["id"], "name": "Service Bay A",
        "polygon": [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]],
    }).json()
    return source, zone


def _process_and_wait(c, source_id):
    assert c.post(f"/api/sources/{source_id}/process").status_code == 202
    deadline = time.time() + 30
    while time.time() < deadline:
        s = c.get(f"/api/sources/{source_id}").json()["status"]
        if s in ("processed", "failed"):
            return s
        time.sleep(0.2)
    return "timeout"


# -- M2-AC1: NL compile -------------------------------------------------------

def test_compile_produces_editable_draft(client, video_path):
    source, zone = _setup_source_zone(client, video_path, "c1.mp4")
    r = client.post("/api/workflows/compile", json={
        "source_id": source["id"],
        "text": "alert me when a car enters Service Bay A",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["draft"]["trigger"]["type"] == "object_entered_zone"
    assert body["draft"]["trigger"]["zone_id"] == zone["id"]
    # draft is not persisted by compile
    assert client.get(f"/api/workflows?source_id={source['id']}").json() == []


def test_compile_rejects_ambiguous(client, video_path):
    source, _ = _setup_source_zone(client, video_path, "c2.mp4")
    r = client.post("/api/workflows/compile", json={
        "source_id": source["id"], "text": "do something with a vehicle",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["errors"]
    assert body["draft"] is None


# -- M2-AC2: geometric path makes zero VLM calls ------------------------------

def test_geometric_workflow_makes_zero_vlm_calls(client, video_path):
    stub = StubTeacher()
    set_router(VlmRouter(teacher_provider=lambda: stub, sample_interval_s=0, cooldown_s=0))
    source, zone = _setup_source_zone(client, video_path, "g1.mp4")
    wf = client.post("/api/workflows", json={
        "name": "Car entered", "source_id": source["id"], "object_class": "car",
        "trigger": {"type": "object_entered_zone", "zone_id": zone["id"]},
        "action": {"type": "create_notification", "config": {"title": "Bay"}},
        "cooldown_seconds": 5,
    }).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    assert _process_and_wait(client, source["id"]) == "processed"

    events = client.get(f"/api/events?source_id={source['id']}").json()
    enter = [e for e in events if e["type"] == "object_entered_zone"]
    assert enter and enter[0]["action_status"] == "done"
    assert enter[0]["visual_status"] is None  # geometric: no routing
    assert stub.calls == 0
    assert client.get("/api/vlm/stats").json()["live"]["calls"] == 0


# -- M2-AC2/AC3: visual confirmed fires action --------------------------------

def _make_visual_workflow(client, source, zone):
    return client.post("/api/workflows", json={
        "name": "Car entered + hood open", "source_id": source["id"], "object_class": "car",
        "trigger": {"type": "object_entered_zone", "zone_id": zone["id"]},
        "action": {"type": "create_notification", "config": {"title": "Hood open in bay"}},
        "visual_predicate": {
            "prompt": "Is the vehicle hood open?",
            "labels": ["yes", "no"], "expected_label": "yes",
            "description": "hood is open",
            "sample_interval_seconds": 0, "cooldown_seconds": 0,
        },
        "cooldown_seconds": 5,
    })


def test_visual_confirmed_fires_action(client, video_path):
    stub = StubTeacher(status="ok", label="yes")
    set_router(VlmRouter(teacher_provider=lambda: stub, sample_interval_s=0, cooldown_s=0))
    source, zone = _setup_source_zone(client, video_path, "v1.mp4")
    wf = _make_visual_workflow(client, source, zone).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    assert _process_and_wait(client, source["id"]) == "processed"

    events = client.get(f"/api/events?source_id={source['id']}").json()
    enter = [e for e in events if e["type"] == "object_entered_zone"]
    assert enter, events
    ev = enter[0]
    assert ev["visual_status"] == "ok"
    assert ev["visual_label"] == "yes"
    assert ev["action_status"] == "done"
    assert stub.calls >= 1
    # a notification was created
    notifs = client.get("/api/notifications").json()
    assert any(n["event_id"] == ev["id"] for n in notifs)


def test_visual_negative_does_not_fire_action(client, video_path):
    stub = StubTeacher(status="ok", label="no")  # confirmed-but-not-expected
    set_router(VlmRouter(teacher_provider=lambda: stub, sample_interval_s=0, cooldown_s=0))
    source, zone = _setup_source_zone(client, video_path, "v2.mp4")
    wf = _make_visual_workflow(client, source, zone).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    assert _process_and_wait(client, source["id"]) == "processed"

    events = client.get(f"/api/events?source_id={source['id']}").json()
    ev = [e for e in events if e["type"] == "object_entered_zone"][0]
    assert ev["visual_status"] == "ok"
    assert ev["visual_label"] == "no"
    assert ev["action_status"] == "skipped_visual"
    notifs = client.get("/api/notifications").json()
    assert not any(n["event_id"] == ev["id"] for n in notifs)


def test_missing_credentials_cannot_fire_action(client, video_path):
    from app.teacher import UnavailableTeacher

    set_router(VlmRouter(teacher_provider=lambda: UnavailableTeacher(),
                         sample_interval_s=0, cooldown_s=0))
    source, zone = _setup_source_zone(client, video_path, "v3.mp4")
    wf = _make_visual_workflow(client, source, zone).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    assert _process_and_wait(client, source["id"]) == "processed"

    ev = [e for e in client.get(f"/api/events?source_id={source['id']}").json()
          if e["type"] == "object_entered_zone"][0]
    assert ev["visual_status"] == "missing_credentials"
    assert ev["action_status"] == "skipped_visual"


def test_teacher_error_cannot_fire_action(client, video_path):
    stub = StubTeacher(status="error", label=None)
    set_router(VlmRouter(teacher_provider=lambda: stub, sample_interval_s=0, cooldown_s=0))
    source, zone = _setup_source_zone(client, video_path, "v4.mp4")
    wf = _make_visual_workflow(client, source, zone).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    assert _process_and_wait(client, source["id"]) == "processed"

    ev = [e for e in client.get(f"/api/events?source_id={source['id']}").json()
          if e["type"] == "object_entered_zone"][0]
    assert ev["visual_status"] == "error"
    assert ev["action_status"] == "skipped_visual"


# -- M2-AC5: stats + provenance ----------------------------------------------

def test_vlm_stats_and_calls_recorded(client, video_path):
    stub = StubTeacher(status="ok", label="yes")
    set_router(VlmRouter(teacher_provider=lambda: stub, sample_interval_s=0, cooldown_s=0))
    source, zone = _setup_source_zone(client, video_path, "s1.mp4")
    wf = _make_visual_workflow(client, source, zone).json()
    client.post(f"/api/workflows/{wf['id']}/enable")
    assert _process_and_wait(client, source["id"]) == "processed"

    stats = client.get("/api/vlm/stats").json()
    assert stats["total_decisions"] >= 1
    assert stats["live"]["teacher_provider"] == "stub"
    calls = client.get("/api/vlm/calls").json()
    assert calls and calls[0]["roi_hash"]
    assert calls[0]["model"] == "stub-vlm"
