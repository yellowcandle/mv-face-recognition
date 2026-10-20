---
status: accepted
---

# Face boxes are frame fractions, in canonical [x1,y1,x2,y2] order

A stored face box is **four fractions of the frame**, `[x1, y1, x2, y2]`, each in 0–1, under the
field name `bbox`. No consumer scales by any width or height: rendering is
`left = offsetX + x1 * renderW`. There is no coordinate space to know, declare, or agree on.

## Considered options

- **Source space (3840).** Rejected: it still leaves a width every reader must match correctly,
  and `video_info.width` disagrees with the MP4 actually served (2592).
- **Declare `detection_width/height` in metadata and have consumers read it.** Rejected: a field
  three codebases must remember to read, where staleness is a silent wrong-scale bug rather than
  a loud failure. This project has already lost two tickets to a number whose meaning had to be
  known out of band (`tolerance` vs cosine, `min_confidence` as a second gate).
- **Publish a 1920-wide rendition so pixel coords match by construction.** Rejected: it changes
  the encoding ladder to serve the storage format, and it is implicit correctness — it breaks
  the day someone publishes a different resolution.
- **Frame fractions.** Chosen.

## Consequences

- **Five widths were in play, and no two agreed.** Source is 3840×1600 for MVs 1/2/3 and
  test-video-mv2 but **1920×1080 for MVs 4 and 5**; detection space is 1920×800 or 1920×1080
  depending on which; `_1080p.mp4` is 2592×1080; `_720p.mp4` is 1728×720. A single declared
  width could never have covered the set. Fractions are per-video and self-describing.
- **This is sound only because the ladder preserves aspect ratio.** 3840×1600 → 2592×1080 →
  1728×720 is 2.4:1 throughout; 1920×1080 → 1280×720 is 16:9 throughout. If a future rendition
  ever letterboxes or crops, fractions break silently — that is the one assumption this decision
  rests on, and it belongs in any review of the encoding settings.
- **Four conversions delete.** `face_detector.py:230` was converting InsightFace's native
  `[x1,y1,x2,y2]` into `(top,right,bottom,left)` to match the `face_recognition` library's
  convention — a library no longer used — and `local_api.py:352`, `worker/src/index.ts:1086` and
  `useViewerMetadata.ts:66` each converted it back. Internal Python that works in pixels
  (`frame_optimizer.py` IoU, tracking) keeps pixels; the conversion happens once, at the
  metadata write boundary.
- **`video_info.width/height` stays the source dimensions** and stops being load-bearing. It is
  display metadata now, not a scale factor. Nothing may divide by it.
- **Existing metadata files are invalid** and must be regenerated. There is no migration path
  and none is warranted: `local_output/` is derived output, and the reference-embedding
  migration (ADR 0001) had already invalidated every run.
- **`frame_data[].detections` now carries every detection**, matched or not, with
  `contestant_id: null` when unmatched. Previously only the 139 matched of 399 were stored, so
  no consumer could see — or click — a face the matcher missed or got wrong. Hand-labelling
  ground truth depends on this.
