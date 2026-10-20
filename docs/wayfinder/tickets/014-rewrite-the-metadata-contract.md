---
id: 014
title: Rewrite the metadata contract
label: wayfinder:task
mode: AFK
blocked_by: [008, 013]
status: closed
assignee: claude
---

## Question

Execute the changes settled by *Settle the bbox coordinate space* and *Settle what match
confidence means on the wire*, then reprocess `test-video-mv2` so the boxes land on the faces
and the numbers beside them mean something.

No decision to make — this is execution. See
[ADR 0002](../../adr/0002-face-boxes-are-frame-fractions.md) and
[CONTEXT.md](../../../CONTEXT.md) (`### Geometry`, plus **Match score** / **Detection score** /
**Band**) for the vocabulary. **Both decisions land in one reprocess.**

## Geometry changes (from 008)

1. **`face_location` → `bbox`, pixels → frame fractions, `[t,r,b,l]` → `[x1,y1,x2,y2]`.**
   Convert **once**, at the metadata write boundary, dividing by the detection-space dimensions
   the pipeline already knows. Internal Python that needs pixels keeps pixels.
2. **`frame_data[].recognitions` → `frame_data[].detections`, carrying all 399**, with
   `contestant_id: null` on unmatched entries.
3. **Delete the `[t,r,b,l]` round trip.** `face_detector.py:230` stops converting InsightFace's
   native `[x1,y1,x2,y2]`; `local_api.py:352`, `worker/src/index.ts:1086` and
   `useViewerMetadata.ts:66` stop converting it back.
4. **Drop `_annotated.mp4`** and with it `bbox_scale` (`process_video.py:322`) and the
   `supervision_annotator.py` render path.

Then: `FaceOverlay.tsx:30-31` and `useAnnotations.ts:78-79` both become `x1 * renderW` /
`y1 * renderH` with no width argument, and `FaceOverlay`'s `videoWidth`/`videoHeight` props and
`Player.tsx:585` delete.

## Score changes (from 013)

5. **`match_confidence` → `match_score`, carrying the raw cosine**, not
   `1 − (distance / tolerance)`. Delete the rescale at `face_detector.py:333` **and 409** — there
   are two sites.
6. **Collapse `confidence` / `detection_confidence` / `recognition_confidence` to `match_score`.**
   All three currently carry the identical value at `local_api.py:357-358`,
   `worker/src/index.ts:1091-1092`, `useViewerMetadata.ts:71-72`.
7. **Store `det_score`** on every detection (it is the only score an unmatched one has). Do
   **not** wire a `det_score` gate.
8. **Bands replace percentages in the UI**, raw score in the tooltip. Compute the cutoffs from
   leave-one-out on the reference cache — the boundaries where measured false-match rate crosses
   1% and 0.1% — not from the observed video distribution. Retune `Flagging.tsx:23-24`,
   `Contestants.tsx:308-310` and `generate_coverage.py:121-123` to the band cutoffs; today none
   of those thresholds is reachable. Fix `classify_quality`, whose last two branches both return
   `"weak"`.
9. **Delete the dead knobs** from `processing_config.yaml` and `face_detector.py`:
   `similarity_threshold`, `max_distance`, `high_confidence_threshold`, `confidence_decay`,
   `face_detection.min_confidence` (and `self.min_confidence` at `:191`).
10. **`recognition_config` reports what ran** — replace the hardcoded `"min_confidence": 0.5`
    (`metadata_generator.py:74`) with `acceptance_threshold` read from config, plus the band
    cutoffs applied, marked provisional.

## Context

- Blast radius for the array rename: `metadata_generator.py`, `worker/src/index.ts`,
  `useViewerMetadata.ts`, `local_api.py`, `generate_coverage.py`.
- `apps/shared/types/index.ts:31-35,53,69` carries the old contract in a comment and two type
  annotations. Update the comment to describe fractions, or the next reader re-derives this.
