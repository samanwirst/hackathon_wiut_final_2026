# HANDOFF — M2 emergency correction pass (workstream A)

Milestone: M2 (exceptional authorized ONE correction pass; no further cycle).
Branch: `experiment/m2-emergency`.
Previous target reviewed: `25bccee269bde978745c168852a716670b7f999b` (verdict CHANGES_REQUIRED).
Implementation SHA (this pass): **`9a6b8a5b27f2b36c266227f03421bf9992e1ceb0`**
Commits: `4379736` (M2-001), `9a6b8a5` (M2-003/004/010).

This does NOT claim milestone PASS. It resolves the four independently reproduced
P1 defects and preserves the previously verified behaviours. Historical M2 BLOCKED
and prior reports are unchanged; no report was overwritten.

## Scope / constraints honoured

No .env/secret read, no rent/spend/publish, no real Student activation, no GPU
calls, no push, no coding CLIs/agents started. M1, protected fallback `723a4a7`,
other worktrees, old reviews/state/history and user datasets untouched. Only owned
mock providers / owned loopback TCP fixtures used. Manual approval remains
mandatory; `demo_safe` default stays true; webhooks remain unavailable.

## Original-script reproduction (QA_ONLY scratch)

Immutable reviewer originals under
`…/review-m2-review-2/.agents/review-evidence/A-25bccee/` were copied verbatim to
owned scratch `/tmp/vf-emergency-qa/`. The ONLY adaptation applied is a path
rewrite `s#/tmp/visionflow-a-qa-25bccee#/tmp/vf-emergency-qa#g` across
`grammar_probe.py`, `network_probe.py`, `test_acceptance.py` (scratch output path
only). No fault boundary, delay, pause point or assertion was changed. The DB
directory `/tmp/vf-emergency-qa/data` must be emptied between network_probe runs
(the probe assumes a fresh SQLite DB; stale `dedupe_key`s otherwise raise an
IntegrityError — a harness-state artefact, not product behaviour).

### Commands executed (actual)
- Reproduce (pre-fix, all four FAIL):
  `PYTHONPATH=services/api .venv/bin/python /tmp/vf-emergency-qa/grammar_probe.py`
  `… /tmp/vf-emergency-qa/network_probe.py`
  `… -m pytest /tmp/vf-emergency-qa/test_acceptance.py -q` → **4 failed**.
- Post-fix (clean DB) → **4 passed**.
- `-m pytest tests/unit/test_nl_compiler.py test_teacher.py test_transport.py
  test_transport_realtcp.py test_vlm_router.py tests/integration/test_m2_visual.py`
  → **113 passed**.
- Full suite `pytest tests/ -q` → **195 passed**.
- `make check` → exit 0 (structure + 195 tests + Next production build).
- `make smoke` → **SMOKE PASS** (real YOLO: `bus #1 entered Service Bay A`,
  evidence + notification persisted; 30 frames, avg inference 56.3 ms).
- Regression meaningfulness: each new test was run against the stashed prior
  source and FAILED there (7 nl_compiler + 8 transport), then passes on the fix.

## Issue → reproduction → fix → tests

### M2-001 — complete/ambiguous intent reduced to a partial rule  (`nl_compiler.py`)
- Repro (now rejected): `Create an alert for 5 minutes when a car stays …`,
  `Notify me for 5 minutes when a car stays …`, `… with hood and trunk open`,
  `… with hood open and lights`, `… with hood`, `3 or more or 5 or more cars`.
  Repro (now correctly ACCEPTED): `… stays … for more than 2.5 minutes` → dwell 150s.
- Fix: action-first split delimits the trigger clause at the trigger-introducer
  (`when/if/once/…`) and validates the action tail (alert duration no longer leaks
  into dwell); visual conditions counted by vehicle-part mentions on the
  zone-stripped trigger clause (multiple/incomplete parts rejected, never dropped);
  count comparisons count every syntax incl. `N or more`/`N+`; decimal-duration
  comparisons no longer mis-classified as counts.
- Evidence: grammar matrix **240/240** correct, **0** control failures; only the
  supported `more than 2.5 minutes` remains accepted among the probe set.
- Tests: `tests/unit/test_nl_compiler.py::test_action_first_*`,
  `test_two_conditions_sharing_state_rejected`,
  `test_condition_plus_bare_second_part_rejected`,
  `test_incomplete_bare_condition_rejected`,
  `test_multiple_inclusive_count_comparisons_rejected`,
  `test_decimal_dwell_more_than_still_ok`.

### M2-003 — DNS/approval/TLS escape the overall deadline  (`teacher.py`, `vlm_router.py`)
- Repro: getaddrinfo 250ms/deadline 100ms; DNS 160ms + TLS stall/deadline 200ms;
  admit() 250ms/deadline 100ms; read timeout 40ms/overall 500ms; refused connect.
- Fix: `_connect_within_deadline` runs `socket.create_connection` (real connect,
  incl. its synchronous resolution) in a deadline-bounded helper thread, abandoning
  and closing an overrun socket; TLS recomputes remaining budget and sets the socket
  timeout before `wrap_socket`; `_call_within` bounds a slow `admit()` by the
  deadline; `_recv` honours `min(read_timeout, remaining)`; socket/SSL/OSError
  normalize to non-confirming timeout/error with bounded retry (never uncaught).
