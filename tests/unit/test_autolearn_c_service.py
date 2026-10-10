"""Regression tests for the AutoLearn service fixes (C-002/C-003/C-005).

All data is QA_ONLY and in-memory. The encoder/Student are mocked ONLY where the
test inspects row-selection / budget / grouping logic (clearly disclosed); these
are boundary checks, not model-quality measurements.

  * C-002 — held-out evaluation, shadow and the gate read the version's own frozen
    membership manifest, not the mutable task-wide split; inconsistent/missing
    snapshots fail closed; the gate requires finite metrics, support equal to the
    snapshot test count, and both classes.
  * C-003 — splitting groups by physical session/source provenance regardless of
    free-form group strings; inconsistent group metadata is rejected; a
    decode/re-encode near-duplicate across groups is refused.
  * C-005 — explicit durable per-task / per-job Teacher budgets, zero charge for a
    missing provider, duplicate suppression and cached reuse.
"""

import io
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import config
from app.autolearn import dataset, labeling, service
from app.autolearn.labeling import LabelCandidate
from app.db import (
    Base,
    AutoLearnTask,
    LabelingAudit,
    ModelVersion,
    ModelVersionSample,
    TrainingSample,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s


def _jpeg(color, size=48, quality=88) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


# =============================================================== C-005 budgets


def _configured_provider(monkeypatch, calls):
    monkeypatch.setattr(labeling.config, "VLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setattr(labeling.config, "VLM_MODEL", "qa/model")
    monkeypatch.setattr(service.config, "VLM_MODEL", "qa/model")

    def fake(image_bytes, *, prompt, labels):
        calls.append(prompt)
        return LabelCandidate(
            status="labeled", label=labels[0], confidence=0.9,
            model="qa/actual", method="chat_json",
            raw={"method": "chat_json", "response_model": "qa/actual"},
        )

    monkeypatch.setattr(labeling, "classify_sync", fake)


def _import_distinct(db, task, n, session_prefix="s"):
    for i in range(n):
        service.import_image(
            db, task, image_bytes=_jpeg((10 + i * 7, 20, 30 + i)),
            session_id=f"{session_prefix}{i}",
        )


def test_missing_provider_consumes_zero_attempts(db, monkeypatch):
    monkeypatch.setattr(labeling.config, "VLM_BASE_URL", "")
    monkeypatch.setattr(labeling.config, "VLM_MODEL", "")
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    _import_distinct(db, task, 3)
    out = service.run_labeling(db, task)
    assert out["status"] == "unavailable"
    assert service._teacher_attempts_spent(db, task) == 0


def test_per_task_budget_caps_real_attempts(db, monkeypatch):
    calls: list[str] = []
    _configured_provider(monkeypatch, calls)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_BUDGET_PER_TASK", 2)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_JOB_MAX", 50)
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    _import_distinct(db, task, 5)
    out = service.run_labeling(db, task)
    assert out["attempts_made"] == 2
    assert out["suppressed_budget"] == 3
    assert len(calls) == 2
    assert service._teacher_attempts_spent(db, task) == 2
    # A second job is fully budget-suppressed (durable accounting).
    out2 = service.run_labeling(db, task)
    assert out2["attempts_made"] == 0
    assert len(calls) == 2


def test_job_max_caps_single_invocation(db, monkeypatch):
    calls: list[str] = []
    _configured_provider(monkeypatch, calls)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_BUDGET_PER_TASK", 100)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_JOB_MAX", 1)
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    _import_distinct(db, task, 4)
    out = service.run_labeling(db, task)
    assert out["attempts_made"] == 1


