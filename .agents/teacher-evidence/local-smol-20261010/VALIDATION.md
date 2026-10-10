# Private local Teacher validation — experimental

- Frozen harness: `3bbd19c` on `experiment/teacher-ten-hour`.
- Earlier raw-generation harness: `7a936cd`.
- Device: NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB VRAM.
- Isolated environment: Python3.12, Torch2.7.1+cu118, CUDA11.8 runtime,
  Transformers4.51.3. The shared CPU API environment was unchanged.
- Model: `HuggingFaceTB/SmolVLM-500M-Instruct`, Apache-2.0, pinned revision
  `a7da5b986cb59b408707209984f360a5f4ad7e47`; weights SHA256 recorded in
  [model-source.json](model-source.json).
- Private listener: only `127.0.0.1:18081`, independently observed with `ss`;
  [listener.txt](listener.txt). No rental, paid endpoint or public service.
- Teacher workflow actions: disabled. M2 remains BLOCKED. No M3 PASS asserted.

## Executed checks and measured results

1. `pip check`: no broken requirements. A genuine CUDA tensor operation passed;
   `torch.cuda.is_available()` was true on the identified GPU.
2. Raw generation: **0/4 strict JSON successes**. Actual content is preserved in
   [synthetic smoke](generative-service-bay.json) and
   [decoded-video smoke](generative-selected-video.json). No output was repaired
   or turned into a positive verified label. Video frames were decoded at
   4.2 and5.2 seconds from the already accepted bus-only demo clip; provenance
   and hashes are in [selected-video-manifest.json](selected-video-manifest.json).
   Its source photo pixels are real, its left/right motion synthetic. This is
   inference proof, not unseen natural-video quality evaluation.
3. Separately configured conditional classification: **2/2 schema-valid**
   responses, fixed labels `occupied/empty`. Both predicted occupied; the second
   prepared image is designated empty and needs human inspection/correction.
   Initial model-call wall times1.2300s and0.1213s; measured harness inference
   times1.2157s and0.1189s. Scoring-mode model load1.7302s; GPU peak allocated
   1,064,910,848 bytes, peak reserved1,086,324,736 bytes. See
   [actual scores and responses](candidate-scoring-smoke.json).
4. **12/12 actual boundary probes passed**: invalid token bounds/types, unknown
   model, unsupported streaming, external image fetching, bad image bytes,
   three-image and2MB body limits, actual in-flight cancellation and admission.
   Cancelling an already admitted HTTP client retained that exact actual GPU
   request and returned429 to another caller; the slot was restored after the
   actual worker finished. See [boundary-probes.json](boundary-probes.json).

For conditional classification, each complete candidate plus closing quote is
scored using one genuine image-conditioned model forward pass. Binary requests
use **two forwards**, with raw token IDs/log likelihoods recorded. Normalized
candidate probabilities supply uncalibrated confidence; generated JSON token
count is zero. Serialization of measured scores is disclosed as a distinct
method. No generation success, calibration or accuracy is inferred from schema.

## Exact commands

Executed from the B worktree. `RT` below names only this experiment's ignored
runtime directory, never a system environment variable. CUDA wheel staging was
moved to project-disk TMPDIR after the small `/tmp` tmpfs quota stopped the
initial download. No unrelated files/processes were deleted.

```sh
RT="$PWD/.agents/runtime/local-teacher"
python3.12 -m venv "$RT/.venv"
mkdir -p "$RT/tmp"
TMPDIR="$RT/tmp" PIP_DEFAULT_TIMEOUT=90 "$RT/.venv/bin/python" -m pip install \
  torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu118
"$RT/.venv/bin/python" -m pip check
```

Additional library installation used the exact pinned packages in
[requirements.lock.txt](requirements.lock.txt). The pinned public checkpoint
was downloaded without an account/token to an ignored directory and its weight
hash checked before direct bf16 GPU loading. Server preparation used:

```sh
HF_HOME="$RT/hf-cache" LOCAL_TEACHER_MODEL_DIR="$RT/cache/pinned-smolvlm" \
  LOCAL_TEACHER_SCORING_LABELS=occupied,empty \
  OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  "$RT/.venv/bin/python" scripts/experiments/local_teacher.py
```

Raw-generation probes ran the same harness before scoring mode was enabled.
The actual selected-frame and binary classification checks were:

```sh
"$RT/.venv/bin/python" scripts/experiments/smoke_local_teacher.py \
  "$RT/smoke-images/video_frame_126.jpg" "$RT/smoke-images/video_frame_156.jpg" \
  --output "$RT/selected-video-smoke.json"
"$RT/.venv/bin/python" scripts/experiments/smoke_local_teacher.py \
  /home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/dataset/s00-f00.png \
  /home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/dataset/s00-f01.png \
  --question 'Is a vehicle present inside the marked service bay?' \
  --labels occupied,empty --output "$RT/candidate-scoring-smoke.json"
"$RT/.venv/bin/python" scripts/experiments/probe_local_teacher_boundaries.py \
  "$RT/smoke-images/video_frame_126.jpg" --output "$RT/boundaries.json"
ss -ltnp '( sport = :18081 )'
```

The first raw synthetic smoke also allowed unknown and preserved its invalid
output. That is not coerced into the accepted binary schema.

## Limits and unexecuted capabilities

Every Teacher proposal is **pending human verification**. Initial confidence
was high even for a suspected false positive. Natural-video accuracy, Student
quality, foveated improvements, actual GPU kernel time, local energy expense,
Vast rental charges and savings remain **UNVERIFIED**. HTTP wall latency and
GPU peak memory are measured; they cannot establish these other claims.

Raw images, model weights, credentials, private user configuration, execution
logs and agent logs are excluded from this evidence commit.
