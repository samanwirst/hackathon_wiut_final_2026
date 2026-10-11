# HANDOFF — LIVE → VIDEO pivot, final correction pass

**Milestone:** LIVE video product (owner input-source pivot)
**Branch:** `experiment/live-judges` (worktree L)
**Base (pass start) HEAD:** `f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49`
**Implementation SHA:** `a3696ad` (branch `experiment/live-judges`; not pushed)
**Date:** 2026-10-11, before the 05:45 UTC correction deadline.

This pass executed the **owner input-source pivot**: the primary public demo is now
**pre-recorded VIDEO inference**, not a physical camera. The unfinished camera /
WebSocket two-device path is **disabled on the public surface**. The isolated live
subapp authentication / planner / approval / engine primitives are reused; the
legacy `app.main` is never mounted.

## What shipped (primary video product)

Single public subapp (`app.live.app`), HTTPS-ready, authenticated, on its own port.

- **Authenticated bounded video upload** — `POST /api/live/rooms/{id}/video`
  (room-owner only; Origin allowlist + session + CSRF + ownership). Body is streamed
  to an **opaque per-room path** and the hard byte cap is enforced **byte-by-byte**
  (a lying/absent `Content-Length` cannot bypass it; `Content-Length` over the cap is
  also rejected pre-stream). Decode-validated with OpenCV (at least one real frame
  must decode); bounded fps / frame-count / dimensions / duration. Invalid, oversize,
  or undecodable input is rejected cleanly (`413`/`422`/`400`) and the partial file
  removed. No client-supplied filename/path is ever used.
- **Real processing** — `POST /api/live/rooms/{id}/video/process` and automatic rerun
  on approval. A per-room background job (`app.live.video`) decodes frames in order
  and runs the **same real YOLO detector + ByteTrack tracker** and the **same
  `ZoneEventEngine`** as M1, builds annotated frames, events, evidence JPEGs and local
  notifications.
- **Video clock** — the temporal (dwell/cooldown) timeline uses the **source video
  clock** (`frame_index / fps`), never processing wall time. Wall latency is recorded
  separately (`processing_latency_ms`) and never labelled "real-time". `duration_seconds`
  (incl. decimals like 1.25) flows unchanged through DSL → approval → runtime.
- **Evidence provenance** — each event carries `source_sha256`, `frame_index`,
  `video_ts_seconds`, `source_fps`, `recv_ts`, `processing_ts`, `processing_latency_ms`,
  `frame_sha256` (raw decoded frame), `detector_model`, and `workflow_version`.
- **NL → typed task** — the real tool-less Claude CLI planner is unchanged in contract
  (no tools/MCP/session, argv list, text on STDIN, throwaway cwd, bounded deadline,
  per-room budget/cooldown). The judge reviews the exact typed-validated JSON and
  explicitly approves; activation re-validates against the backend DSL and binds to a
  monotonic `task_version`.
- **Replacement / disable / re-enable** — a new approved task on the **same video**
  cancels any running job and **reruns from frame 0 with fresh detector/tracker/engine
  state**. Disable/pause cancels the job; the version guard drops any event from a
  superseded generation so **stale work cannot publish after an acknowledged control**.
- **Judges view** — watches the annotated video via authenticated **HTTP polling** of
  `/frame` + `/state` (the WebSocket push channel is disabled). New `/upload` operator
  page; landing links updated (Upload Video + Judges).

## Camera / WebSocket surface — DISABLED publicly

- `config.CAMERA_INGEST_ENABLED` (env `VISIONFLOW_LIVE_ENABLE_CAMERA`) defaults
  **False** (fail-closed). When off: `ws/camera` and `ws/judge` **deny the upgrade**
  (close 4404), `/camera` returns **404**, and the landing page has **no camera link**.
- Verified by `tests/live/test_video_pipeline.py::test_camera_ws_disabled_on_public_default`.
- The legacy WS hardening tests still exercise that now-non-public code only because
  the in-process test app explicitly enables the flag. Per the owner, the original WS
  defects are removed from scope **by actually disabling exposure**.

## Original 11 P1 — before/after / scope

- **Planner strict validation (addressed by fix):** unknown proposal fields (e.g. an
  injected `code`/`tool`/`url`) now rejected; `supported` requires real JSON `true`
  (string `"false"` no longer truthy); boolean `threshold`/`duration_seconds` rejected;
  a malformed `visual_observation` returns `unsupported` instead of 500.
