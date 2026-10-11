"""Backend-owned task DSL and declared capabilities for the live agent.

The Claude CLI planner proposes a task; the BACKEND owns the authoritative schema
and allowlists here. A planner (or an injected instruction inside a judge prompt)
can never escape this typed validation: anything outside the allowlisted classes,
triggers, actions, and canonical zone geometry is rejected, not silently coerced.

No arbitrary URLs, code, file paths, or tools can appear in a valid task.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# COCO classes the YOLO detector genuinely produces and that are useful for the
# automotive + general demo. These are REAL detectable classes, not canned
# phrases. "bottle" is included because YOLO11n (COCO) detects it — the bottle
# example must travel the same general path, never a hardcoded branch.
SUPPORTED_CLASSES = {
    "person",
    "car",
    "truck",
    "bus",
    "motorcycle",
    "bicycle",
    "bottle",
    "cup",
    "cell phone",
    "laptop",
    "backpack",
    "handbag",
    "suitcase",
    "chair",
}

# Geometric temporal primitives, all backed by the existing ZoneEventEngine.
TriggerType = Literal[
    "presence_in_zone",   # object of class present inside the zone (debounced)
    "entered_zone",
    "exited_zone",
    "dwell_in_zone",
    "count_exceeded",
]

# Only local, side-effect-free actions. No outbound delivery (see M1 actions.py).
ActionType = Literal["notify", "focus_notify"]

# Map our live trigger names onto the shared vision EventType values.
TRIGGER_TO_EVENT = {
    "presence_in_zone": "object_entered_zone",  # presence == first entry, debounced
    "entered_zone": "object_entered_zone",
    "exited_zone": "object_exited_zone",
    "dwell_in_zone": "dwell_in_zone",
    "count_exceeded": "object_count_exceeded",
}


class ZoneSpec(BaseModel):
    """Canonical zone geometry. ``full_frame`` expands to the unit square so the
    planner can say "watch the bottle" without drawing a polygon."""

    type: Literal["full_frame", "polygon"] = "full_frame"
    polygon: list[tuple[float, float]] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _canonicalize(self) -> "ZoneSpec":
        if self.type == "full_frame":
            # Canonical unit square; ignore any supplied polygon.
            object.__setattr__(
                self, "polygon", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
            )
            return self
        if len(self.polygon) < 3:
            raise ValueError("polygon zone needs at least 3 vertices")
        for x, y in self.polygon:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError("polygon coordinates must be normalized to 0..1")
        return self


class VisualObservation(BaseModel):
    """An OPTIONAL non-actioning semantic/temporal check routed to the Teacher VLM
    at event time (e.g. "is the bottle being opened"). It is recorded as an
    observation with explicit uncertainty; a weak/uncalibrated Teacher result can
    NEVER by itself authorize an action. This preserves intent for requests like
    "focus on the bottle when somebody opens it" without faking a temporal event
    from a single frame."""

    question: str = Field(min_length=3, max_length=300)
    labels: list[str] = Field(min_length=2, max_length=6)
    temporal: bool = False  # True => use a before/after pair when available

    @field_validator("labels")
    @classmethod
    def _norm(cls, v: list[str]) -> list[str]:
        norm = [x.strip().lower() for x in v if x.strip()]
        if len(set(norm)) < 2:
            raise ValueError("visual observation needs at least two distinct labels")
        return norm


class LiveTask(BaseModel):
    """The authoritative, validated live monitoring task."""

    name: str = Field(min_length=1, max_length=120)
    object_class: str
    zone: ZoneSpec = Field(default_factory=ZoneSpec)
    trigger: TriggerType
    duration_seconds: float | None = Field(default=None, ge=1, le=3600)
    threshold: int | None = Field(default=None, ge=1, le=100)
    action: ActionType = "notify"
    focus: bool = False
    visual_observation: VisualObservation | None = None
    explanation: str = Field(default="", max_length=800)

    @field_validator("object_class")
    @classmethod
    def _class_allowed(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in SUPPORTED_CLASSES:
            raise ValueError(
                f"unsupported object_class '{v}'; detectable classes: {sorted(SUPPORTED_CLASSES)}"
            )
        return v

    @model_validator(mode="after")
    def _trigger_params(self) -> "LiveTask":
        if self.trigger == "dwell_in_zone" and not self.duration_seconds:
            raise ValueError("dwell_in_zone requires duration_seconds >= 1")
        if self.trigger == "count_exceeded" and not self.threshold:
            raise ValueError("count_exceeded requires threshold >= 1")
        if self.action == "focus_notify":
            object.__setattr__(self, "focus", True)
        return self


def capabilities_doc() -> dict:
    """Machine-readable capability declaration handed to the planner. Keeps the
    planner honest about exactly what the backend can execute."""
    return {
        "object_classes": sorted(SUPPORTED_CLASSES),
        "triggers": [
            "presence_in_zone",
            "entered_zone",
            "exited_zone",
            "dwell_in_zone",
            "count_exceeded",
        ],
        "actions": ["notify", "focus_notify"],
        "zone": ["full_frame", "polygon"],
        "focus": "highlight / enlarge the tracked bounding box in the Judges UI (NO physical camera pan/tilt)",
        "visual_observation": (
            "optional non-actioning semantic/temporal check routed to a weak local VLM; "
            "reports uncertainty and never by itself triggers an action"
        ),
        "notes": [
            "Opening/unattended/semantic conditions are not directly detectable by the geometric engine.",
            "Express them as a visual_observation (uncertain) plus the closest geometric trigger, or ask for clarification.",
            "Never silently drop a requested condition.",
        ],
    }
