# HANDOFF — Workstream A (ten-hour, M2 defect resolution)

- Milestone: M2 (visual workflow product) — historical workstream-A defects.
- Base HEAD: `088b17aded860bd5d926600573184c883919d20e`
- Implementation SHA (code + tests): `7d10e0d2024b6dfdfa54f4b2ec3d8d7c389d249b`
- Branch: `experiment/m2-ten-hour`
- Continuation: first Claude process hit its 1800s wallclock timeout at 22:02 UTC
  with no commit; this is the authorized continuation that finished and committed
  its preserved partial work. Not a historical exception or acceptance override.

## Scope (8 files)

Source:
- `services/api/app/nl_compiler.py` — M2-001 grammar completeness.
- `services/api/app/teacher.py` — M2-003 transport, M2-008 preserved.
- `services/api/app/vlm_router.py` — M2-007 admission boundary.

Tests (regressions preserved with behavioral intent, not vacuous seam tests):
- `tests/unit/test_nl_compiler.py`
- `tests/unit/test_teacher.py`
- `tests/unit/test_transport.py`
- `tests/unit/test_vlm_router.py`
- `tests/integration/test_m2_visual.py`

## What was implemented

### M2-001 — complete supported grammar (nl_compiler.py)
- Reject imperative part actuation ("open its hood", "pop the trunk",
  "close the door") via `_PART_ACTUATION`; distinguished from the state
  condition "hood open" by the determiner. Not downgraded to a notification.
- Tighten visual-condition matching: `_COND_GAP` whitelists only small
  scaffolding words between a part and its state, so clauses that smuggle
  unsupported semantics ("hood emitting smoke and open") are rejected rather
  than silently reduced by a greedy `.*`.
- Reject fractional object counts ("more than 5.5 cars") instead of truncating.
- Reject a duration on a non-dwell trigger ("enters ... for 5 minutes",
  "count ... for 10 min") and reject multiple ambiguous durations ("5 or 10
  minutes"); intent is never dropped — the request is rejected with a reason.
- Negation / unsupported comparisons / multiple-or-unrecognised conditions
  remain rejected (unchanged behaviour retained).

### M2-003 — cancellable actual transport / fixed deadline / admission (teacher.py)
- Removed the abandoned-daemon-worker + reaper + slot-defer design. Replaced
  with an owned, in-thread cancellable `httpx.Client.stream` body read. The
  wall-clock `deadline` is checked after response headers and between every
  chunk; on expiry the `with` block closes the response/connection, so the
  request is truly cancelled — no background worker survives.
- `max_response_bytes` (default 2 MiB; `get_teacher` reads optional
  `VLM_MAX_RESPONSE_BYTES` via getattr, no required config change) caps body
  accumulation so an endless/trickling stream cannot grow unboundedly.
- The concurrency permit is always released in `finally` once the (possibly
  cancelled) request returns, so slot capacity is never held while an
  underlying request is active. `_ConcurrencySlot.deferred` retained as a
  constant `False` for call-site compatibility.
- Trickling/stall/cancel are exercised over an injected `httpx.MockTransport`
  (`_transport` seam) driving the real streaming/body-read/cancel path; no
  discarded fake-worker result.

### M2-007 — disable ACK coupled to actual new HTTP request start (vlm_router.py)
- The approval recheck AND the budget grant occur under
  `dispatch_admission_lock` inside `_attempt_guard`, which the adapter calls
  immediately before opening the connection. A disable that committed and
  returned 200 is serialized against this boundary, so no new Teacher POST can
  start after a successful disable, including the paused-post-boundary race.
- Admission is bounded by remaining wall-clock budget: `_attempt_guard(remaining)`
  acquires the lock with a timeout; if contention holds it past the deadline the
  attempt is denied WITHOUT sending (raised as `_AttemptNotAdmitted`), rather
  than blocking and then posting late. The lock is never held across inference.
- The integration race test hook pauses at the ACTUAL send-boundary admission
  (the second `_workflow_enabled` read, held under the lock), not an earlier
  admission flag.

### M2-008 — strict confidence validation (preserved)
- Boolean confidence still cannot authorize an action across
  provider -> router -> event -> local action (`test_boolean_confidence_cannot_fire_action`).

Preserved from prior architecture (unchanged): event selectivity, zero Teacher
geometric calls, shared per-task budgets, caching, security, provider-failure
handling, no exactly-once delivery claim.

## Commands run and actual results
- `git diff` (all 8 scoped files) — reviewed; changes coherent and consistent.
- Static checks: no stray references to removed `defer`/`_deferred`/`_reap`/`box`
  APIs; single `_post_with_deadline` caller; `on_attempt` only ever called with a
  positional `remaining`; `VLM_MAX_RESPONSE_BYTES` guarded by getattr fallback.
- Root (after the timeout) ran the four changed unit files
  `test_nl_compiler.py test_teacher.py test_transport.py test_vlm_router.py`:
  **92 passed in 3.34s** (root `.agents/runtime/ten-hour/A/stopped-pass-targeted-tests.txt`).
  This is ROOT's result, cited — not re-run by this continuation.

## Known limitations / honest notes
- This continuation could NOT execute pytest or any Python itself: the Bash
  permission mode denied all `pytest`/`python` invocations. The integration file
  `tests/integration/test_m2_visual.py` was therefore NOT run in this session;
  its changes are mechanical transport-seam swaps (httpx.post monkeypatch ->
  `_transport` MockTransport) mirroring the already-passing unit transport tests.
  Root should run the full targeted integration/regression suite to confirm.
- No frontend build / full YOLO smoke was run here (root runs these independently).
- Real Teacher semantic quality / foveated savings remain UNVERIFIED (mock
  transport only; no live VLM). No exactly-once delivery is claimed.
- No push performed. No other worktrees / protected fallback / old M2
  reports/state/handoff / M1 engines touched.

## Questions for Codex
- Confirm the in-thread `client.stream` cancel closes the generator's `finally`
  synchronously on all supported httpx versions (the `peak == 1` invariant in
  `test_timeout_cancels_transport_and_never_overlaps` depends on it).
- Confirm the admission-lock `acquire(timeout=remaining)` deadline bound is the
  desired behaviour vs. a hard pre-lock deadline check only.
