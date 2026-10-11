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
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, db as db_module
from app.autolearn import dataset, encoder, labeling, metrics, student
from app.db import (
    ActivationEvent,
    AutoLearnTask,
    LabelingAudit,
    LabelingCache,
    LabelingReservation,
    ModelVersion,
    ModelVersionSample,
    TrainingSample,
)

# Statuses that imply the provider definitely received a request (a response, even
# a bad one, came back). Combined with LabelCandidate.attempted this decides
# whether a durable reservation is kept as an actual attempt (C-005).
_RESPONDED_STATUSES = {"labeled", "invalid_response"}

# Bounded per-task size of the persistent fallback cache (C-005).
_LABEL_CACHE_MAX_PER_TASK = 512


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


def _reservation_session(session: Session):
    """Return (resv_session, independent) for durable budget bookkeeping (C-005).

    When the app's global engine is in use (production, API requests, file-backed
    tests) a brand-new session on its own pooled connection is returned so the
    reservation is committed INDEPENDENTLY of the job's transaction — a later job
    fault cannot roll back committed spend, and separate Uvicorn worker processes
    serialize through the shared SQLite file + ``UNIQUE(task_id, slot)``.

    For an isolated in-memory unit session (no global engine) the job session is
    reused; those tests do not exercise cross-transaction fault independence."""
    engine = session.get_bind()
    if db_module.SessionLocal is not None and engine is db_module._engine:
        return db_module.SessionLocal(), True
    return session, False


def _budget_spent(resv_session, task_id: int) -> int:
    """Durable budget consumed by a task: reserved (in-flight) + sent (actual)."""
    return (
        resv_session.query(LabelingReservation)
        .filter(
            LabelingReservation.task_id == task_id,
            LabelingReservation.status.in_(("reserved", "sent")),
        )
        .count()
    )


def _teacher_attempts_spent(session: Session, task: AutoLearnTask) -> int:
    """Durable budget consumed for this task (C-005).

    Counted from the reservation ledger, so it is authoritative across processes,
    concurrent jobs and the low-margin classify fallback, and survives job faults.
    Only ``reserved``/``sent`` rows count; ``released`` (admission timeout / local
    rejection) and cache/dedupe outcomes consume nothing."""
    resv_session, independent = _reservation_session(session)
    try:
        return _budget_spent(resv_session, task.id)
    finally:
        if independent:
            resv_session.close()


def _dedupe_key(image_hash: str, prompt: str) -> str:
    """Stable identity for one Teacher attempt: image content + prompt + model."""
    model = config.VLM_MODEL or ""
    return hashlib.sha256(f"{image_hash}|{prompt}|{model}".encode()).hexdigest()


def _reserve_attempt(resv_session, task_id: int, *, image_hash: str, dedupe_key: str,
                     budget: int) -> dict:
    """Atomically reserve one durable budget slot BEFORE any outbound request.

    Returns ``{"outcome": ...}`` where outcome is:
      * ``"reserved"`` with ``reservation_id`` — a slot was committed; the caller
        MUST later finalize it as sent or released.
      * ``"budget"`` — the per-task budget is already fully consumed.
      * ``"dedupe"`` — an identical image/prompt/model attempt is already in flight
        or recently sent; reuse/skip without a second outbound request.

    Cross-process atomicity does NOT rely on a count read taken before the insert
    (that read can go stale in a count/slot interleaving). Instead the slot insert
    is durably committed first, then an AUTHORITATIVE post-commit resolution re-reads
    the committed active set and decides ownership from it, so two workers/loops that
    each picked a distinct slot can never both proceed:
      * identical dedupe identity -> only the lowest-slot owner proceeds; a later
        duplicate releases its slot and reports ``dedupe``.
      * budget -> only the ``budget`` lowest-slot rows survive; a row beyond that
        rank releases itself and reports ``budget``.
    ``UNIQUE(task_id, slot)`` still prevents two reservers from taking the same slot
    (recount-and-retry on collision). A released row consumes nothing and stays
    visible in the ledger for traceability."""
    for _ in range(budget + 16):
        # Fast-path: an identical in-flight or already-sent attempt already owns
        # this dedupe identity -> reuse without a second outbound call.
        dup = (
            resv_session.query(LabelingReservation)
            .filter(
                LabelingReservation.task_id == task_id,
                LabelingReservation.dedupe_key == dedupe_key,
                LabelingReservation.status.in_(("reserved", "sent")),
            )
            .first()
        )
        if dup is not None:
            return {"outcome": "dedupe"}
        spent = _budget_spent(resv_session, task_id)
        if spent >= budget:
            return {"outcome": "budget", "spent": spent}
        max_slot = (
            resv_session.query(LabelingReservation.slot)
            .filter(LabelingReservation.task_id == task_id)
            .order_by(LabelingReservation.slot.desc())
            .first()
        )
        next_slot = (max_slot[0] + 1) if max_slot else 0
        row = LabelingReservation(
            task_id=task_id, slot=next_slot, dedupe_key=dedupe_key,
            image_hash=image_hash, status="reserved",
        )
        resv_session.add(row)
        try:
            resv_session.commit()
        except IntegrityError:
            # Another reserver claimed this slot; recount and retry.
            resv_session.rollback()
            continue
        # Authoritative post-commit resolution against the committed active set.
        active = (
            resv_session.query(LabelingReservation)
            .filter(
                LabelingReservation.task_id == task_id,
                LabelingReservation.status.in_(("reserved", "sent")),
            )
            .order_by(LabelingReservation.slot.asc())
            .all()
        )
        same_key = [r for r in active if r.dedupe_key == dedupe_key]
        if same_key and same_key[0].id != row.id:
            # A lower-slot reserver already owns this identical attempt.
            row.status = "released"
            resv_session.commit()
            return {"outcome": "dedupe"}
        winners = {r.id for r in active[:budget]}
        if row.id in winners:
            return {"outcome": "reserved", "reservation_id": row.id}
        # We lost the budget race: release our own slot (consumes nothing) and
        # recount — the next iteration sees the winner and reports ``budget``.
        row.status = "released"
        resv_session.commit()
        continue
    return {"outcome": "budget", "spent": budget}


