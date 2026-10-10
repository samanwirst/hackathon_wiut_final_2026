"""AutoLearn API router (M3 experimental, explicitly UNVERIFIED).

Mounted at ``/api/autolearn``. These endpoints drive an isolated Teacher ->
human review -> Student vertical slice. Nothing here dispatches a workflow
action. Every response carries ``experimental: true`` so the UI can keep the
status visible.
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import config
from app.autolearn import labeling, service
from app.autolearn.encoder import EncoderUnavailable
from app.autolearn.schemas import (
    ActivateRequest,
    DecisionRequest,
    ReviewRequest,
    SampleOut,
    SyntheticImportRequest,
    TaskCreate,
    TaskOut,
)
from app.db import (
    ActivationEvent,
    AutoLearnTask,
    LabelingAudit,
    ModelVersion,
    TrainingSample,
    get_session,
)

router = APIRouter(prefix="/api/autolearn", tags=["autolearn"])

EXPERIMENTAL_NOTE = (
    "AutoLearn is an isolated experimental vertical slice. Teacher labeling, "
    "held-out quality, and cost remain UNVERIFIED until run on real labeled "
    "data with human verification. No workflow action is ever dispatched here."
)


def db() -> Session:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def _task_or_404(session: Session, task_id: int) -> AutoLearnTask:
    task = session.get(AutoLearnTask, task_id)
    if task is None:
        raise HTTPException(404, "autolearn task not found")
    return task


def _sample_out(s: TrainingSample) -> SampleOut:
    return SampleOut(
        id=s.id, task_id=s.task_id, session_id=s.session_id, group_key=s.group_key,
        image_hash=s.image_hash, origin=s.origin,
        image_url=f"/api/autolearn/images/{s.id}",
        video_timestamp=s.video_timestamp, teacher_status=s.teacher_status,
        teacher_label=s.teacher_label, teacher_confidence=s.teacher_confidence,
        verified=s.verified, verified_label=s.verified_label, verified_by=s.verified_by,
        verified_at=s.verified_at, split=s.split,
    )


@router.get("/status")
def autolearn_status():
    return {
        "experimental": True,
        "verified": False,
        "note": EXPERIMENTAL_NOTE,
        "provider_configured": labeling.provider_configured(),
        "gate": {
            "min_f1": config.AUTOLEARN_GATE_MIN_F1,
            "min_test": config.AUTOLEARN_GATE_MIN_TEST,
        },
    }


# ------------------------------------------------------------------- tasks


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, session: Session = Depends(db)):
    try:
        task = service.create_task(
            session, name=body.name, visual_prompt=body.visual_prompt,
            positive_label=body.positive_label, negative_label=body.negative_label,
            teacher_model=body.teacher_model,
        )
    except service.AutoLearnError as exc:
        raise HTTPException(422, str(exc))
    return task


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(session: Session = Depends(db)):
    return session.query(AutoLearnTask).order_by(AutoLearnTask.id.desc()).all()


@router.get("/tasks/{task_id}")
def get_task(task_id: int, session: Session = Depends(db)):
    task = _task_or_404(session, task_id)
    samples = session.query(TrainingSample).filter(TrainingSample.task_id == task_id).all()
    versions = (
        session.query(ModelVersion)
        .filter(ModelVersion.task_id == task_id)
        .order_by(ModelVersion.version.desc())
        .all()
    )
    verified = [s for s in samples if s.verified]
    return {
        "experimental": True,
        "task": TaskOut.model_validate(task, from_attributes=True).model_dump(),
        "counts": {
            "samples": len(samples),
            "verified": len(verified),
            "pending_teacher": sum(1 for s in samples if s.teacher_status == "pending"),
            "sessions": len({s.session_id for s in samples}),
        },
        "versions": [
            {
                "id": v.id, "version": v.version, "status": v.status,
                "threshold": v.threshold, "metrics": v.metrics,
                "train_count": v.train_count, "val_count": v.val_count,
                "test_count": v.test_count, "train_duration_ms": v.train_duration_ms,
                "encoder": v.encoder_name, "encoder_weights": v.encoder_weights_version,
                "dataset_hash": v.dataset_hash, "split_hash": v.split_hash,
                "created_at": v.created_at,
            }
            for v in versions
        ],
    }


@router.post("/tasks/{task_id}/import-synthetic")
def import_synthetic(task_id: int, body: SyntheticImportRequest, session: Session = Depends(db)):
    task = _task_or_404(session, task_id)
    count = service.import_synthetic_qa(
        session, task, n_sessions=body.n_sessions,
        per_class_per_session=body.per_class_per_session,
    )
    return {
        "experimental": True,
        "qa_only": True,
        "disclosure": "Synthetic procedural images; NOT natural footage. No quality claim.",
        "imported": count,
    }


@router.post("/tasks/{task_id}/images", status_code=201)
def upload_image(
    task_id: int,
    session_id: str,
    file: UploadFile = File(...),
    group_key: str | None = None,
    video_timestamp: float | None = None,
    source_id: int | None = None,
    session: Session = Depends(db),
):
    task = _task_or_404(session, task_id)
    data = file.file.read(config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES + 1)
    if len(data) > config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES:
        raise HTTPException(413, "image exceeds size cap")
    try:
        from PIL import Image

        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(400, "file is not a readable image")
    row = service.import_image(
        session, task, image_bytes=data, session_id=session_id,
        group_key=group_key, video_timestamp=video_timestamp, source_id=source_id,
    )
    if row is None:
        return {"imported": False, "reason": "duplicate image content (skipped)"}
    return {"imported": True, "sample_id": row.id}


@router.get("/tasks/{task_id}/samples", response_model=list[SampleOut])
def list_samples(task_id: int, session: Session = Depends(db)):
    _task_or_404(session, task_id)
    rows = (
        session.query(TrainingSample)
        .filter(TrainingSample.task_id == task_id)
        .order_by(TrainingSample.id)
        .all()
    )
    return [_sample_out(s) for s in rows]


@router.get("/tasks/{task_id}/contact-sheet")
def contact_sheet(task_id: int, session: Session = Depends(db)):
    """A concrete manifest for human verification: each sample with its image URL,
    Teacher candidate, and current verification state."""
    _task_or_404(session, task_id)
    rows = (
        session.query(TrainingSample)
        .filter(TrainingSample.task_id == task_id)
        .order_by(TrainingSample.session_id, TrainingSample.id)
        .all()
    )
    return {
        "experimental": True,
        "task_id": task_id,
        "note": "Only human-verified labels enter training.",
        "items": [
            {
                "sample_id": s.id, "session_id": s.session_id, "image_url": f"/api/autolearn/images/{s.id}",
                "teacher_status": s.teacher_status, "teacher_label": s.teacher_label,
                "teacher_confidence": s.teacher_confidence, "verified": s.verified,
                "verified_label": s.verified_label,
            }
            for s in rows
        ],
    }


@router.get("/images/{sample_id}")
def get_image(sample_id: int, session: Session = Depends(db)):
    s = session.get(TrainingSample, sample_id)
    if s is None:
        raise HTTPException(404, "sample not found")
    from pathlib import Path

    p = Path(s.image_path)
    if not p.exists():
        raise HTTPException(410, "image no longer exists")
    return Response(content=p.read_bytes(), media_type="image/jpeg")


# ------------------------------------------------------------------- labeling / review


@router.post("/tasks/{task_id}/label")
def run_labeling(task_id: int, limit: int | None = None, session: Session = Depends(db)):
    task = _task_or_404(session, task_id)
    return service.run_labeling(session, task, limit=limit)


@router.post("/samples/{sample_id}/review", response_model=SampleOut)
def review(sample_id: int, body: ReviewRequest, session: Session = Depends(db)):
    s = session.get(TrainingSample, sample_id)
    if s is None:
        raise HTTPException(404, "sample not found")
    try:
        service.review_sample(session, s, verified_label=body.verified_label, reviewer=body.reviewer)
    except service.AutoLearnError as exc:
        raise HTTPException(422, str(exc))
    return _sample_out(s)


# ------------------------------------------------------------------- train / eval


@router.post("/tasks/{task_id}/train")
def train(task_id: int, session: Session = Depends(db)):
    task = _task_or_404(session, task_id)
    try:
        mv = service.train(session, task)
    except service.dataset.DatasetError as exc:
        raise HTTPException(422, f"dataset not ready: {exc}")
    except service.AutoLearnError as exc:
        raise HTTPException(422, str(exc))
    except EncoderUnavailable as exc:
        raise HTTPException(503, f"encoder unavailable: {exc}")
    return {
        "experimental": True,
        "version": mv.version,
        "version_id": mv.id,
        "threshold": mv.threshold,
        "counts": {"train": mv.train_count, "val": mv.val_count, "test": mv.test_count},
        "metrics": mv.metrics,
        "train_duration_ms": mv.train_duration_ms,
        "dataset_hash": mv.dataset_hash,
        "split_hash": mv.split_hash,
    }


@router.post("/versions/{version_id}/evaluate")
def evaluate(version_id: int, session: Session = Depends(db)):
    v = session.get(ModelVersion, version_id)
    if v is None:
        raise HTTPException(404, "version not found")
    try:
        m = service.evaluate(session, v)
    except EncoderUnavailable as exc:
        raise HTTPException(503, f"encoder unavailable: {exc}")
    return {"experimental": True, "version": v.version, "metrics": m}


@router.get("/tasks/{task_id}/shadow")
def shadow(task_id: int, session: Session = Depends(db)):
    task = _task_or_404(session, task_id)
    try:
        return {"experimental": True, **service.shadow_compare(session, task)}
    except service.AutoLearnError as exc:
        raise HTTPException(422, str(exc))
    except EncoderUnavailable as exc:
        raise HTTPException(503, f"encoder unavailable: {exc}")


@router.get("/versions/{version_id}/gate")
def gate(version_id: int, session: Session = Depends(db)):
    v = session.get(ModelVersion, version_id)
    if v is None:
        raise HTTPException(404, "version not found")
    return {"experimental": True, "version": v.version, "gate": service.gate_status(v)}


# ------------------------------------------------------------------- activation


@router.post("/versions/{version_id}/activate")
def activate(version_id: int, body: ActivateRequest, session: Session = Depends(db)):
    v = session.get(ModelVersion, version_id)
    if v is None:
        raise HTTPException(404, "version not found")
    result = service.activate(session, v, approver=body.approver, approve=body.approve)
    return {"experimental": True, **result}


@router.post("/tasks/{task_id}/rollback")
def rollback(task_id: int, body: DecisionRequest, session: Session = Depends(db)):
    task = _task_or_404(session, task_id)
    try:
        result = service.rollback(session, task, approver=body.approver)
    except service.AutoLearnError as exc:
        raise HTTPException(422, str(exc))
    return {"experimental": True, **result}


@router.post("/tasks/{task_id}/classify")
def classify_offline(task_id: int, file: UploadFile = File(...), session: Session = Depends(db)):
    """Offline classification with the active Student (M3-AC6). Low-margin inputs
    fall back to the Teacher (budgeted, non-actioning) or an explicit unknown.
    Never dispatches a workflow action."""
    task = _task_or_404(session, task_id)
    data = file.file.read(config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES + 1)
    if len(data) > config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES:
        raise HTTPException(413, "image exceeds size cap")
    try:
        return {"experimental": True, **service.classify_offline(session, task, data)}
    except EncoderUnavailable as exc:
        raise HTTPException(503, f"encoder unavailable: {exc}")


@router.get("/tasks/{task_id}/activations")
def activations(task_id: int, session: Session = Depends(db)):
    _task_or_404(session, task_id)
    rows = (
        session.query(ActivationEvent)
        .filter(ActivationEvent.task_id == task_id)
        .order_by(ActivationEvent.id.desc())
        .all()
    )
    return [
        {
            "id": r.id, "action": r.action, "model_version_id": r.model_version_id,
            "decided_by": r.decided_by, "reason": r.reason, "gate_passed": r.gate_passed,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/tasks/{task_id}/audit")
def audit(task_id: int, session: Session = Depends(db)):
    _task_or_404(session, task_id)
    rows = (
        session.query(LabelingAudit)
        .filter(LabelingAudit.task_id == task_id)
        .order_by(LabelingAudit.id.desc())
        .all()
    )
    return [
        {
            "id": r.id, "sample_id": r.sample_id, "provider_host": r.provider_host,
            "model": r.model, "image_hash": r.image_hash, "session_id": r.session_id,
            "status": r.status, "latency_ms": r.latency_ms, "created_at": r.created_at,
        }
        for r in rows
    ]
