# Handoff — M2 review-fix pass (P1 defects M2-001..M2-005)

- **Milestone:** M2 — strict NL workflow drafts + event-routed Teacher VLM
- **Implementation SHA:** `cc4c0ced59709baa3de399df16250b3fad495d3b`
  Controller committed Claude’s completed normal M2 fix-cycle-1 changes after
  Bash/Git denial. No extra implementation call was made. Controller full
  checks and an independent exact-SHA review remain required.
- **Base SHA:** `2127d207a7bf2e1401d40e5ad82d926eb0f66a57`
- **Prior frozen review target:** `36e7ca84d4fe2048cd9c21522e2adfbfc5174798`
- **Branch:** `feature/visionflow`

Scope: fix the five reproduced P1 defects from `.agents/reviews/M2.md` / the
focused review. No M3/M4 work. API contracts preserved; the `foveated`/
`full_frame` strategy selector (M2-EXP1) remains planned.

## Fixes

- **M2-001 — strict NL grammar** (`app/nl_compiler.py`). The compiler now:
  rejects requests naming more than one object class (e.g. "car or truck");
  rejects unsupported actions (email/SMS/phone, webhook/HTTP/Slack/Telegram,
  and code/script/shell execution) instead of silently downgrading to a local
  notification; rejects an unrecognised condition clause introduced by
  verify/check/confirm or `with its…/while…/whose…/that has…`; and **preserves**
  a whitelist of supported visual conditions (hood/trunk/door open, lights on)
  as a structured, non-executable `visual_predicate`. "When a car enters Service
  Bay A with its hood open, create an alert" now compiles **with** the hood
  predicate rather than dropping it.
- **M2-002 — confidence required + minimum** (`app/teacher.py`, `config.py`).
  A classified (non-`unknown`) label with no confidence is `invalid_response`;
  a classified label below `VLM_MIN_CONFIDENCE` (default 0.5) returns the new
  non-confirming status `low_confidence` (kept distinct from `unknown`).
  `confirmed` still requires `status == "ok"`, so neither zero nor missing
  confidence can fire an action.
- **M2-003 — single monotonic deadline** (`app/teacher.py`). One deadline
  (`t0 + overall_timeout`) now bounds semaphore acquisition (bounded
  `acquire(timeout=remaining)` → `timeout` result if it can't be obtained in
  time), each attempt's connect/read/overall phase timeouts (clamped to the
  remaining budget), and every backoff (`min(2.0, 0.5·2^n, remaining)`; skipped
  when no time remains). No phase runs past the deadline.
- **M2-004 — budget at the transport boundary** (`app/vlm_router.py`,
  `app/teacher.py`). The router passes an `on_attempt` guard to `classify`; the
  real adapter calls it before every outbound HTTP attempt (including retries),
  so each attempt consumes one shared budget unit and a retry that would exceed
  the budget is never sent. New counters distinguish `adapter_invocations`,
  `outbound_attempts`, `completed`, and `unavailable`; `UnavailableTeacher`
  makes no request and increments only `unavailable` (zero outbound attempts,
  zero `calls`). Existing keys (`calls`, `cache_hits`, …) are retained.
- **M2-005 — cooldown scope + dedup ordering** (`app/pipeline.py`,
  `app/vlm_router.py`). Cooldown scope is now the stable `(source, workflow)`
  task key instead of the always-unique per-event `dedupe_key` (which disabled
  cooldown entirely). In-flight deduplication is checked **before** the budget,
  sampling and cooldown gates, so an identical concurrent ROI attaches to the
  existing call and shares its result instead of being rejected as
  `suppressed_sampling`.

## Changed files

Production:
- `services/api/app/nl_compiler.py` — strict grammar (M2-001).
- `services/api/app/teacher.py` — confidence rules + `low_confidence` (M2-002);
  monotonic deadline (M2-003); `on_attempt` budget guard (M2-004).
- `services/api/app/vlm_router.py` — per-attempt budget, new counters (M2-004);
  in-flight-before-gates (M2-005).
- `services/api/app/pipeline.py` — stable cooldown scope (M2-005).
- `services/api/app/config.py` — `VLM_MIN_CONFIDENCE`.
- `apps/web/app/page.tsx` — "Outbound attempts" counter column.
- `.env.example` — `VLM_MIN_CONFIDENCE`.

Tests:
- `tests/unit/test_nl_compiler.py` — +5 M2-001 cases.
- `tests/unit/test_teacher.py` — +6 M2-002/M2-003 cases; 5xx-retry fixture now
  carries confidence.
- `tests/unit/test_vlm_router.py` — stub signatures updated for `on_attempt`;
  +4 M2-004/M2-005 cases (`AttemptTeacher`, `BlockingTeacher`).
- `tests/integration/test_m2_visual.py` — `StubTeacher.classify` signature.

Docs/state:
- `docs/TRACEABILITY.md` — "M2 review fixes" table.
- `.agents/STATE.md` — review-fix status.

## Commands executed and actual results

- **No tests were executed in this session.** Bash was denied by the sandbox
  (`don't ask mode`), so `pytest`, `npm run build`, and the real-YOLO smoke
  could NOT be run here. This is an honest limitation, not a passing claim. The
  controller must run, at minimum:
  - `services/api/.venv/bin/python -m pytest tests/ -q`
  - `apps/web` `npm run build`
  - the controller-run real-YOLO geometric smoke (unchanged path).
- Expected deltas vs. the prior 111-test baseline: +15 new unit tests
  (5 NL + 6 teacher + 4 router), with no removals; one teacher fixture updated
  to include confidence (previous assertion encoded the fixed-permissive bug).

## Known limitations

- **Real Teacher still UNVERIFIED.** No `VLM_BASE_URL` configured; all Teacher
  tests use mocks/stubs. Real visual inference, token usage and cost/quality
  comparisons remain deferred (M2-AC3a real smoke, M3/M4). Missing provider
  access is a documented blocker, never fabricated success.
- Cooldown scope is intentionally `(source, workflow)`-stable (documented
  trade-off): it throttles the whole rule within the window rather than a
  single track.
- `low_confidence` results are not cached (treated as soft, re-checkable);
  deterministic `ok`/`unknown` remain cached.
- Carried from M2: ROI-crop + full-frame fallback only; `foveated` selector
  planned; no API auth / live camera / public deployment (M4 scope); DB column
  additions apply to fresh SQLite DBs.

## Review items for Codex

1. Is the `(source, workflow)` cooldown scope the intended granularity, or
   should a per-track scope be offered as a per-workflow option?
2. Is `VLM_MIN_CONFIDENCE=0.5` an acceptable default, and is `low_confidence`
   the right distinct status (vs. collapsing into `unknown`)?
3. Confirm the per-attempt budget-guard interface (`on_attempt`) is acceptable
   for the adapter contract, including the stub fallback that counts one
   outbound attempt when an adapter does not report attempts.

## Controller commit recovery

- Code and regression tests were committed after the agent returned success,
  with testing explicitly unexecuted in that session. The original handoff is
  preserved in ignored runtime storage.
- Actual code-parent SHA: `e6171fd89e6a9bcb9388f9120d7a3373c4e3cdd1`.
- M1 acceptance and the original M2 frozen target remain preserved.
- No PASS, real Teacher quality, or savings measurement is claimed here.
