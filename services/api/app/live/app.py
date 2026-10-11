"""Public LIVE Camera + Judges FastAPI sub-application.

This is an ISOLATED public surface. It contains ONLY authenticated live-demo
endpoints and never imports or re-exposes the legacy unauthenticated upload /
control / media endpoints from ``app.main``. Deploy this app (not the private
fallback) behind the public HTTPS tunnel.

Security model (see auth.py): shared PIN -> role; opaque per-room join code ->
room membership; HttpOnly+Secure+SameSite session cookie; double-submit CSRF +
Origin allowlist on every mutation and WebSocket upgrade; bounded sessions,
rooms, login attempts, and frame sizes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import (
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.live import auth, config, planner, rooms, teacher, worker
from app.live.dsl import LiveTask

logger = logging.getLogger("visionflow.live.app")

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="VisionFlow Live", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    rooms.LIVE_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    worker.start()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------- helpers


def _client_ip(request: Request) -> str:
    # Honor a single proxy hop (cloudflared) via X-Forwarded-For, else peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _set_session_cookies(resp: Response, sess: auth.Session) -> None:
    resp.set_cookie(
        config.SESSION_COOKIE_NAME, sess.token,
        max_age=config.SESSION_TTL_SECONDS, httponly=True,
        secure=config.COOKIE_SECURE, samesite="strict", path="/",
    )
    # CSRF token is readable by JS (double-submit), so NOT HttpOnly.
    resp.set_cookie(
        config.CSRF_COOKIE_NAME, sess.csrf,
        max_age=config.SESSION_TTL_SECONDS, httponly=False,
        secure=config.COOKIE_SECURE, samesite="strict", path="/",
    )


def require_session(request: Request) -> auth.Session:
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    sess = auth.get_session(token)
    if sess is None:
        raise HTTPException(401, "authentication required")
    return sess


def require_mutation(request: Request) -> auth.Session:
    """Session + Origin + CSRF for any state-changing request."""
    if not auth.origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(403, "origin not allowed")
    sess = require_session(request)
    if not auth.csrf_valid(sess, request.headers.get("x-csrf-token")):
        raise HTTPException(403, "invalid CSRF token")
    return sess


def _require_room_member(sess: auth.Session, room_id: str) -> rooms.RoomState:
    room = rooms.get_room(room_id)
    if room is None:
        raise HTTPException(404, "room not found")
    if sess.room_id != room_id:
        # A valid session bound to a different room (or none) cannot cross over.
        raise HTTPException(403, "not a member of this room")
    return room


# ---------------------------------------------------------------- pages


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "landing.html").read_text())


@app.get("/camera", response_class=HTMLResponse)
def camera_page() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "camera.html").read_text())


@app.get("/judges", response_class=HTMLResponse)
def judges_page() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "judges.html").read_text())


@app.get("/api/live/health")
def health():
    return {
        "status": "ok",
        "service": "visionflow-live",
        "pin_configured": auth.pin_configured(),
        "planner_enabled": config.PLANNER_ENABLED,
        "teacher_available": teacher.available(),
        "cookie_secure": config.COOKIE_SECURE,
    }


# ---------------------------------------------------------------- auth


@app.post("/api/live/login")
def login(request: Request, response: Response, body: dict = Body(...)):
    if not auth.origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(403, "origin not allowed")
    ip = _client_ip(request)
    if auth.login_locked(ip):
        raise HTTPException(429, "too many attempts; try again later")
    role = str(body.get("role", "")).strip().lower()
    pin = str(body.get("pin", ""))
    if role not in {"camera", "judge"}:
        raise HTTPException(400, "role must be 'camera' or 'judge'")
    if not auth.verify_pin(pin):
        auth.record_failure(ip)
        raise HTTPException(401, "invalid PIN")
    auth.clear_failures(ip)
    try:
        sess = auth.create_session(role)
    except RuntimeError:
        raise HTTPException(503, "session capacity reached")
    _set_session_cookies(response, sess)
    return {"role": sess.role, "csrf": sess.csrf}


@app.post("/api/live/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    auth.destroy_session(token)
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(config.CSRF_COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/live/me")
def me(sess: auth.Session = Depends(require_session)):
    return {"role": sess.role, "room_id": sess.room_id, "owns_room": sess.owns_room}


# ---------------------------------------------------------------- rooms


@app.post("/api/live/rooms")
def create_room(request: Request, sess: auth.Session = Depends(require_mutation)):
    if sess.role != "camera":
        raise HTTPException(403, "only a camera session can create a room")
    if sess.room_id:
        raise HTTPException(409, "session already bound to a room")
    try:
        room = rooms.create_room(sess.token)
    except RuntimeError:
        raise HTTPException(503, "room capacity reached")
    auth.bind_room(sess.token, room.room_id, owns=True)
    # The join code is returned ONCE to the authenticated owner and never logged
    # or placed in any URL. The owner shares it manually with a judge.
    return {"room_id": room.room_id, "join_code": room.join_code}


@app.post("/api/live/rooms/join")
def join_room(request: Request, sess: auth.Session = Depends(require_mutation),
              body: dict = Body(...)):
    if sess.role != "judge":
        raise HTTPException(403, "only a judge session can join a room")
    join_code = str(body.get("join_code", "")).strip()
    if not join_code:
        raise HTTPException(400, "join_code required")
    room = rooms.room_by_join_code(join_code)
    if room is None:
        # The shared PIN alone must not reveal rooms; an unknown code is a plain 404.
        raise HTTPException(404, "no room for that join code")
    with room.lock:
        if sess.token not in room.judges and len(room.judges) >= config.MAX_JUDGES_PER_ROOM:
            raise HTTPException(503, "room is full")
        room.judges.add(sess.token)
    auth.bind_room(sess.token, room.room_id, owns=False)
    return {"room_id": room.room_id}


def _state_payload(room: rooms.RoomState) -> dict:
    with room.lock:
        return {
            "room_id": room.room_id,
            "task": room.task,
            "task_version": room.task_version,
            "task_enabled": room.task_enabled,
            "task_paused": room.task_paused,
            "history": list(room.history),
            "metrics": {
                "frames_received": room.frames_received,
                "frames_dropped": room.frames_dropped,
                "frames_inferred": room.frames_inferred,
                "observed_fps": room.observed_fps(),
                "last_inference_ms": round(room.last_inference_ms, 1),
                "last_recv_age_s": round(time.time() - room.last_recv_ts, 2) if room.last_recv_ts else None,
                "has_frame": room.latest_jpeg is not None,
                "judges": len(room.judges),
            },
            "events": [
                {
                    "id": e.id, "type": e.type, "class_name": e.class_name,
                    "track_id": e.track_id, "detail": e.detail,
                    "confidence": round(e.confidence, 3),
                    "capture_ts": e.capture_ts, "recv_ts": e.recv_ts, "event_ts": e.event_ts,
                    "task_version": e.task_version,
                    "evidence_url": (
                        f"/api/live/rooms/{room.room_id}/evidence/{e.evidence_file}"
                        if e.evidence_file else None
                    ),
                    "visual_observation": e.visual_observation,
                    "action_status": e.action_status,
                }
                for e in list(room.events)[-80:]
            ],
            "notifications": list(room.notifications)[-80:],
            "planner_attempts_used": planner.room_attempts_used(room.room_id),
            "planner_budget": config.PLANNER_ROOM_BUDGET,
        }


@app.get("/api/live/rooms/{room_id}/state")
def room_state(room_id: str, sess: auth.Session = Depends(require_session)):
    room = _require_room_member(sess, room_id)
    return _state_payload(room)


@app.get("/api/live/rooms/{room_id}/frame")
def room_frame(room_id: str, sess: auth.Session = Depends(require_session)):
    room = _require_room_member(sess, room_id)
    with room.lock:
        jpeg = room.annotated_jpeg or room.latest_jpeg
        meta = dict(room.annotated_meta or room.latest_meta)
    if jpeg is None:
        raise HTTPException(404, "no frame yet")
    headers = {"Cache-Control": "no-store"}
    if meta.get("ts"):
        headers["X-Frame-Ts"] = str(meta["ts"])
    return Response(content=jpeg, media_type="image/jpeg", headers=headers)


@app.get("/api/live/rooms/{room_id}/evidence/{filename}")
def room_evidence(room_id: str, filename: str, sess: auth.Session = Depends(require_session)):
    room = _require_room_member(sess, room_id)
    # Prevent path traversal and cross-room access: filename must belong to room.
    if "/" in filename or ".." in filename or not filename.startswith(f"room_{room_id}_"):
        raise HTTPException(404, "evidence not found")
    path = rooms.LIVE_EVIDENCE_DIR / filename
    if not path.exists():
        raise HTTPException(404, "evidence not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- task control (judges)


@app.post("/api/live/rooms/{room_id}/task/plan")
def plan_task(room_id: str, sess: auth.Session = Depends(require_mutation),
              body: dict = Body(...)):
    if sess.role != "judge":
        raise HTTPException(403, "only a judge can plan a task")
    room = _require_room_member(sess, room_id)
    text = str(body.get("text", ""))
    result = planner.plan(text, room.room_id)
    return {
        "status": result.status,
        "original_text": text,
        "task": result.task,
        "proposal": result.proposal,
        "clarification": result.clarification,
        "unsupported_reason": result.unsupported_reason,
        "error": result.error,
        "provenance": {
            "model": result.model, "cost_usd": result.cost_usd,
            "duration_ms": result.duration_ms, "usage": result.usage,
            "attempt": result.attempt,
        },
    }


@app.post("/api/live/rooms/{room_id}/task/activate")
def activate_task(room_id: str, sess: auth.Session = Depends(require_mutation),
                  body: dict = Body(...)):
    if sess.role != "judge":
        raise HTTPException(403, "only a judge can activate a task")
    room = _require_room_member(sess, room_id)
    raw_task = body.get("task")
    if not isinstance(raw_task, dict):
        raise HTTPException(400, "task object required")
    # Re-validate against the backend-owned DSL: the UI is never trusted.
    try:
        task = LiveTask.model_validate(raw_task)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"task failed validation: {exc}")
    with room.lock:
        fw = room.latest_meta.get("w") or 1
        fh = room.latest_meta.get("h") or 1
        version = rooms.activate_task(room, task.model_dump(), fw, fh)
    return {"ok": True, "task_version": version, "task": task.model_dump()}


@app.post("/api/live/rooms/{room_id}/task/state")
def task_state(room_id: str, sess: auth.Session = Depends(require_mutation),
               body: dict = Body(...)):
    if sess.role != "judge":
        raise HTTPException(403, "only a judge can control the task")
    room = _require_room_member(sess, room_id)
    enabled = body.get("enabled")
    paused = body.get("paused")
    with room.lock:
        rooms.set_task_state(
            room,
            enabled=bool(enabled) if enabled is not None else None,
            paused=bool(paused) if paused is not None else None,
        )
        return {"ok": True, "task_version": room.task_version,
                "task_enabled": room.task_enabled, "task_paused": room.task_paused}


@app.post("/api/live/rooms/{room_id}/probe")
def probe_teacher(room_id: str, sess: auth.Session = Depends(require_mutation),
                  body: dict = Body(...)):
    if sess.role != "judge":
        raise HTTPException(403, "only a judge can probe")
    room = _require_room_member(sess, room_id)
    question = str(body.get("question", "")).strip()
    labels = body.get("labels") or ["yes", "no"]
    if len(question) < 3:
        raise HTTPException(400, "question too short")
    with room.lock:
        jpeg = room.latest_jpeg
    if jpeg is None:
        raise HTTPException(409, "no frame to probe")
    obs = teacher.observe(room.room_id, question, [str(x) for x in labels][:6], [jpeg])
    return {
        "status": obs.status, "label": obs.label, "confidence": obs.confidence,
        "uncertain": obs.uncertain, "image_hash": obs.image_hash, "model": obs.model,
        "latency_ms": obs.latency_ms, "raw": obs.raw, "reason": obs.reason,
    }


# ---------------------------------------------------------------- websockets


def _ws_session(ws: WebSocket) -> auth.Session | None:
    token = ws.cookies.get(config.SESSION_COOKIE_NAME)
    return auth.get_session(token)


def _ws_origin_ok(ws: WebSocket) -> bool:
    return auth.origin_allowed(ws.headers.get("origin"), ws.headers.get("host"))


@app.websocket("/api/live/ws/camera")
async def ws_camera(ws: WebSocket):
    if not _ws_origin_ok(ws):
        await ws.close(code=4403)
        return
    sess = _ws_session(ws)
    if sess is None or sess.role != "camera" or not sess.owns_room or not sess.room_id:
        await ws.close(code=4401)
        return
    room = rooms.get_room(sess.room_id)
    if room is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    pending_meta: dict = {}
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                try:
                    pending_meta = json.loads(msg["text"])
                    if not isinstance(pending_meta, dict):
                        pending_meta = {}
                except (ValueError, TypeError):
                    pending_meta = {}
                continue
            data = msg.get("bytes")
            if data is None:
                continue
            if len(data) > config.MAX_FRAME_BYTES:
                with room.lock:
                    room.frames_dropped += 1
                pending_meta = {}
                continue
            _ingest_frame(room, data, pending_meta)
            pending_meta = {}
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("camera ws error room=%s: %s", room.room_id, exc)


def _ingest_frame(room: rooms.RoomState, data: bytes, meta: dict) -> None:
    now = time.time()
    w = meta.get("w"); h = meta.get("h")
    # Enforce the long-edge bound using declared dimensions when present.
    if isinstance(w, int) and isinstance(h, int) and max(w, h) > config.MAX_FRAME_LONG_EDGE:
        with room.lock:
            room.frames_dropped += 1
        return
    seq = meta.get("seq")
    capture_ts = meta.get("capture_ts")
    with room.lock:
        room.frames_received += 1
        room.last_recv_ts = now
        room.recv_times.append(now)
        # Keep ONLY the latest frame for inference (drop stale); bounded temporal
        # deque retains a few recent raw frames for before/after probes.
        room.latest_jpeg = data
        room.latest_meta = {"w": w, "h": h, "seq": seq,
                            "capture_ts": capture_ts, "recv_ts": now}
        room.temporal.append({"jpeg": data, "ts": now, "seq": seq})
        room.frame_dirty = True


@app.websocket("/api/live/ws/judge")
async def ws_judge(ws: WebSocket):
    if not _ws_origin_ok(ws):
        await ws.close(code=4403)
        return
    sess = _ws_session(ws)
    if sess is None or sess.role != "judge" or not sess.room_id:
        await ws.close(code=4401)
        return
    room = rooms.get_room(sess.room_id)
    if room is None or sess.token not in room.judges:
        await ws.close(code=4404)
        return
    await ws.accept()
    last_sent_ts = None
    interval = 1.0 / max(1.0, config.TARGET_PROCESS_FPS)
    try:
        while True:
            with room.lock:
                jpeg = room.annotated_jpeg
                ts = room.annotated_meta.get("ts")
            if jpeg is not None and ts != last_sent_ts:
                await ws.send_bytes(jpeg)
                last_sent_ts = ts
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.info("judge ws closed room=%s: %s", room.room_id, exc)
