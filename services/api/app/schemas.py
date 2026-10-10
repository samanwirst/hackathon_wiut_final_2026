"""Pydantic API and workflow-DSL schemas.

The workflow DSL is the validated contract between user intent and the event
engine. Unsupported trigger/action types fail validation with a clear error —
they are never silently coerced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Workflow DSL (PRD section 8). M1 supports the four zone triggers; the
# visual_condition_verified trigger arrives with AutoLearn (M3).
# ---------------------------------------------------------------------------

TriggerType = Literal[
    "object_entered_zone",
    "object_exited_zone",
    "dwell_in_zone",
    "object_count_exceeded",
]

# M1 ships only the local, side-effect-free notification action. Arbitrary
# outbound webhooks were removed (M1-011/M1-012): the SSRF/DNS-rebinding guard
# could not safely protect the delivery connection without a risky custom
# DNS/TLS egress transport, so the capability is disabled rather than shipped
# insecurely. A validated-egress integration can be reintroduced later.
ActionType = Literal["create_notification"]

# COCO classes relevant to the automotive vertical, plus "person".
SUPPORTED_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}


class Trigger(BaseModel):
    type: TriggerType
    zone_id: int
    duration_seconds: float | None = Field(default=None, ge=1, le=86400)
    threshold: int | None = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def check_params(self) -> "Trigger":
        if self.type == "dwell_in_zone" and not self.duration_seconds:
            raise ValueError("dwell_in_zone requires duration_seconds >= 1")
        if self.type == "object_count_exceeded" and not self.threshold:
            raise ValueError("object_count_exceeded requires threshold >= 1")
        return self


class Action(BaseModel):
    type: ActionType
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_config(self) -> "Action":
        if self.type == "create_notification":
            title = self.config.get("title")
            # Optional: falls back to a generated title. If present it must be a
            # bounded string — a dict/list would be rejected by SQLite at commit
            # time and strand the source in 'processing' (M1-008).
            if title is not None and (not isinstance(title, str) or len(title) > 255):
                raise ValueError(
                    "create_notification config.title must be a string of at most 255 characters"
                )
        return self


class WorkflowDSL(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_id: int
    object_class: str
    trigger: Trigger
    action: Action
    cooldown_seconds: float = Field(default=10.0, ge=0, le=86400)
    requires_approval: bool = True

    @field_validator("object_class")
    @classmethod
    def check_class(cls, v: str) -> str:
        if v not in SUPPORTED_CLASSES:
            raise ValueError(
                f"unsupported object_class '{v}'; supported: {sorted(SUPPORTED_CLASSES)}"
            )
        return v


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------


class ZoneCreate(BaseModel):
    source_id: int
    name: str = Field(min_length=1, max_length=255)
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=50)

    @field_validator("polygon")
    @classmethod
    def check_normalized(cls, v):
        for x, y in v:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError("polygon coordinates must be normalized to 0..1")
        return v


class ZoneOut(BaseModel):
    id: int
    source_id: int
    name: str
    polygon: list[tuple[float, float]]


class SourceOut(BaseModel):
    id: int
    type: str
    name: str
    status: str
    error: str | None
    width: int | None
    height: int | None
    fps: float | None
    frame_count: int | None
    frames_processed: int
    avg_inference_ms: float | None
    created_at: datetime


class WorkflowOut(BaseModel):
    id: int
    source_id: int
    name: str
    dsl: WorkflowDSL
    enabled: bool
    created_at: datetime


class EventOut(BaseModel):
    id: int
    source_id: int
    workflow_id: int
    track_id: int | None
    type: str
    class_name: str | None
    video_timestamp: float
    confidence: float
    detail: str
    evidence_url: str | None
    action_status: str
    created_at: datetime


class ActionOut(BaseModel):
    id: int
    event_id: int
    action_type: str
    status: str
    attempt_count: int
    error: str | None
    executed_at: datetime | None


class NotificationOut(BaseModel):
    id: int
    event_id: int
    title: str
    message: str
    created_at: datetime
