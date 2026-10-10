"""Real-TCP regressions for the owned Teacher transport (M2-003 / M2-007).

These open a genuine loopback socket to an owned HTTP/1.1 fixture server and drive
the production code path (``self._transport is None`` -> the raw-socket transport),
reproducing the independent reviewer's default-network findings:

- M2-003: the overall wall-clock deadline bounds connect, send, header receipt and
  body receipt — a header/byte trickle or a header-then-stall is cancelled near the
  deadline (the socket is actually closed), not after the full slow transfer.
- M2-007: a disable that lands while the connection is being opened revokes the
  unsent attempt, so NO request is ever written to the provider.

No MockTransport, no moved pause: the pause points (``socket.create_connection``,
a slow ``admit``) are exactly where the reviewer placed them, over real TCP. These
do NOT verify real visual inference — the fixture server is owned and its labels
are not model-quality evidence.
"""

import contextlib
import json
import socket
import socketserver
import threading
import time
from unittest.mock import patch

from app import pipeline as _pipeline  # noqa: F401 — warm the lazy pipeline import
from app.teacher import OpenAICompatibleTeacher
from app.vlm_router import VlmRouter


def _envelope(confidence=0.9) -> bytes:
    return json.dumps(
        {
            "choices": [
                {"message": {"content": json.dumps({"label": "yes", "confidence": confidence})}}
            ],
            "usage": {"total_tokens": 7},
        }
    ).encode()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.settimeout(3)
        raw = b""
        try:
            while b"\r\n\r\n" not in raw:
                d = sock.recv(8192)
                if not d:
                    return  # client closed before sending a request (revoked)
                raw += d
        except OSError:
            return
        head, _, body = raw.partition(b"\r\n\r\n")
        n = 0
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                n = int(line.split(b":", 1)[1])
        while len(body) < n:
            try:
                d = sock.recv(8192)
            except OSError:
                return
            if not d:
                break
            body += d
        # A complete request actually reached the server: record it.
        with self.server.lock:
            self.server.records.append({"at": time.monotonic()})
        payload = _envelope(self.server.confidence)
        mode = self.server.mode
        try:
            if mode == "slow_headers":
                sock.sendall(b"HTTP/1.1 200 OK\r\nX-P: ")
                for _ in range(20):
                    time.sleep(0.04)
                    sock.sendall(b"x")
                sock.sendall(
                    b"\r\nContent-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload
                )
            elif mode == "header_then_stall":
                time.sleep(0.16)
                sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 500\r\n\r\n")
                time.sleep(2)  # body never arrives within the deadline
            else:
                sock.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: "
                    + str(len(payload)).encode()
                    + b"\r\nConnection: close\r\n\r\n"
                    + payload
                )
        except OSError:
            pass


@contextlib.contextmanager
def _server(mode="fast", confidence=0.9):
    srv = _Server(("127.0.0.1", 0), _Handler)
    srv.records, srv.lock, srv.mode, srv.confidence = [], threading.Lock(), mode, confidence
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    t.start()
    try:
        yield srv, f"http://127.0.0.1:{srv.server_address[1]}/v1"
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(1)


def _teacher(url, timeout=0.2, **kw):
    # self._transport stays None -> the production raw-socket path is exercised.
    return OpenAICompatibleTeacher(
        url, "", "qa-fixture", "v1",
        overall_timeout=timeout, read_timeout=5, connect_timeout=5,
        max_retries=kw.pop("max_retries", 0), **kw,
    )


# -- control: the owned raw-socket transport genuinely works -------------------

def test_fast_real_tcp_confirms():
    with _server() as (srv, url):
        t = _teacher(url, timeout=3)
        r = t.classify(b"owned", "hood open?", ["yes", "no"])
    assert r.status == "ok", r
    assert r.confirmed is True
    assert len(srv.records) == 1


# -- M2-003: wall-clock deadline bounds header/body receipt -------------------

def test_slow_header_trickle_bounded_by_deadline():
    with _server(mode="slow_headers") as (srv, url):
        t = _teacher(url, timeout=0.2)
        start = time.monotonic()
        r = t.classify(b"owned", "hood open?", ["yes", "no"])
        elapsed = time.monotonic() - start
    assert r.status == "timeout", r
    assert r.confirmed is False
    # The header trickle alone lasts ~0.8s; the deadline must cut it near 0.2s.
    assert elapsed < 0.45, elapsed


def test_header_then_body_stall_bounded_by_deadline():
    with _server(mode="header_then_stall") as (srv, url):
        t = _teacher(url, timeout=0.2)
        start = time.monotonic()
        r = t.classify(b"owned", "hood open?", ["yes", "no"])
        elapsed = time.monotonic() - start
    assert r.status == "timeout", r
    assert elapsed < 0.5, elapsed


