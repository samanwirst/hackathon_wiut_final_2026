# Матрица трассируемости / Traceability

**Official brief status:** VERIFIED — the official Final Task text is present at
`docs/source/README.md` (the PDF `FINAL_TASK_WIUT_HACKATHON.pdf` itself is not in
the repo; the text version is treated as the source of truth). No conflicts with
`docs/PRD.md` found for M1 scope.

Statuses: planned | in_progress | implemented | verified | blocked.

## M1 — vision-to-action pipeline

| ID | Requirement | Source | Component / file | Check | Status |
| --- | --- | --- | --- | --- | --- |
| R1 | Prototype runs end to end on new input | Brief "prototype runs end to end, live" | whole pipeline | `scripts/smoke_e2e.py` (real YOLO) — PASS 2026-10-10 | verified |
| R2 | MP4 upload with validation | PRD P0.1 | `services/api/app/main.py` upload_source | `tests/integration/test_api_flow.py` (reject non-mp4, garbage, size cap) | verified |
| R3 | Real object detection | PRD P0.3; brief "no faked demos" | `packages/vision/visionflow_vision/detector.py` (YOLO11n) | smoke test: bus detected conf 0.76 | verified |
| R4 | Object tracking | PRD P0.3 | ByteTrack via `model.track(persist=True)` | smoke test: stable track id in events | verified |
| R5 | Polygonal zones | PRD P0.4 | `visionflow_vision/zones.py`; UI canvas drawing | `tests/unit/test_zones.py`; browser flow 2026-10-10 | verified |
| R6 | Temporal events (enter/exit/dwell/count) | PRD P0.5 | `visionflow_vision/events.py` | `tests/unit/test_events.py` (debounce, cooldown, track loss, one-shot) | verified |
| R7 | Validated workflow DSL | PRD §8 | `services/api/app/schemas.py` | `tests/unit/test_dsl.py` (unsupported trigger/action/class rejected) | verified |
| R8 | Explicit enable before workflow is armed | PRD P0.7 | workflows create disabled; `/enable` endpoint | integration test asserts enabled=false on create | verified |
| R9 | Real authorized action | PRD P0.8 | `services/api/app/actions.py` (notification persisted; webhook allowlisted) | integration: notification row created; non-allowlisted webhook rejected | verified |
| R10 | Event persistence with evidence | PRD P0.9 | `TrackEvent` + evidence JPEG in `app/pipeline.py` | smoke + integration: evidence URL serves image/jpeg | verified |
| R11 | Working web interface | PRD P0.10 | `apps/web/app/page.tsx` | manual browser run 2026-10-10: full flow exercised | verified |
| R12 | Automated tests | PRD P0.11 | `tests/` | `pytest tests/` — 60 passed 2026-10-10 | verified |
| R13 | NL → workflow compilation | PRD P0.6 | — | planned for M2 | planned |
| R14 | Live camera source | PRD P0.2 | — | planned (M2+, hardware-dependent) | planned |
| R15 | Public deployment | Brief "publicly available" | — | planned for M4 | planned |
| R16 | AutoLearn | PRD P1 | `packages/autolearn` | planned for M3 | planned |

## M1 review fixes (cycle 1, 2026-10-10)

| ID | Severity | Resolution | File | Test |
| --- | --- | --- | --- | --- |
| M1-001 | P1 | FIXED | `services/api/app/actions.py` — URL canonicalized; userinfo rejected; scheme/host/port exact match; path-prefix enforced; internal-resolution guard | `tests/unit/test_webhook_auth.py` (userinfo never reaches MockTransport; allowlisted delivered) |
| M1-002 | P1 | FIXED | `packages/vision/visionflow_vision/events.py` — aggregate episode counter advances per rising crossing, included in dedupe key | `tests/unit/test_events.py::test_count_rearms_with_distinct_dedupe_keys` |
| M1-003 | P1 | FIXED | `services/api/app/pipeline.py` — authoritative `enabled` re-checked per frame via fresh session before emitting/acting | `tests/integration/test_m1_fixes.py::test_disable_during_processing_revokes_actions` |
| M1-004 | P1 | FIXED | `services/api/app/pipeline.py` — complete session serialized by `_session_lock` around reset + all frame calls | `tests/integration/test_m1_fixes.py::test_concurrent_sources_are_serialized` |
| M1-005 | P1 | FIXED | `services/api/app/{pipeline,main}.py` — startup marks interrupted `processing` rows failed and permits retry | `tests/integration/test_m1_fixes.py::test_interrupted_processing_recovered_and_retryable` |

## Discrepancies / notes

- The PDF named in CLAUDE.md is absent; the official task exists as text in
  `docs/source/README.md`. Treated as the official brief (per operator message).
- Demo video provenance: built by `scripts/make_demo_video.py` from the
  Ultralytics sample photo (real photographic content, synthetic motion).
  Declared in `docs/LICENSES.md`; detection on it is genuine YOLO inference.