def test_identical_image_reuses_cached_label_zero_attempts(db, monkeypatch):
    calls: list[str] = []
    _configured_provider(monkeypatch, calls)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_BUDGET_PER_TASK", 100)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_JOB_MAX", 50)
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    img = _jpeg((40, 50, 60))
    # Same content bytes in two different sessions -> second is an exact duplicate
    # (import skips it). Use a labeled sample + a fresh pending sample with the
    # same content hash to exercise the durable cache path.
    service.import_image(db, task, image_bytes=img, session_id="a")
    service.run_labeling(db, task)  # labels the one sample (1 real call)
    assert len(calls) == 1
    # Force a second pending row with the SAME content hash (import would dedupe,
    # so insert directly as a distinct sample id to model a re-collected frame).
    first = db.query(TrainingSample).first()
    dup = TrainingSample(task_id=task.id, session_id="b", group_key="b",
                         image_path=first.image_path, image_hash=first.image_hash,
                         origin="imported")
    db.add(dup)
    db.commit()
    out = service.run_labeling(db, task)
    assert out["cached"] == 1
    assert out["attempts_made"] == 0
    assert len(calls) == 1  # no new provider call
    assert dup.teacher_status == "labeled" and dup.teacher_label == "occupied"


# =============================================================== C-003 grouping


def test_same_session_arbitrary_groups_cannot_span_split(db):
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    # Six rows, ALL one physical session, but six arbitrary caller group strings.
    for i in range(6):
        for label in ("occupied", "empty"):
            db.add(TrainingSample(
                task_id=task.id, source_id=123, session_id="one-real-session",
                group_key=f"g{i}", image_path="none", image_hash=f"h{i}_{label}",
                verified=True, verified_label=label, origin="qa_synthetic",
            ))
    db.commit()
    # Everything collapses to ONE canonical provenance group -> cannot satisfy the
    # independent-group minimum; refuse honestly instead of fabricating a split.
    with pytest.raises(dataset.DatasetError):
        service.build_split_plan(db, task)


def test_inconsistent_group_metadata_rejected(db):
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    # One group_key reused across two distinct sessions -> inconsistent metadata.
    for ses in ("sesA", "sesB"):
        db.add(TrainingSample(
            task_id=task.id, source_id=1, session_id=ses, group_key="shared",
            image_path="none", image_hash=f"h-{ses}", verified=True,
            verified_label="occupied", origin="qa_synthetic",
        ))
    db.commit()
    with pytest.raises(service.AutoLearnError, match="inconsistent group metadata"):
        service.build_split_plan(db, task)


def test_near_duplicate_reencode_across_groups_refused(db):
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    base = Image.open(io.BytesIO(_jpeg((70, 90, 110), quality=92))).convert("RGB")
    b_hi = io.BytesIO(); base.save(b_hi, format="JPEG", quality=92)
    b_lo = io.BytesIO(); base.save(b_lo, format="JPEG", quality=35)  # re-encode
    # Same scene re-encoded into two different sessions (different sha256) + a
    # second class so the binary-class precondition is met before the near-dup
    # check runs.
    service.import_image(db, task, image_bytes=b_hi.getvalue(), session_id="sesA")
    service.import_image(db, task, image_bytes=b_lo.getvalue(), session_id="sesB")
    service.import_image(db, task, image_bytes=_jpeg((5, 5, 5)), session_id="sesC")
    for s in db.query(TrainingSample).all():
        lab = "empty" if s.session_id == "sesC" else "occupied"
        service.review_sample(db, s, verified_label=lab, reviewer="qa")
    with pytest.raises(dataset.DatasetError, match="near-duplicate"):
        service.build_split_plan(db, task)


def test_distinct_scenes_are_not_flagged_as_near_duplicate(db):
    # Decoded-pixel MAD keeps global tint, so genuinely different scenes split.
    rows = [
        dataset.SampleRow(id=0, group_key="g0", image_hash="h0", label="occupied",
                          fingerprint=np.zeros(300)),
        dataset.SampleRow(id=1, group_key="g1", image_hash="h1", label="empty",
                          fingerprint=np.full(300, 200.0)),
    ]
    # MAD is 200 >> 5.0 default -> no false positive (group count still refuses,
    # but NOT for a near-duplicate reason).
    with pytest.raises(dataset.DatasetError) as exc:
        dataset.build_split(rows, min_train_groups=2, min_val_groups=1,
                            min_test_groups=1, near_dup_max_mad=5.0)
    assert "near-duplicate" not in str(exc.value)


# =============================================================== C-002 manifest


