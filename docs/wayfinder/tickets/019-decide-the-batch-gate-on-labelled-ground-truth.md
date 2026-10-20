---
id: 019
title: Decide the batch gate on labelled ground truth
label: wayfinder:grilling
mode: HITL
blocked_by: [006]
status: open
assignee:
---

## Question

With `test-video-mv2` labelled, does the matching clear the gate — and does the full batch of five
MVs proceed?

The map's gate, settled while charting: **matched-face cosine mean ≥ 0.45 while cross-person stays
≤ 0.2**, against a measured baseline of mean 0.206 / max 0.510. Recognition *rate* was explicitly
rejected as the measure, because it cannot distinguish right answers from confident wrong ones.

## What the labels make answerable for the first time

- **The real separation.** Each labelled detection is either a true match (its cosine joins the
  matched distribution) or an impostor the matcher named anyway (its cosine joins the cross-person
  distribution, instead of being invisible). The leave-one-out sweep that set the current cutoffs
  measured *reference photos* against each other; this measures *video faces* against the reference
  set, which is the quantity that decides the batch.
- **Whether the acceptance threshold moves.** 0.45 was chosen to sit on the leave-one-out 1%
  false-match boundary (0.451). Labelled data either confirms that or moves it.
- **Whether the band cutoffs survive.** They are stamped `provisional: true` in every metadata file
  and recomputed by `mvp-processor/scripts/band_cutoffs.py`; ground truth is what makes them real,
  or replaces them.
- **How wrong the matcher is, and how.** The four verdicts split the failure into *named a
  stranger* (impostor), *left a real contestant unnamed*, and *box is wrong* — only the first is a
  matching problem, and the third is the detector's.

## Decisions this ticket owns

1. Does the gate pass on labelled ground truth — and if it fails, is the fix references, threshold,
   or the matcher itself?
2. Proceed to reprocessing the remaining MVs (1, 2, 3, 5) — all, or only the ones whose content
   resembles the labelled clip?
3. Which compute: local Apple Silicon or reviving Modal. The measured wall time for the 30 s clip
   is ~3 min detect+recognize plus ~7.5 min transcoding, and it does *not* extrapolate to MVs
   1/2/3 (3840×1600) — MV #4 and MV #5 are 1080p.
4. Whether the bands and acceptance threshold are written into config as settled (dropping
   `provisional`) or stay flagged.

## Context

- 30 seconds is the labelled scope on purpose (*Label 30 seconds of test-video-mv2*): resist
  labelling more until this gate says the labelling was worth it.
- Reference-photo curation ("How far does curation go") hangs on the answer here: if the gate
  fails on impostors, curation is the lever; if it fails on misses, curation will not help.
- A reprocess invalidates labels — `labels/v1` pins `source.processing_date`, so any
  re-run must be labelled again or shown to be box-for-box identical.
