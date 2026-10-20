---
id: 002
title: Choose the matching strategy
label: wayfinder:grilling
mode: HITL
blocked_by: [001]
status: closed
assignee: claude
---

## Question

Given the measured numbers, which matching strategy do we commit to?

- **(a)** Max-cosine over all per-photo embeddings, averaging dropped entirely.
- **(b)** (a) plus reference-photo curation — cluster each contestant's photos, drop outliers
  and wrong-person group-shot faces (Embedding Workbench T0.5).
- **(c)** Something else the measurement suggests.

The user pre-committed to "(a), measure, then decide on (b)". This ticket is where the
measurement either honours that or overturns it.

## Context

- The live match is `face_detector.py:290-294`: a Python loop computing `1 - np.dot(...)`
  against each reference, then `argmin`, gated by `tolerance = 0.68`
  (`mvp-processor/config/processing_config.yaml:34`).
- **The hot loop barely changes.** `face_detector.py:280-281` already builds a *flat*
  `known_encodings` list with a parallel `known_names` list. Emit one entry per photo with a
  repeated contestant_id and the existing `argmin` **is** max-cosine over photos.
- `recognize_faces_batch` (`:333-399`, zero production callers) becomes *more* attractive at
  ~740 reference vectors: it replaces 740 Python-level `np.dot` calls per face with one
  `(D,512) @ (512,740)` matmul. Decide whether adopting it rides along with this change.
- Averaging happens at `face_detector.py:149` (no renormalisation, so the stored centroid has
  norm < 1 and the "cosine" at `:291` is not a true cosine) and `:545`
  (in `regenerate_embeddings_from_contestant_photos`, which has **zero callers**).
- `mvp-processor/scripts/cluster_unmatched.py` already implements HDBSCAN over face embeddings
  with an agglomerative fallback — reusable if (b) wins.
- Curation is the expensive option. Make it earn its place with the numbers from ticket 001.

## Decisions (in progress — grilling round 1 settled 2026-09-08)

- **Q1 → (a) max-cosine.** Averaging is dropped, not replaced. `face_detector.py:279-280`
  already builds a flat `known_encodings` + parallel `known_names`, so emitting one entry per
  photo with a repeated contestant_id makes the existing `argmin` at `:290-294` *be*
  max-cosine. The averaging at `:149` is deleted.
- **Q2 → curation rung 2: dedupe + single-face photos only.** Drop the 11 byte-identical
  cross-contestant groups (23 files) and all 232 multi-face photos. HDBSCAN (rung 3) is **not**
  adopted — unmeasured, and rung 2 is where the numbers move. The `max_num`/largest-face
  extraction change stays **out**: it trades a measured win for an unmeasured one.

Measured basis (leave-one-out, query set held fixed at 440 clean photos so only the reference
set varies — see `docs/wayfinder/assets/`):

| references | top-1 | impostor accepted @0.32 | @0.45 |
|---|---|---|---|
| all 672 | 90.9% | 40.2% | 10.2% |
| deduped (−23) | 92.7% | 36.1% | 6.4% |
| deduped + single-face (−232) | **94.0%** | 24.8% | **1.1%** |

Curation is worth +3.1 points of top-1 and a **9× cut in false accepts**. An earlier framing of
this ticket cited 75.7% → 94.0%; that gap was inflated by the strict row also using an easier
query set, and does not survive holding the query set fixed.

Cost: references 672 → 440, and one further contestant loses their last reference (83 → 82),
which feeds *Decide the fate of contestants with no usable reference*.

## Resolution

**(a) max-cosine, with curation rung 2, at an acceptance threshold of 0.45 cosine.**
Settled with the user over two grilling rounds, 2026-09-08. Round 1 above; round 2 here.

- **Q3 → acceptance threshold 0.45 cosine**, i.e. `tolerance: 0.55` in
  `processing_config.yaml:34`, replacing `0.68` (which accepts anything above **0.32** cosine
  and lets an impostor through on 24.8% of queries). Measured on the chosen reference set:

  | cosine | own accepted | impostor also accepted |
  |---|---|---|
  | 0.32 (today) | 91.3% | 24.8% |
  | **0.45** | **78.7%** | **1.1%** |
  | 0.55 | 59.4% | 0.5% |

  **This is provisional.** These queries are reference photos, which are easier than video
  faces, so real own-accept will be lower. Recalibrate once *Label 30 seconds of
  test-video-mv2* produces ground truth. 0.32 is indefensible; 0.55 is premature.

- **Q4 → do not adopt `recognize_faces_batch`.** The flat list grows references 83 → 440, so
  the loop at `:290-294` does 5× more work — still only **224 ms per video**, invisible beside
  4K decode and detection. Zero production callers, so adopting it would mean validating dead
  code for no measurable gain.

  **Trap recorded for whoever revisits this**: with default multi-threaded BLAS, the batched
  form measured **7040 µs** per face against the loop's **561 µs** — i.e. *slower*, from thread
  spin-up on a tiny gemv. Pinned to one thread it is 22 µs (25×), and the whole video in one
  `(400,512)@(512,440)` matmul is 2.2 ms (100×). Any future adoption must pin BLAS threads or
  it is a regression.

- **Q6 → `CONTEXT.md` created** at the repo root. Fixes the two terms that caused real bugs:
  *reference embedding* (one per photo) vs *reference set*, and **acceptance threshold**
  (cosine, higher is stricter) replacing *tolerance* (distance, opposite direction) — the exact
  inversion behind the 0.68/0.32 confusion.

### What this ticket does not decide

- **Q5 → sourcing photos for contestants with none is deferred**, and turned out to be worse
  than charted. See *Decide the fate of contestants with no usable reference*, now unblocked.
- The on-disk shape of a reference set is *Choose the reference-embedding storage shape*.
