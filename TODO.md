# TODO

Project backlog, last tidied 2026-06-10 after a full code review of the
`deploy-ui-rewrite` branch (React admin/viewer rewrite). Dated engineering
notes for in-flight work live in [TODOS.md](TODOS.md).

## Now — make `deploy-ui-rewrite` shippable

All "Now" items from the 2026-06-10 review were fixed on 2026-06-11 (see Done).
Remaining before the branch lands:

- [ ] Production `wrangler deploy` + live smoke test (local `wrangler dev` already serves the React viewer end-to-end; deploy needs user approval)
- [ ] Reprocess videos so stored metadata picks up the new per-recognition `tracker_id` field and post-BGR-fix embeddings (annotated-video traces and the accuracy track both depend on this)
- [ ] `scripts/modal_youtube_processor.py` lost `youtube_cookies.txt` support (age-restricted downloads now fail) and all webhook progress reporting — restore or consciously retire (deferred 2026-06-11: the admin Ingestion page that drove it is disabled until ingestion endpoints exist)

## Next — cleanup confirmed in review

- [ ] Route the pipeline through the vectorized `recognize_faces_batch` (currently zero callers) instead of the per-detection pure-Python loop over ~95 embeddings
- [ ] Export one `formatTime` from `@mv/shared` (currently copy-pasted 5×: Player, PlayerControls, Flagging, Contestants, Analytics)
- [ ] Extract a shared `projectBbox` helper — `FaceOverlay.getBboxStyle` and `useAnnotations.drawAnnotations` duplicate the projection math with different dimension sources (overlay buttons can drift from drawn boxes)
- [ ] Anchor Python data paths on `Path(__file__)` via one shared paths/config module — scripts currently use cwd-relative `Path("../…")` and silently break when run from the repo root; same module should own the `{nickname}_embedding.npy` convention (duplicated 5+ places)
- [ ] Move hardcoded thresholds into `processing_config.yaml`: `min_confidence=0.15` (process_video), coverage quality cutoffs 0.4/0.25, clustering `distance_threshold=0.8`; also de-hardcode InsightFace providers/det_size (CoreML is baked in — Modal GPU runs fall back to CPU)
- [ ] Serve coverage/similarity data from `local_api` instead of committed snapshots in `apps/admin/public/data/` (11k+ lines of generated JSON that goes stale after every reprocessing run)
- [ ] Player component: replace scattered `mode === 'admin' | 'viewer'` branches with capability props (annotation source, canFlag, timeline visibility)
- [ ] One `flagFace()` helper + `Promise.allSettled` for batch flagging (two ~50-line copy-pasted callbacks, sequential awaits)
- [ ] Shared `useInterval` hook to replace the three hand-rolled setInterval/ref patterns (Player, Ingestion, Processing)
- [ ] `Contestants.tsx`: derive `stats` from `appearances` with `useMemo` instead of parallel state reset in three places
- [ ] `Processing.tsx`: drop or implement the request fields `ProcessRequest` silently discards (`mode`, `similarity_threshold`, …) — "Embedding Update" currently queues the same job as "Initial Processing"
- [ ] `ContestantTimeline`: isolate the playhead into its own component so `currentTime` updates stop re-rendering every contestant row
- [ ] `supervision_annotator.annotate_frame`: single BGR→PIL→BGR round trip per frame (currently two, doubling annotation cost)

## Recognition accuracy track

- [ ] Reprocess a test video and re-measure recognition rate now that the BGR/RGB swap is fixed (pre-fix baseline: ~35-37%)
- [ ] Re-collect distance distribution and tune `tolerance` in `processing_config.yaml` (see TODOS.md)
- [ ] Re-run `generate_coverage.py` / `compute_similarity.py` on post-fix data, refresh workbench JSON
- [ ] Embedding Workbench remaining phases: save unmatched embeddings (T0.4), HDBSCAN clustering (T0.5), face crops via canvas (Phase 3), unmatched-faces UI (Phase 5) — see `openspec/changes/embedding-workbench/`

## Tests

- [ ] Fix 8 pre-existing unit-test failures (5 in `test_video_processor.py` — draw_face_box ×3, extract_frames_invalid_video, integration pipeline — and 3 in `test_frame_optimizer.py`; all verified failing on clean HEAD 2026-06-11)
- [ ] Make pytest runnable without manual `PYTHONPATH=$PWD:$PWD/src` (src-layout imports are inconsistent: `from src.x` in tests vs flat `from x` in src)
- [ ] Add tests for the React apps (none exist for `apps/`; the old frontend test suite was deleted with SvelteKit)

## Later / icebox

Kept from the old backlog only where still plausible post-rewrite; everything
referencing deleted SvelteKit/worker code was dropped.

- Modal production integration: real Modal API calls from the worker, job persistence, webhook status endpoint (`modal.web_endpoint`) — needs redesign now that the worker's job routes were removed
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
