# Executed AutoLearn pilot — synthetic-occupancy-v1

Experimental snapshot: `5938b6d1f1396c1513d52ee9d9c3cdb377dc43a4`.
This is an execution record, **not M3 acceptance or permission to activate**.
Independent QA returned CHANGES_REQUIRED. The final bounded correction at
ff48ca9 also failed independent QA with six P1s; neither snapshot is accepted
or integrated. Historical M2 remains BLOCKED; Teacher-backed
workflow actions stay disabled. Active model is null; shadow actions are `none`.

## Inputs and protocol

The human inspected the exact 24-image review sheet and confirmed every displayed
occupied/empty label. That approval applies only to those image hashes. They are
original procedural drawings: 12 rendering sessions, two images per session,
with a shared generator. Teacher proposed occupied for all 24; human verification
corrected 12 labels. This does not establish natural-video performance.

Before the first Student fit, physical source/session grouping replaced caller
keys. The preregistered amendment preserves the old split hash and explains the
changed membership; it was not selected using Student outcomes. Final partition:
14 train / 4 validation / 6 test; test has three occupied and three empty images
from sessions 06, 07 and 11. Dataset and split hashes are in the JSON records.
The two classes are balanced in every partition. Raw images/weights are ignored
and are not committed with this evidence.

## Actually executed

Frozen pretrained ResNet18 (IMAGENET1K_V1) produces 512-dimensional embeddings.
A logistic Student head was genuinely fitted; threshold 0.5 was chosen using
validation only. Fit took 141.741 ms; the whole training API call took 3.033 s.
The saved artifact was reloaded and evaluated against immutable test membership.
Its SHA256 is `72541bb2b6fa8790610169ad1087128a9ae8c28501221ff878438480d401bcb2`.
Held-out confusion: Student TP3/TN3/FP0/FN0; Teacher TP3/TN0/FP3/FN0.
Shadow comparison found 3 disagreements across 6 images, zero actions.
Actual browser rendering showed the trained version and executed the shadow
request without JavaScript errors; it never pressed Activate.

## Paired measurement

Exactly the same six input hashes were used by both paths. One warm-up per path
was excluded; three alternating-order serial rounds produced 18 timing
observations. **Quality support is six unique images**, not eighteen.

| Measurement | Private local Teacher | Frozen encoder + Student |
| --- | ---: | ---: |
| Correct on six unique held-out inputs | 3/6 | 6/6 |
| Precision / recall / F1 | 0.5 / 1.0 / 0.6667 | 1.0 / 1.0 / 1.0 |
| Mean wall latency | 432.792 ms | 40.189 ms |
| p50 / p95 wall latency | 432.565 / 441.543 ms | 40.055 / 45.009 ms |
| Serial predictions/second | 2.311 | 24.883 |
| Actual Teacher HTTP requests, excluding warm-up | 18 | 0 |
| Actual GPU model forwards, excluding warm-up | 36 | 0 |
| Actual CPU frozen encoder + Student forwards | 0 | 18 + 18 |

Teacher was pinned SmolVLM-500M-Instruct on RTX3050 Laptop 4GiB. It scored the
image-conditioned likelihood of two candidate labels, using two actual model
forwards per request, then serialized those scores as JSON. It **did not generate
valid JSON labels**; its attempted generated-JSON path had failed and is recorded
separately. Scores/probabilities are uncalibrated. Raw method, revision, token
counts and candidate likelihoods are retained in paired measurement JSON.

Student ran on Intel i5-11400H CPU with two threads, including image decoding,
actual frozen-encoder inference and the head. Cold encoder/artifact load was
2409.686 ms; timed runs were warm. Both used a shared host with concurrent
workloads. HTTP wall latency includes transport/provider/preprocessing;
CUDA kernel time was not measured. Throughput is serial 1000/mean_ms,
not a saturation/load-test capacity claim.

## Limits and remaining gates

- Natural footage, unseen camera/weather/vehicle quality: **UNVERIFIED**.
- Full-frame vs ROI vs foveated accuracy/token/cost improvements: **UNVERIFIED**.
- Vast rental results/cost, GPU kernel time, electricity/depreciation, total
  cost per event and savings: **UNVERIFIED in this local pilot**.
- M2/M3 acceptance, real-model activation and rollback: not established by this
  experiment. No automatic workflow action or model activation was performed.
- Browser mobile layout at 390px still overflowed to 497px; desktop passed.

The executed API steps were `POST /api/autolearn/tasks/1/train`,
`POST /api/autolearn/versions/1/evaluate`, `GET /api/autolearn/tasks/1/shadow`,
and `GET /api/autolearn/versions/1/gate`. The paired measurement runner verified
version membership/image hashes and used the same held-out images for both paths.
Safe JSON records and their hashes accompany this report. Local runtime paths
and private raw datasets are deliberately outside the committed release.

## Separate local GPU kernel measurement

A separate process loaded the same pinned Teacher and profiled the same six
held-out image hashes using PyTorch CPU/CUDA activity collection. Warm-up was
excluded. Each measured image executed two actual candidate forward passes;
14 total model forwards included warm-up, with zero HTTP requests or actions.
Mean sum of CUDA kernel durations was **86.388 ms per image**. Kernel counts,
per-image durations, copied raw model replies and trace hashes are recorded in
`separate-gpu-kernel-profile.json`; grouped kernel/copy durations are in
`gpu-kernel-aggregates.json`. Complete Chrome traces remain ignored locally.

This is a separate direct-model profiling experiment with profiler overhead,
not GPU timing from the earlier HTTP benchmark. Aggregate kernel duration is
not allocation time, rental billing time or energy; overlapping kernel durations
can differ from elapsed wall time. The original HTTP latency record is unchanged.
Vast GPU inference and kernel time remain UNVERIFIED; no rental cost per event
is inferred. PyTorch's [profiler documentation](https://docs.pytorch.org/docs/2.14/profiler.html)
describes CPU/CUDA activity collection. Actual profiler runtime was Torch2.7.1+cu118.

## Reproduced input bytes

The archived QA generator reproduced **all 24 approved image SHA256s and the
exact review-sheet SHA256** in a fresh owned directory. `input-reproduction.json`
records Python/Pillow versions, the resolved font hash and generator hash.
Run from the delivery repository with an empty output directory:

```sh
services/api/.venv/bin/python scripts/experiments/generate_synthetic_occupancy.py \
  --out /tmp/visionflow-occupancy-reproduction \
  --font /usr/share/fonts/TTF/DejaVuSans.ttf
```

The executed environment used Pillow 12.3.0. On another system, pass the same
DejaVu font bytes and compare outputs against `human-groundtruth-approval.json`.
Regenerated manifest paths differ, so its manifest hash is not the original
approval hash. The generator leaves `human_verified` false and emits proposed
labels/splits; the actual training split is the preregistered amendment above.
This reproduction performs no Teacher inference, training or activation.
