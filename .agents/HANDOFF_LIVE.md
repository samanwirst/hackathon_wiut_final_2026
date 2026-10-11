# HANDOFF — LIVE Camera + Judges (new scope)

- **Milestone / scope:** LIVE (parallel isolated new scope, per FINAL_OWNER_DIRECTIVE).
- **Branch:** `experiment/live-judges` (worktree L).
- **Base:** `d35eb21` (accepted fallback `723a4a7` + owner exception receipt).
- **Implementation SHA:** `1c3e3b8bf94386c947efed5d8421ca88a6f1791f`.
- **Status:** ready for ONE independent new-scope review BEFORE public exposure. Not pushed, not deployed. No main merge.

## What was built (additive, isolated)

A separate public FastAPI sub-app `app.live` served on its own port
(`python -m app.live --port 8001`). It exposes ONLY authenticated live endpoints —
the legacy unauthenticated upload/control/media API (`app.main`) is never mounted on
it, so the public tunnel cannot reach legacy surfaces. The main app, the geometric
fallback, and the M2/M3 worktrees are untouched. Reuses the accepted M1 engine
(`visionflow_vision` detector/tracker + `ZoneEventEngine` + evidence JPEG + local
notifications).

Product flow: public landing with exactly two choices (Live Camera, Judges) → PIN
role auth → camera creates a private room and shares an opaque join code → judge joins
→ camera streams real `getUserMedia` frames over an authenticated WebSocket → judge
describes a task in natural language → the real `claude` CLI planner proposes a typed,
backend-validated task → judge reviews + approves/activates → the live YOLO worker
runs the task on the stream and produces events, annotated feed, evidence, and local
notifications → judge can pause/disable/replace the task without touching the camera.

### Changed files
- `services/api/app/live/{__init__,__main__,config,auth,rooms,dsl,planner,teacher,worker,app}.py`
- `services/api/app/live/static/{landing,camera,judges}.html, common.js, style.css`
- `tests/live/{conftest,test_live_auth,test_live_frames,test_live_planner,test_live_teacher}.py`
- `docs/LIVE_DEMO.md`, `.env.example` (live section)

## Security (new public surface)
- Shared PIN authenticates a ROLE only; it cannot list/join rooms or operate a
  workflow. No room-listing endpoint exists. Opaque per-room join code is the pairing
  secret — returned once to the authenticated owner, never in a URL or log.
- Session cookie HttpOnly+Secure+SameSite=strict, short TTL; double-submit CSRF header
  + Origin allowlist (no wildcard) on every mutation and both WebSocket upgrades.
- Role/room isolation: camera cannot plan/activate; judge cannot push frames; a
  session bound to one room cannot read another room's frames/events/evidence; evidence
  is path-scoped to the room (no traversal).
- Bounds: sessions, rooms, judges/room, login failures (per `X-Forwarded-For` IP),
  frame bytes ≤256 KiB and long edge ≤960, latest-frame-only inference, global
  inference capacity one, CPU threads 2.
- Secure cookie defaults ON; `VISIONFLOW_LIVE_INSECURE_COOKIE=true` is local-QA only.
- No secrets committed; PIN and tokens come only from env.

## Dynamic agent (real, no fallback)
- Real tool-less `claude` CLI: `--print --output-format json --tools "" --permission-mode
  dontAsk --strict-mcp-config --mcp-config '{"mcpServers":{}}' --no-session-persistence
  --safe-mode --system-prompt <caps+honesty> --json-schema <strict>` (all flags verified
  against `claude --help`). Prompt on stdin, `shell=False`, throwaway cwd outside repo,
  minimal env, bounded timeout (75 s), global concurrency 1, per-room budget (10) +
  cooldown (3 s), NO automatic retry, redacted stderr.
- Auth failure / timeout / non-zero exit / invalid JSON → explicit `unavailable`. There
  is NO keyword/heuristic fallback (the blocked M2 nl_compiler is never wired).
- Backend owns the DSL allowlist (`app.live.dsl`): COCO classes, geometric triggers,
  local actions, canonical zone geometry. Every proposal is re-validated; an injected
  instruction cannot escape the typed schema. Unsupported requests clarify/reject
  faithfully and never silently drop a condition.