- Evidence: dns_deadline **100.8ms** / 100ms, dns_tls_deadline **210.1ms** / 200ms,
  slow_production_admission **100.8ms** / 100ms (all within +50ms tolerance);
  read_timeout_configuration **40.6ms**; connection_refused → typed `error`.
  Preserved: slow_headers/trickle stop at ~200ms, permit free, next request ok;
  disable_connection_race → `cancelled`, 0 attempts; disable_actual_send_race blocks
  during the unsent write then completes (1 attempt, action cancelled, 0 notif).
- Tests: `test_transport_realtcp.py::test_tls_handshake_stall_bounded_by_deadline`,
  `test_connection_refused_normalized_to_error`,
  `test_slow_admission_bounded_by_deadline` (plus preserved existing deadline tests).

### M2-004 — partial sends bypass attempt budget/counters  (`vlm_router.py`, `teacher.py`)
- Repro: owned server reads first 8 KiB of each 4 MiB POST then stalls; budget 1.
- Fix: the adapter charges one outbound attempt at the EXACT `sendall` boundary via
  a router-supplied `charge` callback — after the last expiry/disable check, right
  before bytes hit the socket. Pre-write expiry/revoke charges 0; a partial failure
  is NOT refunded.
- Evidence: received_connections **1**, received_bytes **[8192]**,
  outbound_attempts **1**, next two routes `suppressed_budget`.
- Test: `test_transport_realtcp.py::test_partial_send_consumes_budget_and_suppresses_next`.

### M2-010 — malformed/incomplete HTTP authorizes actions  (`teacher.py`)
- Repro: short Content-Length (closes 500B early), `Content-Length: garbage`,
  chunked without the terminal zero chunk.
- Fix: strict framing in `_recv_http_response`/`_read_chunked` — reject conflicting
  CL+TE, non-numeric/ambiguous CL, premature EOF before the declared length, an
  unterminated chunked stream, and a missing chunk CRLF boundary; require the final
  zero-chunk terminator. Framing validated BEFORE label parsing.
- Evidence: truncated_length / truncated_chunked / bad_length → `routed=False`,
  `notifications=0`, `visual=error`; `chunked_fast` positive control still confirms.
- Tests: `test_transport_realtcp.py::test_short_content_length_is_not_confirmed`,
  `test_garbage_content_length_is_not_confirmed`,
  `test_unterminated_chunked_is_not_confirmed`,
  `test_conflicting_framing_is_rejected`, `test_well_framed_chunked_confirms`.

## Known limitations / disclosures

- **Numeric-IP vs DNS:** DNS is bounded by abandoning an overrun
  `create_connection` in a helper thread, NOT by requiring a numeric IP. The
  reviewer's `socket.create_connection`/paused-connect fault injections therefore
  remain effective (they are still called). If an abandoned resolver/connect
  outlives the caller, the concurrency permit is released on caller return rather
  than held until the helper exits; the helper closes any socket it later produces,
  so no connection is actually held open and no POST is sent — but the permit
  accounting for that narrow abandoned-DNS edge is "free on return", not
  "retained". In-main-thread phases (TLS/send/recv) hold the permit until they
  finish/timeout, as before.
- A deadline-exceeded `admit()` yields a non-confirming `error` result (the
  `_AttemptNotAdmitted` path), not a distinct `timeout` status. Non-confirming
  either way; the acceptance assertion checks elapsed only.
- Unmeasured Teacher semantic quality / foveation / cost savings remain
  UNVERIFIED. No real provider auth, GPU inference, tunnel/TLS-gateway deployment,
  or browser journey exercised. Fixture labels are not model-quality evidence.
- M2-009 (completed-result retention outside the primary cache) is a prior
  deferred-risk item and was NOT in scope for this pass.

## Integration compatibility with accepted fallback `749d27b`

Changed components, all server-side and behind existing seams (no schema/API
surface change, safe defaults unchanged):
- `services/api/app/nl_compiler.py` — grammar only; output still a disabled,
  approval-required `WorkflowDSL` draft. No new config.
- `services/api/app/teacher.py` — raw-socket transport internals only; constructor
  signature and `TeacherResult`/`TeacherStatus` unchanged. Honours existing
  `connect_timeout`/`read_timeout`/`overall_timeout`/`max_retries`/
  `max_concurrency`/`max_response_bytes`. Self-hosted OpenAI-compatible endpoint +
  optional token model retained; loopback/SSH/authenticated-TLS usage intact.
- `services/api/app/vlm_router.py` — `on_attempt(remaining, send=…)` guard contract
  unchanged for callers; new internal `send(charge=…)` coupling and `_call_within`
  admit-bounding. Counters unchanged. `set_router`/`get_router` unchanged.
- Tests: `tests/unit/test_nl_compiler.py`, `tests/unit/test_transport_realtcp.py`.

Requirement for fallback integration: fallback `749d27b` must keep `demo_safe`
default true and manual approval; these changes neither read secrets nor enable any
Teacher-backed action without accepted integration, so its safe defaults are not
weakened.

## Questions for reviewer
1. Is abandoning-but-closing an overrun `create_connection` helper (permit freed on
   caller return) acceptable for the DNS edge, given no open connection is retained
   and no POST is emitted? (See limitation #1.)
2. Should a deadline-exceeded `admit()` map to `timeout` rather than `error`?
