# Fresh natural-image Teacher verification

**Real image-conditioned inference ran, and the result was a false positive.**
The visually inspected El Capitan landscape contains cliffs, trees and sky,
with no visible motor vehicle. Under this test's explicit label meanings, the
Teacher nevertheless returned `occupied` with an uncalibrated candidate
probability of **0.9792594578376954**. This is a narrowly observed failure,
not a validated Teacher quality result or human-verified training label.

Exactly **one POST**, no retries, produced HTTP 200 in **0.965985 seconds**.
The unchanged server reported **0.811228 seconds** inference wall time,
**two real model forwards**, 135 prompt tokens, zero generated tokens and
**274 actual model-processed tokens**. Each candidate forward also processes
the image. The returned `experimental_metrics` exactly matches the server's
request log for `local-b90eeca3ce964b968ffdaf2f93548efa`; both are retained
unchanged. OpenAI-shaped `usage.total_tokens=135` does not count the two
candidate forwards and must not be treated as actual model work or billed cost.

## Input and privacy

The new natural photograph is **El Capitan**, N Baggott, 1969, published by
the U.S. National Park Service. The [primary asset page](https://npgallery.nps.gov/AssetDetail/eebcc978003f43338db6e4dd3e31c82e)
explicitly lists **Public domain**. The unmodified downloaded original is
864 × 596 JPEG, **118,385 bytes**, SHA256
`0969a507c3def0e0c73d3cef020df494b1884da6a4b95070049dc325e38e7279`.
It was inspected with `view_image` before inference: no recognizable faces,
readable plates, people or vehicles were visible. It is neither generated
imagery nor the prior bus crop or 24 procedural drawings. The original is
included with attribution for exact reproducibility.

Limited visual observation provides the comparison here: no vehicle is visibly
present. It is not owner-verified dataset ground truth, a natural-video held-out
test set, or evidence that invisible objects are absent.

## Exact method and model

The endpoint remained private at `http://127.0.0.1:18081/v1`; owned PID
**677309** was not restarted or changed. Model identity is
`HuggingFaceTB/SmolVLM-500M-Instruct`, pinned revision
`a7da5b986cb59b408707209984f360a5f4ad7e47`, Apache-2.0. Startup metadata
and `nvidia-smi` corroborate RTX3050 Laptop 4096 MiB, Torch 2.7.1+cu118,
CUDA runtime 11.8, Transformers 4.51.3. The unchanged loader/image tensor
paths configure BF16; dtype is not separately introspected inside the running
process. Peak allocated/reserved memory for this request was
1,063,482,368 / 1,086,324,736 bytes. GPU kernel duration, utilization-integrated
GPU time, electricity cost and throughput benchmarks remain **UNVERIFIED**.

The provider decodes RGB, thumbnails the image to **512 × 353** using Pillow
11.2.1's default BICUBIC, and applies Idefics3 preprocessing with longest edge
512, max image size 512, LANCZOS resize, rescale 1/255, mean/std 0.5 and
padding/image-splitting enabled. Exact pinned preprocessing configuration and
source hashes are retained; the original input bytes are unchanged. Actual
live intermediate tensor shape is not exposed by the unchanged API.

The model **did not generate this JSON**. The existing harness appends
`{"label":"` to the image-bearing chat prompt and separately scores complete
`occupied"` and `empty"` candidate token sequences. It computes
`s(label)=sum log P(candidate token | image, prompt, prior candidate tokens)`
then `p(label)=softmax(s)` across these two permitted labels. Scores were
**-4.050289630889893** and **-7.904995918273926**; probabilities were
**0.9792594578376954** and **0.020740542162304563**. The JSON envelope is
serialized from those measurements. QA independently reconstructed the
softmax and matched the probabilities to 1e-12; confidence is **uncalibrated**.

No raw generation was run on this image. Earlier raw-generation attempts
failed strict JSON on different inputs; those remain disclosed in
[local setup](LOCAL_SETUP.md) and the inherited evidence. They were not repaired
or repeated here, and are not measurements for this fresh image.

## Request and evidence

The exact prompt is:

> Classify visible motor-vehicle presence in the supplied image. For this test, label occupied means at least one visible motor vehicle (car, truck, bus, or motorcycle), and label empty means no visible motor vehicle. Choose only occupied or empty. Do not infer an invisible vehicle.

One user message contains this text then an inline JPEG. `max_tokens=64`,
`stream=false`. The safe request manifest records exact serialization, body
SHA, pinned model and original-image SHA; no base64 payload or request headers
are committed. The full wire request stays in ignored runtime evidence.

The exact executed command used the already installed isolated B environment:

```bash
/home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/worktrees/B/.agents/runtime/local-teacher/.venv/bin/python scripts/experiments/verify_emergency_teacher.py \
  --image /home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/TEACHER_EMERGENCY/nps-el-capitan-original.jpg \
  --provenance /home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/TEACHER_EMERGENCY/input-provenance.json \
  --evidence /home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/TEACHER_EMERGENCY/inference \
  --server-evidence /home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/worktrees/B/.agents/runtime/local-teacher/evidence
```

This runner records a durable attempt before its one POST and refuses an
implicit repeat in the same evidence directory. Compilation, input and record
SHA checks, exact log match, strict numeric confidence validation, and softmax
reconstruction passed. It performs no generation repair, model modification,
credential read, action, training or activation.

Safe records are in
[natural-emergency-20261011](../../../.agents/teacher-evidence/natural-emergency-20261011/response.json):
original image and attribution, provenance, request manifest, byte-exact raw
response, parsed response with unchanged metrics, matching server log,
measurement, GPU/process proof, preprocessing and SHA256 manifest.
All dataset quality, generalization, foveated benefit and savings remain
**UNVERIFIED**. No paid resource, Student training or Student activation occurred.
