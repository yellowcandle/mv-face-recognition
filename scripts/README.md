# Scripts

Entry points for processing, publishing and maintenance. The pipeline itself lives in
`mvp-processor/`; nothing here re-implements it.

## Pipeline and publishing

| Script | Purpose |
| --- | --- |
| `run-full-pipeline.cjs` | orchestrates process → build viewer → publish KV → upload R2 → deploy Worker (`--process-only`, `--skip-upload`, `--skip-deploy`) |
| `publish/build_read_model.py` | normalises each reel, backfills contract fields, validates, stages (default) or writes KV (`--publish`) |
| `upload-to-r2.js` | uploads `local_output/processed_videos/*_{1080p,720p}.mp4` to `processed_videos/` in R2 (`--dry-run` lists them) |
| `update-worker-assets.js` | embeds `apps/viewer/dist` into `worker/embedded-assets.js` |
| `ci/check_baselines.py` | ruff / mypy / pytest ratchets against `scripts/ci/baseline.json` |

```bash
node scripts/run-full-pipeline.cjs --skip-processing   # deploy the current artifacts
uv run --no-project python scripts/publish/build_read_model.py --publish
node scripts/upload-to-r2.js --dry-run
```

## Portraits and Hugging Face

`hf/` stages and materialises the photo corpora and publishes the cropped portraits:

- `stage_sources.py`, `stage_curated.py`, `materialize_source_photo.py` — dataset staging
- `make_portraits.py` — per-contestant face crop (512 px WebP + provenance manifest)
- `publish_portraits_r2.py` — uploads `portraits/<id>.webp` and the manifest the Worker reads

## Embeddings and contestant data

- `check_stored_embeddings.py` — integrity and normalisation checks
- `validate_embeddings.py` — compare stored embeddings against the reference manifest
- `upload_embeddings_to_hf.py` — upload the embedding cache to Hugging Face

The Chroma collection, its roster resolver and the scripts that populated it are deleted.
`source/photo/contestants/reference_manifest.json` is the record (ADR 0001).

## Archive

`archive/` holds the Docker/Fly.io-era scripts. Nothing imports them.
