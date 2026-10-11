"""Regressions for the second (final) AutoLearn blocker-fix pass.

Reproduces, in OWN isolated QA_ONLY fixtures, the seven P1 findings of
AUTOLEARN-TEN-HOUR-FIXED.md and locks in the minimal fixes. All data, labels,
simulated review/activation/rollback decisions and provider responses are
disclosed in-process fixtures. The Teacher transport, encoder and Student are
mocked ONLY at their boundaries where a test inspects reservation / grouping /
gate / version logic rather than model quality — never to fabricate metrics.

Covered:
  * C-005 — durable, cross-session atomic Teacher-attempt budget (reservation
    ledger); admission-timeout / local-input failures release (zero spend);
    in-flight dedupe; persistent bounded fallback cache.
  * C-006 — malformed envelope ``model`` -> invalid_response, actual attempt kept,
    never a DB bind failure.
  * C-007 — image-conditioned likelihood scoring provenance preserved; actual
    model stays distinct from the configured alias.
  * C-008 — unique (task_id, version) + immutable artifact path reserved before
    fitting; artifact/registry provenance verified on load.
  * C-002 — gate reads the COMPLETE frozen manifest + proven metrics (fail-closed);
    non-finite probabilities invalidate evaluation and yield explicit unknown.
  * C-009 — rollback verifies the target artifact BEFORE switching; a missing
    artifact fails visibly and leaves the current active version working.
"""

import io
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app import config, db as db_module
from app.autolearn import dataset, labeling, service, student
from app.autolearn.labeling import LabelCandidate
from app.db import (
    AutoLearnTask,
    LabelingCache,
    LabelingReservation,
    ModelVersion,
    ModelVersionSample,
    TrainingSample,
)


@pytest.fixture
def filedb(tmp_path, monkeypatch):
    """A real file-backed engine so reservation bookkeeping gets its own pooled
    connection — exercising the cross-transaction independence the fix relies on."""
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


def _jpeg(color, size=48) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _provider(monkeypatch, *, cand_factory=None, record=None):
    monkeypatch.setattr(config, "VLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setattr(config, "VLM_MODEL", "qa/alias")

    def fake(image_bytes, *, prompt, labels):
        if record is not None:
            record.append(prompt)
        if cand_factory is not None:
            return cand_factory()
        return LabelCandidate(status="labeled", label=labels[0], confidence=0.9,
                              model="qa/actual", method="chat_json", attempted=True,
                              raw={"method": "chat_json"})

    monkeypatch.setattr(labeling, "classify_sync", fake)


# ============================================================ C-005 budget


def test_durable_budget_is_cross_session(filedb, monkeypatch):
    calls = []
    _provider(monkeypatch, record=calls)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_BUDGET_PER_TASK", 1)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_JOB_MAX", 50)
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="occupied?",
                                   positive_label="occupied", negative_label="empty")
        tid = task.id
        for i in range(3):
            service.import_image(s, task, image_bytes=_jpeg((10 + i * 9, 20, 30)),
                                 session_id=f"ses{i}")
    # First job spends the single budget slot on its own session/connection.
    with filedb.get_session() as s:
        out1 = service.run_labeling(s, s.get(AutoLearnTask, tid))
    # A second job on a DIFFERENT session sees the durable spend and is fully
    # budget-suppressed — no extra provider call.
    with filedb.get_session() as s:
        out2 = service.run_labeling(s, s.get(AutoLearnTask, tid))
    assert out1["attempts_made"] == 1
    assert out2["attempts_made"] == 0
    assert len(calls) == 1
    with filedb.get_session() as s:
        assert service._teacher_attempts_spent(s, s.get(AutoLearnTask, tid)) == 1


def test_admission_timeout_releases_budget(filedb, monkeypatch):
    # A candidate that never reached the provider (attempted False) must NOT consume
    # durable budget.
    _provider(monkeypatch, cand_factory=lambda: LabelCandidate(
        status="timeout", attempted=False, detail="admission timeout"))
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_BUDGET_PER_TASK", 5)
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="occupied?",
                                   positive_label="occupied", negative_label="empty")
        service.import_image(s, task, image_bytes=_jpeg((1, 2, 3)), session_id="a")
        out = service.run_labeling(s, task)
        assert out["attempts_made"] == 0
        assert service._teacher_attempts_spent(s, task) == 0
        # The reservation was released, not left reserved/sent.
        assert s.query(LabelingReservation).filter_by(status="released").count() == 1