def _mock_ml(monkeypatch):
    """Mock embeddings/classifier so evaluate inspects ROW SELECTION, not quality.
    Embedding = [1] for positive label else [0]; classifier returns that proba."""

    def fake_embed(rows):
        X = np.asarray(
            [[1.0 if r.verified_label == "occupied" else 0.0] for r in rows],
            dtype=np.float32,
        )
        return X, [1.0] * len(rows)

    class _Clf:
        def predict_proba(self, X):
            return X[:, 0]

    monkeypatch.setattr(service, "_embed", fake_embed)
    monkeypatch.setattr(service.student.StudentClassifier, "load",
                        staticmethod(lambda path: _Clf()))


def _version_with_manifest(db, task, test_sample_ids):
    mv = ModelVersion(
        task_id=task.id, version=1, artifact_path="QA-mock", encoder_name="resnet18",
        encoder_weights_version="QA", preprocess_version="QA",
        class_mapping={"empty": 0, "occupied": 1}, dataset_hash="d", split_hash="sp",
        train_count=4, val_count=2, test_count=len(test_sample_ids), threshold=0.5,
        train_duration_ms=1.0, environment={"disclosure": "QA mock"}, status="trained",
    )
    db.add(mv)
    db.flush()
    for sid in test_sample_ids:
        s = db.get(TrainingSample, sid)
        db.add(ModelVersionSample(model_version_id=mv.id, sample_id=sid,
                                  image_hash=s.image_hash, verified_label=s.verified_label,
                                  split="test"))
    db.commit()
    return mv


def _seed_verified(db, task, n):
    ids = []
    for i in range(n):
        label = "occupied" if i % 2 == 0 else "empty"
        s = TrainingSample(task_id=task.id, source_id=1, session_id=f"s{i}",
                           group_key=f"s{i}", image_path="none", image_hash=f"h{i}",
                           verified=True, verified_label=label, origin="qa_synthetic")
        db.add(s)
        db.flush()
        ids.append(s.id)
    db.commit()
    return ids


def test_evaluate_uses_frozen_manifest_not_current_split(db, monkeypatch):
    _mock_ml(monkeypatch)
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    ids = _seed_verified(db, task, 6)
    test_ids = ids[:2]  # one occupied, one empty
    mv = _version_with_manifest(db, task, test_ids)
    m = service.evaluate(db, mv)
    assert m["support"] == 2
    # Reshuffle the mutable task-wide split (as a later retrain would). The frozen
    # manifest must still drive evaluation -> support unchanged.
    for s in db.query(TrainingSample).all():
        s.split = "train"
    db.commit()
    m2 = service.evaluate(db, mv)
    assert m2["support"] == 2


def test_evaluate_fails_closed_on_missing_manifest_sample(db, monkeypatch):
    _mock_ml(monkeypatch)
    task = service.create_task(db, name="QA", visual_prompt="is it occupied?",
                              positive_label="occupied", negative_label="empty")
    ids = _seed_verified(db, task, 6)
    mv = _version_with_manifest(db, task, ids[:2])
    # Remove one frozen test sample -> evaluation must not infer a new accuracy.
    db.delete(db.get(TrainingSample, ids[0]))
    db.commit()
    m = service.evaluate(db, mv)
    assert m["f1"] is None
    assert "error" in m
    assert service.gate_status(mv)["passed"] is False


def test_gate_requires_support_equal_snapshot_and_both_classes():
    # Support mismatch (stale/narrowed rows) -> gate denies.
    v = SimpleNamespace(
        metrics={"f1": 1.0, "support": 1, "positives": 1, "negatives": 0},
        test_count=4,
    )
    g = service.gate_status(v)
    assert g["passed"] is False
    assert any("support" in r for r in g["reasons"])
    assert any("both classes" in r for r in g["reasons"])

    # Finite metrics, support == snapshot, both classes, above thresholds -> pass.
    ok = SimpleNamespace(
        metrics={"f1": 0.9, "support": 4, "positives": 2, "negatives": 2},
        test_count=4,
    )
    assert service.gate_status(ok)["passed"] is True


def test_gate_rejects_non_finite_f1():
    v = SimpleNamespace(
        metrics={"f1": float("nan"), "support": 4, "positives": 2, "negatives": 2},
        test_count=4,
    )
    g = service.gate_status(v)
    assert g["passed"] is False
    assert any("finite" in r for r in g["reasons"])
