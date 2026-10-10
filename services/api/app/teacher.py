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
import math
import re
import socket
import ssl
import time
from abc import ABC, abstractmethod
from typing import Callable, Literal, Sequence
from urllib.parse import urlsplit

import threading

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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
    (M2-AC3).

    ``confidence`` must be an *actual* JSON number (M2-008). Pydantic's default
    lax coercion would turn ``true`` into ``1.0`` and ``"0.9"`` into ``0.9``,
    letting a malformed provider answer authorize an action. A ``mode="before"``
    validator rejects booleans (``True``/``False`` are ``int`` subclasses in
    Python), strings, NaN and infinities *before* the numeric bounds are applied,
    so only a finite JSON number in ``[0, 1]`` can ever confirm."""

    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)

    @field_validator("confidence", mode="before")
    @classmethod
    def _require_json_number(cls, v):
        if v is None:
            return v
        # bool is a subclass of int: reject it explicitly so ``true`` cannot be
        # coerced to 1.0. Reject strings (incl. numeric strings) and any other
        # non-numeric type, and reject non-finite numbers.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("confidence must be a JSON number (not a boolean or string)")
        f = float(v)
        if not math.isfinite(f):
            raise ValueError("confidence must be a finite number")
        return f


# A router-supplied guard invoked immediately before every outbound HTTP attempt
# (M2-AC4). It consumes/accounts the shared per-task request budget at the
# transport boundary and returns False when no budget remains, so a retry that
# would exceed the budget is never sent.
AttemptGuard = Callable[[], bool]


class _AttemptNotAdmitted(Exception):
    """Raised at the transport boundary when the router guard denies an attempt
    (shared budget exhausted or the workflow was disabled). No connection is
    opened; ``classify`` maps this to a non-confirming result without a provider
    request (M2-007)."""


class _ConcurrencySlot:
    """A single-owner handle on one bounded-semaphore permit (M2-003).

    The permit is released exactly once. Because the streaming transport is
    cancelled in-thread at the wall-clock deadline (no background worker survives
    the call), ``classify`` always releases the permit in its ``finally`` once the
    request — completed or cancelled — has returned. Capacity is therefore never
    held by an in-flight body read, so the bounded semaphore genuinely caps the
    number of concurrent transport requests (the earlier abandoned-worker design
    that deferred release to a reaper is gone)."""

    def __init__(self, semaphore: "threading.BoundedSemaphore") -> None:
        self._semaphore = semaphore
        self._lock = threading.Lock()
        self._released = False

    def release(self) -> None:
        with self._lock:
            if not self._released:
                self._released = True
                self._semaphore.release()

    @property
    def deferred(self) -> bool:
        # Retained for call-site compatibility; cancellation is now in-thread so a
        # slot is never deferred.
        return False


class TeacherAdapter(ABC):
    """Classifies one image ROI against a visual predicate."""

    provider_name: str = "base"
    # When True, the adapter accounts every real outbound attempt through the
    # router-supplied ``on_attempt`` guard, so the router must NOT add its own
    # fallback attempt/budget unit (M2-004). Stubs that do not call the guard
    # leave this False and are charged one fallback unit so the budget still
    # bounds them.
    reports_attempts: bool = False

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
    # The real adapter calls ``on_attempt`` before every outbound request, so the
    # router accounts attempts/budget exclusively through that guard (M2-004).
    reports_attempts = True

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
        max_response_bytes: int = 2 * 1024 * 1024,
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
        # Cap the bytes we will read from a provider response so an endless or
        # oversized body cannot accumulate unboundedly even before the deadline
        # fires (M2-003).
        self.max_response_bytes = max_response_bytes
        self.max_tokens = max_tokens
        self.min_confidence = min_confidence
        # Bounded concurrency so a burst of candidates cannot overwhelm the
        # self-hosted server (AC3a semaphore/queue limit).
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrency))
        # Transport seam: production uses httpx's default networking; tests inject
        # an ``httpx.MockTransport`` here to exercise the real streaming/cancel
        # path over a mock server without opening a socket.
        self._transport = None

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

        # Bound semaphore acquisition by the remaining deadline. A slot that is
        # still held by an abandoned-but-active worker (M2-003) keeps capacity
        # occupied, so a burst while one request is in flight correctly fails to
        # acquire here and returns ``timeout`` without starting a second worker.
        acquire_budget = _remaining()
        if acquire_budget <= 0 or not self._semaphore.acquire(timeout=acquire_budget):
            return TeacherResult(
                status="timeout", model=self.model, prompt_version=self.prompt_version,
                latency_ms=_elapsed_ms(),
                error="overall deadline exceeded before acquiring Teacher concurrency slot",
            )
        slot = _ConcurrencySlot(self._semaphore)

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
                # Clamp each phase timeout to the remaining deadline.
                attempt_timeout = httpx.Timeout(
                    min(self.overall_timeout, remaining),
                    connect=min(self.connect_timeout, remaining),
                    read=min(self.read_timeout, remaining),
                )
                try:
                    # The budget/approval guard is consulted INSIDE the transport
                    # method, immediately before the connection is opened, so the
                    # authoritative admission and the actual transport start are one
                    # boundary (M2-007). A guard denial raises _AttemptNotAdmitted
                    # and no request is sent.
                    resp = self._post_with_deadline(
                        f"{self.api_base}/chat/completions",
                        payload, headers, attempt_timeout, deadline, slot, on_attempt,
                    )
                except _AttemptNotAdmitted as exc:
                    last = last or TeacherResult(
                        status="error", model=self.model,
                        prompt_version=self.prompt_version, latency_ms=_elapsed_ms(),
                        error=str(exc)[:500],
                    )
                    break
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
            # The streaming transport is cancelled in-thread at the deadline, so no
            # abandoned worker outlives this call: the concurrency permit is always
            # released here once the (possibly cancelled) request has returned, and
            # capacity is never held by an in-flight body read (M2-003).
            if not slot.deferred:
                slot.release()
        return last or TeacherResult(
            status="error", model=self.model, prompt_version=self.prompt_version,
            error="no response",
        )

    def _post_with_deadline(self, url, payload, headers, attempt_timeout, deadline, slot, on_attempt=None):
        """Execute one POST bounded by the overall wall-clock ``deadline`` (M2-003),
        coupling admission to the actual send (M2-007).

        Two transports share this entry point:

        - The REAL path (``self._transport is None``, production) uses an OWNED raw
          socket (:meth:`_post_raw_socket`) so every phase — connect, send, header
          receipt and body receipt — is hard-bounded by the wall-clock deadline and
          the socket is genuinely closed on expiry. This is the path the real-TCP
          regressions and the independent reviewer probes exercise.
        - The TEST path (``self._transport`` set to an ``httpx.MockTransport``) uses
          :meth:`_post_via_httpx` so the response-validation and byte-cap unit tests
          drive the real httpx parse path without opening a socket."""
        if self._transport is not None:
            return self._post_via_httpx(
                url, payload, headers, attempt_timeout, deadline, on_attempt
            )
        return self._post_raw_socket(url, payload, headers, deadline, on_attempt)

    def _post_via_httpx(self, url, payload, headers, attempt_timeout, deadline, on_attempt=None):
        """Injected-transport path for unit tests (``httpx.MockTransport``).

        The guard is consulted immediately before the in-process mock call; there is
        no real connect phase to race against, so the admission boundary here is the
        guard return (no coupled send). The wall-clock deadline is still enforced
        between streamed chunks and the response-byte cap still applies."""
        import httpx

        if on_attempt is not None:
            remaining = deadline - time.perf_counter()
            if remaining <= 0 or not on_attempt(remaining):
                raise _AttemptNotAdmitted(
                    "attempt not admitted before transport start (request budget "
                    "exhausted, workflow disabled, or admission deadline exceeded)"
                )

        client = httpx.Client(timeout=attempt_timeout, transport=self._transport)
        try:
            with client.stream("POST", url, json=payload, headers=headers) as resp:
                if time.perf_counter() >= deadline:
                    raise httpx.TimeoutException(
                        "overall wall-clock deadline exceeded after response headers"
                    )
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > self.max_response_bytes:
                        raise httpx.HTTPError(
                            f"provider response exceeded max_response_bytes "
                            f"{self.max_response_bytes}"
                        )
                    chunks.append(chunk)
                    if time.perf_counter() >= deadline:
                        raise httpx.TimeoutException(
                            "overall wall-clock deadline exceeded during body read"
                        )
                body = b"".join(chunks)
                return httpx.Response(
                    status_code=resp.status_code,
                    headers=resp.headers,
                    content=body,
                    request=resp.request,
                )
        finally:
            client.close()

    def _post_raw_socket(self, url, payload, headers, deadline, on_attempt=None):
        """Owned, cancellable HTTP/1.1 POST over a raw socket (M2-003/M2-007).

        Design rationale (addresses the reviewer's real-network findings):

        - M2-003: ``httpx``'s connect/read timeouts reset per phase, so a provider
          that trickles header bytes within each read window runs far past the
          overall deadline. Here EVERY blocking operation — connect, send and each
          recv for headers and body — is bounded by the remaining wall-clock budget,
          and on expiry the socket is actually closed (``finally``), so no phase and
          no abandoned reader can outlive the deadline.

        - M2-007: the connection is opened BEFORE the admission boundary, outside the
          router's dispatch lock, so a slow connect never blocks a concurrent
          disable. The actual ``sock.sendall`` (the authoritative send) is handed to
          ``on_attempt`` and executed WHILE the dispatch lock is held, re-checking
          both the authoritative enabled state and the deadline immediately before
          the bytes are written. A disable that returned 200 therefore guarantees no
          POST is ever written afterwards; a disable during connect revokes the
          unsent attempt. The lock is released before the response is read."""
        import httpx

        parts = urlsplit(url)
        host = parts.hostname or "127.0.0.1"
        port = parts.port or (443 if parts.scheme == "https" else 80)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query

        body = json.dumps(payload).encode("utf-8")
        req_headers = dict(headers)
        req_headers.setdefault("Content-Type", "application/json")
        req_headers["Host"] = parts.netloc.split("@")[-1]
        req_headers["Content-Length"] = str(len(body))
        req_headers["Accept"] = "application/json"
        req_headers["Connection"] = "close"
        request_line = f"POST {path} HTTP/1.1\r\n"
        header_block = "".join(f"{k}: {v}\r\n" for k, v in req_headers.items())
        raw_request = (request_line + header_block + "\r\n").encode("ascii") + body

        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise httpx.TimeoutException("overall deadline exceeded before connect")

        sock = socket.create_connection(
            (host, port), timeout=min(self.connect_timeout, remaining)
        )
        try:
            if parts.scheme == "https":
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)

            def _send() -> None:
                rem = deadline - time.perf_counter()
                if rem <= 0:
                    raise httpx.TimeoutException(
                        "overall deadline exceeded before sending request"
                    )
                sock.settimeout(rem)
                sock.sendall(raw_request)

            # Admission + send coupled under the router dispatch lock (M2-007). When
            # no guard is supplied (direct adapter use), send immediately.
            if on_attempt is not None:
                admitted = on_attempt(deadline - time.perf_counter(), send=_send)
                if not admitted:
                    raise _AttemptNotAdmitted(
                        "attempt not admitted at the send boundary (request budget "
                        "exhausted, workflow disabled, or admission deadline exceeded)"
                    )
            else:
                _send()

            status_code, resp_headers, resp_body = self._recv_http_response(sock, deadline)
            return httpx.Response(
                status_code=status_code,
                headers=resp_headers,
                content=resp_body,
                request=httpx.Request("POST", url),
            )
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _recv_http_response(self, sock, deadline):
        """Read a full HTTP/1.1 response from ``sock`` under the wall-clock
        ``deadline``, honouring Content-Length, chunked transfer-encoding and
        connection-close framing, and the response-byte cap. Any recv that would
        block past the deadline raises :class:`httpx.TimeoutException`."""
        import httpx

        def _recv(max_bytes: int) -> bytes:
            rem = deadline - time.perf_counter()
            if rem <= 0:
                raise httpx.TimeoutException(
                    "overall wall-clock deadline exceeded while reading response"
                )
            sock.settimeout(rem)
            try:
                return sock.recv(max_bytes)
            except (socket.timeout, TimeoutError):
                # The recv window equalled the remaining budget, so the deadline has
                # now passed: surface it as a timeout rather than looping.
                raise httpx.TimeoutException(
                    "overall wall-clock deadline exceeded while reading response"
                )

        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = _recv(65536)
            if not chunk:
                raise httpx.HTTPError("connection closed before response headers")
            buf += chunk
            if len(buf) > self.max_response_bytes:
                raise httpx.HTTPError(
                    f"provider response headers exceeded max_response_bytes "
                    f"{self.max_response_bytes}"
                )
        head, _, rest = buf.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        try:
            status_code = int(lines[0].split(b" ")[1])
        except (IndexError, ValueError) as exc:
            raise httpx.HTTPError(f"malformed status line: {lines[0][:80]!r}") from exc
        resp_headers: dict[str, str] = {}
        for line in lines[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                resp_headers[k.strip().decode("latin-1").lower()] = v.strip().decode("latin-1")

        body = rest
        te = resp_headers.get("transfer-encoding", "").lower()
        if "chunked" in te:
            body = self._read_chunked(sock, rest, deadline, _recv)
        elif "content-length" in resp_headers:
            try:
                n = int(resp_headers["content-length"])
            except ValueError:
                n = 0
            while len(body) < n:
                chunk = _recv(min(65536, n - len(body)))
                if not chunk:
                    break
                body += chunk
                if len(body) > self.max_response_bytes:
                    raise httpx.HTTPError(
                        f"provider response exceeded max_response_bytes "
                        f"{self.max_response_bytes}"
                    )
        else:
            # Connection-close framing: read until EOF (bounded by the deadline).
            while True:
                chunk = _recv(65536)
                if not chunk:
                    break
                body += chunk
                if len(body) > self.max_response_bytes:
                    raise httpx.HTTPError(
                        f"provider response exceeded max_response_bytes "
                        f"{self.max_response_bytes}"
                    )
        return status_code, resp_headers, body

    def _read_chunked(self, sock, initial, deadline, _recv):
        """Decode a chunked transfer-encoding body under the wall-clock deadline."""
        import httpx

        buf = initial
        out = b""
        while True:
            while b"\r\n" not in buf:
                chunk = _recv(65536)
                if not chunk:
                    return out
                buf += chunk
                if len(out) + len(buf) > self.max_response_bytes:
                    raise httpx.HTTPError(
                        f"provider response exceeded max_response_bytes "
                        f"{self.max_response_bytes}"
                    )
            size_line, _, buf = buf.partition(b"\r\n")
            try:
                size = int(size_line.split(b";")[0].strip() or b"0", 16)
            except ValueError as exc:
                raise httpx.HTTPError("malformed chunk size") from exc
            if size == 0:
                break
            while len(buf) < size + 2:
                chunk = _recv(65536)
                if not chunk:
                    return out + buf[:size]
                buf += chunk
                if len(out) + len(buf) > self.max_response_bytes:
                    raise httpx.HTTPError(
                        f"provider response exceeded max_response_bytes "
                        f"{self.max_response_bytes}"
                    )
            out += buf[:size]
            buf = buf[size + 2:]
        return out

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
            max_response_bytes=getattr(config, "VLM_MAX_RESPONSE_BYTES", 2 * 1024 * 1024),
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
