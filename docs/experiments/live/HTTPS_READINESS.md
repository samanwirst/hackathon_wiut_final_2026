# LIVE public HTTPS and WebSocket readiness — deployment pending

Preparation only: **no tunnel, public endpoint, camera capture, new process or
application edit was made**. Root must first confirm an independent security
**PASS for the exact LIVE implementation commit** and identify its reviewed
public routes. Publication is owner-authorized only after that gate. The
existing fallback, M2/M3 verdicts and private local Teacher remain unchanged.

## Available plumbing

Observed **2026-10-11 03:33 UTC**: `/usr/bin/cloudflared` is version **2026.9.3**;
`node` and `curl` are available; Caddy and nginx are absent. Help confirms
explicit config, URL, metrics, PID file, no-autoupdate, loglevel and grace-period
options. The following ports were free at the check; recheck before starting.

| Process | Proposed bind | Exposure |
| --- | --- | --- |
| Reviewed public gateway / single LIVE entry | `127.0.0.1:19100` | Only tunnel target |
| LIVE web, if separate from entry | `127.0.0.1:19101` | Local only |
| Restricted LIVE API, if separate | `127.0.0.1:19102` | Local only |
| cloudflared metrics | `127.0.0.1:19103` | Local only |

Avoid existing ports 18088, 18085, 13085, 8001 and 3000. Prefer the reviewed
LIVE app serving its UI and APIs through one same-origin entry if supported;
do not introduce an unreviewed custom proxy merely to use all three ports.
If the app separates web/API, root must provide a reviewed route gateway.

