# Project state

Updated: 2026-10-10. Branch: `feature/visionflow`.

## Current stage

M1 exceptional recovery cycle COMPLETE, awaiting ONE exact-SHA independent
review. The four P1 defects from review `cc59523` (`.agents/reviews/M1.md`)
are resolved:

- M1-010: `dispatch_admission_lock` serializes API disable vs worker dispatch
  admission; a disable completed before dispatch suppresses the queued action
  explicitly (`cancelled`).
- M1-011 + M1-012: outbound `send_webhook` removed entirely (no safe egress
  without a risky custom DNS/TLS transport). Only the local
  `create_notification` ships; legacy webhook rows rejected at dispatch with no
  network lookup/delivery. API/UI/docs/tests updated honestly.
- M1-013: decoded-frame count vs reliable container frame count with
  `DECODE_MIN_COMPLETENESS` tolerance; a truncated upload is a failed source.

Gates (2026-10-10): `pytest tests/` 66 passed; frontend production build
passed; real-YOLO smoke PASS (30 frames analyzed/180 decoded, bus enter t=4.2s
conf 0.76, evidence+notification persisted). M1-014 (P2 CI deps) out of scope.

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
