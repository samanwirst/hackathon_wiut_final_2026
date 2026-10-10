# Матрица трассируемости / Traceability

**Official brief status:** VERIFIED — the official Final Task text is present at
`docs/source/README.md` (the PDF `FINAL_TASK_WIUT_HACKATHON.pdf` itself is not in
the repo; the text version is treated as the source of truth). No conflicts with
`docs/PRD.md` found for M1 scope.

Statuses: planned | in_progress | implemented | verified | blocked.
M1 is **accepted with documented P2 risks** after the exceptional review of
`390b337`; the four P1 defects in the previous `cc59523` review were resolved.
Accepted report: `.agents/reviews/M1.md`, pushed on `review/M1-r3`.

## M1 — vision-to-action pipeline

| ID | Requirement | Source | Component / file | Check | Status |
| --- | --- | --- | --- | --- | --- |
| R1 | Prototype runs end to end on new input | Brief "prototype runs end to end, live" | whole pipeline | `scripts/smoke_e2e.py` (real YOLO) — PASS 2026-10-10 | verified |
| R2 | MP4 upload with validation | PRD P0.1 | `services/api/app/main.py` upload_source + `app/pipeline.py` decode-completeness guard | Happy-path/type/size tests pass; truncated decode now surfaces failed source (M1-013) | verified |
| R3 | Real object detection | PRD P0.3; brief "no faked demos" | `packages/vision/visionflow_vision/detector.py` (YOLO11n) | smoke test: bus detected conf 0.76 | verified |
| R4 | Object tracking | PRD P0.3 | ByteTrack via `model.track(persist=True)` | smoke test: stable track id in events | verified |
| R5 | Polygonal zones | PRD P0.4 | `visionflow_vision/zones.py`; UI canvas drawing | `tests/unit/test_zones.py`; browser flow 2026-10-10 | verified |
| R6 | Temporal events (enter/exit/dwell/count) | PRD P0.5 | `visionflow_vision/events.py` | `tests/unit/test_events.py` (debounce, cooldown, track loss, one-shot) | verified |
| R7 | Validated workflow DSL | PRD §8 | `services/api/app/schemas.py` | `tests/unit/test_dsl.py` (unsupported trigger/action/class rejected) | verified |
| R8 | Explicit enable before workflow is armed | PRD P0.7 | workflows create disabled; `/enable` endpoint | integration test asserts enabled=false on create | verified |
| R9 | Real authorized action | PRD P0.8 | `services/api/app/actions.py` (local `create_notification`; outbound webhook removed, M1-011/M1-012) | Action tests pass; disable-before-dispatch suppressed (M1-010); legacy webhook rejected with no network | verified |
| R10 | Event persistence with evidence | PRD P0.9 | `TrackEvent` + evidence JPEG in `app/pipeline.py` | smoke + integration: evidence URL serves image/jpeg | verified |
| R11 | Working web interface | PRD P0.10 | `apps/web/app/page.tsx` | manual browser run 2026-10-10: full flow exercised | verified |
| R12 | Automated tests | PRD P0.11 | `tests/` | `pytest tests/` — 66 passed 2026-10-10 (recovery cycle) | verified |
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

## M1 review fixes (cycle 2, 2026-10-10)

| ID | Severity | Resolution | File | Test |
| --- | --- | --- | --- | --- |
| M1-006 | P1 | FIXED | `services/api/app/actions.py` — authorize and deliver one canonical URL; `'.'/'..'` path segments resolved and prefix enforced after normalization; percent/backslash-encoded traversal rejected | `tests/unit/test_webhook_auth.py` (`test_dotdot_traversal_rejected`, `test_encoded_traversal_rejected`, `test_traversal_never_reaches_admin_via_transport`, `test_authorized_path_is_exactly_what_is_delivered`) |
| M1-003 | P1 | FIXED (re-hardened) | `services/api/app/pipeline.py` — authoritative `enabled` re-checked before EACH event, not once per frame, so a disable between two events in one frame suppresses the remainder | `tests/integration/test_m1_fixes.py::test_disable_between_events_in_one_frame_suppresses_remainder` |
| M1-007 | P1 | FIXED | `services/api/app/pipeline.py` — a committed event with no dispatched action (pending + zero ActionExecution) is resumed on reprocess/recovery; completed events stay deduped | `tests/integration/test_m1_fixes.py::test_interrupted_before_dispatch_resumes_on_retry` |
| M1-008 | P1 | FIXED | `services/api/app/schemas.py` (bounded-string title → 422) + `services/api/app/pipeline.py` (`_record_source_failure` rolls back the aborted transaction, fresh-session fallback) | `tests/integration/test_m1_fixes.py::test_invalid_notification_title_rejected` |
| M1-009 | P2 | FIXED | `services/api/app/pipeline.py` — `_save_evidence` checks `cv2.imwrite` return and raises; event work is rolled back and the source recorded failed | `tests/integration/test_m1_fixes.py::test_evidence_write_failure_fails_source_and_rolls_back` |

