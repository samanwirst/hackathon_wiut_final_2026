# Private RTX3090 attempt — destroyed; local Teacher retained

The one authorized rental attempt was closed under the user's fail-closed
instruction. **No paid instance or associated storage remains**, and no
replacement rental is authorized. The local SmolVLM endpoint at
`127.0.0.1:18081` was not changed or interrupted.

The live account preflight established $5 in existing prepaid credit,
credit-only billing, and no saved payment method. No credit purchase, automatic
funding or billing setting change occurred. The earlier quoted offer had
disappeared; the fresh approved resource was Washington offer **51229946**,
a complete RTX3090 with 24,576 MiB and 60 GiB container storage, quoted at
$0.302222/hour including storage. Its six-hour/network allocation estimate
was $1.83807; this was never represented as a measured bill.

Instance **55296142** was created at **2026-10-10 22:55:22 UTC**. A separate
local watcher started immediately, and the instance-specific platform DELETE
schedule was confirmed through readback. However, the platform's `total_cost`
and bandwidth usage counters were null. The controller's planned 30 GiB
ingress/1 GiB egress allowance did not enforce all template, model and inference
traffic or guarantee the user's total $3 unattended cap. Therefore setup was
stopped and the instance was destroyed, rather than relying on the estimate or
on exhausting prepaid credit.

The API confirmed authoritative instance absence at **22:58:09 UTC**, followed
by additional absence checks. By **22:59:05 UTC**, the temporary account SSH
key and owned scheduled deletion job were also removed and confirmed absent.
The local watcher exited after observing authoritative absence. The owned
private SSH key was discarded; the user's ignored account credential file was
left unchanged. No personal SSH configuration or unrelated process was used.

At **22:59:29 UTC**, Vast's per-instance charges endpoint reported **$0.001**
for this exact contract, rounded to three decimal places: disk $0.001; GPU,
download and upload each $0.000 at that display precision. The latest account
credit at **22:59:50 UTC** was $4.99942113115, giving an observed account debit
of $0.00057886885. Account debit and provider rounded charge are different
measurements; a finalized invoice and possible later billing adjustment remain
**UNVERIFIED**. Neither measurement is an inference cost comparison.

Private SSH verification never completed. No inference token was uploaded, no
model asset download started, and no remote image inference ran. The rented
Qwen endpoint, RTX3090 compatibility, Teacher quality, GPU time, throughput and
baseline/optimized savings remain **UNVERIFIED**. Only the already executed
local SmolVLM evidence is available; its conditional candidate probabilities
remain uncalibrated and its observed strong `occupied` bias is disclosed.

Safe actual evidence: [outcome](../../../.agents/teacher-evidence/vast-rental-20261010/outcome.json),
[cleanup](../../../.agents/teacher-evidence/vast-rental-20261010/cleanup.json),
[provider charges](../../../.agents/teacher-evidence/vast-rental-20261010/billing.json).
Credentials, private keys, connection destinations and account identifiers are
excluded. This experiment does not change the accepted fallback, the M2
BLOCKED record or any Student activation gate.

Primary billing references:

- [Vast per-instance charge fields and rounding](https://docs.vast.ai/api-reference/billing/show-charges)
- [Vast storage and negative-balance billing](https://docs.vast.ai/guides/reference/billing)
