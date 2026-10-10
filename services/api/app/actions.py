"""Authorized action execution.

Two real actions in M1:
- create_notification: persists a Notification row (shown in the UI).
- send_webhook: POSTs the event payload to a destination authorized against
  WEBHOOK_ALLOWLIST. Authorization canonicalizes the URL, rejects embedded
  userinfo, compares scheme/host/port exactly, enforces the permitted path
  prefix, and blocks hosts resolving to internal addresses. Non-allowlisted
  destinations are rejected (status "rejected"), never silently skipped.

Execution is idempotent per event: the engine's dedupe_key makes each event
unique, and actions run exactly once per stored event.
"""

from __future__ import annotations

import ipaddress
import logging
import posixpath
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy.orm import Session

from app import config
from app.db import ActionExecution, Notification, TrackEvent, utcnow

logger = logging.getLogger("visionflow.actions")

# Tests may inject an httpx transport (e.g. MockTransport) so webhook delivery
# can be exercised without real network access. Production leaves this None and
# uses the default transport.
webhook_transport: httpx.BaseTransport | None = None


def _effective_port(scheme: str, port: int | None) -> int:
    if port is not None:
        return port
    return 443 if scheme == "https" else 80


def _canonical_path(raw_path: str) -> str | None:
    """Return a normalized absolute path with '.'/'..' segments resolved, or
    None if the path uses ambiguous or percent/backslash-encoded traversal.

    Encoded separators (%2e, %2f, %5c) and backslashes are rejected outright
    because the server would decode them after our prefix check, re-opening the
    traversal hole. Plain '..' segments are collapsed so authorization sees the
    same effective path the HTTP client will ultimately request."""
    lowered = raw_path.lower()
    if any(tok in lowered for tok in ("%2e", "%2f", "%5c", "\\")):
        return None
    if not raw_path.startswith("/"):
        raw_path = "/" + raw_path
    normalized = posixpath.normpath(raw_path)
    # normpath drops a trailing slash and collapses "/" to "/"; that is fine for
    # prefix comparison. Absolute paths can never escape above root here.
    if normalized == ".":
        normalized = "/"
    return normalized


def _path_within(req_path: str, prefix: str) -> bool:
    """True if the normalized request path is at or below the normalized prefix,
    respecting segment boundaries so '/hookother' does not match '/hook'."""
    if prefix == "/":
        return True
    return req_path == prefix or req_path.startswith(prefix + "/")


def _parse_allowlist() -> list[tuple[str, str, int, str]]:
    """Canonicalize each configured allowlist entry into
    (scheme, hostname, port, path_prefix). Malformed entries are ignored."""
    entries: list[tuple[str, str, int, str]] = []
    for raw in config.WEBHOOK_ALLOWLIST:
        try:
            parts = urlsplit(raw)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                continue
            prefix = _canonical_path(parts.path or "/") or "/"
            entries.append(
                (
                    parts.scheme,
                    parts.hostname.lower(),
                    _effective_port(parts.scheme, parts.port),
                    prefix,
                )
            )
        except ValueError:
            continue
    return entries


def _resolves_to_internal(host: str) -> tuple[bool, str]:
    """Defense in depth against SSRF/DNS-rebinding: reject hostnames that
    resolve to loopback/private/link-local/reserved addresses. Explicit IP
    literals are trusted because they had to match the allowlist exactly."""
    try:
        ipaddress.ip_address(host)
        return False, "ok"  # operator explicitly allowlisted this literal IP
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return True, f"cannot resolve webhook host: {exc}"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True, f"webhook host resolves to internal address {ip}"
    return False, "ok"


