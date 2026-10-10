# Local GPU Teacher experiment

This is an isolated infrastructure harness, not an enabled workflow provider.
The verified fallback is unchanged. M2 remains BLOCKED unless its own exact
commit passes independent review. No experiment can trigger workflow actions.

Candidate: [HuggingFaceTB/SmolVLM-500M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct),
Apache-2.0, pinned revision `a7da5b986cb59b408707209984f360a5f4ad7e47`.
This is a real small image-capable model with unknown suitability for our tasks.
Its upstream results and memory claims are not VisionFlow measurements.

Keep the CUDA environment separate from the CPU API environment while M2 QA
and AutoLearn work proceed. Example preparation from this experimental worktree:

```sh
python3.12 -m venv .agents/runtime/local-teacher/.venv
mkdir -p .agents/runtime/local-teacher/tmp
TMPDIR="$PWD/.agents/runtime/local-teacher/tmp" \
  .agents/runtime/local-teacher/.venv/bin/python -m pip install \
  torch==2.7.1 torchvision==0.22.1 \
  --index-url https://download.pytorch.org/whl/cu118
.agents/runtime/local-teacher/.venv/bin/python -m pip install \
  transformers==4.51.3 accelerate==1.6.0 pillow==11.2.1 \
  fastapi==0.115.12 uvicorn==0.34.2 httpx==0.28.1
export HF_HOME="$PWD/.agents/runtime/local-teacher/hf-cache"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .agents/runtime/local-teacher/.venv/bin/python scripts/experiments/local_teacher.py
```

Use project-disk `TMPDIR` for the CUDA wheels; the host's small `/tmp` tmpfs
exhausted its quota during the initial probe. The completed pinned model
download can also be reused with `LOCAL_TEACHER_MODEL_DIR` pointing at a local
directory containing the downloaded files and a `source.json` identity/hash
manifest. The harness rejects a mismatched manifest or weights hash.

No credentials are required for the public model download. An optional
`LOCAL_TEACHER_TOKEN` is read only from an ignored environment file; the client
uses the same value without printing it. Even without a token, the server
**refuses a non-loopback listener** and non-loopback clients. Do not port-forward
it to the Internet or run it behind an unauthenticated public proxy.

Private experimental configuration, never an automatic workflow activation:

```dotenv
VLM_BASE_URL=http://127.0.0.1:18081/v1
VLM_MODEL=HuggingFaceTB/SmolVLM-500M-Instruct
VLM_API_KEY=
```

The harness accepts inline JPEG/PNG images only, at most two images, at most
2 MB request body, bounded image bytes/pixels, text length and generated tokens.
Image inputs are capped at 512 px longest edge. It runs one actual GPU worker
with no queue; busy admission returns HTTP 429. If a caller cancels/times out,
capacity remains occupied until the actual generation finishes. Generation
has a stopping deadline checked between tokens. This does not guarantee
interrupting a hung GPU driver/kernel; a stalled process must be stopped and
must never be assumed to have freed capacity. No retries are hidden.

Probe selected consent-safe inputs before integration:

```sh
.agents/runtime/local-teacher/.venv/bin/python scripts/experiments/smoke_local_teacher.py \
  data/selected/frame.jpg --output .agents/runtime/local-teacher/smoke.json
```

The smoke records actual raw response, strict JSON validation, generated-token
counts, wall/inference latency and GPU peak memory. Invalid content is retained
as a failed label; no fence stripping, label inference or invented confidence.
Model confidence is self-reported and uncalibrated. Teacher labels stay
**unverified** until a human explicitly approves/corrects them. Only verified
rows may enter the isolated Student training dataset.

Accuracy, generalization, local power costs, paid GPU costs and savings remain
**UNVERIFIED** until the corresponding paired/held-out experiments execute.
Zero rental expense for a local run is not zero total compute cost.
