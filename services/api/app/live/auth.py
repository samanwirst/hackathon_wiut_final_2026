"""Authentication, sessions, rate limiting, and CSRF/Origin checks for the live app.

The shared demo PIN authenticates a ROLE only. It deliberately does NOT grant
access to any room: joining a room requires the opaque per-room join code, so a
PIN holder cannot enumerate or join rooms or operate a workflow.

Sessions are opaque server-side tokens delivered in an HttpOnly, Secure,
SameSite cookie with a short TTL. A double-submit CSRF token plus an Origin
allowlist protects every state-changing request and WebSocket upgrade.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.live import config

Role = str  # "camera" | "judge"


@dataclass
class Session:
    token: str
    role: Role
    csrf: str
    created_at: float
    expires_at: float
    room_id: str | None = None  # the single room this session is bound to
    owns_room: bool = False     # camera that created the room

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) >= self.expires_at


_sessions: dict[str, Session] = {}
_sessions_lock = threading.Lock()

# Per-IP failed-login tracking for rate limiting.
_failures: dict[str, list[float]] = {}
_failures_lock = threading.Lock()


def pin_configured() -> bool:
    return bool(config.DEMO_PIN)


def verify_pin(pin: str) -> bool:
    """Constant-time PIN check. An unconfigured PIN rejects everything."""
    if not config.DEMO_PIN:
        return False
    return hmac.compare_digest(str(pin or ""), config.DEMO_PIN)


# --- rate limiting ---------------------------------------------------------


def _prune_failures(ip: str, now: float) -> list[float]:
    window = config.LOGIN_WINDOW_SECONDS
    fails = [t for t in _failures.get(ip, []) if now - t < window]
    _failures[ip] = fails
    return fails


def login_locked(ip: str) -> bool:
    now = time.time()
    with _failures_lock:
        fails = _prune_failures(ip, now)
        return len(fails) >= config.LOGIN_MAX_FAILURES


def record_failure(ip: str) -> None:
    now = time.time()
    with _failures_lock:
        _prune_failures(ip, now)
        _failures.setdefault(ip, []).append(now)


def clear_failures(ip: str) -> None:
    with _failures_lock:
        _failures.pop(ip, None)


# --- sessions --------------------------------------------------------------


def _sweep(now: float) -> None:
    dead = [t for t, s in _sessions.items() if s.expired(now)]
    for t in dead:
        _sessions.pop(t, None)


def create_session(role: Role) -> Session:
    now = time.time()
    with _sessions_lock:
        _sweep(now)
        if len(_sessions) >= config.MAX_SESSIONS:
            raise RuntimeError("session capacity reached")
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        sess = Session(
            token=token,
            role=role,
            csrf=csrf,
            created_at=now,
            expires_at=now + config.SESSION_TTL_SECONDS,
        )
        _sessions[token] = sess
        return sess


def get_session(token: str | None) -> Session | None:
    if not token:
        return None
    now = time.time()
    with _sessions_lock:
        sess = _sessions.get(token)
        if sess is None:
            return None
        if sess.expired(now):
            _sessions.pop(token, None)
            return None
        return sess


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with _sessions_lock:
        _sessions.pop(token, None)


def bind_room(token: str, room_id: str, owns: bool) -> None:
    with _sessions_lock:
        sess = _sessions.get(token)
        if sess is not None:
            sess.room_id = room_id
            sess.owns_room = owns


def active_session_count() -> int:
    with _sessions_lock:
        _sweep(time.time())
        return len(_sessions)


def _reset_for_tests() -> None:
    """Clear all in-memory auth state (used by unit tests only)."""
    with _sessions_lock:
        _sessions.clear()
    with _failures_lock:
        _failures.clear()


# --- origin / CSRF ---------------------------------------------------------


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Allow same-origin (no Origin header or Origin host == request Host) and
    any explicitly allowlisted origin. Everything else is refused — never ``*``."""
    if not origin:
        # Non-browser or same-origin navigation without an Origin header.
        return True
    if config.ALLOWED_ORIGINS and origin in config.ALLOWED_ORIGINS:
        return True
    if host:
        try:
            oh = urlparse(origin).netloc
        except ValueError:
            return False
        if oh and oh == host:
            return True
    # If an allowlist is configured, anything not in it is refused.
    return False


def csrf_valid(sess: Session, header_token: str | None) -> bool:
    if not header_token:
        return False
    return hmac.compare_digest(sess.csrf, header_token)
