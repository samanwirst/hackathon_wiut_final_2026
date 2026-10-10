"""AutoLearn orchestration (M3).

Ties the DB rows to the encoder, Student, dataset splitter, metrics, offline
labeling client, and version registry. Every function here is honest about its
limits: no synthetic Teacher labels, no training on unverified labels, no
activation without a passed gate and explicit human approval, and no workflow
dispatch ever.
"""

from __future__ import annotations

import hashlib
import io
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.autolearn import dataset, encoder, labeling, metrics, student
from app.db import (
    ActivationEvent,
    AutoLearnTask,
    LabelingAudit,
    ModelVersion,
    ModelVersionSample,
    TrainingSample,
)

# Outcomes that actually contacted the provider and therefore consume budget
# (C-005). "unavailable" (no provider) and cache/dedupe outcomes consume none.
_REAL_ATTEMPT_STATUSES = {"labeled", "invalid_response", "timeout", "error"}


def _fingerprint(image_bytes: bytes) -> "np.ndarray | None":
    """Normalized decoded-pixel fingerprint (flattened 32x32 RGB float array).

    Returns None if the bytes cannot be decoded. Used only for conservative
    near-duplicate leakage checks (C-003); decoded pixels retain global tint that
    a perceptual hash would normalize away, so independent scenes stay distinct."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((32, 32))
        return np.asarray(img, dtype=np.float64).flatten()
    except Exception:  # noqa: BLE001
        return None


class AutoLearnError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------- task / import


def create_task(
    session: Session,
    *,
    name: str,
    visual_prompt: str,
    positive_label: str,
    negative_label: str,
    teacher_model: str | None = None,
) -> AutoLearnTask:
    pos = positive_label.strip().lower()
    neg = negative_label.strip().lower()
    if not pos or not neg or pos == neg:
        raise AutoLearnError("positive_label and negative_label must be distinct non-empty strings")
    task = AutoLearnTask(
        name=name.strip(),
        visual_prompt=visual_prompt.strip(),
        positive_label=pos,
        negative_label=neg,
        teacher_model=teacher_model,
        status="collecting",
    )
    session.add(task)
    session.commit()
    return task


def import_image(
    session: Session,
    task: AutoLearnTask,
    *,
    image_bytes: bytes,
    session_id: str,
    group_key: str | None = None,
    source_id: int | None = None,
    video_timestamp: float | None = None,
    origin: str = "imported",
) -> TrainingSample | None:
    """Store one image for a task. Exact-duplicate content (same hash) within the
    task is skipped (returns None) to avoid trivial leakage."""
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    existing = (
        session.query(TrainingSample)
        .filter(TrainingSample.task_id == task.id, TrainingSample.image_hash == image_hash)
        .first()
    )
    if existing is not None:
        return None
    config.ensure_dirs()
    task_dir = config.AUTOLEARN_IMAGE_DIR / f"task_{task.id}"
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / f"{image_hash}.jpg"
    path.write_bytes(image_bytes)
    sample = TrainingSample(
        task_id=task.id,
        source_id=source_id,
        session_id=session_id,
        group_key=(group_key or session_id),
        image_path=str(path),
        image_hash=image_hash,
        video_timestamp=video_timestamp,
        origin=origin,
    )
    session.add(sample)
    session.commit()
    return sample


def import_synthetic_qa(session: Session, task: AutoLearnTask, **kwargs) -> int:
    """Import QA_ONLY synthetic sessions (disclosed, non-natural data)."""
    from app.autolearn import fixtures

    samples = fixtures.generate_sessions(task_slug=f"t{task.id}", **kwargs)
    count = 0
    for s in samples:
        row = import_image(
            session,
            task,
            image_bytes=s.image_bytes,
            session_id=s.session_id,
            group_key=s.group_key,
            origin="qa_synthetic",
        )
        if row is not None:
            count += 1
    return count


# --------------------------------------------------------------- labeling


def _teacher_attempts_spent(session: Session, task: AutoLearnTask) -> int:
    """Durable count of real provider attempts for this task (C-005).

    Counted from the labeling audit, so it survives across process restarts and
    concurrent/repeated jobs. Only outcomes that actually contacted the provider
    consume budget; unavailable / cache / dedupe outcomes do not."""
    return (
        session.query(LabelingAudit)
        .filter(
            LabelingAudit.task_id == task.id,
            LabelingAudit.status.in_(_REAL_ATTEMPT_STATUSES),
        )
        .count()
    )


def _cached_label(session: Session, task: AutoLearnTask, sample: TrainingSample):
    """Reuse an identical already-labeled result (same task, image content, prompt
    and model) so an identical input costs zero new attempts (C-005)."""
    return (
        session.query(TrainingSample)
        .filter(
            TrainingSample.task_id == task.id,
            TrainingSample.id != sample.id,
            TrainingSample.image_hash == sample.image_hash,
            TrainingSample.teacher_status == "labeled",
            TrainingSample.teacher_prompt == task.visual_prompt,
            TrainingSample.teacher_model == (config.VLM_MODEL or None),
        )
        .order_by(TrainingSample.id)
        .first()
    )


def run_labeling(session: Session, task: AutoLearnTask, *, limit: int | None = None) -> dict:
    """Call the offline Teacher for pending samples under an explicit, durable
    budget. Missing provider -> pending (unavailable, zero attempts), never a
    synthetic label. Identical inputs reuse a cached label (zero attempts), and a
    duplicate image within one job is suppressed. Candidate labels are advisory."""
    pending = (
        session.query(TrainingSample)
        .filter(TrainingSample.task_id == task.id, TrainingSample.teacher_status == "pending")
        .order_by(TrainingSample.id)
        .all()
    )
    if not labeling.provider_configured():
        for s in pending:
            _audit(session, task, s, status="unavailable")  # zero attempts consumed
        session.commit()
        return {
            "status": "unavailable",
            "provider_configured": False,
            "pending": len(pending),
            "detail": "No VLM_BASE_URL/VLM_MODEL configured; labels remain pending for a real provider.",
        }

    labels = [task.positive_label, task.negative_label]
    # Bounded job admission: never unbounded. The per-job cap AND the durable
    # per-task budget both apply (C-005).
    job_cap = config.AUTOLEARN_LABEL_JOB_MAX
    if limit is not None:
        job_cap = min(job_cap, max(0, limit))
    spent = _teacher_attempts_spent(session, task)
    remaining_budget = max(0, config.AUTOLEARN_LABEL_BUDGET_PER_TASK - spent)

    labeled = cached = failed = suppressed = calls = 0
    seen_in_job: dict[str, TrainingSample] = {}

    for s in pending:
        # Within-job duplicate suppression: a second identical image in the same
        # batch reuses the first result rather than paying a new call.
        dup = seen_in_job.get(s.image_hash)
        cache_src = dup or _cached_label(session, task, s)
        if cache_src is not None and cache_src.teacher_status == "labeled":
            s.teacher_status = "labeled"
            s.teacher_label = cache_src.teacher_label
            s.teacher_confidence = cache_src.teacher_confidence
            s.teacher_model = cache_src.teacher_model
            s.teacher_prompt = task.visual_prompt
            s.teacher_raw = {"cache_hit": True, "source_sample_id": cache_src.id}
            _audit(session, task, s, status="cache_hit")  # zero attempts consumed
            cached += 1
            seen_in_job[s.image_hash] = s
            continue

        if calls >= job_cap or remaining_budget <= 0:
            _audit(session, task, s, status="suppressed_budget")  # zero attempts
            suppressed += 1
            continue

        image_bytes = Path(s.image_path).read_bytes()
        cand = labeling.classify_sync(image_bytes, prompt=task.visual_prompt, labels=labels)
        calls += 1
        if cand.status in _REAL_ATTEMPT_STATUSES:
            remaining_budget -= 1
        s.teacher_status = cand.status
        # Column holds the configured model alias (stable request/version identity
        # used as the cache key). The ACTUAL provider model/revision is preserved
        # in the audit (response_model) and in teacher_raw (C-007).
        s.teacher_model = config.VLM_MODEL or None
        s.teacher_prompt = task.visual_prompt
        if cand.status == "labeled":
            s.teacher_label = cand.label
            s.teacher_confidence = cand.confidence
            s.teacher_raw = cand.raw
            labeled += 1
            seen_in_job[s.image_hash] = s
        else:
            failed += 1
        _audit(session, task, s, status=cand.status, latency_ms=cand.latency_ms,
               provider_host=cand.provider_host, model=cand.model, method=cand.method)

    task.teacher_model = task.teacher_model or config.VLM_MODEL or None
    task.status = "review" if (labeled or cached) else task.status
    session.commit()
    return {
        "status": "done",
        "provider_configured": True,
        "labeled": labeled,
        "cached": cached,
        "failed": failed,
        "suppressed_budget": suppressed,
        "attempts_made": calls,
        "budget_remaining": remaining_budget,
    }


def _audit(session, task, sample, *, status, latency_ms=None, provider_host=None,
           model=None, method=None):
    session.add(
        LabelingAudit(
            task_id=task.id,
            sample_id=sample.id,
            provider_host=provider_host,
            model=config.VLM_MODEL or None,
            response_model=model,
            method=method,
            prompt=task.visual_prompt,
            image_hash=sample.image_hash,
            session_id=sample.session_id,
            status=status,
            latency_ms=latency_ms,
        )
    )


def _audit_freeform(session, task, *, status, image_hash, latency_ms=None,
                    provider_host=None, model=None, method=None):
    """Audit a Teacher attempt not tied to a stored sample (e.g. the offline
    classify fallback), so it still consumes the durable per-task budget (C-005)."""
    session.add(
        LabelingAudit(
            task_id=task.id,
            sample_id=None,
            provider_host=provider_host,
            model=config.VLM_MODEL or None,
            response_model=model,
            method=method,
            prompt=task.visual_prompt,
            image_hash=image_hash,
            session_id=None,
            status=status,
            latency_ms=latency_ms,
        )
    )


def review_sample(session: Session, sample: TrainingSample, *, verified_label: str, reviewer: str):
    """Record an immutable human verification. Cannot overwrite a prior one."""
    if sample.verified:
        raise AutoLearnError("sample is already verified; verified labels are immutable")
    task = session.get(AutoLearnTask, sample.task_id)
    permitted = {task.positive_label, task.negative_label}
    label = verified_label.strip().lower()
    if label not in permitted:
        raise AutoLearnError(f"verified_label must be one of {sorted(permitted)}")
    sample.verified = True
    sample.verified_label = label
    sample.verified_by = reviewer.strip() or "unknown"
    sample.verified_at = _utcnow()
    session.commit()
    return sample


# --------------------------------------------------------------- split / train


def _verified_rows(session: Session, task: AutoLearnTask) -> list[TrainingSample]:
    return (
        session.query(TrainingSample)
        .filter(
            TrainingSample.task_id == task.id,
            TrainingSample.verified.is_(True),
            TrainingSample.verified_label.isnot(None),
        )
        .order_by(TrainingSample.id)
        .all()
    )


def _canonical_group(r: TrainingSample) -> str:
    """Physical provenance grouping key (C-003).

    Splitting groups by the session/source a sample physically came from, NOT the
    free-form ``group_key`` a caller may supply. This prevents a user from
    straddling the train/val/test boundary with the same session merely by picking
    different group strings."""
    src = "none" if r.source_id is None else str(r.source_id)
    return f"src:{src}|ses:{r.session_id}"


def build_split_plan(session: Session, task: AutoLearnTask) -> dataset.SplitPlan:
    rows = _verified_rows(session, task)

    # Reject inconsistent group metadata: a single free-form group_key must not
    # span more than one physical provenance identity (C-003).
    group_to_provenance: dict[str, set[str]] = {}
    for r in rows:
        group_to_provenance.setdefault(r.group_key, set()).add(_canonical_group(r))
    inconsistent = {g: p for g, p in group_to_provenance.items() if len(p) > 1}
    if inconsistent:
        raise AutoLearnError(
            "inconsistent group metadata: group(s) "
            f"{sorted(inconsistent)} span multiple session/source identities"
        )

    sr = [
        dataset.SampleRow(
            id=r.id,
            group_key=_canonical_group(r),
            image_hash=r.image_hash,
            label=r.verified_label,
            fingerprint=_fingerprint_for(r),
        )
        for r in rows
    ]
    plan = dataset.build_split(
        sr,
        min_train_groups=config.AUTOLEARN_MIN_TRAIN_GROUPS,
        min_val_groups=config.AUTOLEARN_MIN_VAL_GROUPS,
        min_test_groups=config.AUTOLEARN_MIN_TEST_GROUPS,
        near_dup_max_mad=config.AUTOLEARN_NEAR_DUP_MAX_MAD,
    )
    # Enforce the task's own class polarity (positive -> 1).
    if set(plan.class_mapping) != {task.positive_label, task.negative_label}:
        raise AutoLearnError("verified labels do not match task classes")
    return plan


def _fingerprint_for(r: TrainingSample) -> "np.ndarray | None":
    try:
        return _fingerprint(Path(r.image_path).read_bytes())
    except Exception:  # noqa: BLE001
        return None


def _embed(rows: list[TrainingSample]) -> tuple[np.ndarray, list[float]]:
    enc = encoder.get_encoder()
    blobs = [Path(r.image_path).read_bytes() for r in rows]
    return enc.embed_bytes(blobs)


def train(session: Session, task: AutoLearnTask) -> ModelVersion:
    """Fit, threshold-select on validation, save, and register a Student version.

    Held-out test metrics are computed and stored so the activation gate has real
    numbers to check. The test split is never used for fitting or thresholding."""
    plan = build_split_plan(session, task)
    rows = _verified_rows(session, task)
    by_split: dict[str, list[TrainingSample]] = {"train": [], "val": [], "test": []}
    for r in rows:
        split = plan.assignments.get(r.id)
        if split:
            r.split = split
            by_split[split].append(r)
    session.commit()

    enc = encoder.get_encoder()
    pos = task.positive_label

    def xy(split_rows):
        X, _ = _embed(split_rows)
        y = np.array([1 if r.verified_label == pos else 0 for r in split_rows], dtype=np.int64)
        return X, y

    Xtr, ytr = xy(by_split["train"])
    Xva, yva = xy(by_split["val"])

    clf = student.StudentClassifier(in_dim=encoder.EMBED_DIM, classes=[task.negative_label, pos])
    tr = clf.fit(Xtr, ytr)

    # Threshold selected on validation ONLY.
    if len(by_split["val"]):
        va_probs = clf.predict_proba(Xva)
        threshold, _ = metrics.select_threshold(va_probs, yva)
    else:
        threshold = 0.5

    version_no = (
        session.query(ModelVersion).filter(ModelVersion.task_id == task.id).count() + 1
    )
    model_dir = config.AUTOLEARN_MODEL_DIR / f"task_{task.id}"
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact = model_dir / f"v{version_no}.pt"
    clf.save(
        str(artifact),
        extra={
            "threshold": threshold,
            "class_mapping": plan.class_mapping,
            "encoder_name": encoder.ENCODER_NAME,
            "encoder_weights_version": enc.weights_tag,
            "preprocess_version": encoder.PREPROCESS_VERSION,
            "dataset_hash": plan.dataset_hash,
            "split_hash": plan.split_hash,
        },
    )

    # Held-out test metrics.
    test_metrics = _evaluate_rows(clf, by_split["test"], pos, threshold)

    mv = ModelVersion(
        task_id=task.id,
        version=version_no,
        artifact_path=str(artifact),
        encoder_name=encoder.ENCODER_NAME,
        encoder_weights_version=enc.weights_tag,
        preprocess_version=encoder.PREPROCESS_VERSION,
        class_mapping=plan.class_mapping,
        dataset_hash=plan.dataset_hash,
        split_hash=plan.split_hash,
        train_count=plan.counts["train"],
        val_count=plan.counts["val"],
        test_count=plan.counts["test"],
        threshold=threshold,
        metrics=test_metrics,
        train_duration_ms=tr.duration_ms,
        environment=student.environment_info(),
        status="trained",
    )
    session.add(mv)
    session.flush()  # assign mv.id for the manifest rows

    # Freeze the exact dataset membership for THIS version (C-002). Held-out
    # evaluation, shadow and the activation gate read this manifest, never the
    # mutable task-wide split that a later retrain reshuffles.
    for split_name, split_rows in by_split.items():
        for r in split_rows:
            session.add(
                ModelVersionSample(
                    model_version_id=mv.id,
                    sample_id=r.id,
                    image_hash=r.image_hash,
                    verified_label=r.verified_label,
                    split=split_name,
                )
            )

    task.status = "trained"
    session.commit()
    return mv


def _evaluate_rows(clf, rows: list[TrainingSample], pos: str, threshold: float) -> dict:
    if not rows:
        return {"note": "empty test split", "support": 0}
    X, latencies = _embed(rows)
    y = np.array([1 if r.verified_label == pos else 0 for r in rows], dtype=np.int64)
    probs = clf.predict_proba(X)
    pred = (probs >= threshold).astype(np.int64)
    m = metrics.binary_metrics(y, pred)
    m["latency"] = metrics.latency_percentiles(latencies)
    m["threshold"] = threshold
    return m


def _manifest_test_rows(session: Session, version: ModelVersion) -> list[TrainingSample]:
    """Return the exact held-out test rows frozen for this version, or raise.

    Fails closed (C-002): if the manifest is missing, or a frozen row's current
    sample is absent / its content hash or verified label changed, no accuracy is
    inferred — the caller surfaces the inconsistency instead."""
    manifest = (
        session.query(ModelVersionSample)
        .filter(
            ModelVersionSample.model_version_id == version.id,
            ModelVersionSample.split == "test",
        )
        .order_by(ModelVersionSample.sample_id)
        .all()
    )
    if not manifest:
        raise AutoLearnError(
            "no frozen dataset manifest for this version; cannot evaluate held-out metrics"
        )
    rows: list[TrainingSample] = []
    for ms in manifest:
        s = session.get(TrainingSample, ms.sample_id)
        if s is None:
            raise AutoLearnError(
                f"manifest sample {ms.sample_id} no longer exists; refusing to evaluate"
            )
        if s.image_hash != ms.image_hash:
            raise AutoLearnError(
                f"manifest sample {ms.sample_id} content changed; refusing to evaluate"
            )
        if not s.verified or s.verified_label != ms.verified_label:
            raise AutoLearnError(
                f"manifest sample {ms.sample_id} verified label changed; refusing to evaluate"
            )
        rows.append(s)
    return rows


def evaluate(session: Session, version: ModelVersion) -> dict:
    """Recompute held-out metrics from the reloaded artifact over the version's
    OWN frozen test manifest (C-002). On an inconsistent/missing snapshot the
    metrics are cleared and a fail-closed marker is stored so the gate denies."""
    task = session.get(AutoLearnTask, version.task_id)
    try:
        test_rows = _manifest_test_rows(session, version)
    except AutoLearnError as exc:
        version.metrics = {"error": str(exc), "support": 0, "f1": None}
        session.commit()
        return version.metrics
    clf = student.StudentClassifier.load(version.artifact_path)
    m = _evaluate_rows(clf, test_rows, task.positive_label, version.threshold)
    version.metrics = m
    session.commit()
    return m


# --------------------------------------------------------------- shadow


def shadow_compare(session: Session, task: AutoLearnTask) -> dict:
    """Compare the latest trained Student against Teacher candidate labels on the
    held-out test rows. Records NOTHING actionable and changes no active model."""
    version = (
        session.query(ModelVersion)
        .filter(ModelVersion.task_id == task.id)
        .order_by(ModelVersion.version.desc())
        .first()
    )
    if version is None:
        raise AutoLearnError("no trained Student to run in shadow mode")
    clf = student.StudentClassifier.load(version.artifact_path)
    # Shadow runs on the version's OWN frozen held-out manifest (C-002), so it
    # never leaks rows the Student trained on after a later retrain reshuffle.
    rows = _manifest_test_rows(session, version)
    if not rows:
        return {"compared": 0, "items": [], "note": "no test rows"}
    X, _ = _embed(rows)
    probs = clf.predict_proba(X)
    pos = task.positive_label
    neg = task.negative_label
    items = []
    student_labels = []
    teacher_labels = []
    for r, p in zip(rows, probs):
        s_label = pos if p >= version.threshold else neg
        student_labels.append(s_label)
        teacher_labels.append(r.teacher_label)
        items.append(
            {
                "sample_id": r.id,
                "session_id": r.session_id,
                "student_label": s_label,
                "student_confidence": round(float(p), 4),
                "teacher_label": r.teacher_label,
                "teacher_status": r.teacher_status,
                "verified_label": r.verified_label,
                "action": "none",  # shadow mode never executes an action
            }
        )
    return {
        "version": version.version,
        "compared": len(items),
        "disagreement": metrics.disagreement_rate(student_labels, teacher_labels),
        "items": items,
    }


# --------------------------------------------------------------- activation


def gate_status(version: ModelVersion) -> dict:
    """Fail-closed activation gate (C-002).

    The gate reads the metrics ACTUALLY computed on the frozen manifest. It
    requires: finite f1; evaluated support equal to the frozen snapshot test
    count (not a stale stored number); both classes present in the evaluated
    held-out set; support >= min_test; and f1 >= min_f1. Any inconsistency denies.
    """
    m = version.metrics or {}
    f1 = m.get("f1")
    support = m.get("support", 0)
    positives = m.get("positives")
    negatives = m.get("negatives")
    snapshot_test = version.test_count
    reasons: list[str] = []

    if f1 is None:
        reasons.append("no held-out metrics; run evaluate first")
    elif not (isinstance(f1, (int, float)) and math.isfinite(f1)):
        reasons.append(f"held-out F1 is not a finite number ({f1!r})")

    if support != snapshot_test:
        reasons.append(
            f"evaluated support {support} != frozen snapshot test count {snapshot_test}; "
            "membership is inconsistent"
        )
    if snapshot_test < config.AUTOLEARN_GATE_MIN_TEST:
        reasons.append(
            f"test support {snapshot_test} < required {config.AUTOLEARN_GATE_MIN_TEST}"
        )
    if positives is None or negatives is None or positives < 1 or negatives < 1:
        reasons.append(
            f"held-out set must contain both classes (positives={positives}, negatives={negatives})"
        )
    if f1 is not None and isinstance(f1, (int, float)) and math.isfinite(f1) \
            and f1 < config.AUTOLEARN_GATE_MIN_F1:
        reasons.append(f"held-out F1 {f1} < gate {config.AUTOLEARN_GATE_MIN_F1}")

    passed = not reasons
    return {
        "passed": passed,
        "f1": f1,
        "support": support,
        "min_f1": config.AUTOLEARN_GATE_MIN_F1,
        "test_count": snapshot_test,
        "min_test": config.AUTOLEARN_GATE_MIN_TEST,
        "reasons": reasons,
    }


def activate(session: Session, version: ModelVersion, *, approver: str, approve: bool) -> dict:
    """Activate a Student version for OFFLINE classification only.

    Requires both a passed predefined quality gate and an explicit human approval.
    Never dispatches a workflow action. A rejected or gate-failing request is
    recorded and changes nothing."""
    task = session.get(AutoLearnTask, version.task_id)
    gate = gate_status(version)
    if not approve:
        session.add(ActivationEvent(task_id=task.id, model_version_id=version.id, action="reject",
                                    decided_by=approver, reason="human declined", gate_passed=gate["passed"]))
        session.commit()
        return {"activated": False, "reason": "human declined", "gate": gate}
    if not gate["passed"]:
        session.add(ActivationEvent(task_id=task.id, model_version_id=version.id, action="reject",
                                    decided_by=approver, reason="; ".join(gate["reasons"]),
                                    gate_passed=False))
        session.commit()
        return {"activated": False, "reason": "gate not passed", "gate": gate}

    # Archive the currently active version, if any.
    if task.active_version_id:
        prev = session.get(ModelVersion, task.active_version_id)
        if prev is not None and prev.id != version.id:
            prev.status = "archived"
    version.status = "active"
    task.active_version_id = version.id
    task.status = "active"
    session.add(ActivationEvent(task_id=task.id, model_version_id=version.id, action="activate",
                                decided_by=approver, reason="gate passed + approved", gate_passed=True))
    session.commit()
    return {"activated": True, "version": version.version, "gate": gate}


def rollback(session: Session, task: AutoLearnTask, *, approver: str) -> dict:
    """Restore the most recent previously-active (archived) version."""
    current = session.get(ModelVersion, task.active_version_id) if task.active_version_id else None
    prev = (
        session.query(ModelVersion)
        .filter(ModelVersion.task_id == task.id, ModelVersion.status == "archived")
        .order_by(ModelVersion.version.desc())
        .first()
    )
    if prev is None:
        raise AutoLearnError("no previous version available to roll back to")
    if current is not None:
        current.status = "rolled_back"
    prev.status = "active"
    task.active_version_id = prev.id
    session.add(ActivationEvent(task_id=task.id, model_version_id=prev.id, action="rollback",
                                decided_by=approver, reason="rollback to previous version",
                                gate_passed=True))
    session.commit()
    return {"rolled_back_to": prev.version}


# --------------------------------------------------------------- offline classify


def classify_offline(session: Session, task: AutoLearnTask, image_bytes: bytes) -> dict:
    """Offline classification using the active Student. Low-margin predictions
    fall back to the Teacher (budgeted, non-actioning) or an explicit unknown.
    This NEVER dispatches a workflow action."""
    if not task.active_version_id:
        return {"status": "unavailable", "detail": "no active Student version"}
    version = session.get(ModelVersion, task.active_version_id)
    clf = student.StudentClassifier.load(version.artifact_path)
    enc = encoder.get_encoder()
    X, _ = enc.embed_bytes([image_bytes])
    p = float(clf.predict_proba(X)[0])
    pos, neg = task.positive_label, task.negative_label
    margin = abs(p - version.threshold)
    if margin < config.AUTOLEARN_STUDENT_MIN_MARGIN:
        # Fall back to Teacher if available AND within the durable per-task
        # budget; otherwise explicit unknown (C-005). The fallback never actions.
        if labeling.provider_configured():
            spent = _teacher_attempts_spent(session, task)
            if spent >= config.AUTOLEARN_LABEL_BUDGET_PER_TASK:
                return {
                    "status": "unknown",
                    "detail": "student below margin; Teacher budget exhausted for this task",
                    "student_confidence": round(p, 4),
                    "margin": round(margin, 4),
                    "action": "none",
                }
            # Reuse an identical cached label before spending an attempt.
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            cached = (
                session.query(TrainingSample)
                .filter(
                    TrainingSample.task_id == task.id,
                    TrainingSample.image_hash == image_hash,
                    TrainingSample.teacher_status == "labeled",
                    TrainingSample.teacher_prompt == task.visual_prompt,
                    TrainingSample.teacher_model == (config.VLM_MODEL or None),
                )
                .first()
            )
            if cached is not None:
                return {
                    "status": "teacher_fallback",
                    "student_confidence": round(p, 4),
                    "margin": round(margin, 4),
                    "teacher_status": "cache_hit",
                    "label": cached.teacher_label,
                    "action": "none",
                }
            cand = labeling.classify_sync(image_bytes, prompt=task.visual_prompt, labels=[pos, neg])
            _audit_freeform(session, task, status=cand.status, image_hash=image_hash,
                            latency_ms=cand.latency_ms, provider_host=cand.provider_host,
                            model=cand.model, method=cand.method)
            session.commit()
            return {
                "status": "teacher_fallback",
                "student_confidence": round(p, 4),
                "margin": round(margin, 4),
                "teacher_status": cand.status,
                "label": cand.label if cand.status == "labeled" else None,
                "action": "none",
            }
        return {
            "status": "unknown",
            "detail": "student confidence below margin and no Teacher provider configured",
            "student_confidence": round(p, 4),
            "margin": round(margin, 4),
            "action": "none",
        }
    label = pos if p >= version.threshold else neg
    return {
        "status": "student",
        "label": label,
        "confidence": round(p, 4),
        "version": version.version,
        "action": "none",
    }
