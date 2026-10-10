# Approved private Teacher rental — not yet created

The user approved **one private RTX 3090 instance**, with a **hard USD $3 total
incremental rental, storage and network limit**, no automatic funding and
cleanup after use. This approval does not authorize extra instances, volumes,
credit purchases above the limit, public inference ports or Student activation.
The accepted demo fallback and M2 BLOCKED record are unchanged.

At **2026-10-10 22:04 UTC**, the ignored root project `.env` was absent. No
authenticated account request, SSH key registration, rental, payment or charge
had occurred. All remote inference and monetary results remain **UNVERIFIED**.
The already validated local SmolVLM Teacher remains unchanged.

## Updated candidate

The historical Thailand offer in `RENTAL_PROPOSAL.md` was no longer available
in the **2026-10-10 21:57:09 UTC** read-only search. The preferred replacement
is **offer 48483785**, Poland: one complete RTX 3090, `gpu_frac=1.0`,
24,576 MiB GPU memory, 64,139 MiB CPU RAM, driver 580.173.02 / reported CUDA
13.0, 928.2 Mbps download / 302.9 Mbps upload, and 412 GB available disk.
These are marketplace reports; actual startup compatibility is unverified.

| Component | Quoted rate | Planning quantity | Estimate |
| --- | ---: | ---: | ---: |
| GPU | $0.240000/hour | six hours | $1.44000 |
| 60 GiB container storage | $0.0222222/hour | six hours | $0.13333 |
| Ingress | $0.0026041667/GiB | 30 GiB | $0.07813 |
| Egress | $0.00390625/GiB | 1 GiB | $0.00391 |
| **Total estimated allocation** | **$0.2622222/hour with storage** | | **$1.65536** |

This estimate is **not an invoice or a measured cost**. It leaves a reserve
under the approved $3 limit. Availability and all rates must be checked again
immediately before the single creation attempt. No fractional GPU substitution
is permitted. Stop if required funding exceeds $3 or the replacement estimate
exceeds the conservative $2 planning envelope.

## Account and resource guards

Read `VAST_API_KEY` only from the ignored project `.env`, never from chat,
personal configuration, shell tracing or command-line arguments. A read-only
account preflight retains only funding and autobilling fields. It must establish
at least $3 existing prepaid credit and either credit-only billing or an explicit
zero automatic funding threshold; unknown or enabled funding blocks creation.
No billing setting, saved card, account funding or other user's resource is
changed by this workstream.

The runtime controller records a durable creation-attempt marker before the
one `PUT /asks/{offer_id}/`. It never blindly retries creation after a timeout.
Any uncertain response must be resolved by the unique owned label before
further mutations. No second rental is authorized even if the first fails to
boot. The official immutable vLLM image, pinned Qwen revision and inference
limits are specified in `RENTAL_PROPOSAL.md` and `start_remote_teacher.sh`.

Immediately after an owned instance ID is received, a separate local watcher
starts. Before setup continues, the controller must create and read back an
instance-specific platform DELETE schedule. If this independent cleanup cannot
be confirmed, it destroys the owned instance and confirms authoritative
absence. The schedule's actual support remains **UNVERIFIED until tested**;
a submitted request alone is insufficient evidence.

The local watcher checks only the owned instance and whitelisted prepaid
funding fields. It destroys the instance at six hours; at **2026-10-10 23:25:35
UTC** if real inference is still unverified; when the conservative $2 planning
envelope is reached; when account debit reaches $1.80 or prepaid credit falls
below $1.20; or after three failed monitoring requests. Account debit may include
unrelated usage and is treated conservatively, never reported as this rental's
measured cost. Cleanup keeps retrying until authoritative absence is established.

Limit download to the pinned image and model assets, avoid package builds and
large logs, and copy only bounded evidence. Inspect actual network usage and
the instance-specific charge records during use. **Credit exhaustion is not a
spend cap**: Vast documents continued storage billing and possible saved-card
negative-balance charges. Confirm destruction, temporary SSH key removal, and
final charge records; stopping alone does not satisfy cleanup.

## Private connection

An ephemeral project-local Ed25519 key is created specifically for this one
instance. No personal SSH keys or configuration are read. Its public fingerprint
is `SHA256:tn+pG+h/tjSVKf9xm0zM/mMHJofh47ilZH3jM4NIOjM`.

Publish **SSH only**. The creation `onstart` emits the public SSH host key into
an owned-instance log marker. Retrieve that marker through the authenticated
Vast control plane, verify its key format, and pin it in project-local
`known_hosts`. Do not use unverified `ssh-keyscan` output or disable strict host
key checking. Use `ssh -F /dev/null` with the explicitly owned key,
`IdentitiesOnly=yes`, `IdentityAgent=none`, `StrictHostKeyChecking=yes` and
`ExitOnForwardFailure=yes`.

Bind remote vLLM only to `127.0.0.1:8000`; create the local forward on
`127.0.0.1:18080`. Generate an inference token privately and transfer it only
through verified SSH. Keep account API credentials entirely off the rented
machine. No inference port is mapped to the public Internet.

The remote endpoint becomes available only after private authenticated image
inference succeeds with a real selected image. Preserve actual responses,
strict schema failures, pinned model identity, input SHA, wall latency, token
usage and GPU memory; do not repair failed labels or invent confidence.
Teacher-backed workflow actions remain disabled. Human verification gates any
Teacher labels before Student training; manual Student activation remains
separate.

## Primary sources

- [Vast billing and negative balances](https://docs.vast.ai/guides/reference/billing)
- [Vast instance creation](https://docs.vast.ai/api-reference/instances/create-instance)
- [Vast official CLI: scheduled jobs, SSH and instance destruction](https://github.com/vast-ai/vast-cli/blob/master/vast.py)
- [Vast SSH connections](https://docs.vast.ai/guides/instances/connect/ssh)
- [vLLM environment variables](https://docs.vllm.ai/en/latest/configuration/env_vars/)
- [Pinned vLLM Dockerfile](https://github.com/vllm-project/vllm/blob/v0.31.0/docker/Dockerfile)
- [Qwen2.5-VL recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen2.5-VL.html)

Safe public quote evidence: [updated offers](../../../.agents/teacher-evidence/vast-offers-20261010T2157Z.json).
Account identifiers, connection details, credentials and private keys stay in
ignored runtime files. No remote Teacher quality, latency, billed cost, GPU time
or savings has been measured yet.
