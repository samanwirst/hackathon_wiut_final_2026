# Review — AE frozen M2 emergency snapshot

VERDICT: CHANGES_REQUIRED

TARGET_SHA: 953d0e275177951a71c4c8fccf6b915693e43550

- Reviewed commit: `953d0e275177951a71c4c8fccf6b915693e43550`.
- Base commit: `25bccee269bde978745c168852a716670b7f999b`, verified ancestor.
- Implementation commit: `9a6b8a5b27f2b36c266227f03421bf9992e1ceb0`; the final commit changes only the handoff.
- Review status: FAIL — four independently reproduced P1 findings. Completed within the 2,400-second bound.
- Fresh result only. Historical BLOCKED verdicts and reports remain unchanged. No further correction/review cycle is authorized.
- Official text reviewed: `docs/source/README.md`. The original `FINAL_TASK_WIUT_HACKATHON.pdf` is absent; comparison against the original PDF was unavailable.

Read AGENTS.md, CLAUDE.md, emergency handoff, protocol, relevant PRD acceptance/traceability/self-hosted design, changed implementation/tests and necessary frontend, schema, pipeline and action dependencies.

## Commands actually executed

Repository checks included `git rev-parse HEAD`, `git status --porcelain=v1`, `git log --oneline -6`, base ancestry, changed-file diffs/stat, implementation-to-handoff diff, source reads and `rg` searches. No fetch or ref changes.

Application/test commands used bytecode disabled, `TMPDIR=/tmp`, two-thread OMP/OpenBLAS/MKL/VisionFlow limits, blank provider configuration and owned scratch data. Production imports used `PYTHONPATH=services/api:packages/vision`.

- Ran the copied original `grammar_probe.py` and `network_probe.py` using `services/api/.venv/bin/python`.
- Ran `pytest -p no:cacheprovider tests/unit/test_nl_compiler.py tests/unit/test_teacher.py tests/unit/test_transport.py tests/unit/test_transport_realtcp.py tests/unit/test_vlm_router.py tests/integration/test_m2_visual.py -q` with owned basetemp.
- Ran original `test_acceptance.py` with cache-disabled pytest.
- Ran independent `extended_probe.py`, `additional_probe.py` and `controls_probe.py`.
- The UI probe invoked `node /tmp/visionflow-m2-emergency-review-953d0e2/ui_roundtrip.js`, executing the actual frontend closures.
- Ran cache-disabled pytest for `tests/unit/test_dsl.py`, `tests/unit/test_webhook_auth.py` and independent `test_extended_acceptance.py`.
- Created scratch evidence, hashes and reports; performed final HEAD/full-status/staged/unstaged verification.

## Results

- Independent focused suite: **129 passed**, three warnings, 8.10 seconds.
- Schema/webhook controls: **10 passed**, 0.25 seconds.
- Original supported compiler matrix: **240/240** validated correct drafts.
- Original executable acceptance: **4 passed**. Those assertions cover the original examples, not complete root-cause acceptance.
- Extended desired acceptance: **6 failed, 6 passed**. Failures cover competing states, active capacity, absolute admission deadline, TLS phase limit, malformed framing and UI decimal preservation.
- Inspected root receipts matching this exact SHA: `make check` exited 0 in 26.22 seconds, including 195 tests and frontend build; `make smoke` exited 0 in 6.43 seconds with a real YOLO bus event, evidence and notification. Neither completed full builds nor real YOLO were repeated. These supplied results do not establish Teacher quality or unseen-jury-input acceptance.

[Full report](/tmp/visionflow-m2-emergency-review-953d0e2/report.md), [evidence manifest](/tmp/visionflow-m2-emergency-review-953d0e2/manifest.json), [extended acceptance failures](/tmp/visionflow-m2-emergency-review-953d0e2/extended-acceptance.log), [extended results](/tmp/visionflow-m2-emergency-review-953d0e2/extended-results.json), [additional results](/tmp/visionflow-m2-emergency-review-953d0e2/additional-results.json).

## Original fault boundaries and adaptations

Copied immutable original scripts from `review-m2-review-2/.agents/review-evidence/A-25bccee/`. **Only scratch output/data paths changed**. No callback or endpoint adaptation was necessary; no delay, pause point or assertion changed. Original-script embedded historical SHA labels remain historical metadata; this fresh report and manifest identify the reviewed SHA.

Preserved actual getaddrinfo/connect/admission fault boundaries and the actual socket-send pause. The attempt-budget reproduction retained three distinct 4 MiB inputs and a real server reading its first 8,192 bytes while real `sendall` times out. No mocked send replaced backpressure. Extended malformed framing exercised the real provider adapter → router → persisted event → notification path. Resolver-capacity tests extended the same DNS boundary and waited for helper termination.

