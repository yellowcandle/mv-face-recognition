# TODO

Project backlog, last tidied 2026-06-10 after a full code review of the
`deploy-ui-rewrite` branch (React admin/viewer rewrite). Dated engineering
notes for in-flight work live in [TODOS.md](TODOS.md).

## Now — make `deploy-ui-rewrite` shippable

All "Now" items from the 2026-06-10 review were fixed on 2026-06-11 (see Done).
Remaining before the branch lands:

- [x] Production `wrangler deploy` + live smoke test (2026-10-21): KV read model published, Worker deployed, all five videos return 206 on Range, dense metadata carries ByteTrack `tracker_id`.
- [x] Reprocess `test-video-mv2` (2026-06-30): metadata now carries `tracker_id` + post-fix embeddings. **But recognition is flat at 37.6% (was 35.2%) — the BGR fix produced no accuracy gain.** See accuracy track for the real root cause. Other videos still need a reprocess once matching is fixed (don't reprocess on the broken matcher).
- [x] `scripts/modal_youtube_processor.py`: **retired 2026-10-22** with the rest of the Modal surface (the script, its setup/wrapper, the pipeline and both docs are deleted).

## Next — cleanup confirmed in review

- [ ] Route the pipeline through the vectorized `recognize_faces_batch` (currently zero callers) instead of the per-detection pure-Python loop over ~95 embeddings
- [ ] Export one `formatTime` from `@mv/shared` (currently copy-pasted 5×: Player, PlayerControls, Flagging, Contestants, Analytics)
- [ ] Extract a shared `projectBbox` helper — `FaceOverlay.getBboxStyle` and `useAnnotations.drawAnnotations` duplicate the projection math with different dimension sources (overlay buttons can drift from drawn boxes)
- [ ] Anchor Python data paths on `Path(__file__)` via one shared paths/config module — scripts currently use cwd-relative `Path("../…")` and silently break when run from the repo root; same module should own the `{nickname}_embedding.npy` convention (duplicated 5+ places)
- [ ] Move hardcoded thresholds into `processing_config.yaml`: `min_confidence=0.15` (process_video), coverage quality cutoffs 0.4/0.25, clustering `distance_threshold=0.8`; also de-hardcode InsightFace providers/det_size (CoreML is baked in — Modal GPU runs fall back to CPU)
- [x] Serve coverage/similarity data from `local_api` instead of committed snapshots in `apps/admin/public/data/` (11k+ lines of generated JSON that goes stale after every reprocessing run) — **done 2026-10-22**: published to KV as `embedding_coverage` / `embedding_similarity_matrix` / `embedding_top_pairs`, served at `/api/embedding/*` by both origins; the three static copies are deleted (~190 KiB off the Worker bundle)
- [ ] Player component: replace scattered `mode === 'admin' | 'viewer'` branches with capability props (annotation source, canFlag, timeline visibility)
- [ ] One `flagFace()` helper + `Promise.allSettled` for batch flagging (two ~50-line copy-pasted callbacks, sequential awaits)
- [ ] Shared `useInterval` hook to replace the two hand-rolled setInterval/ref patterns (Player, Processing)
- [ ] `Contestants.tsx`: derive `stats` from `appearances` with `useMemo` instead of parallel state reset in three places
- [x] `Processing.tsx`: drop or implement the request fields `ProcessRequest` silently discards (`mode`, `similarity_threshold`, …) — **done 2026-10-22**: `mode` is honoured (`initial` / `embedding-update` / `coverage-refresh`, 400 otherwise) and the dead `similarity_threshold` / `sync_from_hf` / `upload_results` fields are gone
- [x] Replace the single `flagged_faces` KV array with one key per flag — **done 2026-10-22**: `flag_<id>` per record, legacy array read and claimed on first write; the queue's `no-store` header came out of the same bug hunt (a cached list hid accepted flags)
- [ ] `ContestantTimeline`: isolate the playhead into its own component so `currentTime` updates stop re-rendering every contestant row
- [ ] `supervision_annotator.annotate_frame`: single BGR→PIL→BGR round trip per frame (currently two, doubling annotation cost)

## Recognition accuracy track

**2026-06-30 diagnosis — root cause found (see `memory/project_bgr_fix_did_not_improve_accuracy`):**
BGR fix does NOT help (37.6% vs 35.2%). Distance distribution is a single smeared blob (mean 0.21,
max 0.51 — no true-match cluster). Stored embeddings are FINE (≈ fresh, 0.82-0.97; cross-person
separation 0.07). Bottleneck is **reference-photo quality + averaging**: a contestant's own IG photos
match each other only at mean ~0.3, and the pipeline averages 5 into one mushy centroid. Threshold
tuning and naive regeneration both can't fix this.

- [x] **Max-over-photos matching** — references are flattened per photo (`flatten_references`), so the recognition argmin is max cosine over the whole reference set. Implemented with the consolidated cache.
- [x] **Curate references** (2026-10-21): `build_reference_cache.py` drops a reference when its best cosine against another contestant beats its best against its own photos, with a two-reference floor. HDBSCAN was rejected: with 2–16 photos per contestant it labels most valid poses as noise. 25 of 663 references dropped; impostor p99 0.447→0.412, max 0.585→0.445; genuine p05 0.316→0.377. Recall on `test-video-mv2` is flat (34.8%→34.1%), so the remaining gap is domain, not contamination.
- [ ] Fix `regenerate_embeddings_from_contestant_photos`: it reads `photos/contestant_{id}/` (4KB Git-LFS pointers); real photos are in `source/photo/contestants/ig_photos/contestant_{id}/{id}_ig_N.jpg`.
- [x] Re-tuned the acceptance threshold against the curated cache: `acceptance_threshold` 0.45→0.412, `band_cutoffs` high 0.585→0.445 / medium 0.451→0.412. On `test-video-mv2` recall rises 34.1%→48.4% at the measured 1% reference-level FPR. Still provisional: needs ground-truth labels from `admin → 標記` to measure video-level precision.
- [ ] Reset expectations: even clean IG photos top ~0.5-0.7 and MV faces are small/moving — ~37% may be near the ceiling for this reference set. Better refs raise it; don't assume 90%.
- [ ] Embedding Workbench remaining phases: save unmatched embeddings (T0.4), HDBSCAN clustering (T0.5), face crops via canvas (Phase 3), unmatched-faces UI (Phase 5) — see `openspec/changes/embedding-workbench/`

## Tests

- [ ] Fix 8 pre-existing unit-test failures (5 in `test_video_processor.py` — draw_face_box ×3, extract_frames_invalid_video, integration pipeline — and 3 in `test_frame_optimizer.py`; all verified failing on clean HEAD 2026-06-11)
- [ ] Make pytest runnable without manual `PYTHONPATH=$PWD:$PWD/src` (src-layout imports are inconsistent: `from src.x` in tests vs flat `from x` in src)
- [ ] Add tests for the React apps (none exist for `apps/`; the old frontend test suite was deleted with SvelteKit)

## Later / icebox

Kept from the old backlog only where still plausible post-rewrite; everything
referencing deleted SvelteKit/worker code was dropped.

- ~~Modal production integration~~ retired 2026-10-22 with the Modal surface; the pipeline runs locally through `process_video.py`.
- Error tracking (Sentry) + retry/alerting for processing jobs
- API rate limiting and an input-validation pass on worker endpoints
- Batch/multi-video processing UX and notifications
- Mobile/touch video player polish, accessibility pass
- Automated reprocessing after embedding updates (queue/cron)

## Done

- **2026-06-11** — All "Now" blockers from the 2026-06-10 review fixed:
  - *Deploy path*: `scripts/update-worker-assets.js` rewritten for `apps/viewer/dist/` (also fixed the never-firing `process.argv[1] === import.meta.url` entrypoint guard and the `logger.info` TypeError); binary assets now base64-encoded with a `BINARY_ASSETS` manifest the worker decodes. Verified end-to-end with `wrangler dev`: `/`, hashed assets, and SPA routes all serve the React viewer. `wrangler deploy --dry-run` bundles clean.
  - *Local API*: added `fastapi`/`uvicorn` to `mvp-processor` deps (they were missing — the admin backend couldn't even start). Implemented `GET /api/videos/stream/{id}` (Range-capable FileResponse), flag persistence to `local_output/flagged_faces.json` (`POST /api/faces/flag`, `GET /api/faces/flagged`, `PATCH /api/faces/flagged/{id}`, `DELETE /api/faces/flagged/{id}`, `POST /api/faces/flag/update`), `GET /api/recognition/results`, and `GET /api/contestants/{id}/photo`; `/api/contestants` now reports `has_embedding`/`quality`. All endpoints smoke-tested against real data.
  - *Metadata dirs / video IDs*: everything reads `local_output/metadata/`; `_VIDEO_ID_RE` replaced with `_safe_child` traversal checks so CJK/space IDs work; removed Player's numeric-prefix stripping (IDs now round-trip; worker still maps numeric-prefix KV keys server-side). Dense metadata responses are mtime-cached; `/api/faces/detect` uses floor (bisect) matching like the annotator.
  - *Bbox contract*: canonical wire order `[x1,y1,x2,y2]` derived from stored `face_location` `[top,right,bottom,left]` at every serving boundary; worker `handleFaceDetection` rewritten to read `frame_data` (was reading a nonexistent `detailed_timeline.bbox` shape); worker `handleRecognitionResults` mock data replaced with real KV-backed appearances; contract documented in `apps/shared/types`.
  - *Pipeline*: `bbox_scale` now handles upscaled (<1920) sources; tracker IDs keyed per-recognition via ByteTrack's in-place index-aligned assignment (verified against supervision 0.25 semantics) instead of positional zip against the filtered tracker output; `annotate_frame` traces only real tracks (`tracker_id != -1`). Takes effect on next reprocess.
  - *Ingestion*: page + nav entry disabled (backend routes don't exist anywhere); code kept for revival.
- **2026-06-10** — Code review of `deploy-ui-rewrite` (16 confirmed findings). Fixed: BGR/RGB channel swap in `process_video.py` (frames now reach InsightFace in BGR, matching gallery embeddings); viewer-mode infinite render loop (`useViewerMetadata` memoized return + frame-change guard in Player); frontend metadata schema aligned with real Python output (`processing_summary`, `average_confidence`, `first_appearance`/`last_appearance`) across shared types, Player info panel, and viewer Analytics.
- **2026-03** — React rewrite: SvelteKit frontend deleted; pnpm monorepo with `apps/admin` (local), `apps/viewer` (Cloudflare), `apps/shared` (Player, UI kit, hooks, types). InsightFace + supervision/ByteTrack integration; CJK label rendering via PIL+PingFang; Embedding Workbench Phases 0-1; `local_api.py` FastAPI backend for the admin app.
- **2026-01** — HuggingFace XET migration for photos/embeddings; Modal-frontend integration (SvelteKit era); contestant Instagram handles.
- **2025** — Original SvelteKit system: video player with overlays, flagging workflow, 21-endpoint worker, Zero Trust admin, processing pipeline optimization. Superseded by the rewrite; history in git.
