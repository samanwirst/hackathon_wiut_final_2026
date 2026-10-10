"""Deterministic natural-language -> workflow-DSL compiler (M2-AC1).

This is a disclosed, rule-based compiler. It does NOT call a text model and
requires no credentials; it maps a constrained set of English phrasings onto the
validated :class:`WorkflowDSL`. This is an honest fallback per the task brief:
no generated code is ever produced or executed — only a structured draft.

Contract:

- Output is always a *draft* (``requires_approval=True``, saved disabled). The
  user edits and explicitly approves/enables it; the compiler never arms a rule.
- Unsupported or ambiguous requests are rejected with clear errors instead of a
  fabricated workflow. Assumptions the compiler had to make surface as warnings
  so the user can correct them before saving.
- A visual predicate (a question the geometric rule cannot answer, e.g. "the
  hood is open") is attached only when explicitly requested; it routes to the
  Teacher at runtime (M2-AC2), never during compilation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas import SUPPORTED_CLASSES

# Class synonyms -> canonical supported class. "vehicle"/"car" are deliberately
# NOT merged silently when ambiguous; see below.
_CLASS_SYNONYMS = {
    "car": "car", "cars": "car", "sedan": "car", "automobile": "car",
    "truck": "truck", "trucks": "truck", "lorry": "truck",
    "bus": "bus", "buses": "bus",
    "motorcycle": "motorcycle", "motorbike": "motorcycle", "motorcycles": "motorcycle",
    "bicycle": "bicycle", "bike": "bicycle", "bicycles": "bicycle",
    "person": "person", "people": "person", "pedestrian": "person", "worker": "person",
}

_ENTER_WORDS = ("enter", "enters", "arrive", "arrives", "comes into", "pulls into", "drives into")
_EXIT_WORDS = ("exit", "exits", "leaves", "leave", "departs", "drives out", "pulls out")
_DWELL_WORDS = ("stays", "stay", "remains", "remain", "dwell", "parked", "idles", "waits")
_COUNT_WORDS = ("more than", "at least", "exceed", "exceeds", "count", "number of")

_VISUAL_TRIGGERS = ("verify", "check whether", "check if", "confirm that", "confirm whether")


@dataclass
class CompileResult:
    ok: bool
    draft: dict | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    explanation: str = ""


def _find_class(text: str) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    # "vehicle" is ambiguous across car/truck/bus; ask the user instead of guessing.
    if re.search(r"\bvehicles?\b", text) and not any(
        re.search(rf"\b{re.escape(w)}\b", text) for w in _CLASS_SYNONYMS
    ):
        return None, [
            "the word 'vehicle' is ambiguous — specify car, truck, bus, motorcycle or bicycle"
        ]
    for word, canon in _CLASS_SYNONYMS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return canon, warnings
    return None, warnings


def _find_trigger(text: str) -> str | None:
    # Order matters: dwell/count phrasings often also contain "in zone".
    if any(w in text for w in _DWELL_WORDS) or re.search(r"(longer|more|greater) than .*\b(second|minute|hour)", text):
        return "dwell_in_zone"
    if any(re.search(rf"{re.escape(w)}\b", text) for w in _COUNT_WORDS):
        return "object_count_exceeded"
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in _EXIT_WORDS):
        return "object_exited_zone"
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in _ENTER_WORDS):
        return "object_entered_zone"
    return None


def _parse_duration_seconds(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(second|sec|minute|min|hour|hr)s?", text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit.startswith("min"):
        return value * 60.0
    if unit.startswith("h"):
        return value * 3600.0
    return value


def _parse_threshold(text: str) -> int | None:
    m = re.search(r"(?:more than|at least|exceed[s]?|over)\s+(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s+(?:or more)", text)
    if m:
        return int(m.group(1))
    return None


def _match_zone(text: str, zones: list[dict]) -> tuple[int | None, list[str], list[str]]:
    """Return (zone_id, warnings, errors). zones: [{'id','name'}]."""
    if not zones:
        return None, [], ["no zones exist for this source — draw a zone first"]
    # explicit name match
    for z in zones:
        name = z["name"].lower()
        if name and name in text:
            return z["id"], [], []
    if len(zones) == 1:
        return zones[0]["id"], [f"assuming zone '{zones[0]['name']}' (the only zone)"], []
    names = ", ".join(f"'{z['name']}'" for z in zones)
    return None, [], [f"zone is ambiguous — name one of: {names}"]


def _detect_visual_predicate(text: str) -> dict | None:
    for marker in _VISUAL_TRIGGERS:
        idx = text.find(marker)
        if idx >= 0:
            clause = text[idx + len(marker):].strip(" .,:;")
            # trim trailing action phrasing
            clause = re.split(r"\b(then|and (create|send|alert|notify))\b", clause)[0].strip()
            if not clause:
                continue
            return {
                "prompt": f"Is it true that {clause}?",
                "labels": ["yes", "no"],
                "expected_label": "yes",
                "description": clause,
            }
    return None


def compile_text(text: str, source_id: int, zones: list[dict]) -> CompileResult:
    """Compile a natural-language instruction into a WorkflowDSL draft dict.

    ``zones`` is the list of existing zones for the source: [{'id','name'}].
    """
    raw = (text or "").strip()
    if len(raw) < 3:
        return CompileResult(False, errors=["instruction is empty or too short"])
    if len(raw) > 2000:
        return CompileResult(False, errors=["instruction is too long (max 2000 chars)"])
    low = raw.lower()

    errors: list[str] = []
    warnings: list[str] = []

    object_class, cls_warn = _find_class(low)
    warnings += cls_warn
    if object_class is None and not cls_warn:
        errors.append(
            "could not identify a supported object class "
            f"(one of {sorted(SUPPORTED_CLASSES)})"
        )
    elif object_class is None:
        errors.append("ambiguous object class")

    trigger_type = _find_trigger(low)
    if trigger_type is None:
        errors.append(
            "could not identify a supported trigger — use words like 'enters', "
            "'exits', 'stays for N minutes', or 'more than N'"
        )

    zone_id, zone_warn, zone_err = _match_zone(low, zones)
    warnings += zone_warn
    errors += zone_err

    duration_seconds = None
    threshold = None
    if trigger_type == "dwell_in_zone":
        duration_seconds = _parse_duration_seconds(low)
        if duration_seconds is None:
            errors.append("dwell rule needs a duration, e.g. 'for 10 minutes'")
    if trigger_type == "object_count_exceeded":
        threshold = _parse_threshold(low)
        if threshold is None:
            errors.append("count rule needs a threshold, e.g. 'more than 3 cars'")

    visual_predicate = _detect_visual_predicate(low)

    # Action: only create_notification is supported; mentions of external
    # delivery are rejected rather than silently downgraded.
    if re.search(r"\b(webhook|http|post to|call the api|slack|telegram)\b", low):
        errors.append(
            "external delivery (webhook/HTTP/Slack/Telegram) is not available; "
            "only in-app notifications are supported"
        )

    if errors:
        return CompileResult(
            False, errors=errors, warnings=warnings,
            explanation="Could not compile a complete, unambiguous workflow.",
        )

    trigger: dict = {"type": trigger_type, "zone_id": zone_id}
    if duration_seconds is not None:
        trigger["duration_seconds"] = duration_seconds
    if threshold is not None:
        trigger["threshold"] = threshold

    name = _suggest_name(object_class, trigger_type, visual_predicate)
    draft = {
        "name": name,
        "source_id": source_id,
        "object_class": object_class,
        "trigger": trigger,
        "action": {"type": "create_notification", "config": {"title": name}},
        "cooldown_seconds": 10.0,
        "requires_approval": True,
    }
    if visual_predicate is not None:
        draft["visual_predicate"] = visual_predicate
        warnings.append(
            "a visual predicate was detected; it requires a configured Teacher "
            "VLM at runtime and is checked only on candidate events"
        )

    explanation = (
        f"{object_class} · {trigger_type}"
        + (f" ≥{duration_seconds:.0f}s" if duration_seconds else "")
        + (f" >{threshold}" if threshold else "")
        + (f" · visual: {visual_predicate['description']}" if visual_predicate else "")
        + " → create_notification (draft, disabled until you approve)"
    )
    return CompileResult(True, draft=draft, warnings=warnings, explanation=explanation)


def _suggest_name(object_class: str, trigger_type: str, visual: dict | None) -> str:
    base = {
        "object_entered_zone": f"{object_class} entered zone",
        "object_exited_zone": f"{object_class} exited zone",
        "dwell_in_zone": f"{object_class} dwell in zone",
        "object_count_exceeded": f"{object_class} count exceeded",
    }.get(trigger_type, f"{object_class} rule")
    if visual:
        base += f" + verify {visual['description']}"
    return base[:255]