- **Planner deadline (addressed by fix):** the deadline now **includes the admission
  wait** for the shared capacity lock — a request not admitted within the deadline
  never spawns the subprocess; the subprocess only gets the remaining budget.
- **Frame provenance (addressed in the video path):** events now carry full source /
  frame / model / workflow provenance (see above).
- **Camera/WS ingest, two-device, judge push-channel P1s (scope-removed):** the surface
  is disabled publicly, so these are removed from scope by non-exposure, not by code
  change to the disabled path.

## Teacher / semantic

Teacher is **private, non-actioning**. The video product does **not** invoke Teacher
and dispatches no automatic semantic actions (safest demo). Bottle-opening / general
temporal VLM actions remain faithfully **UNSUPPORTED**. No Student, no AutoLearn, no
training on video, no precomputed/scripted results.

## Commands executed and actual results

- `pytest tests/live/test_video_pipeline.py` → **8 passed** (new; proves upload auth/
  ownership, non-video + oversize rejection + cleanup, real property validation,
  event+evidence with video-clock provenance, camera/WS disabled default, pages served).
- `pytest tests/live/` → **122 passed, 26 failed**.
- `pytest tests/` (full) → **316 passed, 27 failed**.
- `python scripts/smoke_e2e.py` (real YOLO, CPU) → **SMOKE PASS** (bus entered zone,
  30 frames, avg inference ~80 ms, evidence + notification persisted).
- `apps/web && npm run build` → **build OK** (static export).

### The 27 full-suite failures are ALL pre-existing dirty-pass probes, none on the video path

Baseline at pass start (dirty source + new probe files): **51 live failures**; this
pass reduced that to **26** (full-suite 27 adds one collection-order import probe).

- `tests/live/test_acceptance.py` (13): camera-WS ingest probes against the **disabled**
  surface (missing-CSRF upgrade, metadata bound, empty-frame, drop counting,
  socket-revocation, room retire), the `event_exposes_frame_identity` probe (camera
  `h.frame()` path — the **video** path does expose identity), the `model_branch` probe
  (expects the planner throwaway cwd under a fixed review ROOT — incomplete prior-pass
  wiring), and `test_exact_source_imports_and_no_legacy_provider` (asserts `app.main`
  not in `sys.modules`; violated by pytest **collecting** other modules in the full run).
- `tests/live/test_teacher_tcp.py` (14): strictness of the **private non-actioning**
  Teacher HTTP adapter (confidence boundary / missing-confidence / slow-body deadline /
  write-revocation). Not touched this pass; not on the video product path.

`tests/integration/test_demo_safe.py` passes (0 failures); no non-live test regressed.

## Secure startup / env / route inventory

- Startup creates `LIVE_EVIDENCE_DIR` and `LIVE_VIDEO_DIR`, wires session→room teardown,
  starts the worker (idle sweep / legacy camera latest-frame loop).
- Key env (secrets only from env; **no PIN/secret in source/tests/args/logs**):
  `VISIONFLOW_DEMO_PIN` (required; fail-closed), `VISIONFLOW_LIVE_ENABLE_CAMERA`
  (default off), `VISIONFLOW_LIVE_ALLOWED_ORIGINS` / `_ALLOWED_HOSTS`,
  `VISIONFLOW_LIVE_MAX_VIDEO_BYTES|SECONDS|FRAMES|FPS|LONG_EDGE`,
  `VISIONFLOW_LIVE_MAX_VIDEO_JOBS`, `VISIONFLOW_LIVE_INSECURE_COOKIE` (QA only),
  `VISIONFLOW_LIVE_TRUSTED_PROXY_HOPS`.
- Public routes: `GET /`, `/upload`, `/judges`, `/static/*`, `/api/live/health`;
  `POST /api/live/login|logout`; `GET /api/live/me`; room create/join; `GET
  state|frame|evidence`; `POST video|video/process|task/plan|task/activate|task/state|probe`.
  `GET /camera` → 404 and `ws/camera`, `ws/judge` → deny, while camera ingest is off.

## Known risks / limitations

- Video jobs run on CPU; large clips take wall time proportional to frames (progress is
  surfaced; no real-time claim).
- The pre-existing Teacher-adapter and camera-WS probes remain failing (documented above);
  they test a private non-actioning path and a disabled surface respectively.
- The `model_branch` planner probe expects a planner cwd under a fixed review ROOT; the
  prior-pass wiring for that was never completed and was out of this pivot's scope.
- Root to run independent prompt/video/browser E2E after the security review.

Preserved: `HANDOFF_LIVE.md`, prior reviews/reports, and the intentional dirty hardening.
