---
id: 013
title: Settle what match confidence means on the wire
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: closed
assignee: claude
---

## Question

`match_confidence` is stored in every metadata file and rendered in both apps, but it is not a
cosine and not comparable between runs. What should be on the wire?

- **(a)** The raw cosine match score. Matches `CONTEXT.md`, comparable across runs and configs.
- **(b)** Keep the normalised 0–1 value, but derive it from a *fixed* reference point rather
  than from `tolerance`.
- **(c)** Store both: cosine as the truth, a normalised value for display.

## Context

Surfaced 2026-09-08 while reprocessing `test-video-mv2` after the matcher migration.

- `face_detector.py:333` computes `confidence = 1 - (min_distance / self.tolerance)`. It is
  **tolerance-relative**, so the same face at the same cosine gets a different confidence
  whenever the threshold moves. The stored numbers in `local_output/metadata/*.json` are
  therefore not comparable across runs, and a reader has to know that run's tolerance to decode
  them.
- This directly contradicts `CONTEXT.md`, which defines **match score** as a cosine where higher
  is more similar, and warns against exactly this kind of inverted, rescaled quantity — the same
  class of confusion as the `tolerance` / cosine mixup.
- **It had a real consequence.** `process_video.py:257` hardcoded `min_confidence=0.15` as a
  second gate. Because confidence is tolerance-relative, that constant silently set the true
  acceptance bar to `1 - (1-0.15)×tolerance`: cosine **0.5325** under tolerance 0.55, not the
  **0.45** settled in *Choose the matching strategy*. It also moved whenever tolerance moved.
  Fixed by dropping the second gate (`min_confidence=0.0`) so the configured tolerance is the
  single acceptance threshold — measured effect on `test-video-mv2`: 48 recognitions → 139, and
  the observed minimum cosine landed exactly on 0.451.
- **Three values disagree about the same knob**: `processing_config.yaml`
  `face_detection.min_confidence: 0.5`, `metadata_generator.py:74` writing
  `"min_confidence": 0.5` into every metadata file, and the call site that actually ran with
  `0.15`. The metadata therefore *misreports the config it was produced under*.
- Consumers of the stored value: `metadata_generator.py:171-189,282`, the Player's detection
  bar and overlays, `generate_coverage.py`'s `avg_confidence` / `max_confidence` and its
  `classify_quality` thresholds (0.4 / 0.25), which are tuned against the old rescaled numbers
  and will mean something different if this changes.

Whatever wins, `recognition_config` in the metadata must record the values actually used, not a
constant copied from elsewhere.

## Resolution

**Settled 2026-09-09.** The wire carries the **raw cosine**, under the field name `match_score`.
`match_confidence` is deleted, not rescaled.

### What the stored numbers actually were

Decoding `local_output/metadata/test-video-mv2_metadata.json` back through
`cos = 1 − tolerance × (1 − confidence)` at tolerance 0.55, over 139 recognitions:

```
min 0.451   p25 0.477   median 0.508   p75 0.545   p90 0.586   max 0.643
stored as:  0.001       0.052          0.119       0.173       0.247      0.352
```

**A face matched at cosine 0.643 rendered as "35%".** Every downstream threshold is calibrated
against a scale the data cannot reach:

- `Flagging.tsx:23-24` (green ≥0.8, amber ≥0.6) needs cosine **0.89** to go green. **No
  recognition could ever be anything but red.** Same for `Contestants.tsx:308-310` (>0.85/>0.7).
- `generate_coverage.py:121-123` gates good ≥0.4 / weak ≥0.25 against a mean of 0.119, so
  confidence never decided anything and `detection_count` silently did all the work. That
  function also returns `"weak"` from both remaining branches, so the 0.25 test is dead code.
- The map's gate is written in cosine (*matched mean ≥0.45, cross-person ≤0.2*) and could not be
  read off the metadata without knowing that run's tolerance and inverting it.

### Decisions

1. **Wire value: raw cosine, field renamed `match_score`.** `CONTEXT.md` already defines **match
   score** as a cosine where higher is more similar, and already lists *confidence* under
   _Avoid_ — `match_confidence` had been violating the project's own glossary since it was
   written. Rejected: a normalised value from a fixed reference point (still a magic constant a
   reader must know); storing both (two numbers that can drift apart).
2. **Collapse the three confidence fields to one.** `types/index.ts:38,42,43` declares
   `confidence`, `detection_confidence` and `recognition_confidence`; all three boundaries
   (`local_api.py:357-358`, `worker/src/index.ts:1091-1092`, `useViewerMetadata.ts:71-72`) assign
   the *same* value to all three. Pure duplication — collapsing loses nothing.
3. **Display: bands, not a percentage**, with the raw score in the tooltip. A cosine shown as
   "64%" reads as *64% sure*, which it is not. Rejected: rescaling for display only — that
   reintroduces the tolerance-relative rescale one layer down.
4. **Band cutoffs come from measured impostor rate**, not from this distribution. The observed
   cosines are bunched against the 0.45 bar and unlabelled, so cutting them into thirds would
   only describe their own shape. Instead run leave-one-out on the reference cache (machinery
   012 already built) and set boundaries where the measured false-match rate crosses 1% and 0.1%.
   **Provisional, and the metadata must say so** — ground truth (ticket 006) revises them.
5. **Store `det_score` on every detection.** It is currently loaded into `self.min_confidence`
   (`face_detector.py:191`) and never read, and never reaches the wire. Ticket 014 is already
   writing all 399 detections including unmatched ones, where the detector score is the **only**
   score they have — without it an unmatched box on screen carries no number at all. The 0.6
   gate is **not** wired: setting a live threshold on a quantity nobody has inspected is exactly
   the `min_confidence=0.15` mistake.
6. **Delete the dead knobs.** `similarity_threshold`, `max_distance`, `high_confidence_threshold`
   (whose "early termination" comment describes a loop with no early exit), `confidence_decay`,
   and `face_detection.min_confidence`. All are read into attributes that nothing consumes, or
   not read at all.
7. **`recognition_config` records what actually ran.** `metadata_generator.py:74` hardcodes
   `"min_confidence": 0.5` — not from config (which says **0.6**, and is a *detector score*, a
   different quantity), and not what ran (**0.0**). Three numbers, three meanings, one name.
   Replaced by `acceptance_threshold` (the cosine, 0.45) read from config, plus the band cutoffs
   actually applied.

### Consequences

- **No ADR.** `CONTEXT.md` already made this call; the code ignored it. The glossary gains a
  **Detection score** entry and **Match score** gains the wire field name, which is the durable
  record. An ADR would restate the glossary.
- Implementation folds into
  **[Rewrite the metadata contract](014-rewrite-the-metadata-contract.md)** —
  same file, same write path, one reprocess instead of two.
