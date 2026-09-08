---
id: 001
title: Measure within-person embedding separation
label: wayfinder:task
mode: AFK
blocked_by: []
status: closed
assignee: claude
---

## Question

Across **all 96 contestants** (not the 6 of the ad-hoc 2026-06-30 diagnostic), what is the
cosine distribution *within* each contestant's own reference photos, and *between* different
contestants?

This is the go/no-go for the whole matching fix. The plan to stop averaging and match by
max-cosine rests on the claim "within-person max ~0.7 vs mean ~0.3" — a claim no committed
script reproduces. If within-person max really is ~0.7, max-cosine is confirmed. If it isn't,
the migration is wasted work and curation becomes the actual fix.

## Context

- **Read photos from `source/photo/contestants/ig_photos/contestant_{id}/`** — 260 MB, 741
  real JPEGs, 96 contestant dirs. **Not** `photos/`, which is 640 KB of 131-byte Git-LFS
  pointer text; `cv2.imread` returns `None` on every file there. Verified on disk.
- `mvp-processor/scripts/compute_similarity.py` already has the loader, the row-normaliser
  (`:74-76`), the N×N cosine matrix (`:79`) and a `stats` block (`:144-147`). Repoint its
  `load_embeddings` at per-photo embeddings and the same matrix yields within-person blocks
  (diagonal) and between-person blocks (off-diagonal). **No new script needed.**
- `:68` uses `np.stack`, which requires uniform shapes — ragged per-contestant photo counts
  will break it. Handle that.
- Reference extraction uses `faces[0]` from `app.get()`, which is the **highest-detection-score**
  face, not the largest (SCRFD only ranks by area when `max_num > 0`; every call site uses
  the default `0`). It is identity-blind either way, so group shots contaminate references.
  Report how many photos yield multiple faces — that sizes the contamination.
- Do **not** modify production code. Write scratch output; this ticket only produces numbers.

Report: per-contestant within-person mean/min/max, the global between-person distribution,
and an explicit verdict on whether max-cosine clears the ≥0.45 / ≤0.2 separation gate.

## Resolution

**The claim reproduces. Max-cosine is confirmed; the migration is not wasted work.**
But the measurement also surfaced a second, independent defect that no matching strategy fixes.

Assets in `docs/wayfinder/assets/`: `extract_photo_embeddings.py` (phase A, ~10 min),
`analyse_separation.py` (phase B, instant), `photo_embeddings.npz` (672×512 cache, 1.4 MB,
**untracked binary — not committed**), `separation_report.txt` (full per-contestant table).

### The numbers

| | mean | sd | p50 | p95 | max |
|---|---|---|---|---|---|
| within-person pairs (n=4,922) | **0.318** | 0.243 | 0.365 | 0.664 | 1.000 |
| between-person pairs (n=445,990) | **0.034** | 0.079 | 0.030 | 0.169 | 1.000 |

Per contestant: within-person **max** mean 0.646 / median 0.662 / min 0.191;
within-person **mean** 0.308 / median 0.296. The charted claim was "max ~0.7 vs mean ~0.3" —
measured 0.646 vs 0.308.

- 77/82 measurable contestants have a within-person max ≥ 0.45. Only 16/82 have a *mean* ≥ 0.45.
- Between-person pairs above 0.2: 2.4%. Above the production accept cosine 0.32
  (`tolerance: 0.68`, `processing_config.yaml:34`): 0.1%.

**Gate verdict** (matched mean ≥ 0.45, cross-person ≤ 0.2):
- by within-person **MAX**: 0.646 vs 0.034 → **CLEARS**
- by within-person **MEAN**: 0.308 vs 0.034 → **FAILS**

That gap *is* the argument against averaging. Collapsing a contestant to one centroid throws
away the 0.65 signal and keeps the 0.31 one.

**Caveat, stated plainly**: this is reference-to-reference separation, not video-face-to-reference.
It is necessary, not sufficient. The real gate still needs the ground truth from
*Label 30 seconds of test-video-mv2*.

### Coverage is worse than charted

`ig_photos/` has 96 directories, but only **83 contestants yield a usable reference** —
69 of 741 photos (9.3%) produce no detection at all. **13 contestants have zero**:
8 小砂, 13 Ashi, 23 陳祖, 36 精靈, 45 Jade Chan, 53 丁丁, 54 Miko, 58 Kinki, 61 燒賣,
66 Sam, 67 Sarah, 69 鉦貽, 86 Michelle. They cannot be recognised under any strategy.
Contestant 77 has a single photo, so 82 are measurable for within-person spread.

This corrects *Choose the reference-embedding storage shape*, which assumed the migration
gains references for 12 contestants who currently have none.

### Poisoned references — curation is no longer optional

- **232/672 photos (34.5%) contain more than one face**, and `faces[0]` picks by detection
  score, so a third of references may be the wrong person.
- Worse: **11 groups of byte-identical files sit in 2–4 different contestant directories**
  (25 files). `contestant_1/1_ig_2.jpg` = `26/26_ig_6.jpg` = `38/38_ig_2.jpg` = `40/40_ig_3.jpg`.
  These are the cosine-1.000 cross-person pairs. One face is currently the registered
  reference for up to four different contestants — a guaranteed confident wrong match, and
  exactly the failure mode a recognition-rate metric cannot see.

Deduplication is unambiguous and cheap. How much curation beyond that is *Choose the matching
strategy*'s call, now with numbers.
