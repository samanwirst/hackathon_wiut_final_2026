# HANDOFF — VFVIDEO (owner-final emergency round)

- Stream: VFVIDEO (Claude Lead Implementer), isolated worktree.
- Base SHA: `e75554d91ddb15896a23c3b2b260657193cb8790`.
- Scope: LIVE-VIDEO-002, 003, 004 only. Ownership: `services/api/app/live/video.py`,
  `services/api/app/live/rooms.py`, NEW `tests/live/test_owner_final_video_lifecycle.py`,
  this file. NO app.py/auth.py/dsl.py/planner.py/static edits. No push.
- Review consumed: `review-live-review-2/.agents/reviews/VIDEO-FINAL.md` +
  `/tmp/visionflow-live-review-2-e75554d/review.json` and receipts.

## Baseline reproductions (original failures, on e75554d)

| ID | Original actual failure (reproduced before fixing) |
| --- | --- |
| LIVE-VIDEO-004 | `probe()` clamped 0.5 and 61 fps -> 25 fps and ACCEPTED; a JPEG with an .mp4 name decoded as a 1-frame video; a 65%-truncated faststart MP4 reported `done` after 40/60 frames. |
| LIVE-VIDEO-003 | Detector construction raised OUTSIDE try/finally -> `job_status='idle'`, `job_error=None`, job still registered, permit leaked. With capacity 1 + held detector, 4 restarts all started (5 detectors on one slot). |
| LIVE-VIDEO-002 | Disable ACK dropped the event but left an orphan evidence JPEG on disk; logout/expiry committed a late event+notification+private JPEG; source replacement published an old-source event after ACK. |

Reproduced with the venv + scripted detector at 2 CPU threads; receipts match the
review's `fps-0.5.json / fps-61.0.json / jpeg-as-video.json / original-truncation.json
/ detector-startup-failure.json / cancelled-job-capacity.json / disable-evidence-write.json
/ logout-inflight.json / expired-owner-inflight.json / source-replace-inflight.json`.

## Fixes (root-cause)

- **004 — MP4 integrity + real clock (`video.py probe`)**: Validate via `ffprobe`
  (installed, no new dependency, real timeout + process kill). Require a supported
  MP4-family container (reject disguised JPEG/image2/mj2/still-image codecs), a
  genuine finite FPS inside `config.MIN/MAX_VIDEO_FPS` (REJECTED, never clamped to an
  invented 25), and bounds on dimensions/duration/frame-count applied to the ACTUAL
  decoded first frame. `probe()` now also returns `frame_count_reliable`. The job
  compares decoded frames to the reliable container count and reports `error`
  ("truncated/incomplete decode") below 95%. ffprobe-absent fallback still fail-closed
  (magic-byte JPEG/`ftyp` sniff, no fps clamp).
- **003 — real in-flight bound + visible startup errors (`video.py`)**: A global
  `_active_permits` counter reserved in `start_job` and released ONLY in `_finish`
  AFTER the thread exits, so a cancelled/blocked/dead worker keeps its slot; a rerun
  raises `RuntimeError` (busy) until actual exit. Detector construction, engine build
  and capture open are INSIDE the run try/except/finally -> a startup failure becomes
  `job_status='error'` with `job_error`, deregisters the job and releases the permit.
- **002 — isolation + atomic revocation + teardown (`video.py`, `rooms.py`)**: Each
  run captures an IMMUTABLE source+task snapshot and builds FRESH detector/tracker/
  engines (never reuses room-cached engines). Each run gets a unique monotonic
  EXECUTION GENERATION on `RoomState.active_generation`; any source/task/session
  transition resets it to 0, revoking a still-running (even blocked) worker. Authority
  is re-checked under the room lock before engine update, before evidence I/O, and
  atomically at commit; evidence written during a revoked window is deleted. `cancel_job`
  revokes the generation; new `replace_source` swaps source + revokes atomically;
  `close_room` sets `retired`, revokes, and PURGES events/notifications/annotated/
  latest frames + evidence files + the opaque source so nothing private survives
  owner logout/expiry/retirement. `build_engines` applies `cooldown_seconds` (exact
  when supplied, else 10s default).

Central APIs SEC will consume (`replace_source`, `cancel_job`, `start_job`) are
documented in `.agents/runtime/ten-hour/VF/coordination-VFVIDEO.json`. Lock order is
`_jobs_lock -> _rooms_lock -> room.lock` throughout (no reverse nesting, no deadlock).

## Tests (ID -> test -> original failure -> current result)

New `tests/live/test_owner_final_video_lifecycle.py` (14 tests), run at 2 CPU threads:

- 004: `probe_rejects_out_of_range_fps[0.5|61.0]`, `probe_rejects_disguised_jpeg`,
  `probe_accepts_supported_fps_with_real_rate`, `truncated_clip_reports_error`
  (+ complete-clip control = done/60). Was: clamped/accepted/`done@40`. Now: rejected / `error`.
- 003: `detector_startup_failure_reports_error_and_releases_capacity`,
  `cancelled_worker_retains_capacity_until_exit`. Was: idle+registered+leak / 4 started.
  Now: `error`+deregistered+permit=0 / 4 busy, exactly 1 detector, permit freed on exit.
- 002: `disable_ack_deletes_inflight_evidence`, `logout_retire_purges_outputs_and_evidence`,
  `expired_owner_inflight_event_is_suppressed`, `source_replace_revokes_old_run`,
  `rerun_uses_fresh_engines_and_single_notification`, `happy_path_event_has_snapshot_provenance`,
  `cooldown_uses_task_value_else_default`. Was: orphan evidence / late event+notif+JPEG /
  old-source event / reused engine. Now: no orphan, purged, revoked, fresh engine.

Commands executed (actual results):
- `pytest tests/live/test_owner_final_video_lifecycle.py` -> **14 passed**.
- `pytest tests/live/test_video_pipeline.py tests/live/test_live_hardening.py` -> **23 passed**.
- Baseline compare (git stash) for `test_teacher_tcp.py` (14 failed/11 passed) and
  `test_acceptance.py` (12 failed) is IDENTICAL with and without my changes -> my
  changes add ZERO regressions. Those failures are the pre-existing camera/Teacher
  path defects (outside my ownership; dsl/teacher/worker/auth).

## Known limitations / out of scope

- LIVE-VIDEO-001/005/006/007/008/009 are owned by other streams (planner/dsl/auth/
  app middleware/static) — see coordination JSON mapping. M2/M3 remain BLOCKED,
  Student OFF, geometric fallback retained; camera/Teacher paths stay inaccessible.
- Canonical workflow/draft-hash binding (005) is not present yet; when the task dict
  carries it, provenance will include it unchanged.
- Did NOT run the full suite or the Next build (ROOT runs full checks/web build/real
  YOLO once on the integrated exact SHA + ONE fresh Codex review).

## Questions for Codex / ROOT

1. Confirm SEC will adopt `video.replace_source` in `upload_video` to close the
   swap/cancel atomicity window (correctness already holds via `cancel_job` revocation).
2. Confirm the 95% completeness threshold is acceptable for real h264 smoke clips
   (only fires on `frame_count_reliable` container metadata).
