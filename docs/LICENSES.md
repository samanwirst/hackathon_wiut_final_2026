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
| Demo video content (`data/demo/demo_bus.mp4`) | generated | built by `scripts/make_demo_video.py` from the Ultralytics sample photo `bus.jpg` (bundled with the pip package, AGPL-3.0 distribution) | AGPL-3.0 (asset) | Real photographic content translated across a canvas to create motion; generation method declared per brief rules ("data you generate yourself, with the source and the generation method declared"). Not committed to git. |

## Task materials

The official Final Task is stored as text at `docs/source/README.md`
(provided by the hackathon organizers; redistribution limited to this repo).

## Privacy

The demo video contains people from the Ultralytics public sample image, which
is distributed publicly by Ultralytics for exactly this purpose. No private or
customer footage is used. Faces/plates of non-consenting people must not be
uploaded during demos.

## Before release

- [ ] Choose own-code license (consider AGPL obligations from Ultralytics).
- [x] Third-party libraries, models, and data recorded above.
- [ ] Final attribution pass before submission.