UI checks executed exact production closures with simulated state setters/fetch, submitted their output to the real API and exercised the production event engine. This is disclosed contract testing, not a claimed browser or phone run.

All independent provider/model/detector stimuli were **QA_ONLY fixtures**, not genuine Teacher labels or phone evidence. No real Student operation, GPU/provider, physical capture, credentials, root experiment data, spend, publication, coding CLI, agent, source edit or Git mutation occurred. Artifacts/data/report remain in the new owned scratch directory; source and `.agents` stayed read-only.

## Verified behaviors

- Original action-tail duration, hood+trunk, bare hood, multiple comparisons, unknown actions and ordinary negations now reject. Supported decimal values survive compiler validation. Draft creation remains disabled; explicit Enable is separate. No generated-code execution path was found.
- **M2-004 original boundary fixed:** one partially written request charges one attempt, with no refund; subsequent two inputs suppress. Actual raw preflight rejection has zero connections/attempts, and a small control subsequently succeeds. Expired-before-write and revoked attempts count zero. Retry budget 1 sends once; real 503→200 with budget 2 sends twice.
- **M2-007 preserved:** disable during paused connection returns 200 with zero POSTs/attempts and cancellation. Disable during paused actual send blocks until that admitted write completes; eventual local action is cancelled with zero notifications. The tested acknowledgment never precedes a new unsent write.
- **M2-008 preserved:** twelve malformed confidence cases, including bool/missing/string/NaN/infinities/range failures, cannot act. Low confidence cannot act. Numeric 0.9 and integer 1 controls each persist one notification.
- Header/body trickle stops around 200–202 ms against 200 ms overall, with TCP closure before a subsequent successful request. Original caller-only DNS/admission deadlines and configured 40 ms read limit pass. Refusal/socket/TLS timeout failures become non-confirming results.
- Real TCP cache controls distinguish changed ROI/task/model/configured prompt version; identical concurrent requests share one actual call. Focused tests exercise geometric zero-Teacher routing, sampling, cooldown, TTL/LRU, action dedup/recovery and visible unavailable/error states.
- Webhook DSL returns 422; legacy webhook tests prove rejection without DNS/network. Server configuration/token remain outside frontend contracts. Synthetic-token public result/stat controls expose no token, endpoint or image marker. Source retains default TLS certificate verification. Actual provider authentication/private deployment remains unverified.

## Findings

- **M2-001 — P1:** competing headlights states still reduce to lights-on-only; an undelimited action-first clause still donates its duration to dwell. Complete intent rejection remains incomplete.
- **M2-003 — P1:** caller timeout frees capacity while resolver work remains active; admission reuses stale remaining time; TLS ignores the configured connection-phase limit.
- **M2-010 — P1:** conflicting lengths and malformed/incomplete chunk framing still authorize persisted local notifications.
- **M2-011 — P1:** frontend rounding changes supported decimal dwell semantics and permits an earlier event.

Detailed reproduction, expected/actual behavior and minimal fixes are supplied in the findings array and saved full report.

## Acceptance criteria

- **Passed portions:** M2-AC1 supported compiler/schema/separate approval/no generated execution; M2-AC2 geometric zero-Teacher and candidate ROI routing; M2-AC3 confidence and ordinary failure visibility; M2-AC4 partial-write accounting/retries/cache/sharing/sampling/cooldown; M2-AC5 tested disable/write authorization, action dedup and public metadata privacy.
- **Failed:** M2-AC1 complete intent rejection and exact editable-draft preservation; M2-AC3 malformed-response non-confirmation; M2-AC3a absolute/phase deadlines and actual concurrency bounds; M2-AC5 supported new-user decimal dwell semantics.
- **Deferred/incomplete:** prior M2-009 P2 completed-result retention outside the primary bounded cache remains at `vlm_router.py:458`, source inspected but prior reproduction not rerun. UI lacks routing-setting editors. M2-EXP1 documents context-plus-ROI foveation, but the configurable strategy selector remains deferred, not accepted as implemented.
- **NOT TESTED / UNVERIFIED:** genuine Teacher semantic quality, model identity/authentication, private tunnel/authenticated TLS deployment, GPU/Student operation, full browser/phone journey, unseen-jury-video end-to-end behavior, night/rain/local-vehicle quality, foveation gains, accuracy/cost/savings experiments and final public deliverables. Original PDF comparison is unavailable. Fixtures and the supplied YOLO smoke do not establish these claims.

## Final recommendation

**Fix blockers; do not accept this snapshot as M2 PASS.** Preserve the verified partial-write budget, disable serialization and strict confidence behavior. This completed fresh review authorizes no additional automatic correction/review cycle; historical BLOCKED verdicts remain intact.

Final exact verification: HEAD=`953d0e275177951a71c4c8fccf6b915693e43550`; full porcelain status empty; staged and unstaged `git diff --exit-code` both exit 0. Frozen HEAD and clean status preserved.
