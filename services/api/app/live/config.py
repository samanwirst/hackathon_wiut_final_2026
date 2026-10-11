"""Runtime configuration for the LIVE Camera + Judges sub-application.

This is a SEPARATE public surface from the main M1 API. Nothing here is imported
by ``app.main``; the live app is mounted on its own port so the public tunnel
never exposes the legacy unauthenticated upload/control/media endpoints.

Secrets (the demo PIN) come ONLY from the environment. They are never hardcoded
in source, tests, or logs. Session cookies default to Secure so an accidental
HTTP deployment cannot leak them; local QA may opt out with an explicit flag.
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger("visionflow.live.config")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    _log.warning("Unrecognized %s=%r; using default %s", name, raw, default)
    return default


# --- authentication --------------------------------------------------------
# The shared demo PIN authenticates a ROLE (camera or judge). It is NOT
# production-grade security; the per-room join code is the real pairing secret.
# An unset PIN means the live app refuses every login (fail-closed) rather than
# accepting an empty password.
DEMO_PIN = os.environ.get("VISIONFLOW_DEMO_PIN", "")

SESSION_TTL_SECONDS = int(os.environ.get("VISIONFLOW_LIVE_SESSION_TTL", "1800"))  # 30 min
SESSION_COOKIE_NAME = "vf_live_session"
CSRF_COOKIE_NAME = "vf_live_csrf"

# Secure cookie default TRUE. Only an explicit opt-out (local HTTP QA) sets
# VISIONFLOW_LIVE_INSECURE_COOKIE=true; a public HTTPS deployment keeps it on.
COOKIE_SECURE = not _flag("VISIONFLOW_LIVE_INSECURE_COOKIE", False)

# --- bounds (fail-closed resource limits) ----------------------------------
MAX_SESSIONS = int(os.environ.get("VISIONFLOW_LIVE_MAX_SESSIONS", "64"))
MAX_ROOMS = int(os.environ.get("VISIONFLOW_LIVE_MAX_ROOMS", "8"))
MAX_JUDGES_PER_ROOM = int(os.environ.get("VISIONFLOW_LIVE_MAX_JUDGES", "8"))

# Login rate limiting (per client IP): N failures within WINDOW -> locked out.
LOGIN_MAX_FAILURES = int(os.environ.get("VISIONFLOW_LIVE_LOGIN_MAX_FAILURES", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("VISIONFLOW_LIVE_LOGIN_WINDOW", "300"))

# --- frame ingest bounds ---------------------------------------------------
MAX_FRAME_BYTES = int(os.environ.get("VISIONFLOW_LIVE_MAX_FRAME_BYTES", str(256 * 1024)))
MAX_FRAME_LONG_EDGE = int(os.environ.get("VISIONFLOW_LIVE_MAX_LONG_EDGE", "960"))
MIN_FRAME_LONG_EDGE = 64
# Bounded short temporal history kept in memory per room for before/after probes.
TEMPORAL_DEQUE_LEN = int(os.environ.get("VISIONFLOW_LIVE_TEMPORAL_DEQUE", "8"))
# Event evidence retention (bounded TTL + count) per room.
EVIDENCE_MAX_PER_ROOM = int(os.environ.get("VISIONFLOW_LIVE_EVIDENCE_MAX", "60"))

# --- origin / CSRF ---------------------------------------------------------
# Comma-separated allowlist of exact origins permitted for state-changing HTTP
# and WebSocket upgrades. NO wildcard. When empty, same-origin requests (no
# Origin header, or Origin matching Host) are still allowed; cross-origin is
# refused. Populate this for the deployed HTTPS origin.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("VISIONFLOW_LIVE_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

# --- Claude CLI planner ----------------------------------------------------
PLANNER_ENABLED = _flag("VISIONFLOW_LIVE_PLANNER", True)
PLANNER_CLI = os.environ.get("VISIONFLOW_LIVE_CLAUDE_BIN", "claude")
PLANNER_TIMEOUT_SECONDS = float(os.environ.get("VISIONFLOW_LIVE_PLANNER_TIMEOUT", "75"))
PLANNER_MODEL = os.environ.get("VISIONFLOW_LIVE_PLANNER_MODEL", "").strip()  # "" -> CLI default
# Per-room planner attempt budget (whole process lifetime) and cooldown between
# attempts. Protects the real subscription from a flood of judge prompts.
PLANNER_ROOM_BUDGET = int(os.environ.get("VISIONFLOW_LIVE_PLANNER_BUDGET", "10"))
PLANNER_COOLDOWN_SECONDS = float(os.environ.get("VISIONFLOW_LIVE_PLANNER_COOLDOWN", "3"))

# --- Teacher (non-actioning observation adapter) ---------------------------
# Reuses the existing private loopback SmolVLM endpoint. Unset -> unavailable.
TEACHER_BASE_URL = os.environ.get("LIVE_TEACHER_BASE_URL", "").strip()
TEACHER_MODEL = os.environ.get("LIVE_TEACHER_MODEL", "HuggingFaceTB/SmolVLM-500M-Instruct").strip()
TEACHER_TOKEN = os.environ.get("LIVE_TEACHER_TOKEN", "").strip()
TEACHER_TIMEOUT_SECONDS = float(os.environ.get("LIVE_TEACHER_TIMEOUT", "60"))
TEACHER_ROOM_BUDGET = int(os.environ.get("LIVE_TEACHER_ROOM_BUDGET", "20"))
TEACHER_COOLDOWN_SECONDS = float(os.environ.get("LIVE_TEACHER_COOLDOWN", "4"))

# --- worker ----------------------------------------------------------------
THREAD_COUNT = int(os.environ.get("VISIONFLOW_THREADS", "2"))
TARGET_PROCESS_FPS = float(os.environ.get("VISIONFLOW_LIVE_PROCESS_FPS", "4"))
