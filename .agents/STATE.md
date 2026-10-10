# Project state

Updated: 2026-10-10. Branch: `feature/visionflow`.

## Current stage

M1 is NOT accepted. Final review of `cc595239c2d361c714a996f23712643981209b95`
found four P1 defects after two fix cycles. Report: `.agents/reviews/M1.md`,
pushed on `review/M1-r2`. Runtime checkpoint was preserved at BLOCKED/DECIDE.

The operator has now authorized ONE exceptional focused M1 recovery cycle:
Claude fixes only M1-010/011/012/013 with regressions, full checks/build and
real YOLO smoke, followed by ONE exact-SHA independent review. PASS advances
to M2; any P0/P1 or failed gate stops again. No active fix was interrupted.

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
