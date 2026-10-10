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

# Supported visual conditions (whitelist). A visual condition is a question the
# geometric rule cannot answer; only these recognised conditions are preserved as
# a structured, non-executable predicate. An unrecognised condition is REJECTED
# (never silently dropped). The prompt/labels are fixed server vocabulary.
_VISUAL_CONDITIONS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\b(?:hood|bonnet)\b.*\b(?:open|up|raised|popped)\b|\b(?:open|raised|popped)\s+(?:hood|bonnet)\b"),
     "the vehicle hood is open"),
    (re.compile(r"\b(?:trunk|boot|tailgate)\b.*\bopen\b|\bopen\s+(?:trunk|boot|tailgate)\b"),
     "the vehicle trunk is open"),
    (re.compile(r"\bdoor\b.*\bopen\b|\bopen\s+door\b"),
     "a vehicle door is open"),
    (re.compile(r"\b(?:head)?lights?\b.*\b(?:on|flashing|lit)\b"),
     "the vehicle lights are on"),
)

# Connectives that introduce a condition clause. Their presence means the user
# asked for an extra check; if it is not a recognised visual condition the
# request is rejected rather than compiled without it (M2-AC1).
_CONDITION_MARKERS = (
    "verify", "check whether", "check if", "check that",
    "confirm that", "confirm whether",
    "with its", "with their", "with the", "while its", "while the",
    "whose", "having its", "having their", "that has", "that is",
)


def _match_visual_condition(text: str) -> dict | None:
    for pat, desc in _VISUAL_CONDITIONS:
        if pat.search(text):
            return {
                "prompt": f"Does the image clearly show that {desc}?",
                "labels": ["yes", "no"],
                "expected_label": "yes",
                "description": desc,
            }
    return None


@dataclass
class CompileResult:
    ok: bool
    draft: dict | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    explanation: str = ""


def _find_class(text: str) -> tuple[str | None, list[str], list[str]]:
    """Return (object_class, warnings, errors).

    Rejects the ambiguous word 'vehicle' and rejects requests that name more than
    one supported class (e.g. "car or truck") rather than silently picking one.
    """
    warnings: list[str] = []
    # "vehicle" is ambiguous across car/truck/bus; ask the user instead of guessing.
    if re.search(r"\bvehicles?\b", text) and not any(
        re.search(rf"\b{re.escape(w)}\b", text) for w in _CLASS_SYNONYMS
    ):
        return None, [], [
            "the word 'vehicle' is ambiguous — specify car, truck, bus, motorcycle or bicycle"
        ]
    found: list[str] = []
    for word, canon in _CLASS_SYNONYMS.items():
        if re.search(rf"\b{re.escape(word)}\b", text) and canon not in found:
            found.append(canon)
    if not found:
        return None, warnings, []
    if len(found) > 1:
        return None, [], [
            "more than one object class was requested "
            f"({', '.join(sorted(found))}); specify exactly one supported class"
        ]
    return found[0], warnings, []


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


def _detect_visual_predicate(text: str) -> tuple[dict | None, bool]:
    """Return (predicate, had_condition_marker).

    ``predicate`` is a structured visual predicate when the text references a
    supported visual condition (via a verify/check verb or a ``with its ...``
    style connective). ``had_condition_marker`` is True when a condition clause
    was requested at all; a marker with no recognised condition
    (``had_condition_marker and predicate is None``) must be rejected by the
    caller so an unsupported condition is never silently dropped."""
    predicate = _match_visual_condition(text)
    had_marker = any(m in text for m in _CONDITION_MARKERS)
    return predicate, had_marker


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

    object_class, cls_warn, cls_err = _find_class(low)
    warnings += cls_warn
    errors += cls_err
    if object_class is None and not cls_err:
        errors.append(
            "could not identify a supported object class "
            f"(one of {sorted(SUPPORTED_CLASSES)})"
        )

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

    visual_predicate, had_condition_marker = _detect_visual_predicate(low)
    # A requested condition clause that is not a supported visual condition is
    # rejected rather than silently dropped (M2-AC1).
    if had_condition_marker and visual_predicate is None:
        errors.append(
            "an unsupported or unrecognized visual condition was requested; "
            "supported visual conditions: hood/trunk/door open, lights on"
        )

    # Action: only in-app create_notification is supported. External delivery or
    # code/command execution is rejected rather than silently downgraded to a
    # local notification.
    if re.search(r"\b(webhook|https?|post to|call the api|slack|telegram|e-?mails?|sms|text message|phone|call the)\b", low):
        errors.append(
            "external delivery (webhook/HTTP/email/SMS/phone/Slack/Telegram) is "
            "not available; only in-app notifications are supported"
        )
    if (
        re.search(r"\b(python|javascript|shell|bash|source code|exec|eval)\b", low)
        or (re.search(r"\b(run|execute|invoke)\b", low)
            and re.search(r"\b(code|script|command|program)\b", low))
    ):
        errors.append(
            "executing code, scripts, or shell commands is not supported"
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
