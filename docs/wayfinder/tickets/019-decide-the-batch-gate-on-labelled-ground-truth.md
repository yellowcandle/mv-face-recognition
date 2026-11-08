---
id: 019
title: Decide the batch gate on labelled ground truth
label: wayfinder:grilling
mode: HITL
blocked_by: [006]
status: closed
assignee: omp
---

## Question

With `test-video-mv2` labelled, does the matching clear the gate — and does the full batch of five
MVs proceed?

The map's gate, settled while charting: **matched-face cosine mean ≥ 0.45 while cross-person stays
≤ 0.2**, against a measured baseline of mean 0.206 / max 0.510. Recognition *rate* was explicitly
rejected as the measure, because it cannot distinguish right answers from confident wrong ones.

## What the labels make answerable for the first time

- **The real separation.** Each labelled track is either a true match (its representative
  detection's cosine joins the matched distribution) or an impostor the matcher named anyway (its
  cosine joins the cross-person distribution, instead of being invisible). The leave-one-out sweep
  that set the current cutoffs
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
- A reprocess invalidates labels — `labels/v2` pins `source.processing_date`, so any
  re-run must be labelled again or shown to be box-for-box identical.

## Resolution (2026-11-01)

Decided with the user on the live label data, not the ticket's original premises.

**What the data showed.** The batch runs at `acceptance_threshold: 0.412` (commit `757741c7`,
bands `0.445 / 0.412`); test-video-mv2 is the only file still at the old `0.45` (processed before
that commit), so its 35 clean labels cannot validate the 0.412 batch. Across the fresh labels —
MV #3 10, MV #4 77, MV #5 3, test-video-mv2 35 — there were **0 impostors**: every
`not_a_contestant` verdict landed on a track the matcher never named (spot-checked on MV #4: 66 of
66 unclaimed). Matched-side means sat 0.499–0.598. The labels prove the matcher's *claims* are
clean, but they are skewed to unclaimed tracks, so the cross-person side at 0.412 is still
unmeasured.

**Decisions.**

1. **Gate rule replaced.** The ≥3-impostor rule is a sampling proxy a clean matcher cannot satisfy.
   Measure precision over **claimed** tracks instead: label **~30 claimed tracks per MV, highest
   cosine first**, and pass at **≥95% correct claims** with no impostor above the 0.2 cross-person
   line. The *Accept matcher's claim* button makes the true ones one click. Revised 2026-11-09 (ticket 020): the bar is the point estimate; the 0.2 impostor clause is dropped.
2. **test-video-mv2 retired as the gate** — a 30 s clip at the old threshold; its 35 labels stay on
   disk and remain valid for their run.
3. **MV #1 stale labels cleared.** It was reprocessed 2026-11-01T00:03; its 11 labels pinned the
   2026-10-21 run and now 409. Renamed to `…_labels.json.stale-20261021` (recoverable) so the new
   run is labelable.
4. **Bands/threshold stay `provisional`** until the claimed-track sample lands, then recompute from
   video-face labels, not just the reference-photo leave-one-out.
5. **No reprocess / no compute decision needed** — all five MVs are already at 0.412 (MV #1 was
   reprocessed locally today).

**Follows**: *Sample claimed tracks on the 0.412 batch* (ticket 020).
