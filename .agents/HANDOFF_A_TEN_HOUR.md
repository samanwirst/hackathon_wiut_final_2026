# HANDOFF — Workstream A (ten-hour, M2 defect resolution)

- Milestone: M2 (visual workflow product) — remaining workstream-A P1 defects.
- Prior reviewed SHA: `9d69f6891ebd514876f2b9bff0aa6ab041516c6d` (review verdict
  CHANGES_REQUIRED; three reproducible P1s: M2-001, M2-003, M2-007).
- Base before this pass: `9d69f68` (prior handoff of the earlier continuation).
- Implementation SHA (code + tests): `f04c48d393d10fb4dc45ff5d65cfc316306d1aa4`
- Branch: `experiment/m2-ten-hour`
- This is the authorized ONE final focused pass against the fresh independent
  review `M2-TEN-HOUR-INITIAL.md`. Not an acceptance override.

## Findings addressed (from M2-TEN-HOUR-INITIAL.md)

- **M2-001 (P1)** — unsupported command meaning silently discarded.
- **M2-003 (P1)** — real blocking transport exceeds the absolute deadline.
- **M2-007 (P1)** — disable acknowledges before an unsent POST starts.
- M2-008 strict confidence: PRESERVED (untouched, still passing).
- M2-009 (P2 bounded-cache): DEFERRED with documented risk (unchanged), as
  authorised by the review and task scope.

## Scope (changed files)

Source:
- `services/api/app/nl_compiler.py` — M2-001 grammar-first rewrite.
- `services/api/app/teacher.py` — M2-003/M2-007 owned raw-socket transport.
- `services/api/app/vlm_router.py` — M2-007 send-coupled admission guard.

Tests (added):
- `tests/unit/test_transport_realtcp.py` — real loopback-TCP regressions for
  M2-003/M2-007 (no MockTransport, no moved pause).

Existing unit/integration tests unchanged and still pass.

## What was implemented

### M2-001 — complete supported grammar (nl_compiler.py)
Replaced the "patch another blacklist" approach with clause-positional parsing:
- `_split_action` separates the trigger/condition clause from the action clause
  (the only supported action is an in-app alert/notification). Visual conditions,
  durations and counts are now recognised ONLY in the trigger clause, so
  "create an alert for 5 minutes" no longer donates "5 minutes" to a dwell rule,
  and content attached to the action clause is rejected.
- Visual conditions are **part-first** ("hood open", "hood is open", "lights on").
  The verb-first form ("open hood") is an **actuation** handled by
  `_PART_ACTUATION` (determiner now optional) and rejected — so "then open hood"
  is rejected as an unsupported action instead of being read as a condition.
- Every part+state clause is counted via `_COND_CANDIDATE`; **more than one**
  condition ("hood open and trunk up") is rejected rather than keeping only the
  first and dropping the rest. A single unsupported candidate is also rejected.
- Durations are **anchored**: `_BAD_DURATION` rejects ".5 minutes" (leading-dot)
  and "-5 minutes" (negative); a well-formed "2.5 minutes" still parses. Multiple
  durations and **multiple count comparisons** ("more than 3 or more than 5")
  are rejected (the latter fixes the accidental "3 or more" → threshold 2 match).
- The residual-token backstop runs on the trigger clause so no stray token
  survives. Narrow supported wording is documented in the module docstring and
  inline; simple geometric and explicitly-supported visual rules are preserved.

### M2-003 / M2-007 — owned cancellable transport (teacher.py)
Production path (`self._transport is None`) now uses an owned raw-socket HTTP/1.1
client (`_post_raw_socket` + `_recv_http_response` + `_read_chunked`):
- M2-003: connect, send, and every header/body `recv` are bounded by the
  remaining wall-clock budget; on expiry the socket is actually closed in
  `finally` and a `timeout` result is returned. A header byte-trickle, a
  header-then-body-stall, a slow admit and a slow connect are all cut near the
  deadline instead of running the full slow transfer. `max_response_bytes` still
  caps body accumulation (incl. chunked).
- M2-007: the connection is opened OUTSIDE the router dispatch lock (so a slow
  connect never blocks a disable); the actual `sock.sendall` is passed to the
  router guard and executed WHILE the `dispatch_admission_lock` is held, after an
  authoritative `admit()` recheck and a final deadline recheck. A disable that
  returned 200 therefore guarantees no POST is ever written; a disable landing
  during connect revokes the unsent attempt (`cancelled`, 0 outbound). The lock
  is released before the response is read (never held across inference). Budget /
  outbound-attempt accounting is consumed only on an actual send.
- `vlm_router._attempt_guard(remaining, send=None)` performs admit-recheck +
  send + budget grant atomically under the lock; the budget is granted only after
  a successful send.
- The `httpx.MockTransport` path (`_post_via_httpx`) is retained unchanged for the
  response-validation / byte-cap unit tests.

## Commands run and ACTUAL results
- Repro (pre-fix, frozen behaviour) via direct `compile_text` and the six
  reviewer texts: all six returned ok=true drafts — confirmed the defect.
- `pytest tests/unit/test_nl_compiler.py` → **44 passed**.
- `pytest tests/unit/test_teacher.py tests/unit/test_transport.py tests/unit/test_vlm_router.py`
  → **48 passed** (MockTransport path intact).
- `pytest tests/unit/test_transport_realtcp.py` → **8 passed** (real loopback TCP:
  fast-confirm control, slow-header trickle bounded <0.45s, header-then-stall
  bounded, capacity freed after cancel, slow-admit no late POST, slow-connect no
  late POST, disable-during-connect revokes with 0 outbound, 503→200 retry
  consumes budget and confirms).
- `pytest tests/` (full) → **179 passed, 4 warnings** in ~25s. (Warnings are the
  pre-existing simulated-crash resource/thread warnings in
  `tests/integration/test_m1_fixes.py`.)
- API-layer verification via `TestClient`: the six reviewer compile texts each
  return `ok=false, draft=None`; the control "…with hood open, create an alert"
  still compiles with a visual predicate.

## Known limitations / honest notes
- The `on_attempt` guard contract changed to couple the send
  (`on_attempt(remaining, send=...)`) so admission and the actual write are one
  boundary (M2-007). The reviewer's ORIGINAL probes used the prior
  `on_attempt(remaining)` bool contract and patched `httpx.Client`/`socket`; the
  new real-TCP regressions reproduce the same scenarios under the new contract
  over genuine loopback TCP. The behaviours (no late POST, disable revokes unsent
  attempt, deadline-bounded receipt) are verified, not the verbatim old scripts.
- The raw-socket transport runs synchronously in the calling worker thread; it is
  not invoked from an asyncio event loop (the pipeline is sync). No background
  worker survives a cancelled request.
- Real Teacher semantic quality / live VLM / GPU / foveated savings remain
  UNVERIFIED (owned loopback fixtures only; labels are not model-quality evidence).
- M2-009 bounded-cache P2 deferred (documented risk), per scope.
- No frontend build / YOLO smoke run here — root runs `make check`/`make smoke`
  and ONE fresh review at the exact commit. No push performed. No other
  worktrees / protected fallback / old reviews / state / M1 touched.

## Questions for Codex
- Confirm the raw-socket deadline bounds (connect/send/recv) and socket close on
  expiry are acceptable as the "genuinely owned cancellable transport".
- Confirm the send-coupled `_attempt_guard` (lock held across connect's successor
  write, released before response read) satisfies the disable→provider boundary.