def test_local_oversize_never_reserves(filedb, monkeypatch):
    _provider(monkeypatch)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_MAX_IMAGE_BYTES", 1)
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="occupied?",
                                   positive_label="occupied", negative_label="empty")
        service.import_image(s, task, image_bytes=_jpeg((1, 2, 3)), session_id="a")
        out = service.run_labeling(s, task)
        assert out["attempts_made"] == 0
        assert out["failed"] == 1
        assert s.query(LabelingReservation).count() == 0  # no reservation at all
        assert service._teacher_attempts_spent(s, task) == 0


def test_reserve_attempt_dedupes_in_flight(filedb):
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="occupied?",
                                   positive_label="occupied", negative_label="empty")
        tid = task.id
    key = "dedupe-key"
    with filedb.get_session() as s:
        r1 = service._reserve_attempt(s, tid, image_hash="h", dedupe_key=key, budget=5)
        assert r1["outcome"] == "reserved"
    with filedb.get_session() as s:
        r2 = service._reserve_attempt(s, tid, image_hash="h", dedupe_key=key, budget=5)
        assert r2["outcome"] == "dedupe"  # identical key still in flight


def test_fallback_cache_reuses_without_new_call(filedb, monkeypatch):
    calls = []
    _provider(monkeypatch, record=calls)
    monkeypatch.setattr(config, "AUTOLEARN_LABEL_BUDGET_PER_TASK", 5)
    monkeypatch.setattr(config, "AUTOLEARN_STUDENT_MIN_MARGIN", 0.1)
    # A trivial active version + mocked load/encoder so the Student is below margin.
    monkeypatch.setattr(service, "_embed", lambda rows: (np.zeros((len(rows), 1)), [1.0]))

    class _Half:
        extra = {}
        def predict_proba(self, X):
            return np.full(len(X), 0.5)

    monkeypatch.setattr(student.StudentClassifier, "load", staticmethod(lambda p: _Half()))
    monkeypatch.setattr(service.encoder, "get_encoder",
                        lambda: SimpleNamespace(embed_bytes=lambda b: (np.zeros((len(b), 1)), [1.0])))
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="occupied?",
                                   positive_label="occupied", negative_label="empty")
        mv = ModelVersion(task_id=task.id, version=1, artifact_path="QA", encoder_name="e",
                          encoder_weights_version="w", preprocess_version="p",
                          class_mapping={"empty": 0, "occupied": 1}, dataset_hash="d",
                          split_hash="sp", train_count=4, val_count=2, test_count=4,
                          threshold=0.5, train_duration_ms=1.0, environment={}, status="active")
        s.add(mv); s.flush()
        task.active_version_id = mv.id
        s.commit()
        tid = task.id
    img = _jpeg((9, 9, 9))
    with filedb.get_session() as s:
        r1 = service.classify_offline(s, s.get(AutoLearnTask, tid), img)
    with filedb.get_session() as s:
        r2 = service.classify_offline(s, s.get(AutoLearnTask, tid), img)
    assert r1["status"] == "teacher_fallback"
    assert r2["teacher_status"] == "cache_hit"
    assert len(calls) == 1  # second identical fallback served from cache
    with filedb.get_session() as s:
        assert s.query(LabelingCache).filter_by(task_id=tid).count() == 1


# ============================================================ C-006 / C-007


