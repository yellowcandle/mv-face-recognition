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

Done when each MV has ~30 claimed tracks labelled and the result is recorded against the gate
(decided 2026-11-09): **pooled precision ≥95% across the five MVs (point estimate)** passes.
Report per-MV figures and the Wilson CI (not gated). Precision = correct / (correct + misnamed +
impostor); `unsure` (mixed tracks included) and `box_wrong` are counted separately. Report the random
draws separately, outside the gate. A miss is a reference/threshold problem; impostors count as wrong
and have no separate gate. Tolerance: about 160 counted claims (126 + 34), so at most 8 misses keep
it at >= 95%; 6 are already found.

## Context

- The batch runs at `acceptance_threshold: 0.412`, bands `0.445 / 0.412` (commit `757741c7`).
- Claimed tracks still unlabelled: MV #1 186, MV #2 187, MV #3 465, MV #4 194, MV #5 168. These
  are where a false match can exist — an unclaimed track cannot be an impostor.
- The cards title their claim (`matcher claim: …`); tick **Claimed only (cosine first)** to filter
  the grid to claimed tracks in descending cosine order, and the **Accept matcher's claim** button
  records a true match in one click — only the wrong ones need picking manually.
- Evidence so far: 0 impostors across MV #3/#4/#5 and test-video-mv2; matched means 0.499–0.598.
  test-video-mv2 ran at 0.45 and is **not** part of this sample.
- MV #1's `_1080p.mp4` was corrupt (`moov atom not found`): fixed locally (rebuilt 2026-11-01,
  readable at 264.5 s). Whether the R2 copy is the rebuilt file is unchecked until the next
  `upload-to-r2`.
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

Wilson 95% CI [90.0%, 97.8%]; 95.2% currently meets the point-estimate bar, and the top-up
brings each reel to ~30.

Top-up: 54 tracks in `local_output/labelling/ticket-020-sample.json`: cosine-first to ~30 a reel
(MV #1 +3, MV #3 +19, MV #4 +2, MV #5 +10), plus 20 tracks drawn at random (seed 20261106) from the
57 unlabelled MV #1 tracks whose name differs from the 2026-11-01 run. Those 20 say what the new
names on MV #1 are worth, so report them on their own. Each reel's `url` opens its tracks.

Random draw (2026-11-09, seed 20261109): 10 claimed tracks per reel, drawn over all claimed tracks,
in `random_draw` per reel in the same file. 8 of the 50 already have labels, which are reused; 42
are left to label (reel 1: 9, reel 2: 7, reel 3: 10, reel 4: 9, reel 5: 7). Reel 5's track 411
is also in its top-up. Each reel's `random_draw_url` opens the unlabelled ones on the deployed
admin. Reported separately; it measures the 0.412 threshold.

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
precision), not a guessed contestant. A track that mixes two contestants (ticket 017) is also
**unsure** (decided 2026-11-09).

**Reference coverage (refreshed 2026-11-03, 638 refs / 94 of 96 contestants).** Contestants **67
and 77 have zero references**; 12 have fewer than 3, including **47 (1 ref)** and **83 (2 refs)** —
both appear as the matcher's misnamed claims above. Thin references are the probable lever, not the
acceptance threshold.

## Then

If the sample passes: it confirms precision on the top-scoring claims only. 0.412 stays provisional
until the random draw is reported and is not clearly worse; recompute the 0.445 split from the video-face
labels at that point. If it fails on misnamed or impostor claims, curation is the lever (the 6 misses
so far are all look-alikes).
