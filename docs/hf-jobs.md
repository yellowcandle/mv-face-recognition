# Running the pipeline on Hugging Face Jobs

The five reels are processed on HF Jobs instead of this Mac. Inputs and outputs live in the
Storage Bucket `yellowcandle/mv-face-recognition`; each job mounts it at `/mnt/data` and
downloads the `hf-jobs` branch of this repository as a tarball.

## Bucket layout

```
inputs/contestant_info.csv                     uploaded once
manifest/{videos,photos}.json                  written by scripts/hf/stage_sources.py
videos/source/<id>/<sha>.mp4                   existing
photos/reference/<id>/<sha>.jpg                existing (curated IG portraits)
photos/historical/<id>/*.jpg                   extra appearances, merged into the cache build
models/home/.insightface/models/buffalo_l/     uploaded once (326 MB)
models/reference/                              job writes reference_embeddings.npz + manifest
output/<video_id>/                             job writes metadata, renditions, thumbnails, galleries
```

Upload the two one-off inputs:

```bash
hf buckets cp source/contestant_info.csv \
  hf://buckets/yellowcandle/mv-face-recognition/inputs/contestant_info.csv
hf buckets sync ~/.insightface \
  hf://buckets/yellowcandle/mv-face-recognition/models/home/.insightface
hf buckets sync source/photo/historical/contestants \
  hf://buckets/yellowcandle/mv-face-recognition/photos/historical --include "*.jpg" --include "*.png"
```

## Run

```bash
uv run --with "huggingface_hub>=1.8" python scripts/hf/jobs/submit.py
```

It submits one `cache` job, waits for the reference embeddings to land in
`models/reference/`, then submits five `video` jobs in parallel. Defaults: `cpu-upgrade`
(8 vCPU / 32 GB, $0.03/h). Use `--ref <commit>`, `--only 3` or `--skip-cache` as needed.

The Python submitter exists because `hf jobs uv run` first uploads the script to the
`jobs-artifacts` bucket; a token with `job.write` but no bucket write fails there. It also avoids
the CLI splitting a multi-word `bash -lc` command.

GPU mode (`a10g-small`, CUDA image, `onnxruntime-gpu==1.22` for CUDA 12):

```bash
uv run --with "huggingface_hub>=1.8" python scripts/hf/jobs/submit.py --gpu
```

Measured on `test-video-mv2`: detection 3m45s → 18s, but encoding 1080p/720p stays on
CPU (~4 min), so the whole job is ~6 min at $1/h. For the five reels that projects to
~$0.60 each; `cpu-upgrade` is ~$0.05 each. Use GPU when wall-clock matters.

Manual single stage:

```bash
hf jobs uv run --flavor cpu-upgrade --timeout 2h \
  -v hf://buckets/yellowcandle/mv-face-recognition:/mnt/data \
  scripts/hf/jobs/hf_pipeline.py -- video --video-id 3
```

`INSIGHTFACE_PROVIDERS=CPUExecutionProvider` is set by the script; the cache is mounted so the
model is not re-downloaded. `HOME` points into the bucket for the same reason, while uv's cache
stays on the job's ephemeral disk.

## Getting the outputs back

```bash
hf buckets sync hf://buckets/yellowcandle/mv-face-recognition/output ./hf-output
```

Then copy the metadata and renditions into `local_output/`, rebuild the read model and re-upload
the renditions exactly as with a local run.
