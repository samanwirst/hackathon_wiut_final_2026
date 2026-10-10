# Handoff — M2 review-fix pass CYCLE 2 (P1 defects M2-001/003/004/006/007)

- **Milestone:** M2 — strict NL workflow drafts + event-routed Teacher VLM
- **Implementation SHA:** `6d71843f6ba58ccc06c1ca8a057526262676c3e7`
  Controller committed Claude’s completed final normal M2 fix-cycle changes.
  The agent left committing to the controller after its compound Git-status
  command was denied; a separate plain Git-commit denial was not established.
  Full controller checks and independent acceptance remain required.
- **Base SHA:** `2127d207a7bf2e1401d40e5ad82d926eb0f66a57`
- **Branch:** `feature/visionflow`

Scope: fix the five re-opened/new P1 defects from the focused review. No M3/M4
work. API contracts preserved (one additive, optional `admit` kwarg on
`VlmRouter.route`; one additive `reports_attempts` class attribute on the Teacher
adapter). The `foveated`/`full_frame` strategy selector (M2-EXP1) remains planned.

## Fixes

- **M2-001 — strict NL grammar** (`app/nl_compiler.py`). The compiler now:
  rejects **negated/closed-state** visual conditions ("hood not open", "hood
  closed") instead of turning them into a positive hood-open predicate; rejects
  **more than one visual condition**; rejects **more than one trigger family**
  (enter/exit/dwell/count), so "enters or exits" is rejected; rejects
  **unsupported actions** — physical/control actuation and external dispatch
  ("unlock/open the gate", "activate", "turn on/off", "dispatch", "honk", …) —
  rather than silently downgrading to a notification; rejects **unsupported
  appearance attributes** (colour/tint/damage) applied to the object; and
  **converts inclusive counts** correctly — "at least N" → threshold `N-1` (since
  the engine fires on strictly-greater-than), rejecting upper-bound comparisons
  ("fewer than N") and a too-low inclusive bound ("at least 1"). Supported
  phrasings (single class/trigger/zone, positive whitelisted visual condition,
  exclusive "more than N") are preserved exactly.
- **M2-003 — wall-clock deadline across transport + body** (`app/teacher.py`).
  New `_post_with_deadline` runs the blocking request and full-body read in a
  daemon worker and waits only for the remaining monotonic deadline. A provider
  that trickles compliant chunks (each within the read timeout) but overruns the
  overall deadline is abandoned at the deadline and returns a non-confirming
  `timeout`; a late response is never consumed. The existing bounded semaphore,
  retries and deadline-bounded backoff are preserved.
- **M2-004 — budget only via the transport guard** (`app/teacher.py`,
  `app/vlm_router.py`). The real adapter declares `reports_attempts=True`; the
  router now accounts its attempts/budget **exclusively** through the `on_attempt`
  transport guard (an outbound request happened iff `granted>0`). A local
  preflight/queue failure (oversize image, semaphore timeout, budget-exhausted
  retry) never grants the guard, so it consumes **no budget**, counts **zero**
  `outbound_attempts`/`completed`/`calls`, and is recorded only as `failed`. The
  stub-only fallback (one unit when an adapter does not report attempts) is kept
  for test stubs that don't call the guard.
- **M2-006 — resume a confirmed-but-undispatched visual action**
  (`app/pipeline.py` `_resume_pending_event`). On recovery, a pending visual
  event that carries a **valid persisted confirmation** (`visual_status=="ok"`,
  `visual_label` still equal to the current `expected_label`, and
  `visual_routing.confirmed`) is resumed exactly once through the guarded
  idempotent dispatch (which rechecks current approval). A pending visual event
  **lacking** a valid confirmation is marked `interrupted_unverified` /
  `interrupted` instead of firing an unverified action or staying silently
  pending (no frame is available to re-route during recovery).
- **M2-007 — serialize provider admission with workflow disable**
  (`app/pipeline.py` `_route_visual`, `app/vlm_router.py`). Before routing,
  `_route_visual` rechecks the authoritative enabled state **under
  `dispatch_admission_lock`** (the same lock the disable handler commits under);
  a disable that already completed records the candidate as `cancelled` with **no
  Teacher call / image disclosure**. As defense-in-depth for a disable that lands
  mid-route, the router passes an `admit` guard that rechecks approval at the
  transport boundary and, if revoked, returns a `cancelled` decision without any
  outbound attempt.

## Changed files

Production:
- `services/api/app/nl_compiler.py` — strict grammar (M2-001).
- `services/api/app/teacher.py` — `reports_attempts` (M2-004); wall-clock deadline
  `_post_with_deadline` (M2-003).
- `services/api/app/vlm_router.py` — attempt-only accounting + `cancelled` status
  (M2-004); `admit` transport-boundary guard (M2-007).
- `services/api/app/pipeline.py` — confirmation-aware recovery (M2-006);
  admission recheck + `admit` wiring + `cancelled` action status (M2-007).
- `services/api/app/db.py` — status-comment updates only (`interrupted_unverified`,
  `interrupted`, `cancelled`); no schema/column change.

Tests:
- `tests/unit/test_nl_compiler.py` — +10 M2-001 cases.
- `tests/unit/test_transport.py` — NEW: 2 M2-003 genuine-httpx streaming cases.
- `tests/unit/test_vlm_router.py` — +2 M2-004/M2-007 cases.
- `tests/integration/test_m2_visual.py` — +3 M2-006/M2-007 cases.

Docs/state:
- `docs/TRACEABILITY.md` — "M2 review fixes — cycle 2" table.
- `.agents/STATE.md` — cycle-2 status.

## Commands executed and actual results

- `services/api/.venv/bin/python -m pytest tests/ -q --ignore=tests/orchestrator`
  → **123 passed, 4 warnings** (one expected `SystemExit` from the M1
  simulated-crash recovery test, surfaced as a thread-exception warning).
- Targeted: `tests/unit/test_nl_compiler.py tests/unit/test_teacher.py
  tests/unit/test_transport.py tests/unit/test_vlm_router.py` → **66 passed**;
  `tests/integration/test_m2_visual.py` → **11 passed**.
- **Not run here:** frontend `npm run build` and the real-YOLO geometric smoke
  (no frontend change this cycle; controller should still run both). The controller
  committed the completed artifacts and recorded the exact SHA above.

## Known limitations

- **Real Teacher still UNVERIFIED.** No `VLM_BASE_URL` configured; all Teacher
  tests use mocks/stubs (including the M2-003 genuine-httpx test, which uses a
  `MockTransport`, not a real VLM). Real visual inference, token usage and
  cost/quality remain a documented blocker, never fabricated success.
- An over-deadline request is abandoned to a bounded daemon worker (semaphore +
  budget bound it); its late response is rejected and never consumed. True
  socket-level cancellation is not performed.
- An unconfirmed interrupted visual candidate is marked `interrupted` rather than
  re-routed (no frame is retained for recovery) — honest, documented trade-off.
- Carried from M2: ROI-crop + full-frame fallback only; `foveated` selector
  planned; no API auth / live camera / public deployment (M4 scope).

## Review items for Codex

1. Is the `(source, workflow)`-serialized admission recheck under
   `dispatch_admission_lock` (held only around the recheck, not the whole Teacher
   call) the intended granularity for M2-007, with the transport-boundary `admit`
   guard as the mid-route defense?
2. Is `interrupted_unverified` the right terminal state for an unconfirmed
   interrupted visual candidate, or should recovery re-route using the next
   available frame?
3. Confirm the `reports_attempts` adapter contract and attempt-only budget
   accounting (M2-004) are acceptable, including the retained stub fallback.

## Controller commit recovery

- Code-parent SHA: `8b75b63dbab717c0ae6f1a71bff1acc9008effd7`.
- Original agent handoff and output are preserved in ignored runtime storage.
- This is normal M2 fix cycle **2 of 2**, not a new exceptional implementation.
- The daemon-worker cancellation/concurrency behavior remains subject to
  independent acceptance; response-time tests alone do not verify socket
  cancellation or actual maximum outstanding requests.
- M1 remains accepted. No real Teacher performance or savings is claimed.
