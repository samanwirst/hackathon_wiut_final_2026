"""Regression tests for the offline Teacher transport fixes (C-001/C-006/C-007).

These exercise the REAL transport against an owned loopback HTTP server
(QA_ONLY, 127.0.0.1) — no external network, no paid provider, no GPU. They
reproduce the reviewer's material findings:

  * C-001 — cross-thread sync callers share one bounded, cancellable transport;
    admission is counted inside the absolute overall deadline; no worker hangs
    and no "bound to a different event loop" error; a trickling/slow transport
    times out rather than hanging.
  * C-006 — a malformed envelope whose ``content`` is not a string (e.g. an int)
    produces an explicit non-confirming failure, never an uncaught AttributeError.
  * C-007 — the provider's ACTUAL model/revision and labeling method are
    preserved (distinct from the configured alias), with bounded raw provenance
    and no credentials.
"""

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.autolearn import labeling


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length)) if length else {}
        prompt = ""
        try:
            prompt = req["messages"][1]["content"][0]["text"]
        except Exception:
            pass
        srv = self.server
        with srv.lock:
            srv.inflight += 1
            srv.max_inflight = max(srv.max_inflight, srv.inflight)
            srv.requests += 1
        try:
            if prompt.startswith("delay:"):
                time.sleep(float(prompt.split(":", 1)[1]))
            if prompt == "content-int":
                content = 42  # malformed: not a string (C-006)
            else:
                content = json.dumps({"label": "occupied", "confidence": 0.8})
            payload = json.dumps(
                {
                    "model": "qa/actual-revision-2",  # differs from configured alias
                    "choices": [{"message": {"content": content}}],
                    "usage": {"total_tokens": 7},
                }
            ).encode()
            if prompt == "trickle":
                # Trickle the body slower than the overall deadline tolerates.
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                for b in payload:
                    try:
                        self.wfile.write(bytes([b]))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    time.sleep(0.05)
            else:
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        finally:
            with srv.lock:
                srv.inflight -= 1


@pytest.fixture
def server(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.daemon_threads = True
    srv.lock = threading.Lock()
    srv.inflight = 0
    srv.max_inflight = 0
    srv.requests = 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_port
    monkeypatch.setattr(labeling.config, "VLM_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setattr(labeling.config, "VLM_MODEL", "qa/configured-alias")
    monkeypatch.setattr(labeling.config, "VLM_API_KEY", "")
    try:
        yield srv
    finally:
        srv.shutdown()


LABELS = ["occupied", "empty"]


def _call(prompt):
    return labeling.classify_sync(b"img-bytes", prompt=prompt, labels=LABELS)


# ----------------------------------------------------------------- C-001


def test_concurrent_sync_callers_serialize_and_never_hang(server, monkeypatch):
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_OVERALL_TIMEOUT", 5.0)
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_READ_TIMEOUT", 5.0)
    results: dict[int, dict] = {}

    def worker(i):
        try:
            results[i] = {"status": _call("delay:0.1").status}
        except Exception as exc:  # pragma: no cover - must not happen
            results[i] = {"exception": type(exc).__name__, "detail": str(exc)}

    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(i,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.02)
    for t in threads:
        t.join(timeout=6.0)

    assert all(not t.is_alive() for t in threads), "a sync worker hung"
    assert len(results) == 3
    assert all(r.get("status") == "labeled" for r in results.values()), results
    # Single owned transport => at most one real request in flight at a time.
    assert server.max_inflight == 1, server.max_inflight
    # No "bound to a different event loop" (or any) exception escaped.
    assert all("exception" not in r for r in results.values()), results


def test_admission_counted_inside_overall_deadline(server, monkeypatch):
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_OVERALL_TIMEOUT", 0.25)
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_READ_TIMEOUT", 1.0)

    async def run():
        t0 = time.monotonic()
        res = await asyncio.gather(
            *[
                labeling.classify(b"img", prompt="delay:0.5", labels=LABELS)
                for _ in range(3)
            ]
        )
        return time.monotonic() - t0, [r.status for r in res]

    elapsed, statuses = asyncio.run(run())
    assert statuses == ["timeout", "timeout", "timeout"], statuses
    # Were admission NOT inside the deadline, three serialized 0.5s requests would
    # take ~1.5s. With admission inside a 0.25s deadline it is well under 0.5s.
    assert elapsed < 0.5, elapsed


def test_async_cancellation_releases_capacity(server, monkeypatch):
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_OVERALL_TIMEOUT", 5.0)
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_READ_TIMEOUT", 5.0)

    async def run():
        task = asyncio.ensure_future(
            labeling.classify(b"img", prompt="delay:1.0", labels=LABELS)
        )
        await asyncio.sleep(0.1)
        task.cancel()
        # ``classify`` converts cancellation into an explicit ``cancelled``
        # candidate (and releases its admission slot on unwind).
        cand = await task
        # Capacity must be free again: a fresh quick call succeeds.
        follow = await labeling.classify(b"img", prompt="normal", labels=LABELS)
        return cand.status, follow.status

    cancel_status, follow_status = asyncio.run(run())
    assert cancel_status == "cancelled", cancel_status
    assert follow_status == "labeled"


def test_trickling_transport_times_out(server, monkeypatch):
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_OVERALL_TIMEOUT", 0.3)
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_READ_TIMEOUT", 0.3)
    t0 = time.monotonic()
    cand = _call("trickle")
    elapsed = time.monotonic() - t0
    assert cand.status == "timeout", cand
    assert elapsed < 2.0, elapsed  # bounded, not hung


# ----------------------------------------------------------------- C-006


def test_non_string_content_is_rejected_not_crashed(server):
    cand = _call("content-int")
    assert cand.status == "invalid_response", cand
    assert cand.label is None
    assert "string" in (cand.detail or "")


# ----------------------------------------------------------------- C-007


def test_actual_model_and_method_preserved(server):
    cand = _call("normal")
    assert cand.status == "labeled"
    # The provider's actual revision, not the configured alias.
    assert cand.model == "qa/actual-revision-2"
    assert cand.method == "chat_json"
    assert cand.confidence_calibrated is False
    assert cand.raw["response_model"] == "qa/actual-revision-2"
    assert cand.raw["configured_alias"] == "qa/configured-alias"
    assert cand.raw["usage"] == {"total_tokens": 7}
    # No credentials/headers leak into provenance.
    blob = json.dumps(cand.raw).lower()
    assert "authorization" not in blob and "bearer" not in blob