def _authorize_webhook(url: str) -> tuple[bool, str, str | None]:
    """Authorize a webhook destination against WEBHOOK_ALLOWLIST and return the
    exact canonical URL that must be delivered.

    Canonicalizes the requested URL, rejects embedded userinfo (which HTTPX
    would otherwise use to disguise an internal destination), compares
    scheme/hostname/effective-port exactly, resolves '.'/'..' path segments, and
    enforces the permitted path prefix after normalization. The authorized URL
    and the delivered URL are identical, so the HTTP client cannot normalize a
    path out of the allowlist after the check (M1-006). Returns
    (allowed, reason, canonical_url)."""
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        return False, f"invalid webhook URL: {exc}", None
    if parts.scheme not in ("http", "https"):
        return False, "webhook scheme must be http or https", None
    if parts.username or parts.password:
        return False, "webhook URL must not contain userinfo", None
    host = (parts.hostname or "").lower()
    if not host:
        return False, "webhook URL missing host", None
    try:
        port = _effective_port(parts.scheme, parts.port)
    except ValueError:
        return False, "webhook URL has invalid port", None

    req_path = _canonical_path(parts.path or "/")
    if req_path is None:
        return False, "webhook URL uses ambiguous or encoded path traversal", None

    matched = False
    for scheme, ahost, aport, apath in _parse_allowlist():
        if (
            scheme == parts.scheme
            and ahost == host
            and aport == port
            and _path_within(req_path, apath)
        ):
            matched = True
            break
    if not matched:
        return False, "webhook destination not in WEBHOOK_ALLOWLIST; refusing to send", None

    internal, reason = _resolves_to_internal(host)
    if internal:
        return False, reason, None

    netloc = host if parts.port is None else f"{host}:{parts.port}"
    canonical_url = urlunsplit((parts.scheme, netloc, req_path, parts.query, ""))
    return True, "ok", canonical_url


def _webhook_authorization(url: str) -> tuple[bool, str]:
    """Backward-compatible 2-tuple wrapper around :func:`_authorize_webhook`."""
    allowed, reason, _ = _authorize_webhook(url)
    return allowed, reason


def _post_webhook(url: str, payload: dict) -> None:
    if webhook_transport is not None:
        with httpx.Client(transport=webhook_transport, timeout=10.0) as client:
            resp = client.post(url, json=payload)
    else:
        resp = httpx.post(url, json=payload, timeout=10.0)
    resp.raise_for_status()


def execute_action(session: Session, event: TrackEvent, action_type: str, action_config: dict) -> None:
    """Run one action for one stored event; records an ActionExecution row."""
    execution = ActionExecution(
        event_id=event.id, action_type=action_type, status="pending", attempt_count=1
    )
    session.add(execution)
    session.flush()

    try:
        if action_type == "create_notification":
            title = action_config.get("title") or f"VisionFlow: {event.type}"
            session.add(
                Notification(
                    event_id=event.id,
                    title=title,
                    message=event.detail or f"{event.type} at {event.video_timestamp:.1f}s",
                )
            )
            execution.status = "success"

        elif action_type == "send_webhook":
            url = action_config.get("url", "")
            allowed, reason, canonical_url = _authorize_webhook(url)
            if not allowed:
                execution.status = "rejected"
                execution.error = reason
            else:
                payload = {
                    "event_id": event.id,
                    "type": event.type,
                    "class_name": event.class_name,
                    "track_id": event.track_id,
                    "video_timestamp": event.video_timestamp,
                    "confidence": event.confidence,
                    "detail": event.detail,
                }
                # Deliver the exact authorized URL (M1-006): no component the
                # client could re-normalize past the allowlist check.
                _post_webhook(canonical_url, payload)
                execution.status = "success"
        else:
            execution.status = "failed"
            execution.error = f"unknown action type: {action_type}"
    except Exception as exc:  # noqa: BLE001 — record, don't crash the pipeline
        execution.status = "failed"
        execution.error = str(exc)[:1000]
        logger.warning("action %s failed for event %s: %s", action_type, event.id, exc)

    execution.executed_at = utcnow()
    event.action_status = "done" if execution.status == "success" else "failed"
    session.commit()
