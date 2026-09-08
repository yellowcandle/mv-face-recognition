---
id: 003
title: Choose the reference-embedding storage shape
label: wayfinder:grilling
mode: HITL
blocked_by: [002]
status: closed
assignee: claude
---

## Question

If a contestant is no longer one vector, what is stored on disk and how is it addressed?

- **(a)** One `.npy` per contestant of shape `(N, 512)` — keeps the file convention, breaks
  every shape check.
- **(b)** A directory per contestant, one `.npy` per photo — traceable back to source photos,
  more files.
- **(c)** One consolidated gallery file plus an index — fastest to load, worst to diff.

Also decide what `has_embedding` / `embedding_dim` mean once a contestant has N photos of
varying quality, since both are part of the public API surface.

## Context

- **The trap**: `face_detector.py:118` hard-rejects anything whose `shape[0] != 512`. An
  `(N,512)` array flattens to `N*512` and every contestant is **silently skipped** — a
  pipeline that runs clean and recognises nobody.
- On-disk today: exactly 96 files, every one 2176 bytes, `shape: (512,)`, in
  `source/photo/contestants/`. 95 are git-tracked; `*.npy` is LFS-tracked
  (`.gitattributes:12`). Zero `.sha256` sidecars exist, so the sidecar verification in
  `src/database/chroma_setup.py:84-99` always skips.
- `ig_photos/` covers **96** contestants vs `photos/`'s 84 — the migration gains references
  for 12 contestants who currently have none. Decide whether that is in scope here.
- API surface that assumes one-vector-per-contestant: `apps/shared/types/index.ts:6-7`
  (`has_embedding`, `embedding_dim`), `worker/src/index.ts:49` and its ~96 hardcoded rows at
  `:353-448`, `apps/admin/src/pages/EmbeddingWorkbench.tsx:306`,
  `apps/admin/src/pages/Contestants.tsx:176,235`.
- `mvp-processor/scripts/compute_similarity.py:68` (`np.stack`) and
  `generate_coverage.py:48` both assume uniform shape and feed
  `data/coverage.json` / `data/similarity_matrix.json`, which the Embedding Workbench renders.
- The HuggingFace dataset (`yellowcandle/mv-face-recognition-data`) stores embeddings under
  the same convention — `scripts/upload_embeddings_to_hf.py:333-338` rejects `dim != 512`.
  Decide whether HF migrates now or later.

This is a hard-to-reverse data-structure decision touching a published dataset. **Consider an
ADR.**

## Added 2026-09-08 — evidence that nicknames are the wrong key

Cross-checked all 96 contestants in `metadata/contestant_info.csv` against the 參賽者 table on
<https://zh.wikipedia.org/zh-hk/全民造星IV>:

- **Contestant numbers: 96/96 match.** No number present in one source and absent from the other.
- **Names and nicknames: 0 real mismatches.** The CSV is accurate — worth knowing, since it is
  the file `CLAUDE.md` marks as essential.
- **But 7 of 96 nicknames differ by whitespace**, the CSV having a space inserted between CJK
  and Latin: `Ada 仔`/`Ada仔`, `阿 Wing`/`阿Wing`, `阿 J`/`阿J`, `阿 Mic`/`阿Mic`,
  `阿 bee`/`阿bee`, `阿 Yo`/`阿Yo`, `3 妹`/`3妹`.

That whitespace is **already load-bearing**, because the current convention puts the nickname in
the filename: `{nickname}_embedding.npy`. The working tree at the time of writing carries both
`source/photo/contestants/Ada 仔_embedding.npy` and a *deleted* `3 妹_embedding.npy` — the exact
failure this invites.

So the storage decision has a fact behind it now: **numbers are stable across independent
sources, nicknames are not.** Whatever shape wins, address reference sets by contestant number
and treat the nickname as a display label. `ig_photos/contestant_{id}/` already does this; the
`.npy` convention does not.

## Decisions (grilling round 1, 2026-09-08)

