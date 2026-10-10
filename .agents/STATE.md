# Project state

Updated: 2026-10-10. Branch: `feature/visionflow`.

## Current stage

M1 accepted with documented P2 risks at `390b337`, report `review/M1-r3`.
M2 implementation committed as `c746fc0`; frozen review target `36e7ca84d4fe2048cd9c21522e2adfbfc5174798`.
Controller checks: 111 tests passed, frontend build and real YOLO smoke passed.

M2 review-fix pass CYCLE 2 (2026-10-10): the five re-opened/new P1 defects
(M2-001, M2-003, M2-004, M2-006, M2-007) are FIXED in `app/nl_compiler.py`,
`app/teacher.py`, `app/vlm_router.py`, `app/pipeline.py` (+db status comments),
with +18 added tests. Tests WERE executed this session: **123 passed**
(`.venv/bin/python -m pytest tests/ -q --ignore=tests/orchestrator`). Git is
blocked in the sandbox: the controller must commit and fill the exact
implementation SHA (no SHA is fabricated). Base for this pass:
`2127d207a7bf2e1401d40e5ad82d926eb0f66a57`. No frontend change this cycle;
controller should still run the frontend build + real-YOLO smoke.

M2 fixes summary: strict NL grammar now rejects negation, unsupported
actions, alternative triggers, appearance attributes and converts inclusive
counts (M2-001); Teacher enforces a cancellable wall-clock deadline across
transport + body read (M2-003); router accounts real-adapter attempts only via
the transport guard so a local preflight rejection costs no budget (M2-004);
recovery resumes a persisted confirmation once and marks unconfirmed candidates
interrupted (M2-006); provider admission re-checks workflow disable and records
cancelled with no Teacher call (M2-007).

Prior block: M2's controller parent was interrupted, the orphaned review
exceeded the 1,200-second limit, and no complete structured review was
returned. M2 is not yet accepted; M3/M4 have not started.
Report: `.agents/reviews/M2.md`, pushed on `review/M2`.

PRD v1.2, `docs/VLM_ARCHITECTURE.md` and `docs/METRICS.md` preserve the
self-hosted Vast.ai/vLLM contract, foveated/full-frame/ROI experiment and
actual rental measurement gates. Real Teacher and all unexecuted benchmarks
remain UNVERIFIED. No GPU was rented or public endpoint deployed.

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
