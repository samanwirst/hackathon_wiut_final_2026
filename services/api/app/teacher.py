"""Teacher VLM adapter (M2-AC3).

A Teacher classifies a single selected frame or object ROI against a supported
visual predicate (e.g. "the vehicle hood is open"). It returns a *validated*
result: one of the predicate's allowed labels or an explicit ``unknown``, plus
model/version, timing and billable usage where the provider exposes it.

Honesty rules enforced here:

- A timeout, HTTP error, malformed/unparseable response, a label outside the
  declared set, or missing credentials NEVER becomes a positive visual
  condition. Each maps to a non-confirming status (``error``/``timeout``/
  ``invalid_response``/``missing_credentials``) that the router and pipeline
  treat as "not verified".
- The real provider is selected by configuration. With ``TEACHER_PROVIDER=none``
  (the default in this repo, no key configured) the adapter is
  ``UnavailableTeacher`` and every call returns ``missing_credentials``. This is
  a documented blocker, not a fabricated success. Stub adapters used in tests
  are clearly test-only and do not verify real visual inference.

No generated code is executed and there is no per-frame loop: the adapter only
runs when the router admits a single candidate ROI.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Callable, Literal, Sequence

import threading

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app import config

logger = logging.getLogger("visionflow.teacher")

TeacherStatus = Literal[
    "ok",
    "unknown",
    "low_confidence",
    "error",
    "timeout",
    "invalid_response",
    "missing_credentials",
]


class TeacherResult(BaseModel):
    """Validated Teacher response. ``status == 'ok'`` is the only state that may
    ever confirm a visual action; ``label`` is then guaranteed to be one of the
    predicate's declared labels."""

    status: TeacherStatus
    label: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = None
    prompt_version: str = config.TEACHER_PROMPT_VERSION
    latency_ms: float = 0.0
    usage: dict = Field(default_factory=dict)  # provider-billable tokens if exposed
    error: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.status == "ok" and self.label is not None


