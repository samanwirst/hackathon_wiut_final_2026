from pathlib import Path
import json
p=Path('/tmp/visionflow-m2-emergency-review-953d0e2')
findings=[
{
'id':'M2-001','severity':'P1','file_line':'services/api/app/nl_compiler.py:308 (related: 405, 697)',
'reproduction':'POST /api/workflows/compile with "When a car enters Service Bay A with headlights on or off, create an alert" or "... headlights on and off ...". Both return HTTP 200, ok=true. The action-first input "Create an alert for 5 minutes a car stays in Service Bay A" also succeeds with dwell=300 although it lacks a trigger delimiter/dwell duration.',
'expected':'Reject competing/contradictory states and ambiguous clause boundaries; consume the complete instruction instead of reducing it to a supported fragment.',
'actual':'Both competing-state requests become lights-on-only predicates. A single part/candidate passes validation while the residual filter blanks off and ignores and/or. The no-delimiter action-first fallback still donates an action duration to dwell. Plain headlights-off is correctly rejected; headlights-on is a supported positive control.',
'fix':'Validate complete matched condition/clause spans; reject leftover state/comparison/connective semantics and require an unambiguous trigger boundary for action-first instructions. Do not blanket-strip unconsumed state vocabulary.'
},
{
'id':'M2-003','severity':'P1','file_line':'services/api/app/teacher.py:173 (related: 205, 641; services/api/app/vlm_router.py:360)',
'reproduction':'Production raw TCP adapter, max_concurrency=1, overall=60 ms: delay actual getaddrinfo for the owned loopback destination by 500 ms and issue four sequential calls. Separately hold the actual admission lock for 130 ms then delay admit by 140 ms with overall=200 ms. Stall an actual TCP TLS handshake with connect_timeout=40 ms, overall=500 ms.',
'expected':'Underlying resolution/admission/connect work remains capacity-accounted until termination. All phases share one absolute deadline; configured connection/TLS and read limits apply. Expired/revoked work sends/counts zero attempts.',
'actual':'Four resolver helpers are simultaneously active despite limit 1; each timed-out caller frees its permit. All four later establish owned TCP connections (zero POSTs) and terminate. Admission returns after 271 ms against 200 ms because its wait reuses the pre-lock remaining budget. TLS returns after 511 ms instead of the configured 40 ms phase limit. Original caller-only deadlines, 40 ms read limit, refusal normalization and disable/write serialization pass.',
'fix':'Retain capacity until abandoned helpers actually terminate, or explicitly validate/restrict private numeric IP configuration and reject hostnames promptly to remove DNS scope. Recompute remaining time after every wait and apply min(connect_timeout, remaining) to TLS; preserve zero pre-write accounting.'
},
{
'id':'M2-010','severity':'P1','file_line':'services/api/app/teacher.py:738 (related: 751, 817, 823)',
'reproduction':'Owned real TCP provider sends a valid positive JSON envelope with conflicting duplicate Content-Length headers (99999 then actual length), or chunked data ending "0\\r\\nX-QA: owned\\r\\n" without the final blank line, or an invalid trailer line. Exercise provider -> router -> persisted event -> local notification. Additional malformed empty/signed chunk-size, invalid status-line and invalid Transfer-Encoding cases are in extended_probe.py.',
'expected':'Malformed, ambiguous or incomplete HTTP framing must fail before label confirmation and produce zero actions. Correct Content-Length, chunked and valid trailer controls must still pass.',
'actual':'Each of eight extended malformed cases records visual_status=ok, action_status=done and one real Notification. Header dict overwrites conflicting lengths; the zero-chunk branch accepts any first CRLF without validating/completing trailers; int parsing accepts empty/signed chunk sizes. Original short-body, garbage length and missing-zero cases now reject, as do negative/comma-conflicting lengths, CL+TE and bad data CRLF; all three correctly framed controls pass.',
'fix':'Preserve/reject duplicate ambiguous framing headers, validate exact supported transfer coding and HTTP status syntax, require unsigned nonempty hexadecimal chunk sizes, and parse validated trailers through their final blank line before returning success.'
},
{
'id':'M2-011','severity':'P1','file_line':'apps/web/app/page.tsx:277 (related: 289)',
'reproduction':'Compile a supported 1.25-second dwell through the real HTTP API. Execute the exact applyDraft/createWorkflow closures extracted from page.tsx with recorded state setters/fetch, then POST their payload to the real API and explicitly enable. Compare saved DSL and run the production event engine at 1.1 seconds. Other supported controls: 1.4 seconds, 0.024 minutes, 2.5 minutes.',
'expected':'The validated decimal duration survives Apply draft -> Create -> explicit Enable unchanged, so the event cannot fire before the requested minimum dwell.',
'actual':'Compiled 1.25 becomes stored 1.0; the UI-derived rule emits at 1.1 seconds while the original draft does not. 1.4 and 1.44 also become 1.0; 150 seconds stays 150. Create remains disabled and only an explicit Enable arms it. Default action/cooldown/approval fields are preserved for these generated drafts. This is execution of production frontend closures, not a claimed browser/phone test.',
'fix':'Assign the exact floating-point duration instead of Math.round, allow decimal form input, and show sufficient duration precision. Keep the validated draft settings through creation and the separate explicit approval step.'
}
]
report='''# Review — AE frozen M2 emergency snapshot

VERDICT: CHANGES_REQUIRED

TARGET_SHA: 953d0e275177951a71c4c8fccf6b915693e43550

- Reviewed commit: `953d0e275177951a71c4c8fccf6b915693e43550`.
- Base commit: `25bccee269bde978745c168852a716670b7f999b` (verified ancestor).
- Implementation commit: `9a6b8a5b27f2b36c266227f03421bf9992e1ceb0`; the final commit changes only the handoff.
- Review status: FAIL — four independently reproduced P1 findings. Conclusive within the 2,400-second bound; no timeout acceptance.
- Fresh result only. Historical M2/M3 BLOCKED verdicts and reports remain unchanged. No additional correction cycle is authorized.
- Official text: read `docs/source/README.md`. Original `FINAL_TASK_WIUT_HACKATHON.pdf` is absent; authenticity/completeness against the original PDF could not be verified.
- Reviewed AGENTS.md, CLAUDE.md, emergency handoff, protocol, relevant PRD/traceability/self-hosted design, all changed implementation/tests and necessary frontend/pipeline/schema/action dependencies.

## Commands actually executed

Repository reads included `git rev-parse HEAD`, `git status --porcelain=v1`, `git log --oneline -6`, base ancestry, diff/stat/name inspection, `git show --format=fuller --no-patch HEAD`, source reads and `rg` searches. No fetch or ref changes.

All Python application/test commands used `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR=/tmp`, `OMP_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `VISIONFLOW_THREADS=2`, blank `VLM_BASE_URL/VLM_API_KEY/VLM_MODEL`, and owned data directories. Production imports used `PYTHONPATH=services/api:packages/vision`. Executed:

- `services/api/.venv/bin/python /tmp/visionflow-m2-emergency-review-953d0e2/grammar_probe.py` and `network_probe.py`.
- `services/api/.venv/bin/python -m pytest -p no:cacheprovider tests/unit/test_nl_compiler.py tests/unit/test_teacher.py tests/unit/test_transport.py tests/unit/test_transport_realtcp.py tests/unit/test_vlm_router.py tests/integration/test_m2_visual.py -q --basetemp=/tmp/visionflow-m2-emergency-review-953d0e2/pytest`.
- Original `test_acceptance.py` with `pytest -p no:cacheprovider`, `-q` and owned basetemp.
- Independent `extended_probe.py`, `additional_probe.py`, `controls_probe.py`; the UI probe invokes `node /tmp/visionflow-m2-emergency-review-953d0e2/ui_roundtrip.js` to transpile/execute the actual frontend closures.
- `pytest -p no:cacheprovider tests/unit/test_dsl.py tests/unit/test_webhook_auth.py -q` with owned data/basetemp, and `test_extended_acceptance.py` with the same cache-disabled pytest settings.
- Scratch creation/copy, artifact hashing and report serialization through Python; final HEAD/full status/unstaged/staged diff verification.

## Results and evidence

- Independent focused suite: **129 passed**, 3 warnings, 8.10 s. Schema/webhook controls: **10 passed**, 0.25 s.
- Original grammar matrix: **240/240** valid supported drafts. Original executable acceptance: **4 passed**. These assertions cover the original examples, not full root-cause acceptance.
- Extended desired acceptance: **6 failed, 6 passed**. Failures cover competing states, actual active capacity, absolute admission deadline, configured TLS phase limit, malformed framing and UI decimal preservation. Their reproducible consequences are described below.
- Root receipts at `AE/checks-953d0e2` explicitly match this SHA: `make check` exit 0, 26.22 s, including 195 tests and frontend production build; `make smoke` exit 0, 6.43 s, real YOLO bus event with persisted evidence/notification. Inspected receipts/logs only; neither full build nor real YOLO was repeated. This supplied smoke does not establish unseen-jury-input or Teacher quality.
- Reproduction scripts, results, logs and SHA-256 manifest: [owned QA evidence](/tmp/visionflow-m2-emergency-review-953d0e2/manifest.json). [Extended failures](/tmp/visionflow-m2-emergency-review-953d0e2/extended-acceptance.log), [network results](/tmp/visionflow-m2-emergency-review-953d0e2/network-results.json), [extended results](/tmp/visionflow-m2-emergency-review-953d0e2/extended-results.json), [additional results](/tmp/visionflow-m2-emergency-review-953d0e2/additional-results.json).

## Original fault boundaries and adaptations

Copied immutable `grammar_probe.py`, `network_probe.py`, `test_acceptance.py` from `review-m2-review-2/.agents/review-evidence/A-25bccee/`. **Only the scratch output/data path changed** to this review's new directory; no callback/endpoint adaptation was necessary. Embedded historical target labels in original-script JSON were deliberately retained and are not current-SHA attribution; the fresh manifest/report supplies current attribution.

Original DNS/connect/admission delays and actual socket-send pause were preserved. The attempt-budget reproduction still uses three distinct 4 MiB inputs and an actual server reading its first 8,192 bytes while real `sendall` times out. It now sends once, charges one attempt and suppresses the next two. No mocked send replaced TCP backpressure. Extended framing travels through the real adapter/router/persisted event/notification path, not parser-only tests. New resolver-capacity checks extend the same getaddrinfo boundary and wait for helper termination; all four helpers eventually terminate. Frontend testing executes exact production closures with simulated setters/fetch, submits their output to the real API, and uses the production event engine; it does not claim full browser coverage.

All independent model/provider/detector stimuli are **QA_ONLY fixtures**. No genuine Teacher labels, trained Student, phone evidence, real activation, physical capture, GPU/provider calls, credentials, root experiment data, spend or publication were used. All created artifacts/data/report remain in the new owned `/tmp` directory. Source and `.agents` stayed read-only; no coding CLI, agent, code edit, commit, push or ref change occurred.

## Verified behaviors

- Original action-tail duration, hood+trunk, bare hood, multiple comparisons, unknown actions and ordinary negations reject; supported decimal compiler controls preserve values. Drafts validate, are created disabled and require a separate explicit Enable; no generated-code execution path found.
- **M2-004 fixed at its original real boundary:** one partially written POST consumes budget before transmission; subsequent inputs suppress. Actual raw preflight rejection uses zero attempts/connections and the next small input succeeds. Expired-before-write admission and revoked connection use zero attempts. Retry budget 1 sends once; real HTTP 503->200 with budget 2 sends twice.
- **M2-007 preserved:** disable during paused connection returns 200 with zero POSTs/attempts and cancelled action; disable during actual paused send blocks until that admitted write completes, then local action is cancelled with zero notifications. No new write starts after the tested disable acknowledgment.
- **M2-008 preserved:** all 12 malformed confidence cases, including bool/missing/string/NaN/infinity/range failures, cannot act; low confidence cannot act; numeric 0.9 and integer 1 controls each persist one notification.
- Header/body trickle stops around 200–202 ms against 200 ms overall and TCP closes before the next successful request. Original DNS/admission caller deadlines now return around 100–101 ms; DNS+TLS around 207 ms against 200 ms. Configured read limit 40 ms is honored. Refusal/socket/TLS timeouts become non-confirming results.
- Real TCP repeated input caches; changed ROI/task/model/configured prompt version each causes a new call. Concurrent identical inputs share one actual request. Focused tests exercise geometric zero-Teacher routing, sampling, cooldown, cache TTL/LRU, action dedup/recovery and visible unavailable/error outcomes.
- Arbitrary webhook DSL returns 422; legacy webhook tests prove rejection without DNS/network. Server configuration/token remain outside frontend contracts; synthetic-token public result/stat checks expose no token, endpoint or image marker. Source uses default TLS certificate verification. Actual authentication/private deployment is not inferred from fixtures or documentation.

## Findings
'''
for f in findings:
    report+=f"\n### {f['id']} — {f['severity']}\n\n- File and line: `{f['file_line']}`.\n- Reproduction: {f['reproduction']}\n- Expected behavior: {f['expected']}\n- Actual behavior: {f['actual']}\n- Minimal suggested fix: {f['fix']}\n"
