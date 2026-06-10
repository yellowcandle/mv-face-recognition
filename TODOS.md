# TODOS

Dated engineering notes for in-flight work. The full backlog lives in
[TODO.md](TODO.md).

## Open

### Tune tolerance threshold
- **What:** Run test-video-mv2 with InsightFace, collect distance distribution, tune `tolerance` in `processing_config.yaml`
- **Why:** Starting at 0.4 (cosine distance) as default. Optimal value depends on actual data. InsightFace same-person matches are typically 0.1-0.3, cross-person 0.5-1.5. Sweet spot usually 0.35-0.45.
- **Note (2026-06-10):** The BGR/RGB swap fix changes every video-side embedding — any distance distribution collected before it is invalid. Reprocess first, then tune.
- **Added:** 2026-03-23 via /plan-eng-review

### Fixed color assignment for contestants
- **What:** Assign each contestant a stable, fixed color across all videos (vs dynamic per-tracker colors)
- **Why:** Fans would learn to associate specific colors with contestants. Currently using `class_id % palette_size` which cycles through a small palette. For 96 contestants with only ~10 on screen at a time, a 20-color palette with modular assignment works but may have collisions.
- **Options:** (a) Use contestant_id-based fixed colors via class_id. (b) Use a perceptually-distinct palette of 20 colors and accept collisions. (c) Use contestant's theme color if one exists.
- **Added:** 2026-03-23 via /plan-eng-review

## Fixed

### 2026-06-11 (shippability pass on deploy-ui-rewrite)
- **All "Now" blockers from TODO.md fixed** — deploy script targets `apps/viewer/dist/`, local API gaps filled (streaming, flag persistence, recognition results, contestant photos), CJK video IDs round-trip, bbox wire order canonicalized to `[x1,y1,x2,y2]`, `bbox_scale` upscale bug and tracker-ID positional-zip bug fixed, Ingestion page disabled. Details in TODO.md → Done.
- **Discovered along the way:** `fastapi`/`uvicorn` were never in `mvp-processor` deps (admin backend could not start); the deploy script's `main()` was unreachable (`process.argv[1] === import.meta.url` never matches a file path); pre-existing unit-test failures number 8, not 5 (3 more in `test_frame_optimizer.py`, verified on clean HEAD).
- **Tracker-ID fix mechanism:** supervision 0.25's `ByteTrack.update_with_detections` assigns `tracker_id` *in place* on the input detections, index-aligned (recognitions first, then unmatched; -1 = untracked) — verified empirically. Per-recognition `tracker_id` is now stored in `frame_data` recognitions; old `tracker_ids` arrays in existing metadata are ignored, so traces only return after a reprocess.

### 2026-06-10 (code review follow-up)
- **BGR/RGB channel swap** — `process_video.py` converted frames to RGB before `FaceDetector.detect_faces`, but InsightFace expects BGR and the gallery embeddings are built from BGR `cv2.imread` photos. Frames now pass through unconverted; recognition rate should be re-measured (pre-fix baseline ~35-37%).
- **Viewer-mode infinite render loop** — `useViewerMetadata` returned a fresh object every render and sat in a Player effect's dependency array that unconditionally set new state. Hook return is now memoized; the effect only updates `detectedFaces` when the metadata frame actually changes (ref keyed on `videoId:frame_number`).
- **Metadata field-name mismatch** — frontend types were derived from the worker's mock fallback, not real pipeline output. Aligned to the real schema across `apps/shared/types`, Player info panel, and viewer Analytics: `recognition_summary` → `processing_summary`, `avg_confidence` → `average_confidence`, `first/last_appearance_time` → `first/last_appearance`, `total_faces_recognized` → `total_recognitions`; per-contestant max confidence is now computed from `appearances`.

### 2026-03-23
- **Timeline bar "TOP" error** — (1) CJK text rendered via cv2.putText which can't display Chinese → switched to PIL+PingFang. (2) screen_time accumulated from ByteTrack tracked labels which drops custom data → accumulate from original sv_detections labels instead.
- **Bbox displaying early (ahead of face position)** — changed from nearest-timestamp matching (bisect_left + neighbor comparison) to floor-only matching (bisect_right, pick idx-1). Bboxes now only appear after the detection, never before.
