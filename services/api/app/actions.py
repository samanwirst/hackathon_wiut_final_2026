"""Authorized action execution.

Two real actions in M1:
- create_notification: persists a Notification row (shown in the UI).
- send_webhook: POSTs the event payload to a destination that matches the
  WEBHOOK_ALLOWLIST env prefix list. Non-allowlisted destinations are rejected
  (status "rejected"), never silently skipped.

Execution is idempotent per event: the engine's dedupe_key makes each event
unique, and actions run exactly once per stored event.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app import config
from app.db import ActionExecution, Notification, TrackEvent, utcnow

logger = logging.getLogger("visionflow.actions")


def _webhook_allowed(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in config.WEBHOOK_ALLOWLIST)


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
            if not _webhook_allowed(url):
                execution.status = "rejected"
                execution.error = (
                    "webhook destination not in WEBHOOK_ALLOWLIST; refusing to send"
                )
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
                resp = httpx.post(url, json=payload, timeout=10.0)
                resp.raise_for_status()
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