class _ProviderResponse(BaseModel):
    """Strict schema the provider's JSON content must satisfy. Unexpected fields
    are rejected and confidence must be finite and bounded — the model cannot
    smuggle a free-form or out-of-range answer into a confirmed action.

    ``confidence`` is optional *here* because an explicit ``unknown`` answer may
    omit it; a *classified* label, however, must carry a confidence or it is
    downgraded to ``invalid_response`` in :meth:`OpenAICompatibleTeacher._parse`
    (M2-AC3)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)


# A router-supplied guard invoked immediately before every outbound HTTP attempt
# (M2-AC4). It consumes/accounts the shared per-task request budget at the
# transport boundary and returns False when no budget remains, so a retry that
# would exceed the budget is never sent.
AttemptGuard = Callable[[], bool]


class TeacherAdapter(ABC):
    """Classifies one image ROI against a visual predicate."""

    provider_name: str = "base"

    @abstractmethod
    def classify(
        self,
        image_bytes: bytes,
        prompt: str,
        labels: Sequence[str],
        on_attempt: AttemptGuard | None = None,
    ) -> TeacherResult:
        """Return a validated TeacherResult for one ROI. Never raises for
        provider/transport failures — those become non-confirming statuses.

        ``on_attempt``, when supplied by the router, is called once before each
        outbound request; if it returns False the adapter must not send that
        request (budget exhausted)."""

    @property
    def available(self) -> bool:
        return True


class UnavailableTeacher(TeacherAdapter):
    """Default when no provider credentials are configured. Always returns
    ``missing_credentials`` so a visual predicate can never be confirmed and the
    limitation is explicit in events and counters."""

    provider_name = "none"

    def __init__(self, reason: str = "no Teacher provider configured (TEACHER_PROVIDER=none)"):
        self._reason = reason

    @property
    def available(self) -> bool:
        return False

    def classify(
        self,
        image_bytes: bytes,
        prompt: str,
        labels: Sequence[str],
        on_attempt: AttemptGuard | None = None,
    ) -> TeacherResult:
        # Makes no outbound request, so ``on_attempt`` is never invoked and no
        # budget/attempt is consumed: an unavailable provider contributes zero
        # actual requests (M2-AC4).
        return TeacherResult(
            status="missing_credentials",
            model=None,
            latency_ms=0.0,
            error=self._reason,
        )


class OpenAICompatibleTeacher(TeacherAdapter):
    """Calls an OpenAI-style chat/completions vision endpoint.

    The request forces a strict JSON answer constrained to the declared labels;
    the response content is parsed and validated. Any deviation is downgraded to
    a non-confirming status. Requires a real base URL + API key via env.
    """

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        prompt_version: str,
        *,
        connect_timeout: float = 5.0,
        read_timeout: float = 20.0,
        overall_timeout: float = 25.0,
        max_retries: int = 1,
        max_concurrency: int = 1,
        max_image_bytes: int = 4 * 1024 * 1024,
        max_tokens: int = 200,
        min_confidence: float = 0.5,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.prompt_version = prompt_version
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.overall_timeout = overall_timeout
        self.max_retries = max(0, max_retries)
        self.max_image_bytes = max_image_bytes
        self.max_tokens = max_tokens
        self.min_confidence = min_confidence
        # Bounded concurrency so a burst of candidates cannot overwhelm the
        # self-hosted server (AC3a semaphore/queue limit).
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrency))

    def _build_messages(self, image_bytes: bytes, prompt: str, labels: Sequence[str]) -> list:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        label_list = ", ".join(f'"{l}"' for l in labels)
        instruction = (
            "You are a strict visual classifier for an automotive service "
            "operations system. Examine ONLY the provided image region. "
            f"Question: {prompt}\n"
            f"Answer with a single JSON object: "
            f'{{"label": one of [{label_list}, "unknown"], '
            '"confidence": a number 0..1}. '
            "Use \"unknown\" if the image does not clearly show the answer. "
            "Do not output any text outside the JSON object."
        )
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ]

    def classify(
        self,
        image_bytes: bytes,
        prompt: str,
        labels: Sequence[str],
        on_attempt: AttemptGuard | None = None,
    ) -> TeacherResult:
        import httpx

        if len(image_bytes) > self.max_image_bytes:
            return TeacherResult(
                status="error", model=self.model, prompt_version=self.prompt_version,
                error=f"ROI {len(image_bytes)}B exceeds max_image_bytes {self.max_image_bytes}",
            )
        payload = {
            "model": self.model,
            "messages": self._build_messages(image_bytes, prompt, labels),
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # optional: omitted for a private authenticated tunnel
            headers["Authorization"] = f"Bearer {self.api_key}"

        # A single monotonic deadline bounds EVERYTHING: queue (semaphore)
        # acquisition, each HTTP attempt, and every backoff (M2-003). No phase
        # may run past ``deadline``; when the remaining budget is exhausted the
        # call returns a ``timeout`` result instead of overrunning.
        t0 = time.perf_counter()
        deadline = t0 + self.overall_timeout

        def _elapsed_ms() -> float:
            return (time.perf_counter() - t0) * 1000.0

        def _remaining() -> float:
            return deadline - time.perf_counter()

        # Bound semaphore acquisition by the remaining deadline.
        acquire_budget = _remaining()
        if acquire_budget <= 0 or not self._semaphore.acquire(timeout=acquire_budget):
            return TeacherResult(
                status="timeout", model=self.model, prompt_version=self.prompt_version,
                latency_ms=_elapsed_ms(),
                error="overall deadline exceeded before acquiring Teacher concurrency slot",
            )

        last: TeacherResult | None = None
        # Bounded attempts: each outbound attempt consults the router budget
        # guard first, and retries only cover transient failures
        # (timeout / connection / 5xx). Auth (401/403) and schema failures fail
        # visibly without retrying.
        try:
            for attempt in range(self.max_retries + 1):
                remaining = _remaining()
                if remaining <= 0:
                    last = last or TeacherResult(
                        status="timeout", model=self.model,
                        prompt_version=self.prompt_version, latency_ms=_elapsed_ms(),
                        error=f"overall deadline exceeded before attempt {attempt + 1}",
                    )
                    break
                # Budget guard at the transport boundary: a retry that would
                # exceed the shared per-task budget is never sent (M2-AC4).
                if on_attempt is not None and not on_attempt():
                    last = last or TeacherResult(
                        status="error", model=self.model,
                        prompt_version=self.prompt_version, latency_ms=_elapsed_ms(),
                        error=f"request budget exhausted before attempt {attempt + 1}",
                    )
                    break
                # Clamp each phase timeout to the remaining deadline.
                attempt_timeout = httpx.Timeout(
                    min(self.overall_timeout, remaining),
                    connect=min(self.connect_timeout, remaining),
                    read=min(self.read_timeout, remaining),
                )
                try:
                    resp = httpx.post(
                        f"{self.api_base}/chat/completions",
                        json=payload, headers=headers, timeout=attempt_timeout,
                    )
                except httpx.TimeoutException as exc:
                    last = TeacherResult(
                        status="timeout", model=self.model,
                        prompt_version=self.prompt_version, latency_ms=_elapsed_ms(),
                        error=f"provider timeout (attempt {attempt + 1}): {exc}"[:500],
                    )
                except httpx.HTTPError as exc:
                    last = TeacherResult(
                        status="error", model=self.model,
                        prompt_version=self.prompt_version, latency_ms=_elapsed_ms(),
                        error=f"transport error (attempt {attempt + 1}): {exc}"[:500],
                    )
                else:
                    latency_ms = _elapsed_ms()
                    if resp.status_code in (401, 403):
                        return TeacherResult(
                            status="error", model=self.model,
                            prompt_version=self.prompt_version, latency_ms=latency_ms,
                            error=f"provider auth failed HTTP {resp.status_code}",
                        )
                    if resp.status_code >= 500:
                        last = TeacherResult(
                            status="error", model=self.model,
                            prompt_version=self.prompt_version, latency_ms=latency_ms,
                            error=f"provider HTTP {resp.status_code}: {resp.text[:200]}",
                        )
                    elif resp.status_code >= 400:
                        return TeacherResult(
                            status="error", model=self.model,
                            prompt_version=self.prompt_version, latency_ms=latency_ms,
                            error=f"provider HTTP {resp.status_code}: {resp.text[:200]}",
                        )
                    else:
                        return self._parse(resp, labels, latency_ms)
                # Backoff only if another attempt remains AND it fits the deadline.
                if attempt < self.max_retries:
                    remaining = _remaining()
                    if remaining <= 0:
                        break
                    backoff = min(2.0, 0.5 * (2 ** attempt), remaining)
                    if backoff > 0:
                        time.sleep(backoff)
        finally:
            self._semaphore.release()
        return last or TeacherResult(
            status="error", model=self.model, prompt_version=self.prompt_version,
            error="no response",
        )

    def _parse(self, resp, labels: Sequence[str], latency_ms: float) -> TeacherResult:
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {}) or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return TeacherResult(
                status="invalid_response", model=self.model,
                prompt_version=self.prompt_version, latency_ms=latency_ms,
                error=f"unparseable provider envelope: {exc}"[:500],
            )

        parsed = _extract_json_object(content)
        if parsed is None:
            return TeacherResult(
                status="invalid_response", model=self.model,
                prompt_version=self.prompt_version, latency_ms=latency_ms,
                usage=_billable(usage),
                error=f"no JSON object in content: {content[:200]!r}",
            )
        try:
            validated = _ProviderResponse.model_validate(parsed)
        except ValidationError as exc:
            return TeacherResult(
                status="invalid_response", model=self.model,
                prompt_version=self.prompt_version, latency_ms=latency_ms,
                usage=_billable(usage),
                error=f"schema violation: {exc}"[:500],
            )

        allowed = {l.lower() for l in labels}
        label = validated.label.strip().lower()
        # ``unknown`` is an explicit, separate non-confirming outcome; confidence
        # is optional for it.
        if label == "unknown":
            return TeacherResult(
                status="unknown", label=None, confidence=validated.confidence,
                model=self.model, prompt_version=self.prompt_version,
                latency_ms=latency_ms, usage=_billable(usage),
            )
        if label not in allowed:
            return TeacherResult(
                status="invalid_response", model=self.model,
                prompt_version=self.prompt_version, latency_ms=latency_ms,
                usage=_billable(usage),
                error=f"label {label!r} not in declared set {sorted(allowed)}",
            )
        # A *classified* label must carry a confidence — a positive answer with
        # no confidence cannot confirm an action (M2-AC3).
        if validated.confidence is None:
            return TeacherResult(
                status="invalid_response", model=self.model,
                prompt_version=self.prompt_version, latency_ms=latency_ms,
                usage=_billable(usage),
                error=f"classified label {label!r} missing required confidence",
            )
        # Below the configured minimum the classification stands but is
        # non-confirming (distinct from ``unknown``): the label/confidence stay
        # visible for provenance, yet ``confirmed`` is False.
        if validated.confidence < self.min_confidence:
            return TeacherResult(
                status="low_confidence", label=label, confidence=validated.confidence,
                model=self.model, prompt_version=self.prompt_version,
                latency_ms=latency_ms, usage=_billable(usage),
                error=(
                    f"confidence {validated.confidence:.3f} below minimum "
                    f"{self.min_confidence:.3f}"
                ),
            )
        return TeacherResult(
            status="ok", label=label, confidence=validated.confidence,
            model=self.model, prompt_version=self.prompt_version,
            latency_ms=latency_ms, usage=_billable(usage),
        )


def _extract_json_object(content: str) -> dict | None:
    """Parse the first JSON object from a model's text content."""
    if not isinstance(content, str):
        return None
    content = content.strip()
    try:
        obj = json.loads(content)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _billable(usage: dict) -> dict:
    """Keep only billable token counts from a provider usage block."""
    out = {}
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if k in usage:
            out[k] = usage[k]
    return out


