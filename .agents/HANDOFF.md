# Handoff — M2 event-routed visual reasoning + workflow product

- **Milestone:** M2 — strict NL workflow drafts + event-routed Teacher VLM
- **Implementation SHA:** `c746fc098afd69dedc9cab54d6262e589212abc0`
  Controller committed Claude's completed implementation after Git commands
  were denied in the implementation session. Original handoff is retained
  locally; no additional implementation call was made.
- **Base SHA:** `2127d207a7bf2e1401d40e5ad82d926eb0f66a57`
- **Branch:** `feature/visionflow`

Scope: PRD §16 M2-AC1..AC5, plus the Teacher adapter portion of the operator's
M2-AC3a (docs/VLM_ARCHITECTURE.md). No M3/M4 work. The M2-EXP1 foveated/
full-frame strategy selector is only partially present (ROI crop + full-frame
fallback) and remains planned.

## Features implemented

- **M2-AC1 — strict NL → DSL.** `services/api/app/nl_compiler.py` is a disclosed
  deterministic rule-based compiler (no text-model credentials). `POST
  /api/workflows/compile` returns an editable, **disabled** draft or structured
  rejections/warnings. Ambiguous ("vehicle"), unsupported class/trigger, missing
  duration/threshold, and external-delivery requests are rejected. Drafts are
  never saved or enabled by compile; the existing create→enable flow (disabled by
  default, explicit enable) is unchanged. No generated code is produced/executed.
- **M2-AC2 — cheap path preserved, event-routed VLM.** The real YOLO/ByteTrack
  detector, tracker and temporal state machines are unchanged and make **zero**
  Teacher calls. A workflow `visual_predicate` turns a geometric candidate into a
  single ROI classification via `pipeline._route_visual` + `app/vlm_router.py`.
  ROI = the triggering object's bbox (full frame for track-less/aggregate
  candidates). Verified by `test_geometric_workflow_makes_zero_vlm_calls`.
- **M2-AC3 / AC3a — real validated Teacher adapter.** `services/api/app/teacher.py`:
  `OpenAICompatibleTeacher` targets an operator-set `/v1/chat/completions`
  (config `VLM_BASE_URL`/`VLM_MODEL`/`VLM_API_KEY`, server-only, separate from
  user input). Strict response validation: `extra=forbid`, finite bounded
  confidence, label ∈ declared set or `unknown`, else `invalid_response`. Images
  sent as bounded base64 data URLs. Bounded connect/read/overall timeouts,
  bounded retries that cover only transient failures (timeout/connection/5xx) and
  **skip** auth(401/403)/schema, a concurrency semaphore, and a max-image-bytes
  cap. Timeout/HTTP/invalid/missing-credential results can **never** confirm an
  action. With no `VLM_BASE_URL`, `UnavailableTeacher` returns
  `missing_credentials` (honest blocker). **Mocked tests do not verify real
  visual inference; a real vLLM/GPU smoke is UNVERIFIED (no instance connected).**
- **M2-AC4 — router discipline.** `app/vlm_router.py`: a `VersionedTTLCache`
  (LRU + TTL) keyed by task/prompt + prompt/preprocessing version + model + ROI
  hash + scope (changed task/model/ROI miss ⇒ new call); per-task budget;
  per-task sampling interval; per-scope cooldown; in-flight dedup so concurrent
  identical ROIs share one call. Transient failures are not cached. Live counters
  for calls/hits/misses/dedup/suppressed(by reason)/failed/confirmed/unknown.
- **M2-AC5 — provenance, counters, boundaries.** Every decision persists a
  `VlmCall` row; events carry `visual_status`/`visual_label`/`visual_confidence`/
  `visual_routing`. `GET /api/vlm/stats`, `GET /api/vlm/calls`, and
  `/api/metrics.vlm` expose actual calls/hits/misses/suppressed/failures. UI
  section 6 shows counters + teacher availability. Enable/disable (M1-010) and
  webhook-removal boundaries are preserved; the Teacher URL is config-only
  (not reachable from workflow/compile input), so user input cannot steer the
  provider connection. A new-user flow runs without editing source files.

## Changed files