def test_malformed_envelope_model_is_invalid_response(monkeypatch):
    import json as _json

    monkeypatch.setattr(labeling.config, "VLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setattr(labeling.config, "VLM_MODEL", "qa/alias")

    async def _fake(url, body, headers, timeout):
        payload = _json.dumps({
            "model": {"invalid": "object"},
            "choices": [{"message": {"content": _json.dumps({"label": "occupied", "confidence": 0.8})}}],
        }).encode()
        return 200, payload

    monkeypatch.setattr(labeling, "_post_and_read", _fake)
    cand = labeling.classify_sync(b"img", prompt="q", labels=["occupied", "empty"])
    assert cand.status == "invalid_response"
    assert cand.attempted is True  # a real attempt; budget must not be refunded


def test_scoring_provenance_matches_actual_local_teacher_contract():
    # The ACTUAL local experimental Teacher reports provenance in a top-level
    # ``experimental_metrics`` object with the real revision and a candidate-sequence
    # softmax scoring block (output_is_generated_json=False) (C-007).
    data = {
        "model": "qa/verified-actual-model",
        "choices": [{"message": {"content": '{"label": "occupied", "confidence": 0.8}'}}],
        "experimental_metrics": {
            "revision": "qa/pinned-revision",
            "scoring": {
                "method": "candidate_sequence_softmax",
                "uncalibrated": True,
                "candidate_labels": ["occupied", "empty"],
                "normalized_probabilities": [0.8, 0.2],
                "model_forward_calls": 2,
                "actual_model_processed_tokens": 27,
                "output_is_generated_json": False,
            },
        },
    }
    prov = labeling._scoring_provenance(data)
    assert prov["method"] == "candidate_sequence_softmax"
    assert prov["model_revision"] == "qa/pinned-revision"  # from envelope, not model id
    assert prov["candidate_scores"] == {"occupied": 0.8, "empty": 0.2}
    assert prov["forward_passes"] == 2
    assert prov["processed_tokens"] == 27
    assert prov["output_is_generated_json"] is False
    assert prov["scoring_uncalibrated"] is True
    # A plain generated-JSON response (no scoring block) is chat_json, and the
    # revision is never inferred from the model id.
    plain = labeling._scoring_provenance({"model": "qa/x", "experimental_metrics": {}})
    assert plain["method"] == "chat_json"
    assert plain["model_revision"] is None
    # An unknown/invented scoring method is ignored, never trusted.
    bogus = labeling._scoring_provenance(
        {"experimental_metrics": {"scoring": {"method": "totally-made-up",
                                              "output_is_generated_json": False}}}
    )
    assert bogus["method"] == "chat_json"


def test_bounded_scores_tolerates_overflow_and_oversize():
    # A 10**400 int, NaN, bool and 1000 scores must never raise and must be bounded
    # (C-006 P2). ``_finite_number`` drops overflow/NaN/bool; ``_bounded_scores`` caps.
    assert labeling._finite_number(10 ** 400) is None
    assert labeling._finite_number(float("nan")) is None
    assert labeling._finite_number(True) is None
    big = labeling._bounded_scores([f"c{i}" for i in range(1000)],
                                   [float(i) for i in range(1000)])
    assert big is not None and len(big) <= 8
    assert labeling._bounded_usage({"prompt_tokens": True, "completion_tokens": "3",
                                    "total_tokens": float("nan"), "extra": "X" * 9999}) is None


# ============================================================ C-008 versions


def test_reserve_version_is_unique_and_pathed(filedb):
    plan = SimpleNamespace(class_mapping={"empty": 0, "occupied": 1}, dataset_hash="d",
                           split_hash="sp", counts={"train": 4, "val": 2, "test": 4})
    enc = SimpleNamespace(weights_tag="w")
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="occupied?",
                                   positive_label="occupied", negative_label="empty")
        mv1 = service._reserve_version(s, task, plan, enc)
        mv2 = service._reserve_version(s, task, plan, enc)
    assert {mv1.version, mv2.version} == {1, 2}
    assert mv1.artifact_path != mv2.artifact_path
    assert mv1.artifact_path.endswith("v1.pt") and mv2.artifact_path.endswith("v2.pt")


def test_load_verified_artifact_rejects_provenance_mismatch(monkeypatch):
    v = SimpleNamespace(artifact_path="QA", class_mapping={"empty": 0, "occupied": 1},
                        encoder_name="resnet18", encoder_weights_version="w",
                        preprocess_version="p", dataset_hash="d", split_hash="sp")

    class _Clf:
        extra = {"class_mapping": {"x": 0, "y": 1}, "encoder_name": "resnet18"}

    monkeypatch.setattr(student.StudentClassifier, "load", staticmethod(lambda p: _Clf()))
    with pytest.raises(service.AutoLearnError, match="provenance"):
        service._load_verified_artifact(v)


# ============================================================ C-002 gate


def _seed(db, task, n):
    ids = []
    for i in range(n):
        label = "occupied" if i % 2 == 0 else "empty"
        s = TrainingSample(task_id=task.id, source_id=1, session_id=f"s{i}",
                           group_key=f"s{i}", image_path="none", image_hash=f"h{i}",
                           verified=True, verified_label=label, origin="qa_synthetic")
        db.add(s); db.flush(); ids.append(s.id)
    db.commit()
    return ids


