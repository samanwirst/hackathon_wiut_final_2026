# Handoff — M1 ready for independent review

- **Milestone:** M1 — vision-to-action pipeline
- **Implementation HEAD:** `7d0861b02b61881321b3692e6f80fd66d55d8298`
- **Previous review base:** none (first milestone; scaffold base `b131c50`)
- **Branch:** `feature/visionflow`

## Implemented

1. MP4 upload with type/size/readability validation; first-frame snapshot for zone drawing.
2. Real object detection (YOLO11n, ultralytics) + ByteTrack tracking — genuine inference, no mocks in production paths.
3. Normalized polygon zones (bottom-center bbox anchor, ray-cast inclusion).
4. Temporal events: enter, exit, dwell, count-exceeded — with debounce, per-track cooldown, lost-track grace, one-shot per visit, idempotent dedupe keys (PRD §9).
5. Event persistence (SQLite WAL) + annotated evidence JPEG per event.
6. Real authorized actions: `create_notification` (persisted, shown in UI) and `send_webhook` (env allowlist; empty allowlist ⇒ rejected with explicit error).
7. Pydantic workflow DSL; workflows are created disabled and require explicit `/enable`; unsupported trigger/action/class ⇒ validation error.
8. Single-page Next.js UI: upload, canvas zone drawing, workflow builder, event timeline with evidence thumbnails, notifications.

## Key changed files

- `packages/vision/visionflow_vision/{zones,events,detector}.py`
- `services/api/app/{main,schemas,pipeline,actions,db,config}.py`, `services/api/requirements.txt`
- `apps/web/app/{page.tsx,layout.tsx,globals.css}`, `apps/web/{package.json,tsconfig.json,next.config.ts}`
- `tests/{conftest.py,unit/*,integration/test_api_flow.py}`, `scripts/{smoke_e2e.py,make_demo_video.py}`
- `docs/{TRACEABILITY,ARCHITECTURE,LICENSES}.md`, `README.md`, `.env.example`, `.github/workflows/ci.yml`

## Commands executed and actual results (2026-10-10)

- `services/api/.venv/bin/python -m pytest tests/ -q` → **32 passed** (~1.4 s).
- `services/api/.venv/bin/python scripts/smoke_e2e.py` → **SMOKE PASS**: real YOLO detected bus (conf 0.76), `object_entered_zone` at t=4.2 s, evidence JPEG served, notification persisted; 30 frames analyzed, avg CPU inference 136.9 ms cold / 62 ms warm run.
- `make check` → OK (notes absent PDF; official task text is at `docs/source/README.md`).
- Manual browser verification of the full UI flow (upload → select → draw 4-point zone on canvas → create workflow → enable → process → event with evidence thumbnail + notification rendered).
- `npm run build` (apps/web) → success.

## Known limitations

- No live camera source yet (PRD P0.2) — planned M2+.
- NL→DSL compilation (`/api/workflows/compile`) not implemented — M2 scope.
- One background thread per source, no job queue; concurrent `process` calls on the same source return 409.
- No API auth; CORS limited to localhost origins — hardening planned with M4 deployment.
- Integration tests use a **disclosed stub detector** for speed; real-inference coverage is `scripts/smoke_e2e.py` (must stay green).
- Ultralytics is AGPL-3.0 — recorded in `docs/LICENSES.md`; business implications flagged for the pitch.
- Demo video is real photographic content with synthetic motion (generation method disclosed in LICENSES.md); judges' own videos are the real acceptance path.

## Questions for Codex

1. Event-engine semantics: is rising-edge-only for `object_count_exceeded` (re-arms when count drops to threshold) the right interpretation of PRD §9?
2. Is the empty-allowlist ⇒ reject-all webhook default acceptable, or should M1 ship with a localhost allowlist preset for demos?
3. Any objection to AGPL ultralytics before we invest in M2 on top of it (swap candidate: RT-DETR Apache-2.0)?
4. Priorities to confirm for M2: NL compile, SSE vs polling, dashboard scope.