New:
- `services/api/app/nl_compiler.py`
- `services/api/app/teacher.py`
- `services/api/app/vlm_router.py`
- `tests/unit/test_nl_compiler.py`
- `tests/unit/test_teacher.py`
- `tests/unit/test_vlm_router.py`
- `tests/integration/test_m2_visual.py`

Modified:
- `services/api/app/config.py` — VLM/router/thread config.
- `services/api/app/schemas.py` — `VisualPredicate`, `visual_predicate` on
  `WorkflowDSL`, `CompileRequest`/`CompileResponse`, event `visual_*` fields.
- `services/api/app/db.py` — `TrackEvent.visual_*` columns; new `VlmCall` table.
- `services/api/app/pipeline.py` — `_encode_roi`, `_route_visual`, visual
  dispatch gate, visual-recovery guard, CPU thread cap.
- `services/api/app/main.py` — `/api/workflows/compile`, `/api/vlm/stats`,
  `/api/vlm/calls`, `/api/metrics.vlm`, event provenance in `_event_out`.
- `packages/vision/visionflow_vision/detector.py` — torch thread cap (2).
- `apps/web/app/page.tsx` — NL compile box, visual-predicate indicator, event
  Visual column, VLM routing counters section.
- `.env.example` — `VLM_*` + router/thread vars.
- `docs/TRACEABILITY.md`, `docs/ARCHITECTURE.md`, `.agents/STATE.md`.

## Commands executed and actual results (2026-10-10)

- `services/api/.venv/bin/python -m pytest tests/ -q` → **111 passed, 4 warnings**
  (~13.5 s). Baseline before M2 was 66 passed; +45 M2 tests, no regressions. The
  4 warnings are pre-existing (deprecation + the deliberate-crash recovery test).
- New M2 suites: `tests/unit/test_nl_compiler.py` (12), `tests/unit/test_teacher.py`
  (13), `tests/unit/test_vlm_router.py` (11), `tests/integration/test_m2_visual.py`
  (8) — all passing.
- `apps/web` `npm run build` → **compiled successfully**, 4 static pages, route
  `/` 4.43 kB.
- Real-YOLO `scripts/smoke_e2e.py` → **NOT RUN in this session**: launching its
  uvicorn server is blocked by the sandbox. It is controller-run (PASS at M1).
  The geometric dispatch path is logically unchanged for geometric workflows
  (visual_predicate absent ⇒ direct `_dispatch_action`, as before).

## Commit recovery

The implementation session denied Git commands. The controller inspected the
exact changed-file set, preserved the original handoff locally, committed
Claude's implementation, and filled the real SHA above. No source changes,
reset, force push or main merge were used for this recovery. The controller
will run full checks/build and real YOLO smoke before independent review.

## Known limitations

- **Real Teacher UNVERIFIED.** No `VLM_BASE_URL` is configured; all Teacher tests
  use mocks/stubs clearly marked test-only. Real visual inference, token usage and
  any cost/quality comparison are deferred until a provider/GPU is connected
  (M2-AC3a real smoke, M3/M4). Missing access is a documented blocker, not success.
- **Input strategy.** Only ROI-crop (with full-frame fallback for track-less
  candidates) ships. The `foveated`/`full_frame` selector (M2-EXP1) is planned.
- **Visual-candidate recovery.** If a run is interrupted after an event commit but
  before routing, the visual event stays visibly `pending` and is **not**
  auto-dispatched without a confirmed Teacher result (honest, conservative).
- **Transient Teacher errors** on a candidate are recorded `skipped_visual` and,
  due to deterministic dedupe keys, are not auto-retried within the same stored
  event; they remain visible via `visual_status` and `VlmCall`.
- Carried: no API auth, no live camera, no public deployment (M4 scope). DB
  column additions apply to fresh databases (SQLite `create_all`); pre-existing
  dev DBs would need a migration/reset (data dir is gitignored).

## Questions for Codex

1. Is routing a non-confirming Teacher result to `skipped_visual` (no action, full
   provenance) the desired semantics, versus retrying transient errors on a later
   candidate within the same stored event?
2. Confirm the `VLM_BASE_URL`/`VLM_MODEL`/`VLM_API_KEY` naming and the
   presence-based enablement match docs/VLM_ARCHITECTURE.md expectations.
3. Is the deterministic NL compiler acceptable for M2-AC1, with an optional
   text-model path deferred, given no text-model credentials are configured?