## M1 review fixes (exceptional recovery cycle, 2026-10-10)

Authorized single focused M1 recovery pass (base `b131c50`). Only M1-010..013.

| ID | Severity | Resolution | File | Test |
| --- | --- | --- | --- | --- |
| M1-010 | P1 | FIXED | `services/api/app/{pipeline,main}.py` — `dispatch_admission_lock` serializes API disable commit against the worker's authoritative enabled recheck + dispatch; a disable completed before dispatch suppresses the queued action explicitly (`cancelled` execution + event `action_status`) | `tests/integration/test_m1_fixes.py::test_disable_before_dispatch_suppresses_queued_action` |
| M1-011 | P1 | FIXED (by removal) | `services/api/app/actions.py` — outbound webhook delivery removed, eliminating the interrupted/duplicate-external-delivery ambiguity; the retained local action commits atomically with its event status so recovery re-dispatches exactly once | `tests/integration/test_m1_fixes.py::{test_legacy_webhook_action_rejected_no_side_effect,test_interrupted_before_dispatch_resumes_on_retry}` |
| M1-012 | P1 | FIXED (by removal) | `services/api/app/{actions,schemas,config}.py` — `send_webhook` removed from `ActionType`; no DNS lookup or delivery can occur; legacy rows rejected at dispatch; preferred over a risky custom DNS/TLS egress transport | `tests/unit/test_webhook_auth.py`, `tests/unit/test_dsl.py::test_webhook_action_now_rejected`, `tests/integration/test_api_flow.py::test_webhook_action_rejected_at_creation` |
| M1-013 | P1 | FIXED | `services/api/app/{pipeline,config}.py` — decoded-frame count compared to reliable container frame count with `DECODE_MIN_COMPLETENESS` tolerance; substantial shortfall surfaces a failed source instead of silent `processed` | `tests/integration/test_m1_fixes.py::test_truncated_video_reported_failed` |

## Discrepancies / notes

- Cycle-1/2 fix entries above record the developer's changes and passing
  regressions at the time. Final independent review (`cc59523`) found related
  remaining P1 defects M1-010 through M1-013; those are resolved in the
  exceptional recovery cycle above. M1-001/M1-006 (webhook SSRF/traversal)
  became moot once outbound webhooks were removed; those tests were replaced.
- M1-014 (P2, CI omits httpx/SQLAlchemy) is out of scope for this focused pass.
  Removing httpx from `actions.py` reduces but does not formally close it.

- The PDF named in CLAUDE.md is absent; the official task exists as text in
  `docs/source/README.md`. Treated as the official brief (per operator message).
- Demo video provenance: built by `scripts/make_demo_video.py` from the
  Ultralytics sample photo (real photographic content, synthetic motion).
  Declared in `docs/LICENSES.md`; detection on it is genuine YOLO inference.

## Cost-efficient visual analytics — operator requirement (2026-10-10)

These gates extend the PRD; they are not attributed to the official brief.
Full audit: `docs/VISUAL_ANALYTICS_AUDIT.md`. Planned is not implemented.

