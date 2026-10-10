# Handoff — M1 exceptional recovery cycle ready for independent review

- **Milestone:** M1 — vision-to-action pipeline (exceptional recovery cycle)
- **Implementation SHA:** `8bf4d56725dc41f1c380de50b06001e3d7f53d35`
- **Base SHA:** `b131c50cce4937ac41137922d3246f2124241271`
- **Previous review target:** `cc595239c2d361c714a996f23712643981209b95` (`.agents/reviews/M1.md`)
- **Branch:** `feature/visionflow`

Scope: ONLY the four reviewed P1 defects M1-010..M1-013 and their regressions.
No M2/M3/M4 work. M1-014 (P2 CI deps) deliberately out of scope.

## Findings addressed

| ID | Severity | Resolution | Reason |
| --- | --- | --- | --- |
| M1-010 | P1 | FIXED | New `pipeline.dispatch_admission_lock` serializes the API disable commit (`main.py` `disable_workflow`) against the worker's dispatch admission (`pipeline._dispatch_action`). Inside the lock the worker re-reads authoritative `enabled`; a disable committed before dispatch suppresses the queued action explicitly — a `cancelled` `ActionExecution` row plus `TrackEvent.action_status = "cancelled"` — and performs no side effect. A cancelled event is never re-dispatched on reprocess (status != pending). |
| M1-011 | P1 | FIXED (by removal) | Outbound webhook delivery removed, so there is no external side effect that an interrupted recovery could duplicate. The retained local `create_notification` records its `ActionExecution`, `Notification`, and `event.action_status` in a single `session.commit()`, so a crash before commit rolls back fully and recovery re-dispatches exactly once (existing `test_interrupted_before_dispatch_resumes_on_retry` still passes). No claim of generic exactly-once external delivery is made. |
| M1-012 | P1 | FIXED (by removal) | `send_webhook` removed from `ActionType` (creation returns 422). All SSRF/DNS/allowlist machinery deleted from `actions.py`; `WEBHOOK_ALLOWLIST` removed from config/.env. A legacy persisted `send_webhook` row is rejected at dispatch with status `rejected` and **no** `getaddrinfo` call and **no** delivery. Chosen over a risky custom DNS/TLS egress transport, per operator guidance. |
| M1-013 | P1 | FIXED | After the decode loop, `frames_read` (every successfully decoded frame) is compared to the container-reported `frame_count`. If `frames_read < frame_count * DECODE_MIN_COMPLETENESS` (default 0.9) the source is recorded `failed` with an explicit "incomplete video: decoded N of M frames" error instead of `processed`. Guard only fires when reliable metadata exists; a complete faststart video still processes cleanly (verified both ways). |

## Changed files

- `services/api/app/actions.py` — removed all webhook/SSRF code and the httpx dependency; `execute_action` now runs only `create_notification` and rejects any other/legacy action type with no network activity.
- `services/api/app/pipeline.py` — `dispatch_admission_lock`; `_dispatch_action` recheck+suppression; decode-completeness guard.
- `services/api/app/main.py` — `disable_workflow` commits inside `dispatch_admission_lock`.
- `services/api/app/schemas.py` — `ActionType` = `create_notification` only; dropped send_webhook url validation.
- `services/api/app/config.py` — removed `WEBHOOK_ALLOWLIST`; added `DECODE_MIN_COMPLETENESS`.
- `services/api/app/db.py` — document `cancelled` action/execution status.
- `tests/unit/test_webhook_auth.py` — rewritten: legacy webhook rejected with no DNS lookup; notification still works; helpers removed.
- `tests/unit/test_dsl.py` — `test_webhook_action_now_rejected`.
- `tests/integration/test_api_flow.py` — webhook workflow rejected at creation (422).
- `tests/integration/test_m1_fixes.py` — new regressions: `test_disable_before_dispatch_suppresses_queued_action` (M1-010), `test_legacy_webhook_action_rejected_no_side_effect` (M1-011/012), `test_truncated_video_reported_failed` (M1-013).
- Docs: `README.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/TRACEABILITY.md`, `packages/integrations/README.md`, `.env.example`, `.agents/STATE.md`.

## Commands executed and actual results (2026-10-10)

- `services/api/.venv/bin/python -m pytest tests/unit -q` → **30 passed**.
- `services/api/.venv/bin/python -m pytest tests/integration/test_m1_fixes.py -q` → **10 passed** (1 disclosed `PytestUnhandledThreadExceptionWarning` from the deliberate crash in `test_interrupted_before_dispatch_resumes_on_retry`).
- `services/api/.venv/bin/python -m pytest tests/integration/test_api_flow.py -q` → **6 passed**.
- `services/api/.venv/bin/python -m pytest tests/ -q` → **66 passed, 4 warnings** (~11.5 s; includes 16 unchanged controller/orchestrator tests, which were not modified).
- `services/api/.venv/bin/python scripts/smoke_e2e.py` → **SMOKE PASS**: real YOLO, bus `object_entered_zone` at t=4.2 s conf 0.76, 30 frames analyzed / 180 decoded (completeness guard did not false-fire), evidence JPEG served HTTP 200 + notification persisted, avg inference 72.3 ms.
- `apps/web` `npm run build` → **compiled successfully**, 4 static pages generated.

Test count changed 69 → 66 because the removed webhook SSRF/traversal test set (now moot) was larger than the three added regressions.

## Known limitations

- **Outbound actions removed**: M1 performs only the local `create_notification`. No external delivery (webhook/CRM/robot) is shipped. A validated-egress integration is deferred; do not interpret this as exactly-once external delivery support.
- M1-013 guard depends on the container reporting a frame count; for inputs where OpenCV returns no/zero `frame_count` the shortfall cannot be detected and the run completes normally (honest false-negative, not a false-positive). Default tolerance 0.9 (`DECODE_MIN_COMPLETENESS`).
- `dispatch_admission_lock` is held across one local notification commit; negligible at the M1 budget and does not block detection.
- M1-014 (P2): CI job dependency list still needs `SQLAlchemy`; `httpx` is no longer imported by `actions.py` but may still be referenced by other suites. Out of scope for this focused pass.
- Carried from M1: no live camera, no NL→DSL compile, no API auth, no public deployment (M2–M4 scope). The real-YOLO smoke uses a photographic sample with synthetic motion — not a held-out accuracy/latency/cost benchmark. **Public deployment is NOT complete.**

## Questions for Codex

1. M1-010: is `cancelled` (distinct from `failed`) the desired terminal state for a queued action suppressed by a pre-dispatch disable, and should the cancelled event itself remain visible (it does)?
2. M1-011/012: confirm that cleanly removing outbound webhooks (vs. a custom validated-egress transport) is the accepted resolution for M1, with reintroduction deferred to a later milestone.
3. M1-013: is a 0.9 decode-completeness threshold acceptable, or should the tolerance be tighter/looser given codec frame-count inaccuracies?
