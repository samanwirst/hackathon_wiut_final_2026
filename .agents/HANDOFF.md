# Handoff — M1 review fix cycle 2 ready for re-review

- **Milestone:** M1 — vision-to-action pipeline (fix cycle 2)
- **Implementation HEAD:** `ae8f21ad2795bd262f2d1258f8d6780e67d5b8ac`
- **Base SHA:** `b131c50cce4937ac41137922d3246f2124241271`
- **Previous review base:** `dbe61a24bc5d3cf44577c033be118359bf834482` (cycle-1 handoff)
- **Branch:** `feature/visionflow`

## Findings addressed

| ID | Severity | Resolution | Reason |
| --- | --- | --- | --- |
| M1-006 | P1 | FIXED | Authorization now computes the single canonical URL that is also delivered, so the HTTP client cannot normalize a path out of the allowlist after the check. `.`/`..` segments are resolved before the prefix check (segment-boundary aware), and percent/backslash-encoded traversal (`%2e`,`%2f`,`%5c`,`\`) is rejected outright. `_authorize_webhook` returns `(allowed, reason, canonical_url)`; `_webhook_authorization` kept as a 2-tuple wrapper for the existing pure-auth tests. |
| M1-003 | P1 | FIXED (re-hardened) | The worker advances each engine once per frame, then re-reads authoritative `enabled` (fresh session) **before every event**, not once per frame. A disable committed between two events emitted on the same frame now suppresses the remaining event and action while keeping the already-completed first action. |
| M1-007 | P1 | FIXED | On reprocess/recovery, an existing committed event whose action never dispatched (`action_status == 'pending'` and zero `ActionExecution` rows) is resumed and dispatched exactly once. Completed events (status != pending or an execution row present) are left untouched, preserving idempotent dedup. Notification + status persistence remains a single atomic commit. |
| M1-008 | P1 | FIXED | `Action.check_config` validates `create_notification` `config.title` as an optional bounded string (≤255 chars); a dict/list now fails creation/enable with 422. `_record_source_failure` rolls back the aborted worker transaction before recording the failure and falls back to a fresh session, so a DB failure always leaves a visible `failed` source that can be retried (never stuck in `processing`). |
| M1-009 | P2 | FIXED | `_save_evidence` checks `cv2.imwrite`'s boolean return and raises `RuntimeError` on an unwritable/full destination. Because evidence is written before the event commit, the failure rolls back the incomplete event (no dangling evidence URL) and the source is recorded `failed`. |

## Changed files

- `services/api/app/actions.py` — canonical-URL authorization (`_authorize_webhook`, `_canonical_path`, `_path_within`), deliver canonical URL.
- `services/api/app/pipeline.py` — per-event enabled recheck, `_resume_pending_event`/`_dispatch_action`, `_record_source_failure` (rollback + fresh session), `_save_evidence` imwrite check.
- `services/api/app/schemas.py` — bounded notification-title validation.
- `tests/unit/test_webhook_auth.py` — 5 traversal/canonical-delivery cases (incl. MockTransport proof the request never reaches `/admin`).
- `tests/integration/test_m1_fixes.py` — M1-003 two-events-in-one-frame, M1-007 resume, M1-008 title 422, M1-009 evidence-write failure.
- `docs/TRACEABILITY.md`, `.agents/STATE.md` — cycle-2 fix records, test count.

## Commands executed and actual results (2026-10-10)

- `services/api/.venv/bin/python -m pytest tests/unit/test_webhook_auth.py tests/integration/test_m1_fixes.py -q` → **20 passed**.
- `services/api/.venv/bin/python -m pytest tests/unit tests/integration -q` → **53 passed**.
- `services/api/.venv/bin/python -m pytest tests/ -q` → **69 passed** (~6.8 s; includes 16 unchanged controller tests).
- `services/api/.venv/bin/python scripts/smoke_e2e.py` → **SMOKE PASS**: real YOLO detected bus (conf 0.76), `object_entered_zone` at t=4.2 s, 30 frames, avg inference 54.7 ms, evidence JPEG served HTTP 200 + notification persisted.

## Known limitations

- The M1-007 `test_interrupted_before_dispatch_resumes_on_retry` test raises a deliberate `SystemExit` inside the worker thread to simulate a crash after the event commit; pytest surfaces this as a `PytestUnhandledThreadExceptionWarning` (expected, disclosed — not a failure).
- `_record_source_failure` opens one fresh session only when the worker session cannot persist the failure; negligible cost on the failure path.
- Per-event `enabled` recheck issues one small fresh-session query per emitted event; negligible at the M1 frame/event budget.
- Encoded-traversal rejection is conservative: any `%2e`/`%2f`/`%5c`/backslash in the webhook path is refused rather than decoded, so legitimately percent-encoded path segments would be rejected (acceptable for the M1 webhook use case).
- Carried from M1: no live camera source, no NL→DSL compile, no API auth, no public deployment (M2–M4 scope).

## Questions for Codex

1. M1-007: resume re-dispatches the action but does not re-write evidence if it already exists on the committed event. If first-run evidence is also missing, is dispatching the action (notification) without evidence acceptable, or should recovery re-render evidence too?
2. M1-006: is the conservative "reject any encoded path token" policy acceptable, or should specific safe encodings be decoded and re-validated?
3. M1-003: on disable mid-frame the loop `break`s remaining events for that workflow this frame; if a workflow were re-enabled later in the same run, subsequent frames resume normally. Confirm that revocation semantic is desired.