def _complete_version(db, task, ids):
    test_ids, val_ids, train_ids = ids[:2], ids[2:4], ids[4:]
    mv = ModelVersion(task_id=task.id, version=1, artifact_path="QA", encoder_name="resnet18",
                      encoder_weights_version="w", preprocess_version="p",
                      class_mapping={"empty": 0, "occupied": 1}, dataset_hash="d",
                      split_hash="sp", train_count=len(train_ids), val_count=len(val_ids),
                      test_count=len(test_ids), threshold=0.5, train_duration_ms=1.0,
                      environment={}, status="trained",
                      metrics={"f1": 1.0, "support": 2, "positives": 1, "negatives": 1,
                               "manifest_digest": "STALE"})
    db.add(mv); db.flush()
    for sids, split in ((train_ids, "train"), (val_ids, "val"), (test_ids, "test")):
        for sid in sids:
            row = db.get(TrainingSample, sid)
            db.add(ModelVersionSample(model_version_id=mv.id, sample_id=sid,
                                      image_hash=row.image_hash, verified_label=row.verified_label,
                                      split=split))
    db.commit()
    return mv


def test_gate_fails_closed_on_unproven_metrics(filedb):
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="q",
                                   positive_label="occupied", negative_label="empty")
        ids = _seed(s, task, 6)
        mv = _complete_version(s, task, ids)  # metrics carry a STALE digest
        g = service.gate_status(mv, s)
        assert g["passed"] is False
        assert any("frozen manifest" in r or "re-evaluate" in r for r in g["reasons"])


def test_gate_fails_closed_on_missing_manifest_row(filedb):
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="q",
                                   positive_label="occupied", negative_label="empty")
        ids = _seed(s, task, 6)
        mv = _complete_version(s, task, ids)
        row = s.query(ModelVersionSample).filter_by(model_version_id=mv.id, split="test").first()
        s.delete(row); s.commit()
        g = service.gate_status(mv, s)
        assert g["passed"] is False
        assert any("inconsistent" in r for r in g["reasons"])


def test_validate_proba_rejects_nonfinite():
    with pytest.raises(service.AutoLearnError):
        service._validate_proba(np.array([np.nan, 0.4]), 2)
    with pytest.raises(service.AutoLearnError):
        service._validate_proba(np.array([1.5]), 1)
    with pytest.raises(service.AutoLearnError):
        service._validate_proba(np.array([0.4]), 2)  # wrong shape
    ok = service._validate_proba(np.array([0.1, 0.9]), 2)
    assert ok.tolist() == [0.1, 0.9]


# ============================================================ C-009 rollback


def test_rollback_refuses_missing_target_artifact(filedb, monkeypatch):
    with filedb.get_session() as s:
        task = service.create_task(s, name="QA", visual_prompt="q",
                                   positive_label="occupied", negative_label="empty")
        prev = ModelVersion(task_id=task.id, version=1, artifact_path="GONE.pt",
                            encoder_name="e", encoder_weights_version="w", preprocess_version="p",
                            class_mapping={"empty": 0, "occupied": 1}, dataset_hash="d",
                            split_hash="sp", train_count=4, val_count=2, test_count=4,
                            threshold=0.5, train_duration_ms=1.0, environment={}, status="archived")
        cur = ModelVersion(task_id=task.id, version=2, artifact_path="CUR.pt",
                           encoder_name="e", encoder_weights_version="w", preprocess_version="p",
                           class_mapping={"empty": 0, "occupied": 1}, dataset_hash="d",
                           split_hash="sp", train_count=4, val_count=2, test_count=4,
                           threshold=0.5, train_duration_ms=1.0, environment={}, status="active")
        s.add_all([prev, cur]); s.flush()
        task.active_version_id = cur.id
        s.commit()
        cur_id, tid = cur.id, task.id

    def _raise(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(student.StudentClassifier, "load", staticmethod(_raise))
    with filedb.get_session() as s:
        with pytest.raises(service.AutoLearnError, match="unusable"):
            service.rollback(s, s.get(AutoLearnTask, tid), approver="qa")
        # Current active version is unchanged; no gate_passed rollback recorded.
        assert s.get(AutoLearnTask, tid).active_version_id == cur_id
        from app.db import ActivationEvent
        assert s.query(ActivationEvent).filter_by(action="rollback").count() == 0