report+='''
## Acceptance criteria

- **Passed portions:** M2-AC1 supported compile/schema/separate approval/no generated execution; M2-AC2 geometric zero-Teacher/candidate ROI routing; M2-AC3 confidence and normal failure visibility; M2-AC4 partial-write accounting/retries/cache/in-flight sharing/sampling/cooldown; M2-AC5 tested disable/write authorization, local action dedup and public metadata privacy.
- **Failed:** M2-AC1 complete intent rejection and exact editable-draft UI preservation; M2-AC3 malformed-response non-confirmation; M2-AC3a absolute/phase deadlines and actual concurrency bounds; M2-AC5 supported new-user decimal dwell semantics. Full M2 acceptance is not established by the original four green assertions.
- **Deferred/incomplete:** unchanged M2-009 P2 completed-result retention outside the bounded cache remains at `vlm_router.py:458` (source inspected; prior reproduction not rerun). UI exposes the attached predicate but lacks routing-setting editors. M2-EXP1 documents context-plus-ROI foveation; the full configurable strategy selector remains deferred, not accepted as implemented.
- **NOT TESTED / UNVERIFIED:** real Teacher image semantics, provider/model identity/authentication, private tunnel/authenticated TLS deployment, real GPU/Student operation, full browser/phone journey, unseen-jury-video end-to-end behavior, night/rain/local-vehicle quality, strategy gains, latency/accuracy/cost/savings experiments and final public deliverables. Fixtures and supplied YOLO smoke do not establish these claims. Original PDF comparison is unavailable.

## Final recommendation

**Fix blockers; do not accept this snapshot as M2 PASS.** Preserve the verified partial-write budget, disable serialization and strict confidence behavior. This is one completed fresh review and authorizes no further automatic correction/review cycle. Historical BLOCKED verdicts remain intact.

Final verification: `git rev-parse HEAD` = `953d0e275177951a71c4c8fccf6b915693e43550`; full porcelain status is empty; unstaged and staged `git diff --exit-code` both exit 0. Frozen HEAD and clean status preserved.
'''
result={'verdict':'CHANGES_REQUIRED','target_sha':'953d0e275177951a71c4c8fccf6b915693e43550','findings':findings,'report_markdown':report}
(p/'report.md').write_text(report)
(p/'review.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'verdict':result['verdict'],'findings':len(findings),'report':str(p/'report.md')}))
