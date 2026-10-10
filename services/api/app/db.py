"""SQLAlchemy models and session management (SQLite, WAL mode)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app import config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class VideoSource(Base):
    __tablename__ = "video_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16), default="upload")
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    # uploaded | processing | processed | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frames_processed: Mapped[int] = mapped_column(Integer, default=0)
    avg_inference_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id"))
    name: Mapped[str] = mapped_column(String(255))
    polygon: Mapped[list] = mapped_column(JSON)  # [[x, y], ...] normalized 0..1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id"))
    name: Mapped[str] = mapped_column(String(255))
    dsl: Mapped[dict] = mapped_column(JSON)  # validated WorkflowDSL dump
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrackEvent(Base):
    __tablename__ = "track_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id"))
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"))
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    class_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    video_timestamp: Mapped[float] = mapped_column(Float)  # seconds into video
    confidence: Mapped[float] = mapped_column(Float)
    detail: Mapped[str] = mapped_column(Text, default="")
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    evidence_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | done | failed | cancelled | skipped_visual | interrupted_unverified
    # Visual routing provenance (M2). NULL for geometric-only events.
    visual_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ok | unknown | low_confidence | error | timeout | invalid_response
    # | missing_credentials | cancelled | interrupted
    # | suppressed_budget | suppressed_cooldown | suppressed_sampling
    visual_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visual_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_routing: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActionExecution(Base):
    __tablename__ = "action_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("track_events.id"))
    action_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | success | failed | rejected | cancelled
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VlmCall(Base):
    """One VLM router decision for a candidate event (M2-AC5). Persisted for
    auditable routing provenance and counters; every decision is recorded,
    including cache hits, suppressed requests and failures."""

    __tablename__ = "vlm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("track_events.id"), nullable=True)
    source_id: Mapped[int] = mapped_column(Integer)
    workflow_id: Mapped[int] = mapped_column(Integer)
    task_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    # called | cache_hit | deduped | cancelled | suppressed_budget
    # | suppressed_cooldown | suppressed_sampling | failed | unavailable
    teacher_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# AutoLearn (M3 experimental vertical slice). These tables are isolated from the
# accepted M1/M2 pipeline. No row here ever authorizes a workflow action.
# ---------------------------------------------------------------------------


class AutoLearnTask(Base):
    """A repeated binary visual classification task proposed for specialization.

    Labels are operator-configurable (e.g. ``occupied`` vs ``empty``). The task
    tracks only provenance/status; verified labels live on the samples and model
    artifacts live on ModelVersion. ``active_version_id`` is the Student version
    currently approved for *offline* classification only (never dispatch)."""

    __tablename__ = "autolearn_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    visual_prompt: Mapped[str] = mapped_column(Text)
    positive_label: Mapped[str] = mapped_column(String(64))
    negative_label: Mapped[str] = mapped_column(String(64))
    teacher_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="collecting")
    # collecting | labeling | review | trained | active
    active_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrainingSample(Base):
    """One dataset image/crop for an AutoLearn task with full provenance.

    A Teacher *candidate* label is advisory only. Training uses exclusively
    human-verified labels (``verified`` True with an immutable ``verified_label``).
    ``group_key`` is the session / source-asset grouping unit used for
    session-disjoint, leakage-free train/val/test splitting."""

    __tablename__ = "autolearn_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("autolearn_tasks.id"))
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str] = mapped_column(String(128))
    group_key: Mapped[str] = mapped_column(String(128))
    image_path: Mapped[str] = mapped_column(Text)
    image_hash: Mapped[str] = mapped_column(String(64))
    video_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin: Mapped[str] = mapped_column(String(32), default="imported")
    # imported | qa_synthetic  (qa_synthetic is a disclosed QA_ONLY fixture)
    # --- Teacher candidate trace (advisory, never training ground truth) ---
    teacher_status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | labeled | unavailable | invalid_response | error | timeout
    teacher_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    teacher_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    teacher_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    teacher_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # --- Human verification (immutable once set) ---
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    split: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelVersion(Base):
    """A fitted, saved Student artifact plus its exact training provenance."""

    __tablename__ = "autolearn_model_versions"
    # One version number per task; concurrent trains cannot both claim v1 and
    # overwrite the same artifact path (C-008).
    __table_args__ = (UniqueConstraint("task_id", "version", name="uq_autolearn_mv_task_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("autolearn_tasks.id"))
    version: Mapped[int] = mapped_column(Integer)
    artifact_path: Mapped[str] = mapped_column(Text)
    encoder_name: Mapped[str] = mapped_column(String(64))
    encoder_weights_version: Mapped[str] = mapped_column(String(64))
    preprocess_version: Mapped[str] = mapped_column(String(64))
    class_mapping: Mapped[dict] = mapped_column(JSON)
    dataset_hash: Mapped[str] = mapped_column(String(64))
    split_hash: Mapped[str] = mapped_column(String(64))
    train_count: Mapped[int] = mapped_column(Integer)
    val_count: Mapped[int] = mapped_column(Integer)
    test_count: Mapped[int] = mapped_column(Integer)
    threshold: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    train_duration_ms: Mapped[float] = mapped_column(Float)
    environment: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="trained")
    # trained | shadow | active | archived | rolled_back
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelVersionSample(Base):
    """Immutable per-version dataset membership snapshot (M3-AC2 / C-002).

    When a Student version is trained, the exact rows, their verified labels,
    content hashes and split assignment are frozen here. Held-out evaluation,
    shadow mode and the activation gate read THIS manifest, never the mutable
    task-wide ``TrainingSample.split`` (which a later retrain reshuffles). If a
    manifest row's current sample is missing or its content hash changed,
    evaluation fails closed rather than inferring a new accuracy."""

    __tablename__ = "autolearn_model_version_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("autolearn_model_versions.id")
    )
    sample_id: Mapped[int] = mapped_column(Integer)
    image_hash: Mapped[str] = mapped_column(String(64))
    verified_label: Mapped[str] = mapped_column(String(64))
    split: Mapped[str] = mapped_column(String(16))  # train | val | test


class ActivationEvent(Base):
    """Immutable audit of every Student activation / rollback / rejection."""

    __tablename__ = "autolearn_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("autolearn_tasks.id"))
    model_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32))  # activate | rollback | reject
    decided_by: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LabelingAudit(Base):
    """Per-request audit of the offline Teacher labeling client (M3-AC1).

    Records the provider host, model, prompt, image hash and session metadata for
    every attempt. Never stores API keys or raw image bytes."""

    __tablename__ = "autolearn_labeling_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer)
    sample_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Actual provider provenance (C-007): the model/revision reported by the
    # provider (distinct from the configured alias) and the labeling method
    # (e.g. generated JSON vs conditional-likelihood scoring). Nullable so older
    # rows and non-contacting outcomes (unavailable/cache) stay valid.
    response_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LabelingReservation(Base):
    """Durable BEFORE-send Teacher-attempt admission record (C-005/C-006).

    Committed on its own connection independently of the labeling/classify job so
    concurrent requests and separate Uvicorn worker processes share ONE
    authoritative per-task budget. The ``slot`` integer is unique per task; an
    atomic ``UNIQUE(task_id, slot)`` insert (with recount-on-collision) is the
    cross-process serialization primitive — no reliance on a single process.

    Lifecycle:
      reserved -> sent      an outbound POST was actually initiated; this is an
                            ACTUAL attempt and durably consumes budget. A later
                            malformed response or DB/sample-commit fault CANNOT
                            erase it (it was already committed here).
      reserved -> released  a local-config/input failure or an admission timeout
                            occurred BEFORE any outbound byte; consumes NO budget.

    Budget consumed by a task == rows with status in (reserved, sent). Only
    ``sent`` rows are reported as actual attempts."""

    __tablename__ = "autolearn_labeling_reservations"
    __table_args__ = (UniqueConstraint("task_id", "slot", name="uq_autolearn_resv_task_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer)
    slot: Mapped[int] = mapped_column(Integer)
    dedupe_key: Mapped[str] = mapped_column(String(64))
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="reserved")
    # reserved | sent | released
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LabelingCache(Base):
    """Bounded, persistent Teacher result cache (C-005).

    An identical fresh classify-fallback input (same task, image content, prompt
    and configured model) reuses a prior labeled result rather than re-contacting
    the provider. Bounded per task (oldest entries evicted) so it can never grow
    unbounded."""

    __tablename__ = "autolearn_labeling_cache"
    __table_args__ = (UniqueConstraint("task_id", "cache_key", name="uq_autolearn_cache_task_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer)
    cache_key: Mapped[str] = mapped_column(String(64))
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("track_events.id"))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
SessionLocal: sessionmaker | None = None


def init_db(db_path: str | None = None) -> None:
    """Create engine, enable WAL, create tables. Idempotent."""
    global _engine, SessionLocal
    path = db_path or str(config.DB_PATH)
    config.ensure_dirs()
    _engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    Base.metadata.create_all(_engine)
    _migrate_additive(_engine)
    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def _migrate_additive(engine) -> None:
    """Add new nullable columns to pre-existing tables without dropping data.

    ``create_all`` creates missing tables but never alters an existing one, so a
    database created before a new nullable column was introduced would be missing
    it. Only additive ``ADD COLUMN`` of nullable columns is performed here, which
    SQLite applies in place; existing image hashes and human verifications are
    preserved. No column is ever dropped or retyped."""
    additive = {
        "autolearn_labeling_audit": {
            "response_model": "VARCHAR(128)",
            "method": "VARCHAR(48)",
        },
    }
    with engine.begin() as conn:
        for table, columns in additive.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:
                continue  # table absent entirely (fresh create_all handled it)
            for name, decl in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {name} {decl}"
                    )
        # Enforce one version number per task even on databases created before the
        # UniqueConstraint existed (C-008). Additive and honest: this fails loudly
        # if pre-existing rows already violate it rather than silently inferring.
        mv_cols = {
            row[1] for row in conn.exec_driver_sql(
                "PRAGMA table_info(autolearn_model_versions)"
            )
        }
        if mv_cols:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_autolearn_mv_task_version "
                "ON autolearn_model_versions(task_id, version)"
            )


def get_session():
    assert SessionLocal is not None, "init_db() not called"
    return SessionLocal()
