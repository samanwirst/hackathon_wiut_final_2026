# Project state

Updated: 2026-10-10. Branch: `feature/visionflow`.

## Current gate: M2 exceptional recovery — fixed, awaiting review

- M1 remains accepted at `390b337cc1f58504864ba27a23a96c1e811b358d`,
  report branch `review/M1-r3`, with its documented P2 risks.
- Prior frozen review snapshot: `a93d983dd89b31e329689b09726c5a1cfbf4dbb5`
  (base `2127d207a7bf2e1401d40e5ad82d926eb0f66a57`) — all four P1s reproduced.
- The ONE authorized exceptional recovery implemented fixes for the four P1s
  below; implementation SHA recorded in `.agents/HANDOFF.md`.
- Full local suite: **140 passed** (`pytest tests/ --ignore=tests/orchestrator`),
  +17 desired-behaviour regressions. M3/M4 not started; awaits a passing M2 gate.

Read [the consolidated M2 report](reviews/M2.md) for the earlier reproductions,
commands, line references, passed portions and limitations.

## Findings addressed in this recovery

- **M2-001, P1 — FIXED:** anchored grammar + residual-token backstop rejects
  negated triggers, upper-bound dwell, data-deletion actions, multiple named
  zones, extra/unknown visual conditions; supported intent preserved.
- **M2-003, P1 — FIXED:** a timed-out request no longer frees the concurrency
  slot; a deferred slot + reaper caps active transport workers to max_concurrency.
- **M2-007, P1 — FIXED:** approval read + outbound admission are one atomic
  boundary under `dispatch_admission_lock`; a committed disable cannot admit a
  new Teacher request mid-route.
- **M2-008, P1 — FIXED:** `confidence` must be an actual JSON number; booleans,
  strings, NaN and infinities are rejected and cannot authorize an action.
- **M2-009, P2 — NOT in scope** for this exceptional recovery (P1-only).

## Actual verification

Controller `make check`: **143 tests passed, four warnings**, structure check
passed, frontend production build passed. Controller `make smoke`: real YOLO
processed 30 frames, emitted a bus-entry event at 4.2 seconds/confidence 0.76,
served JPEG evidence and persisted a local notification; mean detector inference
60.4 ms. This uses synthetic motion of photographic content and is a limited
smoke measurement, not held-out model accuracy or a VLM savings comparison.

Independent QA: **143 tests passed, four warnings** using the disclosed
runner-only 10 ms asyncio heartbeat in the restricted TestClient environment;
seven focused characterization tests reproduced material defects; frontend
build and fixture-based component handlers passed. No full browser test ran.
All four exceptional M1 P1 recovery regressions remain covered and pass.

## Recovery audit

The original M2 review completed its 111-test command, then returned no final
structured result. Controller-parent interruption removed its 1,200-second
supervision; the orphan reviewer exceeded that limit and was terminated. The
logs do not establish the reason for no further model/transport output.

The user authorized **ONE exceptional review-only recovery**, completed in
602 seconds against original target `36e7ca84d4fe2048cd9c21522e2adfbfc5174798`.
Original implementation `c746fc098afd69dedc9cab54d6262e589212abc0` and handoff
remain intact in history. That review returned CHANGES_REQUIRED, permitting
the normal bounded policy: two focused Claude fixes and two exact-commit
reviews. The last review completed in 923 seconds and still found four P1s.
The controller stopped at its limit, without a synthesized PASS or extra cycle.

Claude completed the fixes and regression tests; the controller committed
those artifacts when the agent left committing to it after compound Bash
commands were denied. No additional implementation call was used to recover
commits. Runtime checkpoints, original handoffs, logs and hashed reproductions
are preserved under ignored `.agents/runtime/`; they are not public artifacts.

## Architecture and unverified capabilities

PRD section 16, `docs/VLM_ARCHITECTURE.md`, and `docs/METRICS.md` retain the
OpenVector-inspired cheap detector/tracker/temporal path, event-selected
Teacher inputs, sampling/deduplication/caching/budgets, self-hosted compatible
adapter, Teacher -> verified data -> frozen embeddings -> Student plan,
held-out/shadow/manual activation/rollback, and identical-input comparisons.

The user-authorized unavailable-provider fallback remains disclosed. No GPU
instance is connected and no external VLM API key is required at this stage.
Real Teacher inference/labels and quality, full-frame/ROI/foveated performance,
Student held-out evaluation, GPU activity/throughput, actual Vast.ai rental
costs and savings remain **UNVERIFIED**. Foveated strategy selection is planned;
ROI selection and full-frame fallback are implemented. No measured percentage
of savings is claimed. M3/M4 implementation awaits a passing M2 gate.

No main merge, force push, hardware operation, GPU rental, purchase, new paid
service or public deployment occurred. Public deployment still requires the
explicit approval specified in the original goal.

## Newly authorized exceptional M2 recovery

The human authorized exactly ONE additional implementation/review cycle for
M2-001, M2-003, M2-007, M2-008 in final review `a93d983`. Before implementation,
the controller replayed all four original reviewer reproductions against that
frozen snapshot: unsupported/negated commands were accepted, four active body
readers exceeded concurrency one, HTTP started after disable acknowledgment,
and boolean confidence created a local notification. These are reproduced
defects, not acceptance passes. Original logs/reproduction hashes are preserved
in ignored runtime storage.

One Claude pass, full checks/build/real YOLO smoke, and ONE fresh exact-commit
Codex review are authorized. No retries or further exception cycles; remaining
P0/P1 or inconclusive review leaves M2 BLOCKED. Only independent PASS permits
M2 acceptance and automatic M3 advancement. M1 remains accepted and unchanged.
Real Teacher, foveated performance, and unexecuted savings remain UNVERIFIED.