def _finalize_reservation(resv_session, reservation_id: int, *, attempted: bool) -> None:
    """Commit the terminal state of a reservation (C-005).

    ``attempted`` True -> ``sent`` (a real outbound POST happened; durable spend).
    ``attempted`` False -> ``released`` (admission timeout / local rejection before
    any outbound byte; frees the slot, consumes nothing)."""
    row = resv_session.get(LabelingReservation, reservation_id)
    if row is None:
        return
    row.status = "sent" if attempted else "released"
    resv_session.commit()


def _attempt_consumed(cand: "labeling.LabelCandidate") -> bool:
    """Whether a candidate reflects an actual outbound attempt (C-005)."""
    if cand.status in _RESPONDED_STATUSES:
        return True
    if cand.status == "unavailable":
        return False
    return bool(getattr(cand, "attempted", False))


def _cache_get(resv_session, task_id: int, cache_key: str):
    return (
        resv_session.query(LabelingCache)
        .filter(LabelingCache.task_id == task_id, LabelingCache.cache_key == cache_key)
        .first()
    )


def _cache_put(resv_session, task_id: int, *, cache_key: str, image_hash: str,
               cand: "labeling.LabelCandidate") -> None:
    """Persist a labeled fallback result and evict beyond the bounded per-task cap."""
    if _cache_get(resv_session, task_id, cache_key) is not None:
        return
    resv_session.add(LabelingCache(
        task_id=task_id, cache_key=cache_key, image_hash=image_hash,
        status=cand.status, label=cand.label, confidence=cand.confidence,
        model=cand.model,
    ))
    try:
        resv_session.commit()
    except IntegrityError:
        resv_session.rollback()
        return
    # Bounded eviction (oldest first).
    count = (
        resv_session.query(LabelingCache)
        .filter(LabelingCache.task_id == task_id).count()
    )
    if count > _LABEL_CACHE_MAX_PER_TASK:
        stale = (
            resv_session.query(LabelingCache)
            .filter(LabelingCache.task_id == task_id)
            .order_by(LabelingCache.id)
            .limit(count - _LABEL_CACHE_MAX_PER_TASK)
            .all()
        )
        for r in stale:
            resv_session.delete(r)
        resv_session.commit()


