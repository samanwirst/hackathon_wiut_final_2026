# Лицензии и источники / Licenses and data sources

Project license: TBD before final submission (candidate: MIT for own code;
note the AGPL-3.0 constraint from Ultralytics below).

## Components and models

| Component / model / data | Version | Source | License | Notes |
| --- | --- | --- | --- | --- |
| Ultralytics (YOLO11n + ByteTrack) | 8.4.175 tested | pypi.org/project/ultralytics | AGPL-3.0 | Detection + tracking. Upstream AGPL obligations must be resolved for the distributed/networked release; public source alone is not a claim of full compliance. See the upstream license below. |
| yolo11n.pt weights | — | github.com/ultralytics/assets | AGPL-3.0 | Pretrained on COCO. Downloaded at first run, not committed. |
| PyTorch (CPU) / TorchVision | 2.14.1+cpu / 0.29.1+cpu tested | pytorch.org | BSD-3-Clause code | Frozen encoder and actual Student fit. Pretrained weights have separate training-data terms; see note below. |
| ResNet18 IMAGENET1K_V1 weights | resnet18-f37072fd.pth | TorchVision pretrained weights | Training-data/model-use terms require separate check | Downloaded into ignored cache; not committed. Used as frozen 512-dimensional encoder, not a trained-from-scratch claim. |
| OpenCV (opencv-python-headless) | 5.0.0.93 tested | pypi | Apache-2.0 | Frame extraction, evidence rendering. |
| FastAPI / Pydantic / SQLAlchemy / uvicorn / httpx | latest | pypi | MIT / MIT / MIT / BSD-3 / BSD-3 | Backend stack. |
| Next.js / React | 15.5.27 / 19.3.0 tested | npm | MIT | Frontend stack. |
| SmolVLM-500M-Instruct | a7da5b986cb59b408707209984f360a5f4ad7e47 | HuggingFaceTB model card | Apache-2.0 | Actually loaded on the local GPU. Candidate likelihood scoring is disclosed separately from failed generated-JSON labeling. Weights not committed. |
| Qwen2.5-VL-7B-Instruct | cc594898137f460bfe9f0759e9844b3ce807cfb5 planned | Qwen model card | Apache-2.0 | Private Vast setup was stopped and destroyed; remote weights/inference remain UNVERIFIED. |
| AutoLearn pilot drawings | synthetic-occupancy-v1 | Original project procedural generator | Own-code/data license decision pending | 24 images, 12 rendering sessions; human confirmed the exact displayed labels. No customer footage, faces, plates or real-world quality claim. Raw assets remain ignored. |
| Demo video content (`data/demo/demo_bus.mp4`, historical M1 smoke) | generated | built by `scripts/make_demo_video.py` from the Ultralytics sample photo `bus.jpg` (bundled with the pip package) | package: AGPL-3.0; image subject rights: **unverified** | Translates the *whole* photo (bus **and** foreground pedestrians) across a canvas. Generation method declared per brief rules. Not committed to git. See the privacy note below — this clip is retained for the historical M1 smoke only. |
| Demo-safe video content (`data/demo/demo_bus_private_crop.mp4`) | generated | built by `scripts/make_demo_safe_video.py` from a **bus-only crop** `[350,220,755,665]` of the same `bus.jpg` | package: AGPL-3.0; image subject rights: **unverified** | The crop excludes the foreground pedestrians and still yields genuine YOLO `bus` detections. Synthetic left→right motion on a flat canvas; only the motion is synthetic, never the prediction. Used for the demo-safe journey. Not committed to git. |

## Task materials

The official Final Task is stored as text at `docs/source/README.md`
(provided by the hackathon organizers; redistribution limited to this repo).

## Upstream asset and license links

- Ultralytics repository and license (AGPL-3.0):
  <https://github.com/ultralytics/ultralytics> ·
  <https://github.com/ultralytics/ultralytics/blob/main/LICENSE>
- Sample asset `bus.jpg` ships inside the `ultralytics` pip package
  (`ultralytics/assets/bus.jpg`). The **package** is AGPL-3.0; this attributes
  the upstream package/repository license only.
- [Ultralytics upstream licensing terms](https://www.ultralytics.com/legal/agpl-3-0-software-license).
- [TorchVision pretrained model terms](https://docs.pytorch.org/vision/stable/models.html)
  explicitly distinguish library licensing from terms derived from model
  training datasets. Commercial permission for the selected encoder weights
  is not established by this dependency inventory.
- Model cards: [SmolVLM-500M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct),
  [Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct).

## Privacy

The original `bus.jpg` sample contains **recognizable pedestrians**. The fact
that the image is publicly downloadable with the package does **not** establish
the subjects' consent, and we make **no such claim**: the subject/portrait
rights of the people in that image are **unverified**.

For this reason the demo-safe journey uses `demo_bus_private_crop.mp4`, a
**bus-only crop that excludes the foreground pedestrians**. The historical M1
smoke clip (`demo_bus.mp4`, whole photo) is retained unchanged for the M1 smoke
only and is not used in the demo-safe journey.

No private or customer footage is used. Faces/plates of non-consenting people
must not be uploaded during demos.

## Before release

- [ ] Choose own-code license (consider AGPL obligations from Ultralytics).
- [x] Third-party libraries, models, and data recorded above.
- [ ] Final attribution pass before submission.