- **`video_info.width/height` stays the source dimensions** and becomes display-only. Nothing
  may divide by it. Grep for `video_info.width` after the change; it should have no arithmetic
  consumers left.
- Existing `local_output/metadata/*.json` are invalid. No migration — regenerate.
- **Leave a runnable check behind**: at minimum, assert every stored `bbox` value is within
  `[0,1]` after a reprocess, and that the four `_1080p` / `_720p` / source renditions all place
  the same box on the same face. That check is what catches a future rendition that letterboxes.
- **Verify visually before closing.** The whole point is boxes landing on faces. Screenshot the
  admin player on `test-video-mv2` and confirm, rather than trusting the numbers.
- Band cutoffs are **provisional**. Ground truth (ticket 006) revises them; the metadata must
  say they are provisional rather than presenting them as settled.
- Baseline to reproduce after the rewrite: 139 recognitions over 399 detections, cosines
  min 0.451 / median 0.508 / max 0.643. The recognition *set* must not change — only the
  representation. If the count moves, something other than the representation changed.
- Reprocess is ~2 min for the 30 s clip. Do not reprocess the 5 MVs here.

## Resolution

**Closed 2026-09-17.** Executed in full; one reprocess of `test-video-mv2` carries both
decisions. The pipeline, the worker, `local_api` and both React apps now speak one contract,
verified end to end in the admin player.

### The contract as landed

Stored (`local_output/metadata/<video>_metadata.json`) and served (worker, `local_api`,
`useViewerMetadata`) agree, and each per-detection entry everyone sees is:

```jsonc
{ "bbox": [0.414, 0.084, 0.619, 0.758],   // FRAME FRACTIONS, canonical [x1,y1,x2,y2]
  "match_score": 0.5416,                  // raw cosine; null when unmatched
  "det_score": 0.838,                     // detector's own score, on every detection
  "contestant_id": "33", "contestant_name": "黃敏蕎", "contestant_nickname": "阿妹",
  "tracker_id": 1, "matched": true }
```

`frame_data[].detections` carries all **399** (260 unmatched, `contestant_id: null`);
`processing_summary.confidence_stats` → `match_score_stats`; every cosine-named
`average_confidence`/`max_confidence`/`min_confidence` → `…_match_score`;
`recognition_config` reports `acceptance_threshold: 0.45` + the band cutoffs + `provisional`.

### Baseline reproduced

139 recognitions / 399 detections / 15 contestants / rate 0.3484 — **unchanged**. Cosines
min **0.4511** / median **0.5076** / max **0.6434** against the pinned 0.451 / 0.508 / 0.643.
Per-detection values differ in the fourth decimal (frame 0: 0.54159 now, 0.54249 decoded from
the old rescaled 0.16816) — run-to-run embedding noise from the CoreML provider, not a logic
change: the acceptance margin is identical and the recognition set is the same.

### Band cutoffs, measured

Leave-one-out over the 663-reference cache (94 contestants), impostor = max cosine against every
*other* contestant's references. The maxima sort 0.5846, 0.5846, 0.5014, 0.4616, 0.4616, 0.4509,
0.4509, then a step down to 0.4446. So:

- **high = 0.585** — zero impostor pairs at or above it.
- **medium = 0.451** — 7 of 663 pairs (1.06%) at or above; the acceptance threshold 0.45 sits
  just under it.

The 0.1% point is **below this sweep's resolution** (0.1% of 663 = 0.66 pairs), so `high` is
"no observed impostor", not a measured 0.1% boundary — the honest reading of the ask. A first
pass reported 0.447 from a percentile interpolation; that is not an observed score and was
corrected in the config, the metadata, the mock and the UI. Reproduce with
`mvp-processor/scripts/band_cutoffs.py`; both numbers are provisional until ticket 006.

### What the ticket did not know

1. **InsightFace emits boxes outside the frame** — e.g. `[0.875, -0.2225, 1.0547, 0.35125]`.
   `CONTEXT.md` says a fraction is 0–1, so boxes are clamped at the single conversion point
   (`detect_faces`) and one that clamps away to nothing is dropped. Found by the new check, not
   by reading code.