| ID | Acceptance requirement | Component / evidence required | Status |
| --- | --- | --- | --- |
| M2-AC1 | Strict NL DSL, rejection, manual approval | `app/nl_compiler.py`, `/api/workflows/compile`, UI compile box; `tests/unit/test_nl_compiler.py`, `test_m2_visual.py` | implemented |
| M2-AC2 | Cheap temporal candidate events select Teacher frame/ROI; zero calls for geometric rules | `app/pipeline._route_visual`, `app/vlm_router.py`; `test_geometric_workflow_makes_zero_vlm_calls` | implemented |
| M2-AC3 | Real validated Teacher adapter; visible unknown/error/budget states | `app/teacher.py` strict validation; `tests/unit/test_teacher.py`; not-confirmed integration tests | implemented (real provider **blocked**: no VLM_BASE_URL configured) |
| M2-AC4 | Sampling, budgets, in-flight dedupe, bounded versioned cache | `app/vlm_router.py` (`VersionedTTLCache`, budget/cooldown/sampling/dedup); `tests/unit/test_vlm_router.py` | implemented |
| M2-AC5 | Actual routing counters, evidence, safe approval/action/data boundaries | `VlmCall` rows, `/api/vlm/stats`, `/api/vlm/calls`, `/api/metrics.vlm`, event `visual_*`; UI section 6 | implemented |
| M3-AC1 | Real Teacher labels, human verification, dataset provenance | Reviewed sample manifest with both classes | planned |
| M3-AC2 | Session-disjoint splits and no near-duplicate leakage | Split manifest and leakage checks | planned |
| M3-AC3 | Frozen pretrained embeddings and actually trained saved Student | Reproducible train/save/reload artifacts | planned |
| M3-AC4 | Computed held-out quality/latency/coverage | Raw predictions, ground truth, sample counts | planned |
| M3-AC5 | Action-free shadow mode, quality gate, manual activation | Integration checks including rejected activation | planned |
| M3-AC6 | Budgeted Teacher fallback, working rollback and durable history | Low-confidence/restart/rollback checks | planned |
| M4-AC1 | Paired baseline VLM / routed Teacher / Student runs | Same held-out inputs/task and real provider calls | planned |
| M4-AC2 | Raw usage, timing, predictions, provenance and comparable quality | Reproducible benchmark artifacts | planned |
| M4-AC3 | Cost derived from actual usage; honest cold/warm and savings claims | Dated rates/bill, denominators, no invented percentages | planned |
| M4-AC4 | Clean deployment, unseen-input smoke, official deliverables, privacy/licenses | Startup smoke, reports and pitch; public deploy needs approval | planned |

## Self-hosting and foveated experiment — operator update (2026-10-10)

PRD version 1.2 and `docs/VLM_ARCHITECTURE.md` define these gates. No external
provider API key is required at this stage. M1 is accepted; current M2 work
continues without interruption or additional calls for this experiment.

| ID | Requirement | Evidence required | Status |
| --- | --- | --- | --- |
| M2-AC3a | Configurable OpenAI-compatible self-hosted Teacher, VLM env vars, strict labels, bounded timeout/retries/concurrency, secure setup | `app/teacher.OpenAICompatibleTeacher` (VLM_BASE_URL/MODEL/API_KEY, connect/read/overall timeouts, bounded retries skipping auth/schema, concurrency semaphore, max image bytes, extra=forbid, data-URL images); `tests/unit/test_teacher.py` | implemented (adapter + boundaries); real vLLM/GPU smoke **UNVERIFIED** (no instance connected) |
| M2-EXP1 | Full frame, ROI, foveated context-plus-ROI interface; full-frame fallback and strategy-aware cache | Input provenance/selection tests; visibly unavailable unfinished strategies | partial — ROI crop (default) with full-frame fallback for track-less/aggregate candidates and roi_hash in cache key; `foveated`/`full_frame` strategy selector NOT implemented (planned) |
| M3-AC7 | Real GPU Teacher labels followed by verified-data Student evaluation | Actual labels/model identity and held-out predictions; currently UNVERIFIED | planned |
| M3-EXP1 | Compare input strategies on the same held-out videos/events | Accuracy/recall, tokens or actual cost, latency, failure cases; unrun results UNVERIFIED | planned |
| M4-AC3a | Actual Vast.ai rental accounting and GPU/latency/throughput/cost per event | Rental records, charged interval, GPU telemetry and paired input manifest; currently UNVERIFIED | planned |

The CVPR 2025 paper is research motivation, not VisionFlow measurement.
ROI-only crops discard scene context and are not labeled foveated. Pixel
reduction is never assumed to scale linearly with tokens or monetary cost.
