"""Teacher transport wall-clock deadline + cancellation tests (M2-003).

These use genuine httpx + httpcore execution over a ``MockTransport`` injected via
the adapter's ``_transport`` seam, so the real streaming/body-read/cancel path is
exercised rather than a fake response object (no socket is opened).

The adapter owns a *cancellable* streaming transport: it drives the body read in
its own thread and checks the wall-clock deadline between chunks, so a trickling
or endless body is cancelled by closing the response/connection at the deadline —
there is no abandoned background worker that keeps reading. The assertions below
measure that stronger invariant (true in-thread cancellation + bounded bytes),
which supersedes the previous "abandoned worker keeps capacity" reproduction.

This does NOT verify real visual inference — the provider is mocked."""

import json
import threading
import time

import httpx

from app.teacher import OpenAICompatibleTeacher


def _envelope_bytes() -> bytes:
    env = {
        "choices": [
            {"message": {"content": json.dumps({"label": "yes", "confidence": 0.9})}}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    }
    return json.dumps(env).encode()


class _TrickleStream(httpx.SyncByteStream):
    """Delivers the body in ``n_chunks`` pieces, sleeping ``delay`` between each.

    Each gap is within the per-read timeout, so no single read times out; only the
    cumulative wall-clock time exceeds the overall deadline."""

    def __init__(self, body: bytes, n_chunks: int, delay: float) -> None:
        size = max(1, (len(body) + n_chunks - 1) // n_chunks)
        self._chunks = [body[i : i + size] for i in range(0, len(body), size)]
        self._delay = delay
        self.closed = False

    def __iter__(self):
        for c in self._chunks:
            time.sleep(self._delay)
            yield c

    def close(self) -> None:
        self.closed = True


def _trickle_transport(*, delay: float, n_chunks: int):
    body = _envelope_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=_TrickleStream(body, n_chunks, delay),
        )

    return httpx.MockTransport(handler)


def test_phase_compliant_trickle_exceeds_overall_deadline():
    # 18 chunks * 25 ms ~= 0.45 s total transfer; each gap < the 50 ms read timeout.
    t = OpenAICompatibleTeacher(
        api_base="https://provider.example/v1", api_key="k", model="vlm",
        prompt_version="v1", overall_timeout=0.1, read_timeout=0.05,
        connect_timeout=0.05, max_retries=0,
    )
    t._transport = _trickle_transport(delay=0.025, n_chunks=18)
    start = time.perf_counter()
    r = t.classify(b"img", "is the hood open?", ["yes", "no"])
    elapsed = time.perf_counter() - start
    assert r.status == "timeout", r
    assert r.confirmed is False
    # Stopped at the ~0.1 s deadline, not at the ~0.45 s full transfer.
    assert elapsed < 0.35, elapsed


def test_fast_streamed_response_still_confirms():
    # Control: when the streamed body fits inside the deadline, the same genuine
    # path reads the full response and confirms.
    t = OpenAICompatibleTeacher(
        api_base="https://provider.example/v1", api_key="k", model="vlm",
        prompt_version="v1", overall_timeout=2.0, max_retries=0,
    )
    t._transport = _trickle_transport(delay=0.001, n_chunks=4)
    r = t.classify(b"img", "q", ["yes", "no"])
    assert r.status == "ok"
    assert r.confirmed is True


# -- M2-003: an endless/trickling body is CANCELLED at the deadline (the active
# transport is closed in-thread), so sequential callers at concurrency 1 never
# overlap and no abandoned worker keeps reading. ------------------------------

def test_timeout_cancels_transport_and_never_overlaps():
    release = threading.Event()
    state = {"active": 0, "peak": 0, "started": 0, "chunks": 0}

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            state["active"] += 1
            state["started"] += 1
            state["peak"] = max(state["peak"], state["active"])
            try:
                while not release.wait(0.005):
                    state["chunks"] += 1
                    yield b" " * 65536
            finally:
                state["active"] -= 1

        def close(self):
            pass

    teacher = OpenAICompatibleTeacher(
        "https://qa.invalid/v1", "", "qa-vlm", "v1",
        overall_timeout=0.06, read_timeout=0.05, max_retries=0, max_concurrency=1,
        max_response_bytes=8 * 1024 * 1024,
    )
    teacher._transport = httpx.MockTransport(lambda req: httpx.Response(200, stream=Stream()))
    try:
        statuses = [
            teacher.classify(b"img", "hood open?", ["yes", "no"]).status
            for _ in range(4)
        ]
        # All four deadline out (non-confirming). Each request truly started AND
        # was cancelled in-thread, so the next could start — but two never overlap,
        # and no body read lingers after its caller returned.
        assert statuses == ["timeout"] * 4
        assert state["peak"] == 1, state
        assert state["started"] == 4, state
        # The single permit is free again: cancellation released it (no deferred
        # reaper holding capacity behind an abandoned reader).
        assert teacher._semaphore.acquire(blocking=False)
        teacher._semaphore.release()
    finally:
        release.set()
        deadline = time.monotonic() + 2
        while state["active"] and time.monotonic() < deadline:
            time.sleep(0.005)
        assert state["active"] == 0, state
