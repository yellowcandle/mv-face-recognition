---
id: 008
title: Settle the bbox coordinate space
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: closed
assignee: claude
---

## Question

Which coordinate space do stored face boxes live in, and how does a consumer know?

Today two consumers disagree, so overlay buttons drift from drawn boxes. Pick one contract and
make it explicit.

- **(a)** Publish 1920-wide video so stored coords match the frame as served.
- **(b)** Store coords in source space (3840) and scale at write time.
- **(c)** Record the space explicitly in metadata and have every consumer read it.

## Context

- `process_video.py:317-318` computes `bbox_scale = orig_width / detect_width` where
  `detect_width = config.video.resize_width = 1920` (`processing_config.yaml:6`), and applies
  it **only** when writing the annotated MP4 (`:358`). The JSON keeps unscaled 1920-space
  coords while `video_info.width` says 3840.
- `FaceOverlay.tsx:30-31` scales by `videoMetadata.video_info.width` (3840) → boxes at ~half
  size, top-left biased. `useAnnotations.ts:75-79` scales by `video.videoWidth` (whatever MP4
  is served) → correct only when that MP4 is 1920 wide.
- **(a) is nearly free given decisions already made**: `_1080p.mp4` is 1920 wide, so
  publishing it makes stored coords correct by construction. It also kills the double-box
  problem, since `_annotated.mp4` has boxes burned into pixels that the JS layer then redraws
  on top of, and `showAnnotations` can only hide the JS layer.
- But (a) is *implicit* correctness — it breaks silently the day someone publishes a
  different resolution. Weigh that against (c)'s explicitness.
- The wire contract is documented at `apps/shared/types/index.ts:31-35`: stored
  `face_location` is `[top, right, bottom, left]`, converted to canonical `[x1,y1,x2,y2]` at
  every serving boundary (`useViewerMetadata.ts:64-66`, `worker/src/index.ts:1082-1084`,
  `local_api.py`). This ticket concerns the *scale*, not that ordering — do not disturb it.
- `TODO.md:20` already wants a shared `projectBbox` helper because these two call sites
  duplicate the projection with different dimension sources. Folding that in is probably the
  smaller diff.
- **Blocks labelling** (ticket 005): the clickable boxes are unusable at half size.

## Resolution

**Settled 2026-09-09.** Stored boxes become **frame fractions in canonical `[x1,y1,x2,y2]`
order**, under the field name `bbox`. No consumer scales by any width; `scaleX = renderW`.

### The ticket's own option (a) was based on a false premise

(a) proposed "publish 1920-wide video so stored coords match the frame as served". Measured:

| space | dimensions | who holds it |
|---|---|---|
| source (MV 1/2/3, test-video-mv2) | 3840 × 1600 (2.4:1) | `video_info.width` |
| source (MV **4**, MV 5) | 1920 × 1080 (16:9) | `video_info.width` |
| detection | 1920 × 800 *or* 1920 × 1080 | what `face_location` was stored in |
| published `_1080p.mp4` | **2592** × 1080 | what the viewer plays |
| `_720p.mp4` | 1728 × 720 | alt rendition |

No rendition is 1920 wide — the ladder scales by height, so a 2.4:1 source yields 2592×1080.
And **MV #4, the MVP video, is 16:9 while test-video-mv2 is 2.4:1**, so detection height differs
per video. A single declared width was never going to hold.

Aspect ratio *is* preserved down the whole ladder in both families, which is what makes
fractions valid across source, 1080p and 720p alike.

### Both consumers were wrong, not one

- `FaceOverlay.tsx:30` divided by `video_info.width` = 3840 → boxes at **50%**.
- `useAnnotations.ts:78` divided by `video.videoWidth` = 2592 → boxes at **74%**.

Correct denominator was 1920 in both. Neither used it. No serving boundary ever scaled —
`local_api.py:352`, `worker/src/index.ts:1086` and `useViewerMetadata.ts:66` only reordered.

### Decisions

1. **Space — frame fractions (0–1).** Rejected: source space (still leaves a width every reader
   must match, and `video_info.width` disagrees with the served MP4); declared
   `detection_width/height` in metadata (a field three codebases must remember to read, stale =
   silent wrong scale); a 1920-wide rendition (changes the ladder to serve the storage format).
   Fractions make the bug class *structurally impossible* across every present and future
   rendition. See [ADR 0002](../../adr/0002-face-boxes-are-frame-fractions.md).
2. **Order — canonical `[x1,y1,x2,y2]`, field renamed `bbox`.** `face_detector.py:218-230` was
   taking InsightFace's *native* `[x1,y1,x2,y2]` and converting it to `(top,right,bottom,left)`
   to honour the `face_recognition` library's convention — a library this project no longer
   uses — after which three boundaries converted it back. Four conversions delete. The contract
   at `types/index.ts:31-35` existed to stop readers reordering *twice*; honouring its intent
   means removing the reorder, not preserving it.
3. **`frame_data[].recognitions` → `detections`, carrying all 399.** Only 139 of 399 detections
   had a stored box; the 260 unmatched had none anywhere, so a labeller could not click a face
   the matcher got wrong. Unmatched entries carry `contestant_id: null`. The rename is forced by
   `CONTEXT.md`, which already reserves *recognition* for a matched detection — putting
   detections in an array called `recognitions` re-introduces the exact collision the glossary
   was written to end. Rejected: two parallel arrays (duplicates every box, two things to sync).
4. **`_annotated.mp4` is dropped.** It was the only consumer of `bbox_scale`
   (`process_video.py:322`). The map already ruled it is never published, and the JS overlay is
   strictly better for review because it toggles.

### Consequences

- One reprocess of `test-video-mv2` covers all four changes. 012 already invalidated the
  existing run, so the marginal cost is ~2 min.
- Implementation is **[Rewrite the metadata contract](014-rewrite-the-metadata-contract.md)**,
  which now blocks *Choose the ground-truth labelling means* in this ticket's place.
- Overlaps *Settle what match confidence means on the wire* (013): same file, same write path,
  same reprocess. Not wired as a dependency — either order works, batching them saves one run.
