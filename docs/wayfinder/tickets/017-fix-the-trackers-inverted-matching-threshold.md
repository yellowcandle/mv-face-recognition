---
id: 017
title: Fix the tracker's inverted matching threshold
label: wayfinder:task
mode: AFK
blocked_by: []
status: closed
assignee: claude
---

## Question

Nothing to decide — `tracker_id` in the stored metadata is near-useless and the reason is one
setting whose meaning is inverted. Surfaced while resolving *Choose the ground-truth labelling
means*, which wanted it as a bulk-labelling shortcut.

## What was measured

On the reprocessed `test-video-mv2` (399 detections, 187 frames):

| | tracks | one-frame tracks | detections with no track at all | longest track |
|---|---|---|---|---|
| shipped (`minimum_matching_threshold: 0.3`) | 119 | 111 | 270 | 4 |
| library default (`0.8`) | 42 | 7 | — | 19 |

## Why

`sv.ByteTrack(minimum_matching_threshold=…)` is passed to `linear_assignment(1 - IoU, threshold)`,
so it is a **cost** ceiling, not a quality floor: `0.3` accepts only pairs with **IoU ≥ 0.7**,
while the default `0.8` accepts IoU ≥ 0.2. The name reads as "require 30% match quality" and
does the opposite — the same class of inversion as the `tolerance`/cosine mixup that `CONTEXT.md`
was written to end. At 6 fps a face moves further than 0.7 IoU between samples (mean best-IoU to
the next frame's faces: 0.40), so almost every detection starts a fresh track.

## Change

Set `minimum_matching_threshold` where the association actually works, and say in a comment what
it means (a cost ceiling on `1 - IoU`). The tracker factory lives in
`mvp-processor/src/process_video.py` (`_create_tracker`). Re-measure rather than trusting 0.8:
try 0.5 / 0.8 / 0.9 and report tracks, one-frame tracks and untracked detections for each.

## Context

- **Nothing consumes `tracker_id` yet** — it is stored metadata only (the render path that traced
  tracks was deleted in ticket 014). So this is cheap now and matters the moment labelling wants
  to apply one verdict to a whole run of frames.
- **A false alarm worth not repeating:** the assignment *looked* misaligned because
  `update_with_detections` returns a *filtered* Detections while mutating the input's
  `tracker_id` in place. Replaying the stored boxes through the same tracker reproduced the stored
  ids on **all 187 frames, zero differences** — the alignment is correct. Verify before fixing.
- Reprocessing is ~3 min detect+recognize plus ~7.5 min transcoding for this 30 s clip.
- Not a blocker for *Choose the ground-truth labelling means*: per-detection labelling needs no
  tracks at all.

## Resolution

**Closed 2026-09-21.** One setting, measured rather than assumed, and the clip reprocessed so the
stored `tracker_id`s match the config that produced them.

### The measurement (replaying the stored detections through the tracker)

| threshold | IoU required | tracks | one-frame | untracked | longest | mean length |
|---|---|---|---|---|---|---|
| **0.3** (shipped) | 0.7 | 119 | 111 | 270 | 4 | 1.08 |
| 0.5 | 0.5 | 81 | 48 | 221 | 16 | 2.20 |
| **0.8** (chosen) | 0.2 | **42** | **7** | **162** | **19** | 5.64 |
| 0.9 | 0.1 | 36 | 3 | 144 | 20 | 7.08 |

**0.8** — the library default — with the cost-ceiling semantics written into the factory's
docstring so the inversion is not rediscovered: the value goes to
`linear_assignment(1 - IoU, threshold)`, so 0.8 accepts IoU ≥ 0.2 while the old 0.3 accepted only
IoU ≥ 0.7. 0.9 buys 6 more tracks for far more aggressive merging (IoU 0.1 across a cut can join
two different people), so the default wins on the boring-is-safe reading.

The replay **predicted the pipeline's output exactly**: 237 of 399 detections would carry an id,
and the reprocess produced 237, with 42 tracks, 7 one-frame and longest 19. That is the check that
the offline measurement and the pipeline agree.

### What did not change

139 recognitions over 399 detections, 15 contestants, cosines min 0.4511 / max 0.6434 — the
tracker cannot touch matching, and the recognitions are identical to the 014 run.

### What the better tracks are, and are not

- 162 detections still carry **no track at all** — an artefact of `update_with_detections`
  re-associating at a fixed IoU 0.5 internally, which `minimum_matching_threshold` does not reach.
- **2 of the 42 tracks claim two different contestants** across their frames (track 1: Jackie and
  阿妹; track 55: Day and Sinnie), and **9 contestants are spread over 2–4 tracks** because a
  track breaks at every cut.

So a track is a **labelling shortcut with a review step, never the unit of truth** — which is
exactly what *Choose the ground-truth labelling means* decided (labels are per detection). Both
facts are now written into *Build the crop-grid labeller and the labels file*, which asks for an
apply-to-track action with an "apply to the N frames of this track" confirmation.

### The false alarm, not repeated

The ticket carried a warning that the id assignment once *looked* misaligned. It was: the earlier
check replayed the stored boxes and reproduced every stored id on all 187 frames with zero
differences, before any change was made. Verify before fixing; this ticket changed one constant.

### Also refreshed

- `local_output/metadata/test-video-mv2_metadata.json` and the galleries, via one reprocess
  (~3 min detect + ~7.5 min transcoding). Free of label cost: `labels/v1` does not exist yet.
- `apps/admin/public/data/coverage.json` + `data/coverage.json` regenerated (7 good / 87 weak /
  2 missing, average match score 0.5066 — unchanged, as scores are unaffected).
- The labelling prototype's data was rebuilt from the new run so the artifact the user approved
  does not carry stale track counts (119 → 42; it had said track mode was unusable, which is no
  longer true).

### Verification

`mvp-processor/tests/unit/test_metadata_contract.py` 6/6 on the reprocessed clip — box fractions
in range, no deleted key, both scores on every detection, timeline ≡ frame_data, rendition aspect
ratios, and the same box cropping the same face out of the source, 1080p and 720p renditions.