def test_capacity_freed_after_deadline_cancel():
    # After a deadline-cancelled request the single permit is free again and the
    # next request over a fresh connection succeeds (no abandoned reader).
    with _server(mode="slow_headers") as (srv, url):
        t = _teacher(url, timeout=0.15, max_concurrency=1)
        first = t.classify(b"owned", "q", ["yes", "no"])
        assert first.status == "timeout"
        assert t._semaphore.acquire(blocking=False)
        t._semaphore.release()
    with _server(mode="fast") as (srv, url):
        t._transport = None
        t.api_base = url.rstrip("/")
        t.overall_timeout = 3
        ok = t.classify(b"owned", "q", ["yes", "no"])
    assert ok.status == "ok"


# -- M2-003: a slow admission never emits a late POST -------------------------

def test_slow_admission_sends_no_late_post():
    with _server(mode="fast") as (srv, url):
        t = _teacher(url, timeout=0.1)
        router = VlmRouter(teacher_provider=lambda: t, sample_interval_s=0, cooldown_s=0)

        def slow_admit():
            time.sleep(0.25)  # authoritative approval returns well past the deadline
            return True

        start = time.monotonic()
        d = router.route(
            task_key="k", scope="k", prompt="q", labels=["yes", "no"],
            image_bytes=b"owned", admit=slow_admit,
        )
        elapsed = time.monotonic() - start
    # Admission resolved after the deadline, so the request must NOT be written.
    assert len(srv.records) == 0, srv.records
    assert d.result.status != "ok"
    assert router.counters.outbound_attempts == 0
    assert elapsed < 0.45, elapsed


def test_slow_connect_sends_no_late_post():
    real_conn = socket.create_connection

    def slow_conn(addr, *a, **kw):
        time.sleep(0.25)
        return real_conn(addr, *a, **kw)

    with _server(mode="fast") as (srv, url):
        t = _teacher(url, timeout=0.1)
        with patch.object(socket, "create_connection", slow_conn):
            r = t.classify(b"owned", "q", ["yes", "no"])
    assert r.status != "ok"
    assert len(srv.records) == 0, srv.records


# -- M2-007: disable during connect revokes the unsent attempt ----------------

def test_disable_during_connect_revokes_unsent_post():
    enabled = {"v": True}
    paused, release = threading.Event(), threading.Event()
    real_conn = socket.create_connection

    with _server(mode="fast") as (srv, url):
        target_port = srv.server_address[1]

        def paused_conn(addr, *a, **kw):
            if addr[1] == target_port:
                paused.set()
                assert release.wait(3)
            return real_conn(addr, *a, **kw)

        t = _teacher(url, timeout=3)
        router = VlmRouter(teacher_provider=lambda: t, sample_interval_s=0, cooldown_s=0)
        out = {}

        def work():
            out["d"] = router.route(
                task_key="k", scope="k", prompt="q", labels=["yes", "no"],
                image_bytes=b"owned", admit=lambda: enabled["v"],
            )

        with patch.object(socket, "create_connection", paused_conn):
            th = threading.Thread(target=work)
            th.start()
            assert paused.wait(3)
            before = len(srv.records)
            enabled["v"] = False  # a disable commits while the connection is opening
            release.set()
            th.join(5)
        assert not th.is_alive()

    assert before == 0
    assert len(srv.records) == 0, srv.records  # no POST ever written
    assert out["d"].status == "cancelled"
    assert out["d"].confirmed is False
    assert router.counters.outbound_attempts == 0


# -- budget/retry accounting preserved over real TCP --------------------------

class _RetryServer(_Server):
    pass


class _RetryHandler(_Handler):
    def handle(self):
        sock = self.request
        sock.settimeout(3)
        raw = b""
        try:
            while b"\r\n\r\n" not in raw:
                d = sock.recv(8192)
                if not d:
                    return
                raw += d
        except OSError:
            return
        head, _, body = raw.partition(b"\r\n\r\n")
        n = 0
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                n = int(line.split(b":", 1)[1])
        while len(body) < n:
            d = sock.recv(8192)
            if not d:
                break
            body += d
        with self.server.lock:
            self.server.records.append({"at": time.monotonic()})
            idx = len(self.server.records)
        payload = _envelope(0.9)
        if idx == 1:
            sock.sendall(b"HTTP/1.1 503 Busy\r\nContent-Length: 4\r\nConnection: close\r\n\r\nbusy")
        else:
            sock.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: "
                + str(len(payload)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + payload
            )


def test_real_tcp_retry_consumes_budget_and_confirms():
    srv = _RetryServer(("127.0.0.1", 0), _RetryHandler)
    srv.records, srv.lock, srv.mode, srv.confidence = [], threading.Lock(), "fast", 0.9
    th = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    th.start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/v1"
        t = _teacher(url, timeout=3, max_retries=1)
        router = VlmRouter(
            teacher_provider=lambda: t, sample_interval_s=0, cooldown_s=0, budget_per_task=2
        )
        d = router.route(
            task_key="k", scope="k", prompt="q", labels=["yes", "no"], image_bytes=b"owned"
        )
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(1)
    assert d.result.status == "ok"
    assert len(srv.records) == 2  # 503 then success, both actually sent
    assert router.counters.outbound_attempts == 2
    assert router.counters.completed == 1
