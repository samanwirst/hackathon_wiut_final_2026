# Private deployment candidate — executed validation

Application matches the accepted fallback (`7f3b5eb` / tested handoff
`99e8670216a8aa9161cfb2517a2e5b4b955edd0b`). Delivery source is `749d27b`:
deployment infrastructure and isolated Teacher scripts were added; no accepted
application source changed. This is not a M2, M3 or public M4 PASS verdict.

Commands executed:

```text
docker compose -f deploy/compose.yaml config --quiet
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml -f deploy/compose.gateway.yaml build
docker compose -f deploy/compose.yaml -f deploy/compose.gateway.yaml build api
docker compose -f deploy/compose.yaml -f deploy/compose.gateway.yaml up -d
services/api/.venv/bin/python .agents/runtime/ten-hour/delivery/container/check_running.py
node .agents/runtime/ten-hour/delivery/public-candidate/browser-check.mjs
```

Builds completed. The first cold inference failed because the tracking `lap`
dependency was absent: it is now explicitly pinned to the observed native
version `0.5.13` and installed at image build. Rebuilt unprivileged API completed
real YOLO inference: **30 sampled frames**, mean **71.18ms** inference on the
local CPU, a genuine bus-entry event, accessible JPEG evidence, one successful
local action and one notification. The photographic motion fixture is synthetic
motion, not a natural-camera quality benchmark. Safe evidence includes actual
input/evidence hashes and responses.

API and frontend run as unprivileged users; persistent data/model cache are
separate volumes. Host listeners bind only to `127.0.0.1` (API18085/web13085,
gateway18088). The authenticated gateway rejected anonymous requests to frontend,
API and media with401, while authorized frontend/API succeeded. Chromium rendered
the actual zone/rule builder through the same-origin gateway with no JavaScript
errors. Password and hash were never copied into evidence or committed.

The initial host port8080 was occupied by an unrelated container. No unrelated
container was stopped; dedicated unused ports were selected. All cleanup operates
only on the `visionflow-private-demo` compose project and preserves its volumes.

The recorded browser fallback executed upload, polygon drawing, exact JSON draft
review/approval, real entry/dwell events, evidence, notification deduplication,
edit/disable/re-enable. It contains20.96seconds of actual browser capture. The
recording is under `docs/presentation/VisionFlow-fallback-demo.mp4`; it is not a
mock UI and has no fabricated inference.

## Remaining limits

- Public TLS hosting/tunneling has not been started; it needs approval of the
  concrete reviewed release. Judges' external reachability remains UNVERIFIED.
- AutoLearn has not been integrated into this candidate; exact-commit QA pending.
- Natural-video accuracy, weather/local-vehicle robustness, billed GPU costs,
  GPU kernel activity and savings remain UNVERIFIED.
- `npm audit` reports one high PostCSS issue and one moderate transitive Next
  issue. The upstream [PostCSS advisory](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q)
  requires attacker-controlled CSS processed by PostCSS. This product accepts
  video/image inputs and builds only trusted repository CSS; no user CSS processing
  path was found. This is a documented P2 dependency risk, not an executed exploit
  against the application. A forced major framework upgrade is deferred.
- Actual installed Python dependencies and image IDs/digests are preserved;
  repository deployment locks pin the build dependencies and CPU wheels.
