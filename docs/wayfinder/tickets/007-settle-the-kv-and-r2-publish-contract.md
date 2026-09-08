---
id: 007
title: Settle the KV and R2 publish contract
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: open
assignee:
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
