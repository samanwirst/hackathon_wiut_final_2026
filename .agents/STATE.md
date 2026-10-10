# Состояние проекта / Project state

Updated: 2026-10-10.

## Current stage

**M1 complete** — working vision-to-action pipeline, awaiting Codex review.
Branch: `feature/visionflow`.

## Done (M1)

- `packages/vision`: zones (ray-cast, normalized polygons, bottom-center
  anchor), temporal event engine (enter/exit/dwell/count, debounce, cooldown,
  lost-track grace, one-shot per visit, dedupe keys), YOLO11n + ByteTrack
  detector wrapper (real inference).
- `services/api`: FastAPI + SQLite(WAL); upload with validation, snapshots,
  zones, Pydantic workflow DSL (create disabled → explicit enable), background
  processing thread, evidence JPEGs, actions (notification persisted; webhook
  with env allowlist, empty = reject), events/notifications/metrics endpoints.
- `apps/web`: single-page Next.js UI — upload, canvas zone drawing, workflow
  form, event timeline with evidence thumbnails, notifications. Polls every 2.5 s.
- Tests: 60 passing (`pytest tests/`); real-YOLO smoke `scripts/smoke_e2e.py` PASS.
- Docs: TRACEABILITY (brief verified at docs/source/README.md), ARCHITECTURE,
  LICENSES (AGPL note for ultralytics), README quickstart, .env.example.
- CI: structure check + unit tests + frontend build.

## M1 review fix cycle 1 (2026-10-10) — all FIXED

- M1-001 webhook SSRF: userinfo rejected + canonical scheme/host/port match +
  path prefix + internal-resolution guard (`actions.py`).
- M1-002 count re-arm dedupe: per-rising-crossing episode counter in dedupe key.
- M1-003 disable during run: authoritative `enabled` re-checked each frame.
- M1-004 shared tracker: full session serialized by `_session_lock`.
- M1-005 interrupted recovery: startup marks stale `processing` rows failed.
- New tests: `tests/unit/test_webhook_auth.py`, count re-arm case in
  `tests/unit/test_events.py`, `tests/integration/test_m1_fixes.py`.

## M1 review fix cycle 2 (2026-10-10) — all FIXED

- M1-006 webhook path traversal: authorize and deliver one canonical URL;
  `'.'/'..'` resolved and prefix enforced after normalization; encoded
  traversal (`%2e`/`%2f`/`%5c`/`\`) rejected (`actions.py`).
- M1-003 disable between two events in one frame: `enabled` re-checked before
  each event, not once per frame (`pipeline.py`).
- M1-007 interrupted before dispatch: resume committed-but-undispatched events
  (pending + zero ActionExecution) on reprocess/recovery; completed events stay
  deduped (`pipeline.py`).
- M1-008 bad notification title: bounded-string validation → 422; failed
  transactions rolled back before recording source failure, fresh-session
  fallback (`schemas.py`, `pipeline.py`).
- M1-009 evidence write failure: `cv2.imwrite` return checked, raises, event
  work rolled back, source recorded failed (`pipeline.py`).
- New tests: traversal cases in `tests/unit/test_webhook_auth.py`; M1-003/007/
  008/009 cases in `tests/integration/test_m1_fixes.py`.

## Verified by actual execution (2026-10-10)

- `pytest tests/` → 69 passed (16 controller tests unchanged).
- `scripts/smoke_e2e.py` → PASS: bus detected (conf 0.76), enter event at
  t=4.2 s, evidence JPEG served 200, notification; 54.7 ms avg CPU inference.
- Manual browser run of the full UI flow (upload → zone → workflow → process
  → event + evidence + notification).

## Next (M2)

NL → workflow compilation (LLM structured output + Pydantic), multiple
triggers UX, dashboard/timeline pages, SSE updates, security/failure handling.

## Autonomous execution (operator-authorized 2026-10-10)

- Main controller: `scripts/orchestrate.py`; sequential Claude implementation
  and independent Codex reviews; full workflow in `.agents/AUTOPILOT.md`.
- Controller recovery/gate tests: 16 passed using real temporary Git repos
  and mocked CLI subprocesses (not product-inference evidence).
- Current controller phase: M1 first fix cycle. Review `a622572` found five
  P1 issues (webhook SSRF, count re-arm dedupe, disable during processing,
  shared tracker state, interrupted-source recovery). Report pushed to
  `review/M1`; exact-SHA JSON retained locally. Generated dependency-link
  ignore issue fixed without repeating the independent review.
- Runtime JSON/logs are local and ignored; durable milestone acceptance is
  recorded in review reports. Maximum two fix cycles per milestone.
- Claude/Codex/GitHub authenticated; CPU, FFmpeg, Python/Node available.
- Public deployment is required by the brief and awaits explicit approval
  once the reviewable deployment result is prepared.

## Known limitations

- Processing is a single background thread per source; no queue.
- No live camera source yet (PRD P0.2) — M2+.
- `visual_condition_verified` trigger and `robot_preset`/`create_service_event`
  actions not implemented yet (M2/M3).
- No deployment yet (M4). No auth on API (planned with deployment).
- Ultralytics is AGPL-3.0 — noted in LICENSES.md for the business pitch.
