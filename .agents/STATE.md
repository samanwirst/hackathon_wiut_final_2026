# Project state

Updated: 2026-10-10. Branch: `feature/visionflow`.

## Current stage

M2 COMPLETE (event-routed visual reasoning + NL workflow product), awaiting
independent review. Base `2127d207`. M1 recovery cycle accepted at that base.

M2 delivered (PRD §16 M2-AC1..AC5, plus adapter for AC3a):

- M2-AC1: deterministic NL→DSL compiler (`app/nl_compiler.py`) +
  `POST /api/workflows/compile`. Ambiguous/unsupported rejected with reasons;
  draft saved disabled; explicit enable required; no code generated/executed.
- M2-AC2: geometric detector/tracker/temporal path unchanged and makes ZERO
  Teacher calls. A `visual_predicate` routes the triggering object's ROI to the
  Teacher only on a candidate event (`pipeline._route_visual`).
- M2-AC3/AC3a: `app/teacher.py` strict adapter. Config by `VLM_BASE_URL`/
  `VLM_MODEL`/`VLM_API_KEY` (server-only). Strict JSON (`extra=forbid`, bounded
  finite confidence, declared labels or `unknown`), connect/read/overall
  timeouts, bounded retries (skipping auth/schema), concurrency semaphore, max
  image bytes, data-URL images. No creds → `missing_credentials`, never
  confirms. Real vLLM/GPU smoke UNVERIFIED (no instance connected).
- M2-AC4: `app/vlm_router.py` — versioned TTL+LRU cache, per-task budget,
  sampling interval, per-scope cooldown, in-flight dedup; live counters.
- M2-AC5: `VlmCall` provenance rows, `/api/vlm/stats`, `/api/vlm/calls`,
  `/api/metrics.vlm`, event `visual_*` fields; UI section 6 shows counters and
  teacher availability. Webhook removal + enable/disable boundaries preserved.

Gates (2026-10-10): `pytest tests/` **111 passed** (66→111; +45 M2 tests), 4
pre-existing warnings. Frontend production build passed. Real-YOLO smoke is
controller-run (sandbox blocks launching the uvicorn server here); the geometric
dispatch path is logically unchanged for geometric workflows.

## Existing implementation and evidence

- Real sampled YOLO11n/ByteTrack, polygon enter/exit/dwell/count state machines.
- MP4 upload, disabled-by-default workflow approval, SQLite events/evidence,
  local notification actions, Next.js upload/zone/workflow/timeline UI.
- Last application gate: 69 tests passed; frontend production build passed.
- Controller real-YOLO smoke: 30 analyzed frames, bus confidence 0.76,
  enter at 4.2 s, served JPEG, persisted notification, 55.6 ms mean frame
  inference. Preliminary synthetic-motion photographic sample, not a
  held-out quality or cost benchmark.
- Independent QA verified the unchanged 69-test suite using a disclosed
  temporary asyncio heartbeat in its restricted TestClient environment.
- Four reproduced P1 gaps: disable/dispatch race; ambiguous webhook replay
  after delivery interruption; DNS rebinding; premature decode reported done.
- P2 CI dependency gap remains documented; it is outside this focused pass.

## Architecture steering preserved

`docs/VISUAL_ANALYTICS_AUDIT.md` audits the current snapshot. PRD section 16
and TRACEABILITY now contain M2-AC1..5, M3-AC1..6 and M4-AC1..4.

- M2: cheap continuous vision -> temporal candidate -> selected frame/ROI ->
  budgeted Teacher; sampling, in-flight dedupe, versioned cache and counters.
- M3: Teacher labels -> human verification -> frozen embeddings -> fitted
  Student; session-held-out metrics, shadow, gated manual activation,
  Teacher fallback and working rollback.
- M4: real paired baseline/routed/Student runs on identical held-out inputs;
  actual usage, latency and quality; no invented savings percentages.
- No VLM provider credential is configured. Provider interfaces and honest
  fallbacks can be implemented; real Teacher capabilities remain unverified
  until access is configured. Development-agent login is not a Teacher key.

## Orchestration and delivery limits

`scripts/orchestrate.py` alone schedules sequential Claude/Codex CLI calls.
It preserves exact-SHA reviews and interrupted checkpoints, never merges
main, and protects independent reports/source brief/controller code from
implementation-agent edits. Normal limit: two fixes per milestone.
`--exceptional-m1-recovery` grants the single approved extra M1 pass only;
counters persist and repeated resume cannot grant more attempts.

CPU-only, limited RAM; existing dependencies are installed. No public
production deployment, robot operation, purchases or new paid service
activation is authorized. Public deployment awaits explicit approval of a
concrete prepared result. No API auth/deployment/live camera yet. Current
Ultralytics/model/data licensing limitations are in `docs/LICENSES.md`.
