# Review — Ten-hour M2 defect resolution

VERDICT: CHANGES_REQUIRED

TARGET_SHA: 9d69f6891ebd514876f2b9bff0aa6ab041516c6d

- Reviewed commit: `9d69f6891ebd514876f2b9bff0aa6ab041516c6d`
- Implementation commit: `7d10e0d2024b6dfdfa54f4b2ec3d8d7c389d249b`
- Base commit: `088b17aded860bd5d926600573184c883919d20e`
- Review status: FAIL — three reproducible P1 defects remain.
- Final HEAD matches the target; tracked, staged and untracked status is clean. No application code, refs, history, historical reports or M1 state changed. No agents, coding CLI, rental or publication used.

## Commands executed

- Git status, HEAD/history, commit existence, base ancestry, changed-file diff and final clean-tree checks. No fetch or branch mutation.
- Read the exact ten-hour handoff, changed implementation/tests, historical M2 final findings and supplemental reproduction, supplied source brief, relevant PRD/TRACEABILITY/protocol and architecture.
- Targeted pytest: `tests/unit/test_nl_compiler.py`, `test_teacher.py`, `test_transport.py`, `test_vlm_router.py`, and `tests/integration/test_m2_visual.py`, with cache writes disabled and temporary data under `/tmp`.
- Owned loopback TCP/HTTP probes: `/tmp/visionflow-a-qa-9d69f68/probes.py` and corrected `final_probes.py`.
- Three desired-behavior assertions against the recorded independent HTTP results: `/tmp/visionflow-a-qa-9d69f68/test_acceptance.py`.
- Commands were bounded to at most 60 seconds; CPU thread limits were two. Imports resolved to this review worktree. Transport versions: httpx 0.28.1, httpcore 1.0.9.

## Test results

- Independently executed targeted suite: **105 passed, three deprecation warnings, 5.83 seconds**.
- Primary real-network probes and corrected supplemental probes: exit 0. Initial scratch harness import/constructor mistakes were corrected; those failures were not application findings.
- Desired-behavior assertions over recorded HTTP evidence: **three failed**, corresponding to M2-001, M2-003 and M2-007.
- Controller evidence inspected for this exact SHA: `make check` exit 0 in **27.17 seconds**, including **171 tests** and Next production build; `make smoke` exit 0 in **7.28 seconds**, with real YOLO event, evidence and notification. These are controller results, not independently rerun checks. No frontend rebuild was repeated.
- Safe evidence: [primary HTTP results](/tmp/visionflow-a-qa-9d69f68/results.json), [supplemental results](/tmp/visionflow-a-qa-9d69f68/final-results.json), [acceptance failures](/tmp/visionflow-a-qa-9d69f68/acceptance.log), and [corrected supplemental log](/tmp/visionflow-a-qa-9d69f68/final-probes-corrected.log).

## Verified behaviors

- The prior exact grammar examples now reject: determiner-based hood actuation, smoke embedded in a condition, two explicit durations, and duration attached to entry. Complete supported-command rejection still fails on unseen phrasing below.
- Supported drafts remain editable and save disabled; explicit enable is required. No generated-code execution was found.
- Geometric workflows make zero Teacher calls in the independently executed integration suite. Selected-event routing, unavailable/error handling, sampling, cooldown, deduplication and primary-cache bounds pass targeted tests.
- Real HTTP retry accounting: one 503 followed by success consumes two attempts from the shared budget; identical input hits cache; a different input is suppressed after budget exhaustion. Exactly two provider requests reach the owned server.
- Ordinary trickling-body timeout closes the actual TCP connection before the next test call and frees its concurrency permit. Subsequent real requests succeed. The former abandoned-worker defect is improved; hard wall-clock enforcement remains defective.
- M2-008 stays strict across real HTTP provider → router → event → action checks: eleven invalid confidence fixtures produce `invalid_response`, one low-confidence fixture remains non-actioning, and valid 0.9/integer-1 controls each create one notification. Invalid cases include Boolean, null, string, non-finite numbers, range errors and containers.
- Local action revocation remains effective in both disable races: zero notifications, action status `cancelled`.
- Webhooks remain removed/rejected rather than exposing arbitrary user destinations. Server-only endpoint configuration and private tunnel documentation were inspected.

## Findings

