# M3 BLOCKED — unaccepted, nonactioning synthetic pilot

**M3 remains BLOCKED / CHANGES_REQUIRED at `0c877e227062af7d3def121490419be158cb16c4`.** This single owner-authorized private experiment does not accept M3, reopen its six P1 findings, integrate its application, or activate a Student. QA report commit: `c912cb76964ee4a4be56f55bc7c20fb8b6dd17ca`. No application source was changed.

On 2026-10-11, the unchanged application performed one fresh 24-image Teacher labeling job, applied the owner's existing exact-hash ground-truth approval, trained a new Student, reloaded its archive for held-out evaluation, and ran nonactioning shadow comparison. The inputs are **original procedural synthetic drawings**, 12 sessions with two images each. They are not natural videos. The earlier pilot's metrics and archive were not reused.

| Same six held-out synthetic images | TP | FP | FN | TN | F1 | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Real local Teacher | 3 | 3 | 0 | 0 | 0.6667 | 0.5 |
| Fresh, independently reloaded Student | 3 | 0 | 0 | 3 | 1.0 | 1.0 |

The Teacher predicted **occupied for all 24 images**, including all 12 owner-verified empty images. Those 12 human corrections supplied the training ground truth; Teacher confidence was not treated as verification. The six-image Student result is evidence of this small synthetic experiment, not natural-world model quality or successful milestone acceptance. The independent natural-image Teacher false positive in [NATURAL_IMAGE_EMERGENCY.md](NATURAL_IMAGE_EMERGENCY.md) remains unchanged; that request was not repeated.

## Actual model work and timing

The preserved private Teacher is `HuggingFaceTB/SmolVLM-500M-Instruct`, pinned revision `a7da5b986cb59b408707209984f360a5f4ad7e47`, NVIDIA RTX 3050 Laptop GPU, BF16 configured by the unchanged harness. It performed **24 genuine image-conditioned requests, 48 model forwards, 7,392 processed model tokens**, with zero retries, cache hits, failures, or additional labeling jobs. The labeling HTTP wall time was 4,499.357 ms; the sum of harness-measured inference intervals was 3.867018 s. These are wall intervals, not CUDA kernel execution time or billed GPU time.

The output method is **candidate sequence likelihood scoring**: `s(label) = Σ log P(candidate token | image, prompt, preceding candidate tokens)`; probabilities are `softmax(s(occupied), s(empty))`. Two real forwards score candidate token sequences `[27450, 18]` and `[16451, 18]`. The server serializes the selected label and score into JSON. It does **not** successfully generate that JSON, and its probability is **uncalibrated**. Historical attempted free generation failed the structured JSON contract, as disclosed in [LOCAL_SETUP.md](LOCAL_SETUP.md). No model, prompt tuning, or provider implementation was changed for this pilot.

The Student is real 512-dimensional logistic regression trained on frozen pretrained ResNet18/ImageNet1K_V1 embeddings, CPU with two threads. Fresh fit duration was 96.668 ms; training API wall time was 1,974.637 ms. Reloaded held-out evaluation API wall time was 162.261 ms; its reported per-image encoder intervals were p50 24.502 ms / p95 25.506 ms. These intervals cover different components and are **not** an identical-video baseline/optimized cost comparison. No percentage savings is claimed.

## Independent checks

- Production preregistration preceded the first fit: 14 train / 4 validation / 6 test images, 7 / 2 / 3 disjoint sessions, balanced classes in each split. All 24 actual bytes, owner-approved labels, session membership, and persisted version membership matched before and after fitting. No alternate split was selected.
- Dataset hash: `3a83ca9c28de3115a9d932c4d7731fb708f63f4f73bd6bd3adf88085104a8e77`; split hash: `b338f78465b9245ef8fde6a6f12f0a28cb45fba8ec37a781beb2523dfedf741a`.
- Fresh Student archive SHA-256: `ea6b63ebb16ec05ca9d6ee6bc7232d8fedfd04ff70dd69f6658a5515023049b9`. Artifact, registry, and evaluated thresholds all remained **0.5**. Class order `[empty, occupied]` and class mapping `{empty: 0, occupied: 1}` matched for this specific task. This does not resolve the blocked class-order defect for other labels.
- Encoder checkpoint SHA-256 before and after fit: `f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec`. The independently loaded encoder was frozen/eval; its state hash stayed unchanged through verification. The exact saved Student was reloaded and its predictions independently recomputed from its stored standardization and linear weights. Independent confusion/F1 matched the fresh API result on the same six held-out images.
- The active Student pointer stayed **null**, activation history stayed **zero rows**, and all six shadow items had `action: none`. No activation endpoint, workflow action, public endpoint, paid resource, or additional training was used.
- The observed application gate said `passed: true`; this is a captured application response, **not an independent acceptance verdict**. Its known P1 integrity weaknesses remain in [BLOCKED_STATUS.json](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/BLOCKED_STATUS.json).

