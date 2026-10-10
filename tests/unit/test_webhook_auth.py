"""Webhook SSRF authorization tests (M1-001).

The authorization layer must canonicalize URLs, reject embedded userinfo (which
HTTPX would otherwise use to reach an internal host), compare scheme/host/port
exactly, and enforce the configured path prefix.
"""

import httpx
import pytest

from app import actions, config, db


@pytest.fixture
def session(tmp_path):
    db.init_db(str(tmp_path / "wh.db"))
    s = db.get_session()
    try:
        yield s
    finally:
        s.close()


def _make_event(session) -> db.TrackEvent:
    ev = db.TrackEvent(
        source_id=1,
        workflow_id=1,
        track_id=1,
        type="object_entered_zone",
        class_name="car",
        video_timestamp=1.0,
        confidence=0.9,
        detail="car entered",
        dedupe_key=f"k-{id(object())}",
    )
    session.add(ev)
    session.commit()
    return ev


# ------------------------------------------------------- pure authorization


def test_userinfo_disguising_internal_host_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://approved.example"])
    allowed, reason = actions._webhook_authorization(
        "http://approved.example@127.0.0.1:9876/private"
    )
    assert not allowed
    assert "userinfo" in reason.lower()


def test_exact_ip_literal_match_allowed(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://127.0.0.1:9876/hook"])
    allowed, reason = actions._webhook_authorization("http://127.0.0.1:9876/hook")
    assert allowed, reason


def test_path_prefix_enforced(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://127.0.0.1:9876/hook"])
    allowed, _ = actions._webhook_authorization("http://127.0.0.1:9876/elsewhere")
    assert not allowed


def test_wrong_host_rejected(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://127.0.0.1:9876/"])
    allowed, _ = actions._webhook_authorization("http://127.0.0.2:9876/")
    assert not allowed


def test_wrong_port_rejected(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://127.0.0.1:9876/"])
    allowed, _ = actions._webhook_authorization("http://127.0.0.1:8000/")
    assert not allowed


def test_empty_allowlist_rejects_everything(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", [])
    allowed, reason = actions._webhook_authorization("http://127.0.0.1:9876/")
    assert not allowed
    assert "allowlist" in reason.lower()


# ------------------------------------------------- end-to-end via transport


def test_userinfo_url_never_reaches_transport(session, monkeypatch):
    """A real httpx client with MockTransport must never observe the request:
    authorization rejects the userinfo URL before any delivery."""
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://approved.example/"])
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200)

    monkeypatch.setattr(actions, "webhook_transport", httpx.MockTransport(handler))

    ev = _make_event(session)
    actions.execute_action(
        session, ev, "send_webhook",
        {"url": "http://approved.example@127.0.0.1:9876/private"},
    )

    assert seen == []  # no network request was sent
    exec_row = (
        session.query(db.ActionExecution)
        .filter(db.ActionExecution.event_id == ev.id)
        .one()
    )
    assert exec_row.status == "rejected"
    assert "userinfo" in (exec_row.error or "").lower()


def test_allowlisted_destination_is_delivered(session, monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_ALLOWLIST", ["http://127.0.0.1:9000/hook"])
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200)

    monkeypatch.setattr(actions, "webhook_transport", httpx.MockTransport(handler))

    ev = _make_event(session)
    actions.execute_action(
        session, ev, "send_webhook", {"url": "http://127.0.0.1:9000/hook"}
    )

    exec_row = (
        session.query(db.ActionExecution)
        .filter(db.ActionExecution.event_id == ev.id)
        .one()
    )
    assert exec_row.status == "success", exec_row.error
    assert seen == ["127.0.0.1"]
