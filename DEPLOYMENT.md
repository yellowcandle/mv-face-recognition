# Deployment

> **Retired surface (2026-10-22).** The FastAPI `backend/` tree, its `Dockerfile`, the Heroku
> `Procfile` and the four ad-hoc upload scripts are gone. The deployable product is the
> Cloudflare Worker in `worker/` (API + both embedded SPAs), the KV read model it serves,
> and the encodes in R2. The admin app is embedded at `/admin` on the same Worker origin and
> sits behind a Cloudflare Access application.

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
- `HF_TOKEN` as a Worker secret, with `job.write` (and bucket read): the admin's processing jobs
  dispatch to HF Jobs (`worker/src/lib/hfJobs.ts`). Without it the job routes fail closed with
  `503`/`502` naming the token; nothing silently queues.
- `pnpm install` (viewer build) and `uv` (publisher).
- Reels processed into `local_output/metadata/` and `local_output/processed_videos/`.

## Steps

```bash
# 1. Build the viewer and the admin, and embed both into the Worker
npm run build            # pnpm --filter @mv/viewer build && pnpm --filter @mv/admin build && node scripts/update-worker-assets.js

# 2. Stage and validate the read model (no writes), then publish to KV
npm run publish:metadata
npm run publish:metadata:remote

# 3. Upload the encodes to R2 (dry run first: -- --dry-run)
npm run upload:videos -- --dry-run
npm run upload:videos

# 4. Deploy the Worker
cd worker && npx wrangler secret put HF_TOKEN   # once per environment, or after a rotation
cd .. && npm run deploy                          # cd worker && wrangler deploy
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
`/admin` serves the back office from the same origin; it answers 302 to Cloudflare Access
until the session exists, so a `curl` on that path is expected to redirect rather than 200.

Processing jobs have their own check, because they spend money:

```bash
# unauthenticated: the gate must refuse before any KV write or HF call
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<worker-host>/admin/api/processing/trigger
# → 401 (503 if CF_ACCESS_AUD / CF_ACCESS_TEAM_DOMAIN are unset)

# authenticated, from the deployed /admin console: trigger one reel, watch it reach
# completed or failed, then cancel one. Both must show a terminal state.
```

A reel run defaults to GPU (`a10g-small`, ~$0.60, ~3 min); a cache rebuild stays on
`cpu-upgrade` (~$0.05). A job left in `queued` means the dispatch failed and the record should
say why in `error` — check `npx wrangler tail` for `HF job stage unreadable` /
`HF job cancel rejected`.

## Inspecting KV and R2

```bash
cd worker
npx wrangler kv key list --binding METADATA_KV --remote
npx wrangler kv key get "processed_videos_list" --binding METADATA_KV --remote
npx wrangler kv key list --binding JOB_STORE --remote   # job:<8 hex> records, 7-day TTL
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
