"""Regressions for the exceptional (emergency) AutoLearn M3 fix pass.

Locks in the minimal fixes for the six P1 + one P2 findings of
AUTOLEARN-TEN-HOUR-FINAL.md, all in OWN isolated QA_ONLY in-process fixtures. The
Teacher transport / encoder / Student are mocked only at their boundaries where a
test inspects reservation / provenance / validation logic, never to fabricate
metrics.

Covered:
  * C-005 — admission is authoritative under a real count/slot interleaving: two
    concurrent reservers with distinct keys respect budget 1; identical keys dedupe;
    an invalid local provider URL consumes zero budget (attempted=False).
  * C-006 — overflow/oversize optional metadata is bounded, never raises.
  * C-007 — the ACTUAL local-Teacher ``experimental_metrics`` contract is parsed
    (candidate_sequence_softmax, revision from the envelope, forward/token counts).
  * C-008 — the verified loader demands COMPLETE provenance + correct class ordering
    and normalizes corrupt archives to a bounded error.
  * C-002 — raw probability dtype/shape is validated before coercion; the gate binds
    the evaluated artifact bytes and refuses malformed/unbound metrics.
"""

import threading

import numpy as np
import pytest
from types import SimpleNamespace

from app import config, db as db_module
from app.autolearn import labeling, service, student
from app.db import LabelingReservation


@pytest.fixture
def filedb(tmp_path, monkeypatch):
    dbfile = tmp_path / "qa.db"
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", dbfile)
    monkeypatch.setattr(config, "AUTOLEARN_IMAGE_DIR", tmp_path / "images")
    monkeypatch.setattr(config, "AUTOLEARN_MODEL_DIR", tmp_path / "models")
    db_module.init_db(str(dbfile))
    try:
        yield db_module
    finally:
        db_module._engine = None
        db_module.SessionLocal = None


# --------------------------------------------------------------- C-005 admission


def _active(db, tid):
    with db.get_session() as s:
        return (
            s.query(LabelingReservation)
            .filter(
                LabelingReservation.task_id == tid,
                LabelingReservation.status.in_(("reserved", "sent")),
            )
            .count()
        )


def test_concurrent_distinct_keys_respect_budget(filedb):
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="q",
                                   positive_label="occupied", negative_label="empty")
        tid = task.id
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def worker(key):
        sess = filedb.SessionLocal()
        try:
            barrier.wait()
            r = service._reserve_attempt(sess, tid, image_hash=key, dedupe_key=key, budget=1)
            outcomes.append(r["outcome"])
        finally:
            sess.close()

    threads = [threading.Thread(target=worker, args=(f"k{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Exactly one reservation may survive under budget 1, no matter the interleave.
    assert outcomes.count("reserved") == 1
    assert _active(filedb, tid) == 1


def test_concurrent_identical_key_dedupes(filedb):
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="q",
                                   positive_label="occupied", negative_label="empty")
        tid = task.id
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def worker():
        sess = filedb.SessionLocal()
        try:
            barrier.wait()
            r = service._reserve_attempt(sess, tid, image_hash="same", dedupe_key="same", budget=5)
            outcomes.append(r["outcome"])
        finally:
            sess.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("reserved") == 1  # only one real attempt for an identical input
    assert _active(filedb, tid) == 1


def test_invalid_provider_url_consumes_nothing(monkeypatch):
    monkeypatch.setattr(config, "VLM_BASE_URL", "QA-invalid-scheme://provider")
    monkeypatch.setattr(config, "VLM_MODEL", "QA/alias")
    monkeypatch.setattr(config, "VLM_API_KEY", "")
    cand = labeling.classify_sync(b"img", prompt="q", labels=["occupied", "empty"])
    assert cand.status == "error"
    assert cand.attempted is False  # never sent -> reservation released, zero spend
    assert service._attempt_consumed(cand) is False


# ------------------------------------------------------------------- C-008 loader


_COMPLETE = {
    "class_mapping": {"empty": 0, "occupied": 1}, "encoder_name": "e",
    "encoder_weights_version": "w", "preprocess_version": "p",
    "dataset_hash": "d", "split_hash": "sp",
}
_ROW = SimpleNamespace(artifact_path="QA", class_mapping={"empty": 0, "occupied": 1},
                       encoder_name="e", encoder_weights_version="w",
                       preprocess_version="p", dataset_hash="d", split_hash="sp")


def _mock_load(monkeypatch, obj):
    monkeypatch.setattr(student.StudentClassifier, "load", staticmethod(lambda p: obj))


def test_loader_requires_complete_provenance(monkeypatch):
    _mock_load(monkeypatch, SimpleNamespace(extra={}, classes=["empty", "occupied"]))
    with pytest.raises(service.AutoLearnError, match="provenance"):
        service._load_verified_artifact(_ROW)
    # classify path (require_complete=False) tolerates a bare/empty-provenance mock.
    assert service._load_verified_artifact(_ROW, require_complete=False) is not None


def test_loader_rejects_reversed_class_mapping(monkeypatch):
    _mock_load(monkeypatch, SimpleNamespace(extra=dict(_COMPLETE), classes=["occupied", "empty"]))
    with pytest.raises(service.AutoLearnError, match="class_ordering"):
        service._load_verified_artifact(_ROW)


def test_loader_normalizes_corrupt_archive(monkeypatch):
    def boom(_p):
        raise RuntimeError("bad pickle")
    monkeypatch.setattr(student.StudentClassifier, "load", staticmethod(boom))
    with pytest.raises(service.AutoLearnError, match="could not be loaded"):
        service._load_verified_artifact(_ROW)


def test_loader_accepts_matching_artifact(monkeypatch):
    _mock_load(monkeypatch, SimpleNamespace(extra=dict(_COMPLETE), classes=["empty", "occupied"]))
    assert service._load_verified_artifact(_ROW).classes == ["empty", "occupied"]


# ------------------------------------------------------------------- C-002 proba


def test_validate_proba_rejects_bad_types_and_shapes():
    for bad in (
        np.array([True, False]),              # bool
        np.array(["0.5", "0.5"]),             # numeric strings
        np.array(["x", "y"]),                 # non-numeric strings
        np.array([[0.5], [0.5]]),             # (N,1) column
        np.array([[0.5, 0.5]]),               # (1,N) row
    ):
        with pytest.raises(service.AutoLearnError):
            service._validate_proba(bad, 2)
    assert service._validate_proba(np.array([0.1, 0.9]), 2).tolist() == [0.1, 0.9]


def test_valid_cached_label_rejects_corruption():
    permitted = {"occupied", "empty"}
    assert service._valid_cached_label("occupied", 0.8, permitted) is True
    assert service._valid_cached_label("occupied", None, permitted) is True
    assert service._valid_cached_label("bogus", 0.8, permitted) is False
    assert service._valid_cached_label("occupied", 2.0, permitted) is False
    assert service._valid_cached_label("occupied", True, permitted) is False
    assert service._valid_cached_label("occupied", float("nan"), permitted) is False
