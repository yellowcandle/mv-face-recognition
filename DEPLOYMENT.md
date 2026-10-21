# Deployment

> **Retired surface (2026-10-22).** The FastAPI `backend/` tree, its `Dockerfile`, the Heroku
> `Procfile` and the four ad-hoc upload scripts are gone. The deployable product is the
> Cloudflare Worker in `worker/` (API + embedded viewer build), the KV read model it serves,
> and the encodes in R2. The admin app is a local back office and is not deployed.

## What gets written

| Target | Key | Written by | Read by |
| --- | --- | --- | --- |
| KV | `metadata_<video_id>` (full id, e.g. `4-《全民造星IV》極限拍MV`) | `scripts/publish` | `/api/videos/metadata/dense/*` |
| KV | `contestants_structured` | `scripts/publish` | `/api/contestants` |
| KV | `processed_videos_list` | `scripts/publish` | `/api/videos/processed/list` |
| R2 | `processed_videos/<stem>_1080p.mp4`, `_720p.mp4` | `scripts/upload-to-r2.js` | `/videos/*` |
| R2 | `portraits/<id>.webp` | publish step (Phase 3) | `/api/contestants/<id>/thumb/face` |

Nothing writes the old families (`video_metadata_collection`, `contestants`,
`video_metadata_<id>`, `videos_list`, `annotated_metadata_collection`, `app_settings`) any
more; the Worker's remaining reads of them are fallbacks, not the contract.

## Prerequisites

- `wrangler login` with the account that owns the KV namespace and R2 bucket in
  [worker/wrangler.toml](worker/wrangler.toml).
- `pnpm install` (viewer build) and `uv` (publisher).
- Reels processed into `local_output/metadata/` and `local_output/processed_videos/`.

## Steps

```bash
# 1. Build the viewer and embed it into the Worker
npm run build            # pnpm --filter @mv/viewer build && node scripts/update-worker-assets.js

# 2. Stage and validate the read model (no writes), then publish to KV
npm run publish:metadata
npm run publish:metadata:remote

# 3. Upload the encodes to R2 (dry run first: -- --dry-run)
npm run upload:videos -- --dry-run
npm run upload:videos

# 4. Deploy the Worker
npm run deploy           # cd worker && wrangler deploy
```

`npm run setup` runs 1 → 2(remote) → 3. Steps 2 and 3 are independent of step 4 and can be
re-run whenever metadata or encodes change.

Keys are the full video id (`metadata_4-《全民造星IV》極限拍MV`), the same string
`processed_videos_list` serves; a missing key returns 404 naming it. Publishing after an
older deploy leaves `metadata_dense_*` entries behind — delete them with
`npx wrangler kv key delete <key> --binding METADATA_KV --remote` once the new keys are live.

## Verify a deploy

```bash
# the list the viewer reads
curl -s https://<worker-host>/api/videos/processed/list | head -c 200

# one reel's dense metadata (numeric 編號)
curl -s https://<worker-host>/api/videos/metadata/dense/4 | head -c 200

# an encode the list points at (must be 200/206, not 404)
curl -sI -H 'Range: bytes=0-1023' "https://<worker-host>/videos/processed_videos/<stem>_1080p.mp4"
```

Then open the Worker host in a browser: 圖庫 lists the reels, 點唱單 plays one and draws boxes.

## Inspecting KV and R2

```bash
cd worker
npx wrangler kv key list --binding METADATA_KV --remote
npx wrangler kv key get "processed_videos_list" --binding METADATA_KV --remote
npx wrangler r2 object list mv-face-recognition-videos --prefix processed_videos/
npx wrangler tail     # live Worker logs
```

## Troubleshooting

- **Video 404 but the reel is listed** — the key named by `stream_url` is not in R2. List the
  bucket and compare; re-run `npm run upload:videos` after checking the encode exists in
  `local_output/processed_videos/`.
- **`/api/contestants` returns the CSV fallback** — `contestants_structured` is missing from
  KV; run `npm run publish:metadata:remote`. The fallback claims no embeddings on purpose.
- **Publish fails on a reel** — `validate_payload` rejected it; the message names the field
  (bbox outside `[0,1]`, band cutoff disagreeing with `bands.ts`, missing duration/rate/id).
  Fix the source metadata; do not bypass the check.
- **KV value too large** — the publisher refuses anything over 25 MiB, Cloudflare's limit.
- **`wrangler` auth / namespace errors** — `wrangler whoami`, then check the binding ids in
  `worker/wrangler.toml`.
