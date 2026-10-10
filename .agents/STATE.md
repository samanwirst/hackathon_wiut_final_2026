# Project state

Updated: 2026-10-10. Branch: `feature/visionflow`.

## Current gate: M2 BLOCKED

- M1 remains accepted at `390b337cc1f58504864ba27a23a96c1e811b358d`,
  report branch `review/M1-r3`, with its documented P2 risks.
- Latest M2 implementation: `6d71843f6ba58ccc06c1ca8a057526262676c3e7`.
- Exact tested/reviewed snapshot: `a93d983dd89b31e329689b09726c5a1cfbf4dbb5`.
- Final independent verdict: **CHANGES_REQUIRED / FAIL** on `review/M2-r3`.
- Controller phase: **BLOCKED — two normal fix cycles exhausted**.
- M2 is not accepted. M3 and M4 have not started. No further implementation or
  review cycle was launched after the final verdict.

Read [the consolidated M2 report](reviews/M2.md) for exact reproductions,
commands, line references, passed portions and limitations.

## Remaining findings

- **M2-001, P1:** Unsupported/negated NL conditions and actions silently compile
  into different rules; e.g. “does not enter”, “less than 10 minutes”, and
  “delete the video”.
- **M2-003, P1:** Timed-out daemon HTTP workers continue after releasing the
  semaphore; four unfinished requests overlapped with configured concurrency one.
- **M2-007, P1:** An earlier approval read can admit a new image request after
  API disable has returned. The later local action is correctly cancelled.
- **M2-008, P1:** Boolean confidence is coerced to 1.0 and can authorize an
  action; numeric strings also pass the supposedly strict schema.
- **M2-009, P2:** Completed deduplication results evade the bounded TTL/LRU
  cache and are retained indefinitely.

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
