"""Offline Teacher labeling client (M3-AC1).

A self-contained async HTTP client for the OFFLINE dataset-labeling job. It is
deliberately separate from the frozen legacy M2 Teacher transport and is never
wired to workflow dispatch — its output only proposes candidate labels for human
review. Teacher-backed workflow actions remain completely off.

Guarantees:
  * Server-only configuration (``VLM_BASE_URL`` / ``VLM_MODEL`` / ``VLM_API_KEY``).
    A missing endpoint yields ``unavailable`` — never a synthetic label.
  * Overall timeout + connect/read timeouts, cancellation, bounded concurrency
    (serial), a request image-byte cap and a streamed response-byte cap.
  * Strict local validation of the returned JSON: a permitted label and a finite
    numeric confidence in [0, 1]. A JSON-looking response is not acceptance.
  * Audit metadata (provider host, model, prompt, image hash, session) with no
    API keys and no raw image bytes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import threading
import time
import weakref
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app import config

# --- Bounded, cancellable, cross-thread transport (C-001) -------------------
# A single asyncio.Semaphore bound to one event loop cannot be reused across the
# fresh loops that ``asyncio.run`` creates per sync call (it raises "bound to a
# different event loop"). Instead admission is a per-running-loop semaphore, and
# all SYNC callers are funnelled onto one owned persistent loop/thread so they
# genuinely share bounded, cancellable transport. Admission is acquired INSIDE
# the overall deadline so a queued caller cannot wait past it, and capacity is
# only released after transport cancellation unwinds (the ``async with`` exit).
_sem_lock = threading.Lock()
_loop_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)

_owned_loop: asyncio.AbstractEventLoop | None = None
_owned_loop_lock = threading.Lock()


def _loop_semaphore() -> asyncio.Semaphore:
    """Admission semaphore bound to the *currently running* loop.

    Each event loop gets its own semaphore so it is never used from a loop it was
    not created on. Concurrency is capped at ``AUTOLEARN_LABEL_CONCURRENCY`` (1)
    so at most one real request is in flight per loop."""
    loop = asyncio.get_running_loop()
    with _sem_lock:
        sem = _loop_semaphores.get(loop)
        if sem is None:
            sem = asyncio.Semaphore(config.AUTOLEARN_LABEL_CONCURRENCY)
            _loop_semaphores[loop] = sem
        return sem


def _run_owned_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_owned_loop() -> asyncio.AbstractEventLoop:
    """Lazily start one daemon-thread event loop shared by all sync callers."""
    global _owned_loop
    with _owned_loop_lock:
        if _owned_loop is None or _owned_loop.is_closed():
            loop = asyncio.new_event_loop()
            threading.Thread(
                target=_run_owned_loop, args=(loop,),
                name="autolearn-labeling-loop", daemon=True,
            ).start()
            _owned_loop = loop
        return _owned_loop


# Allowlisted labeling methods (C-007). ``chat_json`` is generated-JSON chat
# completion; ``two_candidate_likelihood`` is image-conditioned candidate
# likelihood scoring (two forward passes, serialized JSON). A provider-reported
# method outside this set is ignored (never trusted into storage).
_ALLOWED_METHODS = {"chat_json", "two_candidate_likelihood"}


@dataclass
class LabelCandidate:
    status: str  # labeled | unavailable | invalid_response | timeout | error | cancelled
    label: str | None = None
    confidence: float | None = None
    model: str | None = None
    latency_ms: float | None = None
    provider_host: str | None = None
    detail: str | None = None
    # Labeling method provenance (C-007): "chat_json" for generated-JSON chat
    # completions; a likelihood-scoring provider reports "two_candidate_likelihood".
    method: str | None = None
    # Actual provider model/revision reported in the envelope, distinct from the
    # configured alias in ``config.VLM_MODEL`` (C-007). None when the provider did
    # not report one (an "unknown actual model", never faked from the alias).
    model_revision: str | None = None
    # Validated candidate likelihood scores and forward-pass count for a scoring
    # provider (C-007); None for generated JSON.
    candidate_scores: dict | None = None
    forward_passes: int | None = None
    # Whether ``confidence`` is calibrated. Generated self-reported confidence is
    # NOT calibrated; likelihood scores are explicitly uncalibrated too.
    confidence_calibrated: bool = False
    # Whether an outbound POST was ACTUALLY initiated (C-005). Admission timeouts
    # and local-config/input rejections never start a request -> False, so they
    # consume no durable budget. Any received response (labeled/invalid_response/
    # HTTP error) or a transport-level timeout/cancel after send -> True.
    attempted: bool = False
    raw: dict | None = field(default=None)


def provider_configured() -> bool:
    return bool(config.VLM_BASE_URL and config.VLM_MODEL)


def _provider_host() -> str | None:
    if not config.VLM_BASE_URL:
        return None
    try:
        return urlparse(config.VLM_BASE_URL).hostname
    except Exception:  # noqa: BLE001
        return None


def _parse_strict(content, labels: list[str]) -> tuple[str | None, float | None, str]:
    """Strictly parse the model text into (label, confidence, error)."""
    # Content must be text. A numeric/boolean/object content (e.g. a provider
    # returning ``"content": 42``) is a malformed envelope, not a label (C-006).
    if content is None:
        return None, None, "response content is empty"
    if not isinstance(content, str):
        return None, None, f"response content is not a string (got {type(content).__name__})"
    text = content.strip()
    # Tolerate a single fenced code block, nothing more exotic.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
    except Exception:  # noqa: BLE001
        return None, None, "response was not valid JSON"
    if not isinstance(obj, dict):
        return None, None, "JSON root is not an object"
    label = obj.get("label")
    conf = obj.get("confidence")
    permitted = {l.strip().lower() for l in labels}
    if not isinstance(label, str) or label.strip().lower() not in permitted:
        return None, None, f"label not in permitted set {sorted(permitted)}"
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        return None, None, "confidence missing or non-numeric"
    conf = float(conf)
    if not math.isfinite(conf) or not (0.0 <= conf <= 1.0):
        return None, None, "confidence not a finite value in [0, 1]"
    return label.strip().lower(), conf, ""


async def classify(
    image_bytes: bytes,
    *,
    prompt: str,
    labels: list[str],
) -> LabelCandidate:
    """Classify one image. Returns a validated candidate or an explicit failure."""
    host = _provider_host()
    if not provider_configured():
        return LabelCandidate(status="unavailable", detail="VLM_BASE_URL/VLM_MODEL not set")
    if len(image_bytes) > config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES:
        return LabelCandidate(
            status="error",
            provider_host=host,
            detail=f"image exceeds {config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES} byte cap",
        )

    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    sys_prompt = (
        "You are a strict image classifier. Respond with ONLY a compact JSON "
        'object: {"label": <one of %s>, "confidence": <number 0..1>}. No prose.'
        % labels
    )
    body = {
        "model": config.VLM_MODEL,
        "max_tokens": config.AUTOLEARN_LABEL_MAX_TOKENS,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }
    headers = {"Content-Type": "application/json"}
    if config.VLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.VLM_API_KEY}"

    url = config.VLM_BASE_URL.rstrip("/") + "/chat/completions"
    timeout = httpx.Timeout(
        config.AUTOLEARN_LABEL_OVERALL_TIMEOUT,
        connect=config.AUTOLEARN_LABEL_CONNECT_TIMEOUT,
        read=config.AUTOLEARN_LABEL_READ_TIMEOUT,
    )
    t0 = time.perf_counter()
    # ``outbound["started"]`` flips True only once an actual POST is initiated, so
    # the caller can tell an admission-queue timeout (no attempt) from a transport
    # timeout after the request was sent (an actual, uncertain attempt) (C-005).
    outbound = {"started": False}
    try:
        # Admission is INSIDE the overall deadline: a caller queued behind the
        # single in-flight request cannot wait past the absolute timeout. On
        # cancellation the ``async with`` releases capacity only after the
        # transport unwinds, so no abandoned worker holds the slot.
        result = await asyncio.wait_for(
            _admit_and_post(url, body, headers, timeout, outbound),
            timeout=config.AUTOLEARN_LABEL_OVERALL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        # attempted reflects whether we got past admission into an actual POST.
        return LabelCandidate(status="timeout", provider_host=host,
                              attempted=outbound["started"], detail="overall timeout exceeded")
    except asyncio.CancelledError:
        return LabelCandidate(status="cancelled", provider_host=host,
                              attempted=outbound["started"], detail="request cancelled")
    except httpx.TimeoutException:
        return LabelCandidate(status="timeout", provider_host=host,
                              attempted=True, detail="transport timeout")
    except _ResponseTooLarge as exc:
        return LabelCandidate(status="error", provider_host=host, attempted=True, detail=str(exc))
    except httpx.HTTPError as exc:
        return LabelCandidate(status="error", provider_host=host, attempted=True,
                              detail=f"transport error: {type(exc).__name__}")
    latency_ms = (time.perf_counter() - t0) * 1000.0

    status_code, payload = result
    # A response was received: this is unambiguously an actual attempt.
    if status_code == 401 or status_code == 403:
        return LabelCandidate(status="error", provider_host=host, latency_ms=latency_ms,
                              attempted=True, detail="authentication failed")
    if status_code >= 400:
        return LabelCandidate(status="error", provider_host=host, latency_ms=latency_ms,
                              attempted=True, detail=f"HTTP {status_code}")
    try:
        data = json.loads(payload)
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):  # some servers return content parts
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
    except Exception:  # noqa: BLE001
        return LabelCandidate(
            status="invalid_response", provider_host=host, latency_ms=latency_ms,
            attempted=True, detail="missing choices/message/content",
        )
    # Validate provider-controlled envelope metadata as a bounded optional string
    # BEFORE it can reach a String DB column (C-006). A dict/bool/number ``model``
    # is a malformed envelope -> invalid_response (still an actual attempt).
    raw_model = data.get("model") if isinstance(data, dict) else None
    if raw_model is not None and not isinstance(raw_model, str):
        return LabelCandidate(
            status="invalid_response", provider_host=host, latency_ms=latency_ms,
            attempted=True, detail=f"envelope model is not a string (got {type(raw_model).__name__})",
        )
    label, conf, err = _parse_strict(content, labels)
    if err:
        return LabelCandidate(
            status="invalid_response", provider_host=host, latency_ms=latency_ms,
            attempted=True, detail=err,
        )
    # Provenance (C-007): record the model/revision the provider actually
    # reported (distinct from the configured alias), the labeling method, a bounded
    # raw snippet + usage counts, and, when present, validated candidate-likelihood
    # scoring metadata. Never store API keys or raw image bytes.
    actual_model = _bounded_str(raw_model, 128)
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        usage = None
    content_preview = content[:256] if isinstance(content, str) else None
    method, revision, scores, forwards = _scoring_provenance(data)
    return LabelCandidate(
        status="labeled",
        label=label,
        confidence=conf,
        model=actual_model,  # None (unknown actual model) is never faked from the alias
        model_revision=revision or actual_model,
        candidate_scores=scores,
        forward_passes=forwards,
        latency_ms=latency_ms,
        provider_host=host,
        method=method,
        confidence_calibrated=False,  # neither self-report nor likelihood is calibrated
        attempted=True,
        raw={
            "method": method,
            "configured_alias": config.VLM_MODEL,
            "response_model": actual_model,
            "model_revision": revision,
            "candidate_scores": scores,
            "forward_passes": forwards,
            "confidence_calibrated": False,
            "usage": usage,
            "content_preview": content_preview,
        },
    )


def _bounded_str(value, max_len: int) -> str | None:
    """Return ``value`` only if it is a reasonably bounded string, else None."""
    if isinstance(value, str) and 0 < len(value) <= max_len:
        return value
    return None


def _scoring_provenance(data) -> tuple[str, str | None, dict | None, int | None]:
    """Extract validated, allowlisted labeling-method provenance (C-007).

    Honours an optional image-conditioned likelihood-scoring block
    (``providerexperimental_classification``) emitted by a scoring provider: two
    candidate forward passes + serialized JSON. Never hardcodes ``chat_json`` when
    the provider reports a valid scoring method; untrusted/malformed metadata is
    dropped (method falls back to the default generated-JSON label)."""
    default = ("chat_json", None, None, None)
    if not isinstance(data, dict):
        return default
    block = data.get("providerexperimental_classification")
    if not isinstance(block, dict):
        return default
    method = block.get("method")
    if not isinstance(method, str) or method not in _ALLOWED_METHODS:
        return default
    revision = _bounded_str(block.get("model_revision"), 128)
    scores = None
    raw_scores = block.get("candidate_scores")
    if isinstance(raw_scores, dict):
        clean = {
            str(k)[:64]: float(v)
            for k, v in raw_scores.items()
            if isinstance(k, str) and isinstance(v, (int, float))
            and not isinstance(v, bool) and math.isfinite(float(v))
        }
        scores = clean or None
    forwards = block.get("forward_passes")
    if not (isinstance(forwards, int) and not isinstance(forwards, bool) and 0 < forwards <= 8):
        forwards = None
    return method, revision, scores, forwards


class _ResponseTooLarge(RuntimeError):
    pass


async def _admit_and_post(url, body, headers, timeout, outbound) -> tuple[int, bytes]:
    """Acquire the per-loop admission slot, then POST+read. Wrapped by the
    caller's overall ``wait_for`` so both admission and transport share one
    absolute deadline, and the slot is freed on cancellation unwind.

    ``outbound["started"]`` is set the instant admission succeeds and an actual
    POST begins, so a timeout waiting for admission is distinguishable from a
    timeout after the request was already sent (C-005)."""
    async with _loop_semaphore():
        outbound["started"] = True
        return await _post_and_read(url, body, headers, timeout)


async def _post_and_read(url, body, headers, timeout) -> tuple[int, bytes]:
    """POST and stream the response body with a hard byte cap."""
    cap = config.AUTOLEARN_LABEL_MAX_RESPONSE_BYTES
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > cap:
                    raise _ResponseTooLarge(f"response exceeds {cap} byte cap")
                chunks.append(chunk)
            return resp.status_code, b"".join(chunks)


def classify_sync(image_bytes: bytes, *, prompt: str, labels: list[str]) -> LabelCandidate:
    """Synchronous wrapper for sync endpoints / the background labeling worker.

    All sync callers (possibly on different threads) are funnelled onto one owned
    persistent event loop so they share the same bounded, cancellable transport
    and admission — never a per-call ``asyncio.run`` loop that would make a shared
    semaphore illegal and let an abandoned worker hang (C-001). ``classify``
    enforces the absolute overall deadline itself; a hard outer budget guarantees
    a wedged transport can never block the calling thread indefinitely."""
    loop = _get_owned_loop()
    future = asyncio.run_coroutine_threadsafe(
        classify(image_bytes, prompt=prompt, labels=labels), loop
    )
    # Outer safety budget: the coroutine already returns a ``timeout`` candidate
    # at the overall deadline, so this only fires if the loop itself is wedged.
    budget = (
        config.AUTOLEARN_LABEL_OVERALL_TIMEOUT
        + config.AUTOLEARN_LABEL_CONNECT_TIMEOUT
        + 5.0
    )
    try:
        return future.result(timeout=budget)
    except FuturesTimeoutError:
        future.cancel()  # request cancellation on the owned loop; frees the slot
        # The owned loop is wedged past even the absolute deadline: conservatively
        # treat this as an actual (uncertain) attempt so budget is not refunded for
        # work that may have reached the provider (C-005).
        return LabelCandidate(
            status="timeout",
            attempted=True,
            detail="owned-loop safety budget exceeded",
        )