Cloudflare Quick Tunnels supply a temporary HTTPS hostname without a domain or
account. They have no uptime guarantee, change hostname on restart, allow 200
in-flight requests and do not support SSE. They are a hackathon deployment
option, not evidence of production availability. No VPS, paid service, account
login, DNS mutation or rental is needed for this proposed path.
[Official Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

After root's exact-commit PASS, the intended command is the installed binary's
`tunnel` operation with **only** `--url http://127.0.0.1:19100`, explicit
project-local configuration, `--no-autoupdate`, `--metrics 127.0.0.1:19103`,
an owned runtime PID file and `--loglevel info`. Do not enable debug/trace
logging, diagnostics exposure, account login or a named billed service. Use a
sanitized subprocess environment without the app's PIN/session/provider
secrets, and project-local config rather than personal tunnel configuration.
This exact config/launch remains **UNEXECUTED** until root supplies the reviewed
origin and security PASS. Only owned PIDs may be stopped during cleanup.

## Public route boundary

The route manifest must come from the exact reviewed LIVE app, not assumptions
about its current implementation. Public entry pages may disclose the two
roles and login UI. Review and allow only the implemented static asset paths,
role login/logout/status, room create/join, bounded frame ingest/WebSocket,
room-scoped viewer/evidence, and approved task control routes. Dynamic room IDs
must match an exact bounded format; unknown or malformed paths default to 404.
Changing or encoded path variants must not escape the allowlist.

Never point the tunnel at the old full API/frontend or broadly proxy `/api`,
`/media`, uploads, docs/OpenAPI, filesystem evidence, `/v1`, metrics, internal
Teacher, arbitrary upstreams or arbitrary requested paths. Route gating is
additional to server-side role/room authorization. A public evidence route
must remain tied to the authenticated room and return private, noncached data.
Check application bundles for secrets and blocked-feature claims before launch.

## Dynamic HTTPS origin and sessions

Create the tunnel while the reviewed app remains fail-closed for live APIs.
Extract its one HTTPS hostname from owned runtime logs, validate the hostname,
and have root set the isolated app's **exact public origin and allowed Host**.
Do not accept all `trycloudflare.com` hosts, reflect arbitrary Origin, or use
credentialed wildcard CORS. Same-origin relative HTTP and `wss://` URLs avoid
mixed-content failures; public clients must never call workstation localhost.
If root must restart the app to apply its reviewed configuration, start physical
streaming only after that restart and repeat its health/auth gates.

Before WebSocket upgrade, check the exact browser Origin, valid short-lived
server-side session, role and room membership. Missing/foreign Origin must
fail closed for this browser-only demo. A forged Origin alone cannot authenticate
a nonbrowser client. A Judges session must not ingest camera frames or mutate
another room. Session expiry/logout must terminate or deny continued protected
streaming according to the reviewed contract. Never put PIN/session credentials
in URLs or record cookie/token values in evidence.
[Browser WebSocket handshake and Origin guidance](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers).

Use Secure, HttpOnly, short-lived cookies under the reviewed session contract;
trust proxy scheme/client headers only through the defined loopback gateway
chain. Confirm login rate limiting survives the proxy's shared connection
address and cannot be bypassed by attacker-supplied forwarding headers. The
same shared demo PIN does not by itself grant a private camera room to every
authenticated visitor; a separate room identifier/role check is necessary.

Cloudflare supports WebSockets but can interrupt them during network updates
or idle periods. Verify bounded heartbeat/reconnect and queue limits in the
reviewed app, and preserve actual reconnect evidence. Cloudflare's initial
handshake security does not validate subsequent application frames.
[Official Cloudflare WebSocket behavior](https://developers.cloudflare.com/network/websockets/).

## Checks after root authorizes launch

1. Record clean exact deployment SHA, build evidence, independent review SHA,
   UTC, only-owned PIDs, binds and public HTTPS origin. Confirm frontend/backend
   are this commit and old API/Teacher ports remain private.
2. From the public URL, verify valid TLS without disabling certificate checks;
   HTTPS entry, two role choices, no secret in HTML/bundle; `isSecureContext`
   true and `navigator.mediaDevices.getUserMedia` available on the phone.
   Browser camera permission still requires a deliberate user grant.
3. Attempt every protected HTTP and WSS route without a session, with an expired
   session, the wrong role, a different room, missing/foreign Origin and spoofed
   forwarding headers. They must reject before protected data or state changes.
   Confirm unknown and legacy media/API/Teacher paths are unavailable.
4. Use authenticated same-origin WSS: establish the real upgrade, send a bounded
   consenting camera frame, observe its timestamp at Judges, and inspect actual
   backend processing evidence. Try oversized/invalid payloads and a brief
   connection interruption; queues stay bounded and status becomes honest.
5. Owner-confirmed **two physical devices**: phone A starts consenting live
   camera, then stays on its stand; device B preferably uses another network,
   joins the private room, proposes a novel automotive task, inspects/approves
   its DSL and sees real execution/evidence. Replace/disable the task from B
   without touching A. Record actual frame FPS, frame/event wall latency and
   bounded queue/drop behavior, with measurement boundaries and clock caveats.
6. Capture one approved privacy-safe live-phone frame and make genuine local
   Teacher inference through the accepted provider path. Preserve source frame
   SHA/timestamp, request/response and server log; keep errors or false positives
   visible. This live-camera evidence has **not** been collected by this plan.
7. Test a temporal request with genuine before/after context, unsupported intent,
   task replacement, deduplication, pause/re-enable and reconnect. Report missed
   events as failures. Never label browser automation or fake camera output as
   a physical two-device test.

The Media Capture specification marks the API as SecureContext; HTTPS plus
permission is required for this remote phone scenario. Screen Wake Lock may be
released when the page is hidden; do not claim it keeps a locked/backgrounded
phone streaming. Test the actual phone and keep it foregrounded on power.
[Media Capture specification](https://w3c.github.io/mediacapture-main/),
[Screen Wake Lock specification](https://w3c.github.io/screen-wake-lock/).

Keep raw credentials, room join material, unconsented footage and detailed
headers in ignored runtime storage. Commit only sanitized evidence and exact
commands without secret values. External HTTPS/WSS, physical-device behavior,
live-phone Teacher inference and uptime remain **UNVERIFIED until executed**.
Hard code freeze is **07:42:00 UTC**; submission is **08:12:00 UTC**. After
freeze, deployment may use only the exact frozen submitted commit.
