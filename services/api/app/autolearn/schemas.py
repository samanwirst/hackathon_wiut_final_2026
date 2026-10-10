"""Pydantic schemas for the AutoLearn API (M3 experimental)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    visual_prompt: str = Field(min_length=3, max_length=500)
    positive_label: str = Field(min_length=1, max_length=64)
    negative_label: str = Field(min_length=1, max_length=64)
    teacher_model: str | None = Field(default=None, max_length=128)


class TaskOut(BaseModel):
    id: int
    name: str
    visual_prompt: str
    positive_label: str
    negative_label: str
    teacher_model: str | None
    status: str
    active_version_id: int | None
    created_at: datetime


class SampleOut(BaseModel):
    id: int
    task_id: int
    session_id: str
    group_key: str
    image_hash: str
    origin: str
    image_url: str
    video_timestamp: float | None
    teacher_status: str
    teacher_label: str | None
    teacher_confidence: float | None
    verified: bool
    verified_label: str | None
    verified_by: str | None
    verified_at: datetime | None
    split: str | None


class ReviewRequest(BaseModel):
    verified_label: str = Field(min_length=1, max_length=64)
    reviewer: str = Field(min_length=1, max_length=128)


class ActivateRequest(BaseModel):
    approve: bool
    approver: str = Field(min_length=1, max_length=128)


class SyntheticImportRequest(BaseModel):
    n_sessions: int = Field(default=5, ge=2, le=20)
    per_class_per_session: int = Field(default=3, ge=1, le=20)


class DecisionRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=128)