def _valid_cached_label(label, confidence, permitted: set) -> bool:
    """Whether a persisted/cached Teacher result is still trustworthy to reuse
    (C-005). A corrupted cache row (unsupported label, or confidence that is a
    bool/non-number/non-finite/out-of-range) must NEVER authorize a classification;
    it is treated as a miss so the caller re-labels under budget instead."""
    if label not in permitted:
        return False
    if confidence is None:
        return True
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return False
    return math.isfinite(confidence) and 0.0 <= float(confidence) <= 1.0


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
    # per-task budget (reservation ledger) both apply (C-005).
    job_cap = config.AUTOLEARN_LABEL_JOB_MAX
    if limit is not None:
        job_cap = min(job_cap, max(0, limit))
    budget = config.AUTOLEARN_LABEL_BUDGET_PER_TASK

    labeled = cached = failed = suppressed = deduped = attempts = 0
    seen_in_job: dict[str, TrainingSample] = {}
    resv_session, independent = _reservation_session(session)
    try:
        for s in pending:
            # Durably commit each sample's result/audit as it completes and NEVER
            # hold the job's write transaction open across an independent reservation
            # commit or the outbound network call (C-005): the independent
            # reservation session serializes on the shared SQLite file, so a
            # long-lived job writer would self-lock it. Partial jobs stay traceable.
            # Within-job duplicate suppression / durable cached reuse: a repeated
            # identical image reuses the first result rather than paying a call.
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
                session.commit()
                cached += 1
                seen_in_job[s.image_hash] = s
                continue

            if attempts >= job_cap:
                _audit(session, task, s, status="suppressed_budget")  # zero attempts
                session.commit()
                suppressed += 1
                continue

            # Validate LOCAL input BEFORE reserving budget (C-005): an oversize
            # image never contacts the provider, so it must consume nothing.
            image_bytes = Path(s.image_path).read_bytes()
            if len(image_bytes) > config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES:
                s.teacher_status = "error"
                s.teacher_prompt = task.visual_prompt
                _audit(session, task, s, status="error")  # local, zero attempts
                session.commit()
                failed += 1
                continue

            dkey = _dedupe_key(s.image_hash, task.visual_prompt)
            resv = _reserve_attempt(resv_session, task.id, image_hash=s.image_hash,
                                    dedupe_key=dkey, budget=budget)
            if resv["outcome"] == "budget":
                _audit(session, task, s, status="suppressed_budget")  # zero attempts
                session.commit()
                suppressed += 1
                continue
            if resv["outcome"] == "dedupe":
                _audit(session, task, s, status="deduped")  # zero attempts
                session.commit()
                deduped += 1
                continue

            cand = labeling.classify_sync(image_bytes, prompt=task.visual_prompt, labels=labels)
            consumed = _attempt_consumed(cand)
            _finalize_reservation(resv_session, resv["reservation_id"], attempted=consumed)
            if consumed:
                attempts += 1
            s.teacher_status = cand.status
            # Column holds the configured model alias (stable request/version
            # identity used as the cache key). The ACTUAL provider model/revision
            # is preserved in the audit (response_model) and teacher_raw (C-007).
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
            # Durably commit this sample's result + audit before the next iteration
            # so a later sample's fault cannot roll back completed work (C-005).
            session.commit()

        task.teacher_model = task.teacher_model or config.VLM_MODEL or None
        task.status = "review" if (labeled or cached) else task.status
        session.commit()
        spent = _budget_spent(resv_session, task.id)
    finally:
        if independent:
            resv_session.close()
    return {
        "status": "done",
        "provider_configured": True,
        "labeled": labeled,
        "cached": cached,
        "deduped": deduped,
        "failed": failed,
        "suppressed_budget": suppressed,
        "attempts_made": attempts,
        "budget_remaining": max(0, budget - spent),
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

    An immutable uploaded asset (``source_id`` set, e.g. one uploaded video) is ONE
    partition no matter how many arbitrary session/group names a caller attaches —
    all of its frames must stay together, so adjacent frames can never straddle the
    train/val/test boundary. Only session-free synthetic render sessions (no
    ``source_id``) fall back to the independent per-session grouping, and that
    string is kept identical to the historical form so existing synthetic splits
    hash the same. The caller's free-form ``group_key`` never subdivides a source."""
    if r.source_id is not None:
        return f"src:{r.source_id}"
    return f"src:none|ses:{r.session_id}"


def build_split_plan(session: Session, task: AutoLearnTask) -> dataset.SplitPlan:
    rows = _verified_rows(session, task)

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


_ARTIFACT_PROVENANCE_FIELDS = (
    ("class_mapping", "class_mapping"),
    ("encoder_name", "encoder_name"),
    ("encoder_weights_version", "encoder_weights_version"),
    ("preprocess_version", "preprocess_version"),
    ("dataset_hash", "dataset_hash"),
    ("split_hash", "split_hash"),
)

_NO_EXTRA = object()


def _load_verified_artifact(version: ModelVersion, *, require_complete: bool = True):
    """Load a Student artifact and verify its stored provenance matches the
    registry row (C-008/C-009).

    A missing artifact file raises ``FileNotFoundError``; a corrupt/unpicklable
    archive is normalized to a bounded ``AutoLearnError`` (never a raw 500). When
    the loaded artifact carries provenance it must MATCH its row (class mapping +
    ordering, encoder/preprocess identity, dataset/split hashes); when
    ``require_complete`` (gate/evaluate/activate/rollback) every provenance field is
    also MANDATORY, so an empty/partial-provenance archive or a reversed class
    mapping is refused rather than silently trusted. A bare mock classifier without
    an ``.extra`` attribute (unit fixtures) skips the metadata check."""
    try:
        clf = student.StudentClassifier.load(version.artifact_path)
    except FileNotFoundError:
        raise
    except AutoLearnError:
        raise
    except Exception as exc:  # noqa: BLE001 — corrupt/unpicklable archive
        raise AutoLearnError(f"artifact could not be loaded ({type(exc).__name__})")

    extra = getattr(clf, "extra", _NO_EXTRA)
    if extra is _NO_EXTRA:
        return clf  # bare mock fixture: no provenance to verify
    if not isinstance(extra, dict):
        raise AutoLearnError("artifact provenance is missing or malformed")

    if require_complete:
        missing = [field for field, _ in _ARTIFACT_PROVENANCE_FIELDS if not extra.get(field)]
        if missing:
            raise AutoLearnError(
                "artifact is missing required provenance: " + ", ".join(missing)
            )

    mismatches = []
    for field, attr in _ARTIFACT_PROVENANCE_FIELDS:
        value = extra.get(field)
        if value is not None and value != getattr(version, attr):
            mismatches.append(field)
    # The saved model's class ordering must agree with the registry class mapping
    # (classes[i] -> i); a reversed mapping would invert every prediction (C-008).
    classes = getattr(clf, "classes", None)
    if classes is not None and version.class_mapping:
        if {c: i for i, c in enumerate(classes)} != version.class_mapping:
            mismatches.append("class_ordering")
    if mismatches:
        raise AutoLearnError(
            "artifact provenance does not match its registry row: " + ", ".join(mismatches)
        )
    return clf


def _reserve_version(session: Session, task: AutoLearnTask, plan, enc) -> ModelVersion:
    """Transactionally claim a unique (task_id, version) + artifact path BEFORE
    fitting (C-008). Two concurrent trains can never both claim v1: the
    ``UNIQUE(task_id, version)`` insert collides and this recounts/retries, so each
    job owns a distinct version number and a distinct immutable artifact path."""
    model_dir = config.AUTOLEARN_MODEL_DIR / f"task_{task.id}"
    model_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(128):
        top = (
            session.query(ModelVersion.version)
            .filter(ModelVersion.task_id == task.id)
            .order_by(ModelVersion.version.desc())
            .first()
        )
        version_no = (top[0] + 1) if top else 1
        artifact = model_dir / f"v{version_no}.pt"
        mv = ModelVersion(
            task_id=task.id, version=version_no, artifact_path=str(artifact),
            encoder_name=encoder.ENCODER_NAME, encoder_weights_version=enc.weights_tag,
            preprocess_version=encoder.PREPROCESS_VERSION, class_mapping=plan.class_mapping,
            dataset_hash=plan.dataset_hash, split_hash=plan.split_hash,
            train_count=plan.counts["train"], val_count=plan.counts["val"],
            test_count=plan.counts["test"], threshold=0.5, metrics=None,
            train_duration_ms=0.0, environment=student.environment_info(),
            status="training",
        )
        session.add(mv)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            continue
        return mv
    raise AutoLearnError("could not reserve a unique model version (too many collisions)")


def _artifact_sha256(path) -> str | None:
    """SHA-256 of the artifact file bytes, or None if unreadable (C-002).

    Bound into the evaluated metrics so the gate can refuse metrics that were
    computed against a DIFFERENT artifact than the one currently on disk (tampered /
    swapped weights that still load but no longer produce the measured quality)."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _manifest_digest(members: list[tuple]) -> str:
    """Deterministic digest of a frozen membership list (C-002).

    ``members`` is an iterable of (split, sample_id, image_hash, verified_label).
    The same function hashes the in-memory split at train time and the persisted
    ModelVersionSample rows at gate/eval time, so a changed/removed row is caught."""
    items = sorted(f"{split}:{sid}:{h}:{lab}" for (split, sid, h, lab) in members)
    return hashlib.sha256("|".join(items).encode()).hexdigest()


def train(session: Session, task: AutoLearnTask) -> ModelVersion:
    """Fit, threshold-select on validation, save, and register a Student version.

    Held-out test metrics are computed and stored so the activation gate has real
    numbers to check. The test split is never used for fitting or thresholding. The
    version identity and immutable artifact path are reserved transactionally
    BEFORE fitting; the artifact is written to a private temp file and atomically
    renamed into place, so concurrent trains never reference an overwritten v1.pt
    (C-008)."""
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

    mv = _reserve_version(session, task, plan, enc)
    artifact = Path(mv.artifact_path)
    tmp_path: Path | None = None

    try:
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

        # Atomic temp -> final write: a crash/collision never leaves a partial
        # or cross-version artifact at the canonical path (C-008).
        fd, tmp_name = tempfile.mkstemp(
            dir=str(artifact.parent), prefix=f".{artifact.stem}.", suffix=".tmp"
        )
        os.close(fd)
        tmp_path = Path(tmp_name)  # tracked for cleanup on failure
        clf.save(
            str(tmp_path),
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
        os.replace(tmp_path, artifact)

        # Held-out test metrics + the frozen-manifest digest they were computed
        # against, so the gate can refuse stale/unproven metrics (C-002).
        test_metrics = _evaluate_rows(clf, by_split["test"], pos, threshold)
        members = [
            (split_name, r.id, r.image_hash, r.verified_label)
            for split_name, split_rows in by_split.items()
            for r in split_rows
        ]
        test_metrics["manifest_digest"] = _manifest_digest(members)
        # Bind the exact artifact bytes these metrics were measured against (C-002).
        test_metrics["artifact_sha256"] = _artifact_sha256(artifact)

        mv.threshold = threshold
        mv.metrics = test_metrics
        mv.train_duration_ms = tr.duration_ms
        mv.status = "trained"

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
    except Exception:
        # Record the failed version and clean up ONLY this job's own artifact; never
        # touch another version's file (C-008).
        try:
            session.rollback()
            mv2 = session.get(ModelVersion, mv.id)
            if mv2 is not None:
                mv2.status = "failed"
                session.commit()
        except Exception:  # noqa: BLE001
            session.rollback()
        for p in (artifact, tmp_path):
            try:
                if p is not None and p.exists():
                    p.unlink()
            except OSError:
                pass
        raise


def _validate_proba(probs, n: int) -> "np.ndarray":
    """Return a validated 1-D probability array or raise (C-002).

    The RAW output type and shape are validated BEFORE any float coercion: a bool
    array, a string/object array (incl. numeric strings like ``"0.5"``), or a
    multi-dimensional array (a (N,1) column or (1,N) row) is a broken model, not a
    passing one — np coercion would silently paper over it. Only a genuine real
    numeric 1-D array with exactly one finite value per row in [0, 1] is accepted;
    anything else raises so metrics are never computed from it and classification
    returns an explicit unknown instead."""
    arr = np.asarray(probs)
    if arr.dtype == np.bool_:
        raise AutoLearnError("student produced boolean outputs, not probabilities")
    if not np.issubdtype(arr.dtype, np.number) or np.issubdtype(arr.dtype, np.complexfloating):
        raise AutoLearnError(
            f"student produced non-numeric outputs (dtype {arr.dtype}), not probabilities"
        )
    if arr.ndim != 1:
        raise AutoLearnError(
            f"student probabilities must be 1-D (got shape {tuple(arr.shape)})"
        )
    if arr.shape[0] != n:
        raise AutoLearnError(
            f"student produced {arr.shape[0]} probabilities for {n} inputs (wrong shape)"
        )
    arr = arr.astype(np.float64)
    if not np.all(np.isfinite(arr)):
        raise AutoLearnError("student produced non-finite probabilities")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise AutoLearnError("student produced probabilities outside [0, 1]")
    return arr


def _evaluate_rows(clf, rows: list[TrainingSample], pos: str, threshold: float) -> dict:
    if not rows:
        return {"note": "empty test split", "support": 0}
    X, latencies = _embed(rows)
    y = np.array([1 if r.verified_label == pos else 0 for r in rows], dtype=np.int64)
    probs = _validate_proba(clf.predict_proba(X), len(rows))
    pred = (probs >= threshold).astype(np.int64)
    m = metrics.binary_metrics(y, pred)
    m["latency"] = metrics.latency_percentiles(latencies)
    m["threshold"] = threshold
    return m


def _frozen_manifest(session: Session, version: ModelVersion) -> dict:
    """Validate and digest the version's COMPLETE frozen membership (C-002).

    Fails closed on ANY inconsistency: a missing manifest (incl. versions created
    before manifests existed), a per-split count that disagrees with the registry
    row, a duplicated sample membership, a referenced sample that no longer exists,
    or a changed content hash / verified label. Returns the per-split rows plus a
    digest the gate compares against the digest the metrics were computed under, so
    cached metrics from an older membership can never pass."""
    manifest = (
        session.query(ModelVersionSample)
        .filter(ModelVersionSample.model_version_id == version.id)
        .order_by(ModelVersionSample.split, ModelVersionSample.sample_id)
        .all()
    )
    if not manifest:
        raise AutoLearnError("no frozen dataset manifest for this version")
    seen: set[int] = set()
    by_split: dict[str, list[TrainingSample]] = {"train": [], "val": [], "test": []}
    members: list[tuple] = []
    for ms in manifest:
        if ms.split not in by_split:
            raise AutoLearnError(f"manifest has unknown split {ms.split!r}")
        if ms.sample_id in seen:
            raise AutoLearnError(f"manifest sample {ms.sample_id} appears more than once")
        seen.add(ms.sample_id)
        s = session.get(TrainingSample, ms.sample_id)
        if s is None:
            raise AutoLearnError(f"manifest sample {ms.sample_id} no longer exists")
        if s.image_hash != ms.image_hash:
            raise AutoLearnError(f"manifest sample {ms.sample_id} content changed")
        # Bind the ACTUAL image bytes on disk, not just the recorded DB hash (C-002):
        # a file whose bytes were swapped under an unchanged DB hash must fail closed.
        # (If the file is absent — e.g. pure-DB unit fixtures — the DB-hash check
        # above already applies; embedding would fail later for a real evaluation.)
        try:
            disk_bytes = Path(s.image_path).read_bytes()
        except OSError:
            disk_bytes = None
        if disk_bytes is not None and hashlib.sha256(disk_bytes).hexdigest() != ms.image_hash:
            raise AutoLearnError(f"manifest sample {ms.sample_id} image bytes changed on disk")
        if not s.verified or s.verified_label != ms.verified_label:
            raise AutoLearnError(f"manifest sample {ms.sample_id} verified label changed")
        by_split[ms.split].append(s)
        members.append((ms.split, ms.sample_id, ms.image_hash, ms.verified_label))
    for split, expected in (
        ("train", version.train_count),
        ("val", version.val_count),
        ("test", version.test_count),
    ):
        if len(by_split[split]) != expected:
            raise AutoLearnError(
                f"frozen {split} membership ({len(by_split[split])}) != registry "
                f"count ({expected}); membership is inconsistent"
            )
    return {"by_split": by_split, "digest": _manifest_digest(members)}


def evaluate(session: Session, version: ModelVersion) -> dict:
    """Recompute held-out metrics from the reloaded artifact over the version's
    OWN complete frozen manifest (C-002). On an inconsistent/missing snapshot, an
    unloadable/mismatched artifact, or a non-finite prediction the metrics are
    replaced with a fail-closed marker so the gate denies until a real, valid
    re-evaluation succeeds. The stored metrics carry the manifest digest they were
    computed against so a later membership change invalidates them."""
    task = session.get(AutoLearnTask, version.task_id)
    try:
        info = _frozen_manifest(session, version)
        clf = _load_verified_artifact(version)
        m = _evaluate_rows(clf, info["by_split"]["test"], task.positive_label, version.threshold)
        m["manifest_digest"] = info["digest"]
        m["artifact_sha256"] = _artifact_sha256(version.artifact_path)
    except (AutoLearnError, FileNotFoundError) as exc:
        version.metrics = {"error": str(exc), "support": 0, "f1": None}
        session.commit()
        return version.metrics
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
    clf = _load_verified_artifact(version)
    # Shadow runs on the version's OWN frozen held-out manifest (C-002), so it
    # never leaks rows the Student trained on after a later retrain reshuffle.
    rows = _frozen_manifest(session, version)["by_split"]["test"]
    if not rows:
        return {"compared": 0, "items": [], "note": "no test rows"}
    X, _ = _embed(rows)
    probs = _validate_proba(clf.predict_proba(X), len(rows))
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


def gate_status(version: ModelVersion, session: Session | None = None) -> dict:
    """Fail-closed activation gate (C-002).

    When a ``session`` is supplied (every real caller) the gate first verifies the
    COMPLETE current frozen manifest (counts, unique membership, existing samples,
    matching hashes/labels) and that the stored metrics were actually computed
    against THIS manifest (digest match). Old/unproven snapshots fail closed until a
    real re-evaluation. It then requires: finite f1; evaluated support equal to the
    frozen snapshot test count; both classes present; support >= min_test; and
    f1 >= min_f1. Any inconsistency denies.
    """
    m = version.metrics or {}
    f1 = m.get("f1")
    support = m.get("support", 0)
    positives = m.get("positives")
    negatives = m.get("negatives")
    snapshot_test = version.test_count
    reasons: list[str] = []

    if session is not None:
        try:
            info = _frozen_manifest(session, version)
            if m.get("manifest_digest") != info["digest"]:
                reasons.append(
                    "stored metrics were not computed against the current frozen "
                    "manifest; re-evaluate before activation (fail-closed)"
                )
        except AutoLearnError as exc:
            reasons.append(f"frozen manifest inconsistent: {exc}")
        # Bind the artifact bytes the metrics were measured against (C-002): tampered
        # weights that still load but change quality must invalidate the gate.
        stored_hash = m.get("artifact_sha256")
        current_hash = _artifact_sha256(version.artifact_path)
        if not stored_hash:
            reasons.append(
                "stored metrics are not bound to an artifact hash; re-evaluate "
                "before activation (fail-closed)"
            )
        elif current_hash is None:
            reasons.append("artifact file is missing or unreadable")
        elif current_hash != stored_hash:
            reasons.append(
                "artifact bytes changed since evaluation; re-evaluate before "
                "activation (fail-closed)"
            )

    # Strict F1 validation (C-002): a real finite number in [0, 1]. bool, NaN/inf,
    # numeric strings and out-of-range values can never pass or be serialized raw.
    f1_valid = (
        isinstance(f1, (int, float)) and not isinstance(f1, bool)
        and math.isfinite(f1) and 0.0 <= float(f1) <= 1.0
    )
    if f1 is None:
        reasons.append("no held-out metrics; run evaluate first")
    elif not f1_valid:
        reasons.append(f"held-out F1 is not a finite number in [0, 1] ({f1!r})")

    if not isinstance(support, int) or isinstance(support, bool) or support != snapshot_test:
        reasons.append(
            f"evaluated support {support!r} != frozen snapshot test count {snapshot_test}; "
            "membership is inconsistent"
        )
    if snapshot_test < config.AUTOLEARN_GATE_MIN_TEST:
        reasons.append(
            f"test support {snapshot_test} < required {config.AUTOLEARN_GATE_MIN_TEST}"
        )
    if not isinstance(positives, int) or isinstance(positives, bool) \
            or not isinstance(negatives, int) or isinstance(negatives, bool) \
            or positives < 1 or negatives < 1:
        reasons.append(
            f"held-out set must contain both classes (positives={positives!r}, negatives={negatives!r})"
        )
    if f1_valid and float(f1) < config.AUTOLEARN_GATE_MIN_F1:
        reasons.append(f"held-out F1 {f1} < gate {config.AUTOLEARN_GATE_MIN_F1}")

    passed = not reasons
    return {
        "passed": passed,
        # Only ever surface a JSON-safe F1 (never raw NaN/inf/bool/string).
        "f1": float(f1) if f1_valid else None,
        "support": support if (isinstance(support, int) and not isinstance(support, bool)) else None,
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
    gate = gate_status(version, session)
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

    # Verify the artifact is loadable and matches its registry row before trusting
    # it as the active model (C-008). A broken/mismatched artifact never activates.
    try:
        _load_verified_artifact(version)
    except (AutoLearnError, FileNotFoundError) as exc:
        session.add(ActivationEvent(task_id=task.id, model_version_id=version.id, action="reject",
                                    decided_by=approver, reason=f"artifact unusable: {exc}",
                                    gate_passed=False))
        session.commit()
        return {"activated": False, "reason": f"artifact unusable: {exc}", "gate": gate}

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
    """Restore the most recent previously-active (archived) version — but only if
    it is genuinely usable (C-009).

    The target artifact is loaded and its provenance verified, its frozen manifest
    is re-validated and its metrics must still clear the gate against that manifest,
    ALL before the active pointer is moved. A missing/corrupt/mismatched target
    raises a bounded failure, the current active version keeps working, and NO
    gate_passed=true rollback record is written."""
    current = session.get(ModelVersion, task.active_version_id) if task.active_version_id else None
    prev = (
        session.query(ModelVersion)
        .filter(ModelVersion.task_id == task.id, ModelVersion.status == "archived")
        .order_by(ModelVersion.version.desc())
        .first()
    )
    if prev is None:
        raise AutoLearnError("no previous version available to roll back to")

    # Verify BEFORE switching: load+provenance-check the artifact and re-run the
    # full gate (manifest completeness + proven metrics) against the target.
    try:
        _load_verified_artifact(prev)
    except (AutoLearnError, FileNotFoundError) as exc:
        raise AutoLearnError(
            f"cannot roll back to version {prev.version}: artifact unusable ({exc}); "
            "current active version is unchanged"
        )
    gate = gate_status(prev, session)
    if not gate["passed"]:
        raise AutoLearnError(
            f"cannot roll back to version {prev.version}: it no longer passes the "
            f"held-out gate ({'; '.join(gate['reasons'])}); current active version is unchanged"
        )

    if current is not None:
        current.status = "rolled_back"
    prev.status = "active"
    task.active_version_id = prev.id
    session.add(ActivationEvent(task_id=task.id, model_version_id=prev.id, action="rollback",
                                decided_by=approver, reason="rollback to verified previous version",
                                gate_passed=True))
    session.commit()
    return {"rolled_back_to": prev.version}


# --------------------------------------------------------------- offline classify


def classify_offline(session: Session, task: AutoLearnTask, image_bytes: bytes) -> dict:
    """Offline classification using the active Student. Low-margin predictions
    fall back to the Teacher (budgeted, non-actioning) or an explicit unknown.
    This NEVER dispatches a workflow action."""
    if not task.active_version_id:
        return {"status": "unavailable", "detail": "no active Student version", "action": "none"}
    version = session.get(ModelVersion, task.active_version_id)
    # Load through the VERIFIED loader so the active route can never classify with a
    # mismatched/wrong-row artifact while reporting this version (C-008). A
    # missing/unusable/mismatched artifact is a bounded unavailable state, not a 500.
    try:
        clf = _load_verified_artifact(version, require_complete=False)
    except FileNotFoundError:
        return {"status": "unavailable", "detail": "active Student artifact is missing", "action": "none"}
    except AutoLearnError as exc:
        return {"status": "unavailable", "detail": f"active Student artifact unusable: {exc}", "action": "none"}
    except Exception:  # noqa: BLE001
        return {"status": "unavailable", "detail": "active Student artifact could not be loaded", "action": "none"}
    enc = encoder.get_encoder()
    X, _ = enc.embed_bytes([image_bytes])
    # A non-finite / out-of-range probability is an explicit unknown, never a NaN
    # serialized into the response or a crash (C-002).
    try:
        p = float(_validate_proba(clf.predict_proba(X), 1)[0])
    except AutoLearnError as exc:
        return {"status": "unknown", "detail": str(exc), "action": "none"}
    pos, neg = task.positive_label, task.negative_label
    margin = abs(p - version.threshold)
    if margin < config.AUTOLEARN_STUDENT_MIN_MARGIN:
        # Fall back to Teacher if available AND within the durable per-task
        # budget; otherwise explicit unknown (C-005). The fallback never actions.
        if labeling.provider_configured():
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            cache_key = _dedupe_key(image_hash, task.visual_prompt)
            # Reuse an identical cached label (training-sample OR persistent fallback
            # cache) before spending any attempt.
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
            if cached is not None and _valid_cached_label(
                cached.teacher_label, cached.teacher_confidence, {pos, neg}
            ):
                return {
                    "status": "teacher_fallback", "student_confidence": round(p, 4),
                    "margin": round(margin, 4), "teacher_status": "cache_hit",
                    "label": cached.teacher_label, "action": "none",
                }
            resv_session, independent = _reservation_session(session)
            try:
                cache_row = _cache_get(resv_session, task.id, cache_key)
                if cache_row is not None and cache_row.status == "labeled":
                    # Strictly re-validate the persisted cache before trusting it
                    # (C-005): a corrupted row never authorizes a classification.
                    if _valid_cached_label(cache_row.label, cache_row.confidence, {pos, neg}):
                        return {
                            "status": "teacher_fallback", "student_confidence": round(p, 4),
                            "margin": round(margin, 4), "teacher_status": "cache_hit",
                            "label": cache_row.label, "action": "none",
                        }
                    resv_session.delete(cache_row)
                    resv_session.commit()
                resv = _reserve_attempt(
                    resv_session, task.id, image_hash=image_hash,
                    dedupe_key=cache_key, budget=config.AUTOLEARN_LABEL_BUDGET_PER_TASK,
                )
                if resv["outcome"] == "budget":
                    return {
                        "status": "unknown",
                        "detail": "student below margin; Teacher budget exhausted for this task",
                        "student_confidence": round(p, 4), "margin": round(margin, 4),
                        "action": "none",
                    }
                if resv["outcome"] == "dedupe":
                    return {
                        "status": "unknown",
                        "detail": "student below margin; identical Teacher fallback already in flight",
                        "student_confidence": round(p, 4), "margin": round(margin, 4),
                        "action": "none",
                    }
                cand = labeling.classify_sync(image_bytes, prompt=task.visual_prompt, labels=[pos, neg])
                consumed = _attempt_consumed(cand)
                _finalize_reservation(resv_session, resv["reservation_id"], attempted=consumed)
                if cand.status == "labeled":
                    _cache_put(resv_session, task.id, cache_key=cache_key,
                               image_hash=image_hash, cand=cand)
            finally:
                if independent:
                    resv_session.close()
            _audit_freeform(session, task, status=cand.status, image_hash=image_hash,
                            latency_ms=cand.latency_ms, provider_host=cand.provider_host,
                            model=cand.model, method=cand.method)
            session.commit()
            return {
                "status": "teacher_fallback", "student_confidence": round(p, 4),
                "margin": round(margin, 4), "teacher_status": cand.status,
                "label": cand.label if cand.status == "labeled" else None, "action": "none",
            }
        return {
            "status": "unknown",
            "detail": "student confidence below margin and no Teacher provider configured",
            "student_confidence": round(p, 4), "margin": round(margin, 4), "action": "none",
        }
    label = pos if p >= version.threshold else neg
    return {
        "status": "student", "label": label, "confidence": round(p, 4),
        "version": version.version, "action": "none",
    }
