# Different photographic input — executed geometric smoke

Running container application source:
`749d27b33bcec03883d4a1b1ac481ee9a95fd91e`. Teacher workflow actions are
disabled and Student is inactive. This is QA evidence, not a milestone verdict.

A different bus photograph was acquired from [Don Bai's Pexels photo 7666059](https://www.pexels.com/photo/yellow-school-bus-on-the-road-7666059/).
The [Pexels license](https://www.pexels.com/license/) permits use and modification;
the source/author/license and downloaded byte hash are in `provenance.json`.
Only the visually inspected upper-rear crop `[190,490,1160,1090]` from the
1400×2144 download entered the detector. The license plate and recognizable
people are excluded. The original download is ignored, not committed.

The crop was resized to 360×223 and moved right to left over a 1280×720 canvas,
held inside a polygon for 4.5 seconds and moved out. The 20fps MP4 has 200 frames.
All parameters were fixed before processing; detection output did not construct
the input. The motion is synthetic, while detection is genuine inference on
new photographic content for this application smoke.

Executed command from the shared root workspace:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  services/api/.venv/bin/python \
  .agents/runtime/ten-hour/delivery/new-photo-input/new_photo_smoke.py
```

Result: exit 0; **50 real YOLO samples**, mean inference **35.028 ms**; one
entry and one dwell event, both with fetched JPEG evidence, one successful
local action and one notification each. `demo_safe:true`, Teacher unavailable,
no model activation. Actual API responses and evidence hashes are retained in
`actual-result.json`; input hashes and parameters are in `input-manifest.json`.
The executed runner is archived as `executed_smoke.py` and retains its exact
local runtime paths. The committed privacy-safe crop permits reconstructing
that runtime input without distributing the original image.

The earlier source was the Ultralytics bus photo; this uses a distinct school
bus photo. This does not establish that model pretraining never saw the photo.
It is one partial-photo/synthetic-motion test, **not natural-video, night/rain,
local-vehicle or general event-accuracy evidence**. No throughput/cost/savings
comparison is inferred from this run. Public external access remains untested.
