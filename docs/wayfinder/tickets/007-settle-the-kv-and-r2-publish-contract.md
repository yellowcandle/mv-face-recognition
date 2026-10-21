---
id: 007
title: Settle the KV and R2 publish contract
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: closed
assignee: claude
---

## Question

What exactly gets written to KV and R2, under which keys, by which single script?

The publish path is **broken in the middle**: the worker reads KV keys that nothing in the
repo writes. This is the reason a deploy today would serve a site that looks populated and is
entirely synthetic.

## Context

- **Keys the worker reads**: `metadata_dense_<numeric>` (`index.ts:1049,1131,1133,1813`),
  `processed_videos_list` (`:801`), `contestants_structured` (`:544`),
  `videos_list_optimized` / `video_metadata_collection` (`:706,716`).
- **Keys anything writes**: `scripts/upload_metadata_to_kv.js` writes
  `<filename>_metadata`, `video_metadata_collection`, `annotated_metadata_collection`,
  `contestants_structured`. `scripts/upload-metadata.js` (the one wired as `upload:metadata`)
  writes `contestants`, `video_metadata_${videoId}`, `videos_list`, `processing_report`,
  `app_settings`. **Neither writes `metadata_dense_*` or `processed_videos_list`** — verified
  by repo-wide grep.
- Fallbacks that hide the breakage: `/api/videos/processed/list` returns 5 hardcoded videos
  (`:753-799`); `/api/videos/metadata/dense/*` returns a **mock** with one fake contestant
  "Ivy So" (`:1822-1852`). Decide whether these fallbacks should be *removed* so the failure
  is loud.
- **The numeric-prefix rule is a real decision.** Three call sites (`:1047,1130,1806`) do
  `videoId.match(/^(\d+)-/)` and key on capture group 1 — so `"5-《…》"` → `metadata_dense_5`.
  `test-video-mv2` has no digit prefix and falls through to the literal id. All 5 MVs are
  digit-prefixed, so this works today by luck. Keep it, or key on something stable?
- `:1854` reads a fourth key `video_metadata_dense_${videoId}` that nothing writes. Dead.
- **R2**: the correct key prefix is `processed_videos/<file>` (what `handleVideoRequest:2059`
  expects), produced only by `scripts/upload_videos_to_r2.js:38`. But `package.json:9` wires
  `upload:videos` to `scripts/upload-to-r2.js`, which uploads to a **bare key that 404s** and
  prints `https://your-worker.your-domain.com/...`, an unedited placeholder.
- Source dir: all four scripts read `metadata/` (repo root). The pipeline writes
  `local_output/metadata/`. Nothing bridges them.
- **Already settled**: publish `_1080p.mp4`, never `_annotated.mp4`.
- The lazy shape is likely **one script replacing all four**, reading `local_output/metadata/`.
  Confirm that before writing it.

## Grounding (2026-09-09) — findings verified, awaiting four decisions

**Status: claimed and parked.** The facts below are confirmed against the code; the four
questions at the end need the user before this can close.

### Corrections to the Context above

- The numeric-prefix rule is at **five** sites, not three: `:730, 1049, 1132, 1808, 1872`. And
  `:730` uses `/^(\d+)/` (no hyphen) while the other four use `/^(\d+)-/`.
- **A sixth key family exists and is not in the Context**: `metadata_${metadataKey}` read at
  `:1879`, written by nothing.
- `handleVideoRequest` does **not** expect `processed_videos/`. It does
  `videoPath = pathname.replace('/videos/', '')`, so the R2 key is whatever `stream_url` says.
  The prefix is data, not worker logic.

### The bridge exists and points at poison

Not merely "nothing bridges `metadata/` and `local_output/metadata/`" — running `npm run setup`
today would publish actively wrong data:

- **Repo-root `metadata/` holds stale metadata for all 5 MVs** from the pre-012 averaged-embedding
  era (`1-…_metadata.json` … `5-…_metadata.json`, plus `_annotated_dense_metadata.json` variants,
  ~15 MB). Both metadata upload scripts read this directory.
- **Repo-root `processed_videos/` holds 708 MB of `_annotated.mp4`** — the files the map ruled must
  never be published, and which *Settle the bbox coordinate space* deleted from the pipeline.
  That is what `upload:videos` uploads.
- The hardcoded fallback list (`:757-799`) also serves `stream_url` pointing at `_annotated.mp4`.

### Full key inventory

Read by the worker, **written by nothing**: `metadata_dense_<numeric>`, `metadata_<numeric>`,
`video_metadata_dense_${videoId}`, `processed_videos_list`, `videos_list_optimized`.
Read **and** written: `video_metadata_collection`, `contestants_structured` (by
`upload_metadata_to_kv.js`); `contestants`, `video_metadata_${id}`, `app_settings` (by
`upload-metadata.js`).
Written, **never read**: `videos_list`, `processing_report`, `annotated_metadata_collection`,
`processed_videos_manifest`, `r2_access_info`.

### New defects found

- **`thumbnails` in metadata are absolute local paths** —
  `/Users/yellowcandle/dev/mv-face-recognition/local_output/thumbnails/…`. Publishing that leaks
  the home directory and 404s everywhere. Also only 1 thumbnail for a 30 s video.
