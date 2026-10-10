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
- Tests: 32 passing (`pytest tests/`); real-YOLO smoke `scripts/smoke_e2e.py` PASS.
- Docs: TRACEABILITY (brief verified at docs/source/README.md), ARCHITECTURE,
  LICENSES (AGPL note for ultralytics), README quickstart, .env.example.
- CI: structure check + unit tests + frontend build.

## Verified by actual execution (2026-10-10)

- `pytest tests/` → 32 passed.
- `scripts/smoke_e2e.py` → PASS: bus detected (conf 0.76), enter event at
  t=4.2 s, evidence JPEG, notification; 136.9 ms avg CPU inference (cold),
  62 ms warm.
- Manual browser run of the full UI flow (upload → zone → workflow → process
  → event + evidence + notification).

## Next (M2)

NL → workflow compilation (LLM structured output + Pydantic), multiple
triggers UX, dashboard/timeline pages, SSE updates, security/failure handling.

## Known limitations

- Processing is a single background thread per source; no queue.
- No live camera source yet (PRD P0.2) — M2+.
- `visual_condition_verified` trigger and `robot_preset`/`create_service_event`
  actions not implemented yet (M2/M3).
- No deployment yet (M4). No auth on API (planned with deployment).
- Ultralytics is AGPL-3.0 — noted in LICENSES.md for the business pitch.
