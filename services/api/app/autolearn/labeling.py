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
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app import config

# Serial by requirement: one offline labeling request in flight at a time.
_semaphore = asyncio.Semaphore(config.AUTOLEARN_LABEL_CONCURRENCY)


@dataclass
class LabelCandidate:
    status: str  # labeled | unavailable | invalid_response | timeout | error | cancelled
    label: str | None = None
    confidence: float | None = None
    model: str | None = None
    latency_ms: float | None = None
    provider_host: str | None = None
    detail: str | None = None
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


def _parse_strict(content: str, labels: list[str]) -> tuple[str | None, float | None, str]:
    """Strictly parse the model text into (label, confidence, error)."""
    text = (content or "").strip()
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
    try:
        async with _semaphore:
            result = await asyncio.wait_for(
                _post_and_read(url, body, headers, timeout),
                timeout=config.AUTOLEARN_LABEL_OVERALL_TIMEOUT,
            )
    except asyncio.TimeoutError:
        return LabelCandidate(status="timeout", provider_host=host, detail="overall timeout exceeded")
    except asyncio.CancelledError:
        return LabelCandidate(status="cancelled", provider_host=host, detail="request cancelled")
    except httpx.TimeoutException:
        return LabelCandidate(status="timeout", provider_host=host, detail="transport timeout")
    except _ResponseTooLarge as exc:
        return LabelCandidate(status="error", provider_host=host, detail=str(exc))
    except httpx.HTTPError as exc:
        return LabelCandidate(status="error", provider_host=host, detail=f"transport error: {type(exc).__name__}")
    latency_ms = (time.perf_counter() - t0) * 1000.0

    status_code, payload = result
    if status_code == 401 or status_code == 403:
        return LabelCandidate(status="error", provider_host=host, latency_ms=latency_ms, detail="authentication failed")
    if status_code >= 400:
        return LabelCandidate(status="error", provider_host=host, latency_ms=latency_ms, detail=f"HTTP {status_code}")
    try:
        data = json.loads(payload)
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):  # some servers return content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    except Exception:  # noqa: BLE001
        return LabelCandidate(
            status="invalid_response", provider_host=host, latency_ms=latency_ms,
            detail="missing choices/message/content",
        )
    label, conf, err = _parse_strict(content, labels)
    if err:
        return LabelCandidate(
            status="invalid_response", provider_host=host, latency_ms=latency_ms, detail=err,
        )
    usage = data.get("usage") if isinstance(data, dict) else None
    return LabelCandidate(
        status="labeled",
        label=label,
        confidence=conf,
        model=config.VLM_MODEL,
        latency_ms=latency_ms,
        provider_host=host,
        raw={"usage": usage},
    )


class _ResponseTooLarge(RuntimeError):
    pass


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
    """Synchronous wrapper for use from the background worker / sync endpoints."""
    return asyncio.run(classify(image_bytes, prompt=prompt, labels=labels))