- **`package.json:build:frontend` runs `cd mvp-processor && npm run build`** — the *SvelteKit*
  app — while `scripts/update-worker-assets.js:57` correctly reads `apps/viewer/dist`. The build
  and the embed disagree about which frontend exists.
- `local_output/galleries/*.json` is produced and **read by nothing** in either app or the worker.

### Open questions (blocking closure)

1. **Key scheme** — write what the worker already reads (keep the numeric-prefix rule), or key on
   the full video id and delete the extraction at all five sites? *Recommended: full video id;
   the prefix rule's failure mode is silently serving the wrong video's metadata.*
2. **Fallbacks** — delete the hardcoded 5-video list and the "Ivy So" mock so failure is loud?
   *Recommended: delete both, 404 naming the missing key.*
3. **Artifact set** — thumbnails fixed and published, or dropped from the contract? Galleries
   published, or left local? *Recommended: fix and publish thumbnails; publish no galleries.*
4. **Legacy dirs and build wiring** — delete the four upload scripts, root `processed_videos/`,
   and the stale `metadata/*_metadata.json` (keeping `metadata/contestant_info.csv`)? And fix
   `build:frontend` here rather than leaving it to the deploy fog? *Recommended: yes to both.*

## Settled (2026-10-12, user accepted all recommendations)

- **Q1 key scheme**: full video id. Worker keys become `metadata_<video_id>`, the numeric-prefix
  extraction is deleted at all five sites (`:730, 1049, 1132, 1808, 1872`).
- **Q2 fallbacks**: hardcoded 5-video list and "Ivy So" mock deleted. Missing key returns 404 whose
  body names the key.
- **Q3 artifacts**: thumbnails published with relative paths (absolute paths fixed); galleries not
  published.
- **Q4 legacy**: delete the four upload scripts, root `processed_videos/`, stale
  `metadata/*_metadata.json`; keep `metadata/contestant_info.csv`. `build:frontend` builds
  `apps/viewer`.
- **Q5 R2 layout**: `processed_videos/<video_id>_1080p.mp4` and `_720p.mp4`; `stream_url` is derived
  from the same string the publish script uploads to.

### Contract (proposed from the above — confirm to close)

One script, `scripts/publish.js`, reads `local_output/metadata/` and `local_output/processed_videos/`
(`_1080p` and `_720p` only), and `local_output/thumbnails/`.

| Target | Key | Written by publish | Read by worker |
|---|---|---|---|
| R2 | `processed_videos/<video_id>_1080p.mp4`, `_720p.mp4` | yes | `/videos/*` |
| R2 | `thumbnails/<video_id>/<file>` | yes | thumbnail route |
| KV | `metadata_<video_id>` | yes (one per published video) | dense metadata routes |
| KV | `processed_videos_list` | yes (ids + `stream_url`) | `/api/videos/processed/list` |
| KV | `contestants_structured` | yes (from `contestant_info.csv`) | `:544` |

Not written any more: `videos_list`, `processing_report`, `annotated_metadata_collection`,
`processed_videos_manifest`, `r2_access_info`, `video_metadata_collection`, `app_settings`,
`contestants`, `video_metadata_${id}`, `metadata_dense_*`, `<filename>_metadata`. Worker keys
`videos_list_optimized` and `video_metadata_dense_*` are dead reads and get deleted.

Open for confirmation: the KV key name `metadata_<video_id>` (the worker's current `metadata_dense_`
prefix is dropped) and the thumbnail R2 key layout above.

---

**Executed 2026-10-22 (repo side).** `build:frontend` now builds `apps/viewer` and runs
`scripts/update-worker-assets.js`; the root `wrangler.toml` (pointing at the deleted
`worker/index.js`) is gone and `dev`/`deploy` run from `worker/`. `upload_metadata_to_kv.js`,
`upload-metadata.js` and `upload_videos_to_r2.js` are deleted — `scripts/publish` owns KV.
`upload-to-r2.js` is rewritten as ESM (the file lives under `scripts/` with `"type": "module"`,
so the old `require` version could not run at all), reads `local_output/processed_videos/`, and
uploads only `_1080p` / `_720p` under `processed_videos/`; `--dry-run` lists eight encodes.
`stream_url` in the published list now names that same object: `/videos/processed_videos/<stem>_1080p.mp4`
(reels 1–3), falling back to the source filename for reels 4–5, which have no local encode.
**Q1 executed 2026-10-22.** KV keys are now `metadata_<full video id>` — the same string
`processed_videos_list` serves. The numeric-prefix extraction is gone from
`handleDenseMetadata`, `handleVideoMetadata`, `handleFaceDetection` and the
recognition-results scan (which now lists the `metadata_` prefix). The mocked dense/basic
metadata fallbacks and the dead `video_metadata_dense_*` read are deleted: a miss returns 404
naming the key. `worker/tests/metadata-keys.test.mjs` pins the key for all three routes
(6/6 node:test pass). The orphaned `worker/tests/api.test.js` is deleted — it was never
executed (`npm test` runs `node --test tests/*.test.mjs`, and vitest is not a dependency).
The viewer's Analytics now requests the list's id instead of stripping digits.