2. **ByteTrack now activates on `det_score`.** Its activation threshold is 0.25 and it was fed
   the rescaled confidence (0–0.35, mostly below), so most detections never activated a track.
   `tracker_id` coverage changes; the recognition set does not.
3. **`generate_coverage.py` was doubly broken** — it looked contestants up by *nickname* in a
   timeline keyed by contestant number (every lookup missed, so `detection_count`/`avg` were
   always 0) and read a `recognition_summary` key nothing writes. Both fixed; the snapshot is
   regenerated against `local_output/metadata` (21 good / 73 weak / 2 missing, avg cosine
   **0.5066** where the old rescaled average read 0.354). Metadata written before this contract
   is now skipped loudly instead of being averaged in — two such files sit beside the
   reprocessed one.
4. **`.gitignore`'s bare `lib/` (Python template) silently ignored `apps/shared/lib/bands.ts`** —
   the band helper would never have been committed, and the deployed build would have broken on
   a file that exists only on this Mac. Re-included `apps/*/lib/` and `worker/src/lib/` (a new
   file there was equally invisible).
5. The **flag record keeps a field named `confidence`**, now carrying the raw cosine. Deliberate:
   015 leaves flagging untouched and 005 decides the labelling schema. It is the only surviving
   cosine under that name, and `types/index.ts` says so.

### Deleted with the render path

`supervision_annotator.py` and its test, the `annotated_video:` config section, `--no-annotate`
and `ProcessRequest.no_annotate`, `local_api`'s `_annotated.mp4` stream candidate, `bbox_scale`,
`screen_time`, `ignore_face_size`-era dead knobs (`similarity_threshold`, `max_distance`,
`high_confidence_threshold`, `confidence_decay`, `face_detection.min_confidence`), and the
`[t,r,b,l]` round trip at all four sites.

### Verification

- **`mvp-processor/tests/unit/test_metadata_contract.py` (new, 6/6)** — every stored box is a
  fraction in range with positive extent; no deleted key survives; every detection stored with
  both scores and unmatched ones carrying no match score; timeline ≡ frame_data; every rendition
  keeps the source aspect ratio; **and the same stored box crops the same pixels out of the
  source, the 1080p and the 720p rendition** (worst disagreement 7.18 of 255 — re-encode noise).
- **Visual** — admin player on `test-video-mv2` through `local_api`, two timestamps: a green box
  labelled "房婷婷 medium" on a face at 0.56 cosine, and "余潔瀅 high" at 0.59 on another. Boxes
  land on faces with band labels and the cosine in the tooltip. Before 008 the box rendered at
  half size; before 013 no score could render above 35%.
- **Tests** — `mvp-processor`: 85 passed, 8 failed, and the 8 are exactly the pre-existing
  `test_frame_optimizer` / `test_video_processor` failures `TODO.md` already records.
  `tests/contract`: 37/37.
- **Typechecks** — `tsc --noEmit` clean in `worker`, `apps/shared`, `apps/viewer`, `apps/admin`.

### Loose ends, deliberately not resolved here

- `worker/src/index.ts.backup` — a 91 KB tracked stale copy of the worker, not compiled and
  imported by nothing, still carrying the deleted names. Left in place: tracked content nobody
  asked me to delete. It will keep polluting greps.
- `local_output/processed_videos/test-video-mv2_annotated.mp4` (91 MB) and the repo-root
  `processed_videos/` (708 MB of `_annotated.mp4`) are still on disk; 007's open question 4
  decides their fate.
- The worker's fabricated `processed_videos_list` fallback still names `_annotated.mp4` (007),
  and `worker/src/api/modal.js`'s `--similarity-threshold` stays (Modal revival is out of scope
  on the map).
- Nothing is committed: the tree carries this ticket's changes alongside the user's own
  in-flight edits.