## Safe evidence and exact execution

The [evidence manifest](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/evidence-manifest.json) hashes 82 preserved artifacts. Key records are [preregistration](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/06-preregistration.json), [independent reload](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/INDEPENDENT_RELOAD.json), [complete Teacher trace](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/complete-teacher-trace.json), [raw server scoring records](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/teacher-server-requests.jsonl), and [cleanup receipt](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/CLEANUP.json).

The complete trace retains candidate token IDs, log likelihoods, normalized scores, revision, input SHA, forward counts and client/server intervals. C still drops some of these fields and does not persist provider request IDs or the complete HTTP response wire body. Image-to-record correlation is disclosed: exclusively reserved serial job, production `TrainingSample.id` ordering, matching audit/image hashes, and exact label/probability agreement. The separate raw server records are preserved unchanged; no omitted provenance is claimed to have been fixed in C. The transmitted application contract base64-encodes stable PNG bytes but advertises `image/jpeg`; the unchanged server decodes the actual image bytes. No cryptographic server-side input hash or independent request-wire capture is claimed. The [root independent check](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/ROOT_INDEPENDENT_CHECK.json) separately checked the archive, approved source hashes, thresholds, split, raw scores and predictions.

The runtime base was `.agents/runtime/ten-hour`. The following owned commands were executed once, with `VISIONFLOW_DATA_DIR=.../CE/blocked-nonactioning-pilot-0c877e2/data`, `PYTHONPATH=.../worktrees/C-emergency/services/api:.../worktrees/C-emergency/packages/vision`, and OMP/MKL/OPENBLAS thread caps of 2 for both server and runner. Provider configuration used only private `http://127.0.0.1:18081/v1`, model ID above, and an empty local provider token. No `.env` was read or logged.

```bash
systemd-run --user --unit=visionflow-blocked-pilot-0c877e2 --collect \
  --property=Type=simple --property=Restart=no --property=UMask=0077 \
  --property=StandardOutput=append:.../blocked-pilot-control/supervisor.txt \
  --property=StandardError=append:.../blocked-pilot-control/supervisor.txt \
  /usr/bin/python3 .../start_accepted_pilot.py \
  --sha 0c877e227062af7d3def121490419be158cb16c4 --port 8096 \
  --isolated-blocked-experiment

.../worktrees/C-emergency/services/api/.venv/bin/python .../rerun_approved_pilot.py \
  --worktree .../worktrees/C-emergency \
  --sha 0c877e227062af7d3def121490419be158cb16c4 \
  --base-url http://127.0.0.1:8096 \
  --evidence .../CE/blocked-nonactioning-pilot-0c877e2/evidence \
  --isolated-blocked-experiment

.../worktrees/C-emergency/services/api/.venv/bin/python \
  .../TEACHER_EMERGENCY/blocked-pilot-control/independent_check.py
systemctl --user stop visionflow-blocked-pilot-0c877e2.service
```

The [exact argv/env receipt](../../../.agents/teacher-evidence/blocked-pilot-0c877e2-20261011/EXECUTION.json), preserved runtime helper sources, and full paths in receipts disambiguate `...`. **Do not rerun the labeling or training commands without another explicit instruction**: the authorized job is complete. The read-only independent checker makes no requests, fits, or activation calls.

Owned supervisor **1030863** and API child **1030875** were stopped; both were absent and loopback port 8096 was closed afterward. The original experiment data/archive remain ignored at the new runtime location. The unchanged Teacher **989679** remained healthy and idle on private loopback 18081 for later separately authorized work.

Natural-video event quality, unseen physical-camera behavior, foveated performance, baseline-versus-optimized video savings, GPU kernel time, electricity cost and cost per event remain **UNVERIFIED**. Model weights, Student archive, raw synthetic image bytes, credentials and PINs are not committed here.