- **Q1 → (c) one consolidated cache file.** Reference embeddings are a *derived cache*, not
  source data: the photos are the source of truth and the cache exists only to avoid a ~12
  minute recompute. So one file, one atomic write, no ragged-shape handling, no 964-file
  footprint, and diffing is irrelevant because you regenerate rather than merge. Format is the
  one already proven across this map — `photo_embeddings.npz`, carrying `embeddings`,
  `contestant_ids`, `photo_paths`, `n_faces`, `det_scores`. `photo_paths` gives (b)'s
  traceability without (b)'s file count.
- **Q2 → keyed by contestant number.** Evidence from *Measure within-person embedding
  separation* and the Wikipedia cross-check: numbers matched 96/96 across independent sources
  while 7 nicknames differed by whitespace alone, and the working tree still carries a deleted
  `3 妹_embedding.npy` beside a live `Ada 仔_embedding.npy`. `ig_photos/contestant_{id}/`
  already keys by number; the `.npy` convention is the outlier. Nickname is a display label.
- **Q3 → keep `has_embedding`, replace `embedding_dim` with `reference_count`.**
  `embedding_dim` was always the constant 512 and answers nothing once a contestant has a
  reference *set*. `reference_count` surfaces something real: contestant 8 has 8 references,
  contestant 67 has none. Touches `apps/shared/types/index.ts`, `EmbeddingWorkbench.tsx:306`
  (its only reader), and the producer at `generate_coverage.py:46-58`.
- **Q4 → HuggingFace loses embeddings entirely.** Derived data does not belong in a dataset
  repo; that is precisely how its 338 single-vector files became silently misleading.

### The trap this decision has to survive

`face_detector.py:110` calls `.flatten()` **before** the `shape[0] != 512` check at `:118`, so
an `(N,512)` file flattens to `N*512`, fails, and the contestant is skipped with only a
`logger.warning` — a pipeline that runs clean and recognises nobody. The fallback at `:132`
cannot rescue it either: it reads `photos/contestant_{id}/`, the dead LFS-pointer directory,
where `cv2.imread` returns `None` on every file. Both paths must change together.

### Current shape of the data

95 contestants with 3–20 photos each, median 9 — genuinely ragged, which also breaks
`compute_similarity.py:68` (`np.stack`) and `generate_coverage.py:48`.

## Resolution

**Reference embeddings become one gitignored, regenerable `.npz` cache keyed by contestant
number, with a committed manifest for staleness detection.** Recorded as
[ADR 0001](../../adr/0001-reference-embeddings-are-a-derived-cache.md).

- **Q5 → gitignore the cache, commit a manifest.** `*.npy` is contradictorily both LFS-tracked
  (`.gitattributes:12`) and gitignored (`.gitignore:23`); `*.npz` matches **neither**, so a
  cache file under `source/photo/contestants/` would silently commit a ~2 MB binary into
  history on every regeneration. Instead: gitignore the `.npz`, and commit a small JSON
  manifest of per-contestant photo counts plus a hash of the photo list. The loader compares
  the manifest against the photo directory and **refuses to run when stale** rather than
  warning — staleness that only warns is the exact failure mode that had this map measuring
  against an out-of-date cache for hours today.

### Contract

```
source/photo/contestants/
├── ig_photos/contestant_{id}/*.jpg     # source of truth
├── reference_embeddings.npz            # gitignored, regenerable (~12 min)
│     embeddings (N,512) · contestant_ids (N,) · photo_paths (N,)
│     n_faces (N,) · det_scores (N,)
└── reference_manifest.json             # committed; per-contestant counts + photo-list hash
```

The 96 legacy `{nickname}_embedding.npy` files are deleted, not migrated. They hold averaged
centroids under a convention *Choose the matching strategy* removed.

### Not decided here

Backing up the photos themselves. Raised, not answered: **the 964 photos exist only on the
user's Mac** — `.gitignore:18` excludes them, `git ls-files` returns 0, the LFS objects are
absent from the remote, and HuggingFace holds pointer text. That includes the 223 sourced on
2026-09-08, some from a site that has already lost half its images, so re-sourcing is not
guaranteed to work twice. Strictly outside this map's destination, but losing that directory
would undo the whole effort.