# Factory ----------------------------------------------------------------------

# Tests inject a deterministic stub here (clearly test-only). Production builds
# the configured provider.
teacher_factory = None
_teacher: TeacherAdapter | None = None


def get_teacher() -> TeacherAdapter:
    global _teacher
    if teacher_factory is not None:
        return teacher_factory()
    if _teacher is not None:
        return _teacher
    # Enabled by presence of the operator-set base URL + model (key optional for
    # a private authenticated tunnel). Missing config -> unavailable blocker.
    if config.VLM_BASE_URL and config.VLM_MODEL:
        _teacher = OpenAICompatibleTeacher(
            api_base=config.VLM_BASE_URL,
            api_key=config.VLM_API_KEY,
            model=config.VLM_MODEL,
            prompt_version=config.TEACHER_PROMPT_VERSION,
            connect_timeout=config.VLM_CONNECT_TIMEOUT,
            read_timeout=config.VLM_READ_TIMEOUT,
            overall_timeout=config.VLM_TIMEOUT_SECONDS,
            max_retries=config.VLM_MAX_RETRIES,
            max_concurrency=config.VLM_MAX_CONCURRENCY,
            max_image_bytes=config.VLM_MAX_IMAGE_BYTES,
            max_tokens=config.VLM_MAX_TOKENS,
            min_confidence=config.VLM_MIN_CONFIDENCE,
        )
    elif config.VLM_BASE_URL and not config.VLM_MODEL:
        _teacher = UnavailableTeacher("VLM_BASE_URL set but VLM_MODEL is unset")
    else:
        _teacher = UnavailableTeacher()
    logger.info("Teacher adapter: %s (available=%s)", _teacher.provider_name, _teacher.available)
    return _teacher


def reset_teacher() -> None:
    global _teacher
    _teacher = None
