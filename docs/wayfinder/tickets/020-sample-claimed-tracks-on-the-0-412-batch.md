---
id: 020
title: Sample claimed tracks on the 0.412 batch
label: wayfinder:task
mode: HITL
blocked_by: []
status: open
assignee: omp
---

## Question

Label ~30 claimed tracks per MV (highest cosine first) to measure precision at the 0.412 acceptance
threshold. Only the user can identify the faces.

Done when each MV has ~30 claimed tracks labelled, per-MV precision is computed (correct claims /
claims sampled), and the result is recorded against the gate: **≥95% correct claims and no impostor
above 0.2** passes; a miss is a reference/threshold problem, an impostor is the matcher's.

## Context

- The batch runs at `acceptance_threshold: 0.412`, bands `0.445 / 0.412` (commit `757741c7`).
- Claimed tracks still unlabelled: MV #1 186, MV #2 187, MV #3 465, MV #4 194, MV #5 168. These
  are where a false match can exist — an unclaimed track cannot be an impostor.
- The cards title their claim (`matcher claim: …`); tick **Claimed only (cosine first)** to filter
  the grid to claimed tracks in descending cosine order, and the **Accept matcher's claim** button
  records a true match in one click — only the wrong ones need picking manually.
- Evidence so far: 0 impostors across MV #3/#4/#5 and test-video-mv2; matched means 0.499–0.598.
  test-video-mv2 ran at 0.45 and is **not** part of this sample.
- **MV #1's `_1080p.mp4` is corrupt** (`moov atom not found`). The crop endpoint now falls back to
  the intact 720p so labelling works, but the Viewer still serves the broken 1080p — re-transcode
  MV #1 separately.
- A reprocess invalidates labels (`labels/v2` pins `source.processing_date`); if an MV is
  reprocessed, its sample is void and must be redone.

## Current sample (2026-11-06)

This replaces the 2026-11-01 table below. All five MVs were reprocessed. The sample is not void:
`carry_labels.py` moved every label onto the new runs, and each labelled track came across whole
(coverage 1.0, no boxes from another track). The local files and Worker KV held different labels,
now merged: 207 in total, 126 of them on claimed tracks with a verdict.

| MV | claimed | sampled | correct | misnamed | impostor | precision |
|---|---:|---:|---:|---:|---:|---:|
| #1 | 238 | 27 | 25 | 2 | 0 | 93% |
| #2 | 189 | 40 | 37 | 3 | 0 | 93% |
| #3 | 465 | 11 | 11 | 0 | 0 | 100% |
| #4 | 193 | 28 | 27 | 1 | 0 | 96% |
| #5 | 167 | 20 | 20 | 0 | 0 | 100% |
| all | 1,252 | 126 | 120 | 6 | 0 | 95.2% |

Wilson 95% CI [90.0%, 97.8%], so the 95% bar is still not resolved.

Top-up: 54 tracks in `local_output/labelling/ticket-020-sample.json`: cosine-first to ~30 a reel
(MV #1 +3, MV #3 +19, MV #4 +2, MV #5 +10), plus 20 tracks drawn at random (seed 20261106) from the
57 unlabelled MV #1 tracks whose name differs from the 2026-11-01 run. Those 20 say what the new
names on MV #1 are worth, so report them on their own. Each reel's `url` opens its tracks.

## Earlier sample (2026-11-01)

92 claimed tracks sampled across the five MVs: **87 correct, 5 misnamed, 0 impostors** → 94.6%
(Wilson 95% CI [87.9%, 97.7%], so the 95% bar is not yet resolvable). Four MVs are under the ~30
target; MV #2 is done.

| MV | sampled | correct | misnamed | impostor | precision |
|---|---:|---:|---:|---:|---:|
| #1 | 12 | 11 | 1 | 0 | 92% |
| #2 | 34 | 32 | 2 | 0 | 94% |
| #3 | 11 | 10 | 1 | 0 | 91% |
| #4 | 19 | 18 | 1 | 0 | 95% |
| #5 | 16 | 16 | 0 | 0 | 100% |

Top-up to ~30/MV: MV #1 +18, MV #3 +19, MV #4 +11, MV #5 +14 (≈62 more). Tick **Claimed only** +
**Unlabelled only**; the grid is already cosine-first.

The 5 misnamed claims are all high-cosine look-alikes (0.577–0.718), so the acceptance threshold is
not the lever — curation is: (#1 t321 3→15), (#2 t71 91→81), (#2 t72 83→91), (#3 t106 47→92),
(#4 t636 5→44).

**Legibility.** Crops now prefer the 1080p, then the **source before the 720p** (MV #1's 1080p is
corrupt), and the sheet renders at **512px**. All five misnamed faces are legible at 512px, so they
are genuine look-alike calls, not pixelation — but re-judge any the old 320/160px crop made
ambiguous; if the crop genuinely cannot decide it, the verdict is **unsure** (excluded from
precision), not a guessed contestant.

**Reference coverage (refreshed 2026-11-03, 638 refs / 94 of 96 contestants).** Contestants **67
and 77 have zero references**; 12 have fewer than 3, including **47 (1 ref)** and **83 (2 refs)** —
both appear as the matcher's misnamed claims above. Thin references are the probable lever, not the
acceptance threshold.

## Then

If the sample passes: recompute the bands from video-face labels and drop `provisional`. If it fails
on impostors, curation is the lever; if on misses, curation will not help.
