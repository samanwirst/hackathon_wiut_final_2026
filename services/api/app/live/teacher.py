"""Clean, non-actioning Teacher observation adapter for the live app.

Routes a SELECTED event frame (or a before/after pair) to the existing private
loopback SmolVLM endpoint for a semantic/temporal observation. This is a weak,
UNCALIBRATED model: its output is recorded as an observation with explicit
uncertainty and can NEVER by itself authorize an action. There is no per-frame
call — only an event-triggered or explicit manual probe, bounded by a per-room
budget + cooldown, with a small result cache keyed by image hash + question.

The server base URL/token are configuration, never client-supplied. This module
does not modify the Teacher server or its contract.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field

from app.live import config

logger = logging.getLogger("visionflow.live.teacher")

_room_calls: dict[str, int] = {}
_room_last: dict[str, float] = {}
_cache: dict[str, "Observation"] = {}
_lock = threading.Lock()
_concurrency = threading.Semaphore(1)


@dataclass
class Observation:
    status: str                 # "ok" | "unavailable" | "budget" | "cooldown" | "error" | "unsupported"
    label: str | None = None
    confidence: float | None = None
    uncertain: bool = True      # always true: the model is uncalibrated
    image_hash: str | None = None
    image_count: int = 0
    model: str | None = None
    revision: str | None = None
    latency_ms: float | None = None
    raw: dict | None = None     # bounded provenance from the server contract
    reason: str | None = None


# Tests inject a deterministic transport here (QA ONLY) so no real GPU call runs.
transport = None


def available() -> bool:
    return bool(config.TEACHER_BASE_URL) or transport is not None


def _reserve(room_id: str) -> tuple[bool, str | None]:
    now = time.monotonic()
    with _lock:
        used = _room_calls.get(room_id, 0)
        if used >= config.TEACHER_ROOM_BUDGET:
            return False, "budget"
        last = _room_last.get(room_id)
        if last is not None and (now - last) < config.TEACHER_COOLDOWN_SECONDS:
            return False, "cooldown"
        _room_calls[room_id] = used + 1
        _room_last[room_id] = now
        return True, None


def _reset_for_tests() -> None:
    with _lock:
        _room_calls.clear()
        _room_last.clear()
        _cache.clear()


def observe(room_id: str, question: str, labels: list[str],
            images: list[bytes]) -> Observation:
    """Produce a non-actioning observation for one or two JPEG frames."""
    if not images:
        return Observation(status="error", reason="no image", uncertain=True)
    images = images[:2]  # provider supports at most two
    h = hashlib.sha256()
    for img in images:
        h.update(img)
    h.update(question.encode())
    image_hash = h.hexdigest()

    with _lock:
        cached = _cache.get(image_hash)
    if cached is not None:
        return cached

    if not available():
        return Observation(status="unavailable", image_hash=image_hash,
                           reason="Teacher endpoint not configured", uncertain=True)

    ok, reason = _reserve(room_id)
    if not ok:
        return Observation(status=reason or "unavailable", image_hash=image_hash,
                           reason=f"teacher refused: {reason}", uncertain=True)

    if transport is not None:
        obs = transport(question, labels, images)
        obs.image_hash = image_hash
        obs.image_count = len(images)
        with _lock:
            _cache[image_hash] = obs
        return obs

    obs = _call_server(question, labels, images)
    obs.image_hash = image_hash
    obs.image_count = len(images)
    with _lock:
        _cache[image_hash] = obs
    return obs


def _call_server(question: str, labels: list[str], images: list[bytes]) -> Observation:
    import httpx

    content: list[dict] = [{"type": "text", "text": question[:300]}]
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    payload = {
        "model": config.TEACHER_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 96,
    }
    headers = {"Content-Type": "application/json"}
    if config.TEACHER_TOKEN:
        headers["Authorization"] = f"Bearer {config.TEACHER_TOKEN}"

    if not _concurrency.acquire(timeout=config.TEACHER_TIMEOUT_SECONDS + 5):
        return Observation(status="error", reason="teacher busy", uncertain=True)
    t0 = time.monotonic()
    try:
        resp = httpx.post(
            config.TEACHER_BASE_URL.rstrip("/") + "/v1/chat/completions",
            json=payload, headers=headers, timeout=config.TEACHER_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("teacher call failed: %s", exc)
        return Observation(status="error", reason=str(exc)[:200], uncertain=True)
    finally:
        _concurrency.release()
    latency_ms = (time.monotonic() - t0) * 1000.0

    if resp.status_code != 200:
        return Observation(status="error", latency_ms=latency_ms,
                           reason=f"teacher HTTP {resp.status_code}", uncertain=True)
    try:
        body = resp.json()
        text = body["choices"][0]["message"]["content"]
        metrics = body.get("experimental_metrics", {})
    except Exception as exc:  # noqa: BLE001
        return Observation(status="error", latency_ms=latency_ms,
                           reason=f"teacher bad response: {exc}", uncertain=True)

    label, confidence = None, None
    try:
        parsed = json.loads(text)
        label = str(parsed.get("label")) if parsed.get("label") is not None else None
        if parsed.get("confidence") is not None:
            confidence = float(parsed["confidence"])
    except (ValueError, TypeError, AttributeError):
        label = (text or "").strip()[:40] or None

    return Observation(
        status="ok",
        label=label,
        confidence=confidence,
        uncertain=True,  # uncalibrated model: always flagged uncertain
        model=body.get("model"),
        revision=metrics.get("revision"),
        latency_ms=latency_ms,
        raw={
            "scoring": metrics.get("scoring"),
            "inference_seconds": metrics.get("inference_seconds"),
            "image_count": metrics.get("image_count"),
            "output_is_generated_json": (metrics.get("scoring") or {}).get("output_is_generated_json"),
        },
        reason="uncalibrated observation (non-actioning)",
    )