### M2-001 — P1 — unsupported command meaning still discarded

- File and line: `services/api/app/nl_compiler.py:237`, related lines 248, 341, 376 and 530.
- Reproduction: POST compile with “When a car enters Service Bay A, then open hood”; “When a car enters Service Bay A with hood open and trunk up, create an alert”; or dwell “for .5 minutes”.
- Expected behavior: reject unsupported actions/additional conditions; correctly parse or explicitly reject fractional duration notation.
- Actual behavior: HTTP 200, `ok=true`, valid drafts. Actuation becomes a predicate/notification, trunk-up disappears, and .5 minutes becomes 300 seconds. “for -5 minutes” also becomes 300 seconds. “more than 3 or more than 5 cars” becomes threshold 2. An alert-duration clause can incorrectly supply the dwell duration.
- Minimal suggested fix: constrain recognition to supported clause positions, consume only recognized spans, preserve unmatched semantics, anchor numeric tokens and reject multiple comparisons.

### M2-003 — P1 — real blocking transport exceeds the absolute deadline

- File and line: `services/api/app/teacher.py:479`, related lines 364, 471, 481 and 488.
- Reproduction: default transport; owned server trickles header bytes every 40 ms with a 200 ms overall deadline. Separately send headers after 160 ms then stall. Delay production approval callback or Client initialization 250 ms with a 100 ms deadline.
- Expected behavior: enforce one deadline throughout admission and active transport; never start an expired request.
- Actual behavior: header trickling takes **644.7 ms**; delayed headers/body stall takes **365.9 ms**. Slow production admission sends after **280.0 ms**, and delayed Client construction sends after **255.3 ms**, despite a 100 ms deadline. Timeout results prevent confirmation but do not prevent late network activity or bound capacity occupancy.
- Minimal suggested fix: recheck expiry after admission/construction and enforce cancellation during blocking header/body operations. Close the actual socket before releasing capacity.

### M2-007 — P1 — disable acknowledges before an unsent POST starts

- File and line: `services/api/app/vlm_router.py:332`; `services/api/app/teacher.py:479`.
- Reproduction: pause Client construction after guard completion, disable through real HTTP, then resume. Repeat at actual socket connection creation.
- Expected behavior: successful disable acknowledgment prevents every queued/unsent Teacher request.
- Actual behavior: both runs have zero requests before disable 200/enabled=false and one POST afterward. Construction pause: **6.32 ms** after acknowledgment. Connection pause: **0.49 ms** afterward. The fixture confirms; local action remains cancelled.
- Minimal suggested fix: couple authoritative approval to actual request-start/write admission and revoke unsent attempts before acknowledging disable; keep response waiting outside the lock.

### M2-009 — P2 — completed shared results bypass cache bounds

- File and line: `services/api/app/vlm_router.py:392`.
- Reproduction: ten distinct inputs, cache capacity two.
- Expected behavior: bounded completed-result retention.
- Actual behavior: two primary-cache entries, ten retained `_inflight_result` entries.
- Minimal suggested fix: release completed sharing records or bound retention. This unchanged historical P2 may be deferred with documented risk.

## Acceptance criteria

- **Passed portions:** M2-AC1 supported drafts, schema validation and explicit approval; M2-AC2 geometric zero-call/event routing; M2-AC3 strict confidence and non-confirming failures; M2-AC4 retry budgets, cache, sampling, cooldown and deduplication; M2-AC5 local-action revocation and removed webhook boundary.
- **Failed:** M2-AC1 complete unsupported/ambiguous rejection; M2-AC3/AC3a absolute deadline enforcement; M2-AC5 disable-to-provider authorization boundary. M2-AC4 retains the documented P2 storage risk.
- **NOT_TESTED:** real Teacher semantic quality, real GPU inference/authentication/usage, foveated performance, savings, live tunnel deployment, full browser workflow and optional hardware. All network providers used owned fixtures; their labels are not model-quality evidence. Original source-PDF fidelity is unavailable; the supplied brief was reviewed. Historical incomplete UI routing-setting exposure and unfinished input strategies remain disclosed limitations.

## Final recommendation

**Fix blockers.** M2 is not accepted at this frozen SHA. Preserve the verified confidence validation, real TCP cleanup and local-action revocation while closing the three P1 gaps. Historical M2 reports and M1 remain unchanged.