# Independent validation — separate desktop demo

- Branch: `feature/demo-safe`.
- Base: `088b17aded860bd5d926600573184c883919d20e`.
- Exact tested handoff: `99e8670216a8aa9161cfb2517a2e5b4b955edd0b`.
- Application code: `7f3b5ebe459eab07dca68ee27b31f655cb3189cb`.
- Subsequent evidence/startup-document edits do not change application code.
- **M1 accepted; M2 BLOCKED; M3/M4 not started.** This is no new milestone
  verdict and does not repair or override the M2 review.

## Executed commands and results

From the repository root, on the exact handoff:

```sh
NEXT_PUBLIC_API_URL=http://127.0.0.1:8092 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 VISIONFLOW_DEMO_SAFE=true make check
NEXT_PUBLIC_API_URL=http://127.0.0.1:8092 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 VISIONFLOW_DEMO_SAFE=true make smoke
services/api/.venv/bin/python scripts/make_demo_safe_video.py data/demo/demo_bus_private_crop.mp4
DEMO_REUSE_BUILD=true services/api/.venv/bin/python .agents/runtime/demo/browser_servers.py
node .agents/runtime/demo/journey.mjs
node .agents/runtime/demo/final_capture.mjs
```

The ignored runtime harness started fresh, owned API/Next/HTTP-sentinel servers
on loopback ports 8092/3092/8093. It reused the successful exact-target production
build; it never ran the milestone controller. Published equivalents below use
configurable dependency paths and build their own frontend.
Committed command output only normalizes trailing whitespace/carriage returns;
[source-output hashes](raw-output-sha256.json) preserve its provenance.

| Check | Observed result | Evidence |
| --- | --- | --- |
| `make check` | Exit 0; structure check; **195 tests passed**, 4 warnings, 16.41s; Next production build/type/lint completed | [receipt](check-result.json), [output](full-checks.txt) |
| `make smoke` | Exit 0; real YOLO: 30 sampled / 180 decoded frames; mean inference **62.4ms**; bus entry at 4.2s; evidence JPEG + local notification | [receipt](smoke-result.json), [output](real-yolo-smoke.txt) |
| Production Chromium journey | Actual upload, polygon, disabled JSON draft, explicit approval, event/evidence/action, disable/re-arm, replay deduplication, edit → real dwell event | [journey](journey.json), [workspace](workspace-desktop.png), [evidence modal](evidence-desktop.png) |
| Demo boundaries | Unsupported compile visibly unavailable; visual create rejected; legacy visual row unavailable; zero configured Teacher HTTP calls, including a completed run with that row enabled | [egress](teacher-egress.json), [completed run](viewport-validation.json), demo-safe regression tests |
| Source transition | New source cannot inherit old-source approval, rules or events while responses are delayed | `journey.json` source-race probes |
| Desktop layout | No page-wide overflow at 1024/1280/1440px with actual video loaded | [viewport results](viewport-validation.json) |
| Phone layout | **Known P2:** loaded source at 390px expands page to 1011px | Same viewport results; use desktop >=1024px |

Hardware: Intel i5-11400H, 12 logical CPUs, CPU inference with thread counts 2;
Python 3.14.7, Ultralytics 8.4.175, Next 15.5.27, Chromium/Playwright Core 1.64.
The four test warnings concern deprecated application lifecycle APIs and an
intentional crash/recovery test. No temporary event-loop heartbeat workaround
was used. Historical M2 tests explicitly opt out of demo mode to retain their
original assertions; their passing suite does not supersede M2's failing review.

The cropped UI fixture is 180 frames, 30fps, 960x540: real bus pixels with
declared synthetic motion. Its first run produced entry at 4.2s, detector
confidence 0.9664, 30 analyzed frames, mean inference 68.89ms; the edited 1s dwell
rule produced an event at 5.2s. Both local actions completed exactly once in this
tested local replay; this is **not an external exactly-once guarantee**.
Detector confidence is not measured event accuracy. The historical smoke uses
a different whole-photo fixture; these timings are not a paired optimization
comparison. Fixture source, crop, version and hashes: [manifest](fixture-manifest.json).
Upstream attribution and unresolved subject rights: [licenses](../../../docs/LICENSES.md).

The browser's real journey makes no inference mocks. Negative checks deliberately
delay old/new source responses and simulate HTTP 503 and missing/false demo-safe
capabilities to check UI failure handling. The legacy Teacher record is seeded
only into the harness's fresh database. Zero Teacher requests demonstrate disabled
routing, **not measured savings**. An earlier phone probe passed while a newly
uploaded source was still loading; the final loaded-source probe exposes the P2
and takes precedence for phone readiness.

## Reproduce browser verification

Use the committed harnesses from this directory, from the repository root after
installing the README dependencies. Ports 8092, 3092 and 8093 must be free; the
harness refuses port conflicts rather than replacing another process. Chromium
is required (`CHROMIUM_PATH` can override `/usr/bin/chromium`).

```sh
services/api/.venv/bin/python scripts/make_demo_safe_video.py data/demo/demo_bus_private_crop.mp4
browser_deps=$(mktemp -d /tmp/visionflow-browser-deps.XXXX)
npm install --prefix "$browser_deps" --no-audit --no-fund playwright-core@1.64.0
export PLAYWRIGHT_MODULE="$browser_deps/node_modules/playwright-core/index.mjs"

# run in background; builds an isolated production frontend and uses fresh data
services/api/.venv/bin/python .agents/demo-evidence/99e8670/start_browser_servers.py &
demo_qa_pid=$!

# after startup; outputs default to .agents/runtime/demo/qa-reproduction/
node .agents/demo-evidence/99e8670/browser_journey.mjs
node .agents/demo-evidence/99e8670/viewport_probe.mjs

# stop only the owned QA process and its two child servers
kill "$demo_qa_pid"
wait "$demo_qa_pid"
```

The published scripts were syntax-checked; behavioral evidence comes from the
runtime versions executed above. Changes to the published scripts only make
dependency/output paths configurable and remove the controller-state dependency.
The viewport probe records the deferred phone defect without disguising it as a
phone pass. An optional `DEMO_QA_DIR` selects another ignored output directory.

## Working, disabled and unverified

**Working:** recorded MP4 selection/upload; polygon drawing/selection; explicit
enter/exit/dwell/count schema; server-canonical JSON; deliberate approval;
real sampled YOLO/ByteTrack geometric events; persistent evidence and local
notifications; editing through disabled replacement; disable and reviewed
re-enable. Entry and dwell ran through the actual browser; exit/count behavior
is covered by the existing engine tests, not a separate real-video browser run.

**Disabled in the demo:** natural-language compilation, Teacher-backed visual
actions, legacy visual workflow activation/editing, arbitrary webhooks; live
camera/RTSP unavailable. Unknown safe-mode flag values keep the guard on. The UI
blocks demo mutations when the API cannot prove safe mode.

**UNVERIFIED / planned:** real Teacher labeling, AutoLearn/Student, shadow
evaluation/rollback, full-frame/ROI/foveated quality comparisons, unseen natural
video accuracy/night/rain, GPU inference/rental costs/throughput, any savings,
public deployment and mobile readiness. No broad backend/integration work was
added. A jury-provided supported MP4 can be uploaded, but quality on their
unseen footage has not yet been measured. The official brief's public-hosting,
deck and recorded-backup requirements remain outside this local deliverable.

Original M2 state/report/handoff/algorithms and `feature/visionflow` remained
unchanged: [preservation receipt](preservation.json). The demo branch extends
history without rewriting it. [Startup and seven-minute script](../../../docs/DEMO_GUIDE.md).
