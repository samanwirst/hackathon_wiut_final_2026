# Лицензии и источники / Licenses and data sources

Project license: TBD before final submission (candidate: MIT for own code;
note the AGPL-3.0 constraint from Ultralytics below).

## Components and models

| Component / model / data | Version | Source | License | Notes |
| --- | --- | --- | --- | --- |
| Ultralytics (YOLO11n + ByteTrack) | 8.4.x | pypi.org/project/ultralytics | AGPL-3.0 | Detection + tracking. AGPL applies to the combined service; acceptable for an open hackathon repo. Commercial pilot would need an Ultralytics license or a detector swap (e.g. RT-DETR Apache-2.0). |
| yolo11n.pt weights | — | github.com/ultralytics/assets | AGPL-3.0 | Pretrained on COCO. Downloaded at first run, not committed. |
| PyTorch (CPU) | 2.14.x | pytorch.org | BSD-3-Clause | |
| OpenCV (opencv-python-headless) | 5.0.x | pypi | Apache-2.0 | Frame extraction, evidence rendering. |
| FastAPI / Pydantic / SQLAlchemy / uvicorn / httpx | latest | pypi | MIT / MIT / MIT / BSD-3 / BSD-3 | Backend stack. |
| Next.js / React | 15.x / 19.x | npm | MIT | Frontend stack. |
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
