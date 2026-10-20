---
status: accepted
---

# Reference embeddings are a derived cache, keyed by contestant number

A contestant is identified by a **reference set** — one 512-d embedding per reference photo,
matched by max cosine — rather than by a single averaged vector. We store that set as **one
consolidated `.npz` cache** regenerated from the photos, not as per-contestant or per-photo
`.npy` files, because the photos in `source/photo/contestants/ig_photos/contestant_{id}/` are
the only source of truth and the embeddings are reproducible from them in about 12 minutes.
The cache is addressed by **contestant number**, never nickname.

## Considered options

- **One `(N,512)` `.npy` per contestant.** Rejected: still ragged (3–20 photos, median 9),
  still 95 files, and it walks straight into the trap below.
- **A directory per contestant, one `.npy` per photo.** Rejected: ~964 files for traceability
  that a `photo_paths` array inside the cache already provides.
- **One consolidated cache plus an index.** Chosen.

## Consequences

- **The `512` check is a trap, not a safeguard.** `face_detector.py:110` calls `.flatten()`
  *before* testing `shape[0] != 512` at `:118`, so an `(N,512)` file flattens to `N*512`,
  fails, and the contestant is skipped with a `logger.warning`. The pipeline then runs clean
  and recognises nobody. The photo fallback at `:132` cannot rescue it: it reads
  `photos/contestant_{id}/`, which holds Git-LFS pointer text, so `cv2.imread` returns `None`
  on every file. Any migration must change both paths together.
- **Nicknames are not stable keys.** Cross-checked against
  <https://zh.wikipedia.org/zh-hk/全民造星IV>, contestant numbers matched 96/96 while 7 of 96
  nicknames differed by whitespace alone (`Ada 仔`/`Ada仔`, `3 妹`/`3妹`, …). That whitespace is
  load-bearing under the old `{nickname}_embedding.npy` convention, which is why the working
  tree carried a deleted `3 妹_embedding.npy` beside a live `Ada 仔_embedding.npy`.
- **The cache is gitignored; a small JSON manifest is committed instead.** The manifest records
  photo counts per contestant and a hash of the photo list, so a cache that disagrees with the
  photos is a loud failure rather than a silently wrong answer. `*.npz` matches neither
  `.gitattributes` nor `.gitignore` today, so without this it would commit a ~2 MB binary into
  history on every regeneration.
- **HuggingFace no longer stores embeddings at all.** Its 338 single-vector files became
  misleading precisely because derived data went stale unnoticed in a dataset repo.
- **`embedding_dim` is replaced by `reference_count`** in the public contract. The old field
  was always the constant 512; the new one reports something real.
