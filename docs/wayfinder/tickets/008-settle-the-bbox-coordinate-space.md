---
id: 008
title: Settle the bbox coordinate space
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: open
assignee:
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
