# Teacher GPU rental proposal — approval required

Historical proposal: the later single approved rental was destroyed under the
user's fail-closed budget requirement. See [actual rental outcome](RENTAL_OUTCOME.md).
No replacement rental is authorized; only the validated local Teacher remains.

Observed **2026-10-10 21:29 UTC** by a public read-only Vast.ai offer search.
No account was accessed, credits added, instance rented or charge incurred.
Offer availability and prices must be checked again immediately before purchase.
The verified `feature/demo-safe` fallback and M2 BLOCKED verdict are unchanged.

Preferred candidate: **offer 54465048**, Thailand, **one RTX 3090, 24576 MiB**,
`gpu_frac=1.0`, verified host, 31,927 MiB CPU RAM, driver 580.173.02,
reported CUDA compatibility 13.0, 420.2 Mbps download / 427.6 Mbps upload.
Reported reliability is 0.9836916; this is marketplace telemetry, not our
availability guarantee. Allocate **60 GiB** container storage. Do not substitute
an offer with fractional GPU allocation merely because its VRAM field says 24 GB.

| Component | Quoted rate | Six-hour estimate |
| --- | ---: | ---: |
| GPU | $0.1866667/hour | $1.12000 |
| 60 GiB storage | $0.0111111/hour | $0.06667 |
| Inbound model/container traffic, budget 25 GiB | $4/TB, API equivalent $0.00390625/GiB | $0.09766 |
| Outbound evidence, budget 1 GiB | same | $0.00391 |
| **Estimated allocation** | GPU + storage $0.1977778/hour | **$1.28823** |

The 25 GiB and 1 GiB quantities are planning limits, not measured transfer.
Taxes, exchange fees, minimum credit funding and stopped-instance storage are
excluded from this estimate. The API's hourly storage total is used directly;
do not add its monthly storage rate a second time. Actual invoice/transfer
records are required for eventual monetary comparison. No savings are claimed.

Requested authorization: **at most USD $3 total incremental rental/storage/
network charges**, one on-demand single-GPU instance, no automatic top-up,
no reserved commitment, no additional volumes. If the offer disappears, a
replacement must satisfy the same resource constraints and total cap; otherwise
ask again with a concrete proposal. Funding beyond $3 requires a new approval.
Configure any `VAST_API_KEY` only in an ignored project environment file; never
send a credential in chat. Account/key availability alone is not approval.

## Private setup and bounded stop

1. After approval, register only the operator's intended public SSH key and
   use a pinned vLLM image/version. Current upstream release observed today is
   `v0.31.0`; the official Docker Hub linux/amd64 image digest is
   `sha256:a4a4c0437bf7240089da5f08aa370c4aee17ae5290f7a3b468825ee26c4c3a6b`
   (compressed size 9,035,211,086 bytes). Its tagged Dockerfile uses CUDA 13.0.3,
   matching the candidate's reported CUDA 13.0 compatibility. Actual image
   startup/GPU compatibility still needs verification. Never use `latest`.
2. Candidate Teacher is `Qwen/Qwen2.5-VL-7B-Instruct`, Apache-2.0, pinned
   revision `cc594898137f460bfe9f0759e9844b3ce807cfb5`. Actual fit and performance
   on the 3090 remain **UNVERIFIED**. Cap context, images and concurrent sequences;
   full model's default context is inappropriate for a 24 GB hackathon instance.
3. Start inference on **remote `127.0.0.1:8000`**. Publish SSH only, never inference
   HTTP. Set an inference token out of source control even with the private tunnel.
   An API key is not protection for every vLLM administrative route.
4. Verify the instance SSH host key through the operator's trusted connection
   details. Forward `127.0.0.1:18080` locally to remote `127.0.0.1:8000` with
   `ExitOnForwardFailure=yes`. Do not disable host-key checking.
5. Validate real image inference and capture model revision, prompt, response,
   latency and usage before allowing isolated AutoLearn labeling. Teacher-backed
   workflow actions stay disabled. Human review is required before training.
6. Infrastructure work stops at **2026-10-10 23:25:35 UTC** if it has not produced
   real inference. Once authorized rental work ends, copy only required artifacts,
   then destroy the authorized experimental instance/storage to cease charges;
   stopping an instance alone continues storage billing. Confirm deletion and
   final billing. No unattended rental is left active past the approved window.

Safe offer evidence: [timestamped JSON](../../../.agents/teacher-evidence/vast-offers-20261010T2129Z.json).
Only public offer metadata is retained, with host IP addresses omitted.

Primary sources checked:

- [Vast pricing and continuous storage billing](https://docs.vast.ai/guides/instances/pricing)
- [Vast official CLI and public search implementation](https://github.com/vast-ai/vast-cli)
- [Vast SSH and port forwarding](https://docs.vast.ai/guides/instances/connect/ssh)
- [vLLM Qwen2.5-VL recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen2.5-VL.html)
- [vLLM releases](https://github.com/vllm-project/vllm/releases)
- [vLLM tagged Dockerfile](https://github.com/vllm-project/vllm/blob/v0.31.0/docker/Dockerfile)
- [Official vLLM Docker image tag](https://hub.docker.com/r/vllm/vllm-openai/tags?name=v0.31.0)
- [Qwen model and license](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct)

All remote inference, compatibility, actual cost and benchmark claims are
**UNVERIFIED until executed**. A separate no-charge SmolVLM-500M local GPU
experiment is being attempted while rental approval is pending.