## Teacher (non-actioning)
- Clean adapter to the existing private loopback SmolVLM endpoint (unchanged). Event-
  or manual-probe only (never per-frame), bounded budget/cooldown + image-hash cache.
  Output is uncalibrated and ALWAYS flagged uncertain; it can never by itself authorize
  an action. Unset `LIVE_TEACHER_BASE_URL` → unavailable. Full real Teacher testing is
  left for root (hardware).

## Tests actually run (on this SHA's tree)
- `tests/live/` — **34 passed** (auth/role/CSRF/Origin/brute-force/session-expiry/
  room-cross-access/WS origin+auth rejection; JPEG size/latest-only/drop; worker
  event→evidence→notification; task replacement; disable-while-camera-persists; version
  guard; planner strict typed validation + budget/cooldown via injected transport, QA
  only; Teacher non-actioning/uncertain/cached/budget).
- Full suite `tests/` — **229 passed**, 6 warnings, ~17 s (no M1/M2/M3 regressions).
- `scripts/check_structure.py` — OK.
- `apps/web` `npm run build` — OK (legacy UI untouched; live UI is static HTML served
  by the backend, no build step).
- `make smoke` (real YOLO, main app M1) — **PASS** (bus entered zone t=4.2s conf 0.76,
  evidence + notification; avg inference 62.1 ms).

### Out-of-band real verifications (not in the unit suite)
- **Real YOLO through the live worker** on an owned photographic QA frame (ultralytics
  `bus.jpg`, NOT a phone claim): detected `bus` conf 0.94, produced event + notification,
  inference ~27–30 ms after warmup.
- **Real `claude` CLI planner** (genuine novel prompts):
  - "Alert me when a car enters the service bay" → `entered_zone`, full_frame, notify.
  - "Notify me if a car stays in this area for more than 30 seconds" → `dwell_in_zone` 30 s.
  - "Focus on the bottle if anybody opens it" → `bottle` presence + focus_notify +
    `visual_observation` (temporal, uncertain), intent preserved.
  - "Watch the mechanic's workspace and flag a potentially unattended object" →
    `dwell_in_zone` backpack + temporal visual_observation + clarification on object types.
  - "Play loud music when it rains" → honestly rejected (no audio action; rain only an
    uncertain visual check).
- **Real uvicorn boot** smoke: health ok, landing served, wrong PIN 401 / right PIN 200,
  static assets 200.

## Runtime call cost bounds (actual)
- Planner CLI: ~**$0.03–0.09 per plan**, ~7–15 s, model `claude-fable-5` (CLI default).
  Per-room budget 10 + 3 s cooldown + global concurrency 1 cap the spend. Real
  model/usage/cost/duration are surfaced to the judge UI and recorded per plan.
- No new paid GPU. Teacher uses the existing local GPU endpoint only.

## Public proxy setup (for root, after review)
- `cloudflared tunnel --url http://127.0.0.1:8001` in front of the live port ONLY.
- Set `VISIONFLOW_LIVE_ALLOWED_ORIGINS=https://<tunnel-origin>` and
  `VISIONFLOW_DEMO_PIN`. Keep Secure cookies ON. `uvicorn --proxy-headers` is enabled by
  the entrypoint. Private fallback 18088 is untouched. See `docs/LIVE_DEMO.md`.

## Limitations / honest scope
- Semantic/temporal conditions are expressed as uncertain, non-actioning Teacher
  observations + the closest geometric trigger; never faked from a still frame.
- One shared detector across rooms: switching the active streaming room resets tracker
  identities (designed for one active camera per demo).
- Phone lock/background can pause capture; wake lock requested + limitation disclosed.
- Demo PIN is not production-grade auth.
- The real camera must be exercised by root/operator on hardware (not read here); never
  substitute prerecorded frames as a phone claim.

## Questions for the reviewer
1. Is the isolated sub-app boundary acceptable, or should the live app instead be a
   narrowly mounted subpath on the main app with a path allowlist?
2. CSRF uses Origin allowlist + double-submit token; is that sufficient for the public
   surface or do you want a stricter per-request nonce?
3. Confirm the planner cost bounds (budget 10 / cooldown 3 s / timeout 75 s) are within
   the owner's subscription acceptance for live judging.

## STOP
Stopping for ONE independent new-scope LIVE review before any public exposure. No push,
no deploy, no main merge performed.
