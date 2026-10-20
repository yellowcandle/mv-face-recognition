---
id: 012
title: Migrate the reference-embedding convention
label: wayfinder:task
mode: AFK
blocked_by: []
status: closed
assignee: claude
---

## Question

Execute the migration. Nothing is left to decide: the shape is fixed by
[ADR 0001](../../adr/0001-reference-embeddings-are-a-derived-cache.md) and the blast radius is
enumerated by *Triage the embedding-convention call sites*. This ticket is the doing.

Done when the pipeline matches by max cosine over per-photo reference embeddings loaded from
the new cache, the admin app still renders, and the tests pass against the new contract.

## Context

**The one failure that must not happen.** `face_detector.py:110` calls `.flatten()` *before*
testing `shape[0] != 512` at `:118`. Any multi-vector file flattens to `N*512`, fails, and the
contestant is skipped with a `logger.warning` — the pipeline runs clean and recognises nobody.
The photo fallback at `:132` cannot rescue it because it reads `photos/contestant_{id}/`, which
holds Git-LFS pointer text. **Change both paths in the same commit**, and leave a check that
fails loudly if the loaded reference count is zero.

**Order that keeps things working**: cache writer → `face_detector` loader + hot loop → the two
artifact scripts → regenerate the three JSON files → types and UI → tests → deletions.

- **Write the cache**: promote `docs/wayfinder/assets/extract_photo_embeddings.py` into a real
  script emitting `source/photo/contestants/reference_embeddings.npz` (`embeddings`,
  `contestant_ids`, `photo_paths`, `n_faces`, `det_scores`) plus the committed
  `reference_manifest.json`. Apply the curation from *Choose the matching strategy* at write
  time: drop cross-contestant byte-identical duplicates and multi-face photos. Gitignore the
  `.npz` — it currently matches neither `.gitattributes` nor `.gitignore`, so it would commit a
  ~2 MB binary.
- **Loader** (`face_detector.py:104-155`): read the cache keyed by contestant number, populate
  one entry per photo. `:279-280` already builds a flat `known_encodings` with parallel
  `known_names`, so repeating the contestant_id makes the existing `argmin` at `:290-294`
  *be* max-cosine. Delete the averaging at `:149`.
- **Threshold**: `processing_config.yaml:34` `tolerance: 0.68` → `0.55` (accept above 0.45
  cosine). Provisional until ground truth exists.
- **Artifacts**: `generate_coverage.py:46-58` and `compute_similarity.py:54,59,68` (its
  `np.stack` breaks on ragged sets), then regenerate
  `apps/admin/public/data/{coverage,similarity_matrix,top_pairs}.json`.
- **Contract**: `apps/shared/types/index.ts:6-7` `embedding_dim` → `reference_count`; update its
  sole reader `EmbeddingWorkbench.tsx:306`, plus `Contestants.tsx:176,235`,
  `local_api.py:189`, `worker/src/index.ts:49` and its ~96 hardcoded rows at `:353-448`.
- **Tests**: `test_face_detector.py:375-460` asserts `shape == (512,)` — that encodes the old
  contract and must be rewritten, not deleted.
- **Deletions**: the 96 legacy `{nickname}_embedding.npy`, the three duplicate script pairs, and
  the four unimportable scripts. Full list in the triage ticket.
- **Open sub-decision carried over**: `recognize_faces_batch` (`:333-399`) was declined but *is*
  tested at `test_face_detector.py:311,331,358`. Deleting it means deleting those tests. Decide
  when you get there rather than assuming.

**Verification, not vibes**: after migrating, rerun the leave-one-out benchmark
(`docs/wayfinder/assets/`) and confirm top-1 is still ~94% and false accepts at 0.45 stay ~1%.
A silent regression here looks exactly like success.

## Resolution

**Migrated and verified 2026-09-08.** The matcher now scores by max cosine over per-photo
reference embeddings loaded from the consolidated cache. Orchestrated across three subagents
(Python core, TypeScript contract, tests) with verification run in the main session.

### Built
- `mvp-processor/scripts/build_reference_cache.py` — new. Applies curation at write time and
  emits `reference_embeddings.npz` (gitignored) + `reference_manifest.json` (committed).
  **663 references across 94 contestants from 964 photos**; dropped 69 no-face and 232
  multi-face. Cross-contestant duplicates came to 0 *because* the multi-face filter already
  removed all 11 groups — the two curation rules overlap completely on this data.

### Changed
- `face_detector.py` — cache loader keyed by contestant number; `flatten_references()` builds
  the flat per-photo lists once at load; the hot loop's existing `argmin` is now max-cosine.
  Averaging deleted. **629 → 439 lines.**
- `face_detector.py` now **raises** rather than warns on: missing cache, wrong shape, id/row
  mismatch, stale manifest, zero references loaded.
- `local_api.py` — `has_embedding` and new `reference_count` from the manifest (memoised);
  `PHOTOS_DIR` repointed from the dead `photos/` to `ig_photos/`.
- `processing_config.yaml` — `tolerance`/`max_distance` 0.68 → 0.55 (accept above 0.45 cosine).
- `generate_coverage.py`, `compute_similarity.py` — read the cache; the similarity matrix is now
  **max cosine between reference sets**, which is how the matcher actually scores.
- `apps/shared/types/index.ts`, `EmbeddingWorkbench.tsx:306`, `Contestants.tsx`,
  `worker/src/index.ts` — `embedding_dim` → `reference_count`.
- Regenerated `apps/admin/public/data/{coverage,similarity_matrix,top_pairs}.json`.

### Deleted
95 legacy `{nickname}_embedding.npy`; 6 duplicate/unimportable scripts;
`face_detector.py:440-629` (`RegenerationResult` + `regenerate_embeddings_from_contestant_photos`,
which still *wrote* the removed convention); `scripts/modal_hf_processor.py`, its only caller.

**Correction to my own earlier caution**: I initially spared `modal_hf_processor.py` believing
the map protected it. The map protects `scripts/modal_youtube_processor.py` — a different file,
untouched.

### Verification
- `tests/unit/test_face_detector.py`: **19 passed** (was 10 passed / 5 failed). Added
  `test_matches_nearest_reference_photo_not_the_average` and
  `test_reference_set_is_not_flattened` — the latter guards the ADR trap directly — plus four
  loud-failure tests (missing, stale, wrong-dimension, empty cache).
- Leave-one-out on the production cache: 659 queries, **top-1 95.9%**, own mean 0.592,
  impostor mean 0.300, **impostor accepted @0.45 unchanged at 1.1%**. Not a like-for-like
  comparison with the pre-migration 94.0% (that run held the query set fixed at 440 shared
  photos to compare two caches); the claim is *no regression*, not *improvement*.
- End-to-end: 96 contestants loaded, 94 with references, 663 flat entries, name resolution
  correct (42 → 王綺玲 / 2Ling).

### Pre-existing failures, NOT caused by this work
`tests/unit/test_video_processor.py` fails collection (`src/video_processor.py:13` does a bare
`from exceptions import` while `pytest.ini` sets `pythonpath = .`), and three
`test_frame_optimizer.py` tests fail. Proven pre-existing by stashing this migration's test
changes and rerunning — identical failures. Untouched by this ticket.

### Left standing, deliberately
- `recognize_faces_batch` (`face_detector.py:333-399`) kept with its three tests. Declined for
  production, but deleting tested code was flagged as a judgement call, not an assumption.
- **7 contestants are down to ≤2 references** (38, 41, 42, 47, 60, 65, 72) — they had 9 photos
  each, mostly group shots the curation rule removes. With max-cosine, one reference is one
  chance to match. The YouTube solo-clip method used for the missing 11 would top these up.
- **Contestant 77 (TABI) has dropped to zero references**, joining 67. Her only detectable photo
  is a group shot. Exactly what *Decide the fate of contestants with no usable reference*
  predicted when it noted the set can only grow.

### Follow-up from the subagent reports

Both flagged leftovers the migration orphaned; both are now resolved:

- `regenerate_embeddings_from_contestant_photos` still wrote averaged `{nickname}_embedding.npy`.
  Deleted along with `scripts/modal_hf_processor.py`, its only caller. The agent correctly
  declined to delete it because that caller was outside its assigned files.
- `ContestantDatabase.embeddings_cache` (`face_detector.py:72`) and the config keys
  `contestants.embeddings_cache` / `face_recognition.embeddings_path` were read by nothing —
  the loader derives the cache path from `photo_dir`. Removed. An unread config key that names
  a pickle the design never produces is the same class of hazard as the stale HuggingFace
  embeddings.

Re-verified after the cleanup: 19/19 tests, loader returns 94 contestants / 663 references.

### Reprocessed `test-video-mv2` on the migrated matcher (2026-09-08)

Same 399 detections across 187 frames in all three runs:

| run | recognitions | rate | contestants | cos avg | cos min |
|---|---|---|---|---|---|
| before — averaging, bar 0.32 | 150 | 37.6% | 14 | 0.520 | 0.422 |
| after — hidden gate, effective bar 0.53 | 48 | 12.0% | 11 | 0.569 | 0.534 |
| **after — bar 0.45 as agreed** | **139** | **34.8%** | **15** | 0.515 | **0.451** |

The observed minimum landing on 0.451 confirms the configured threshold now governs.

**The middle row is a bug this run exposed**, not a result: `process_video.py:257` hardcoded a
second gate at `min_confidence=0.15`, which — because confidence is tolerance-relative — set the
real bar to cosine 0.5325 rather than the 0.45 settled in *Choose the matching strategy*. Removed
so tolerance is the single acceptance threshold. The wider problem is ticketed as *Settle what
match confidence means on the wire*.

**Do not read 34.8% as an improvement over 37.6%.** They are not comparable: the old figure is
matches against averaged centroids at a 0.32 bar, the new one is max-cosine against 663 per-photo
references at 0.45. A recognition rate cannot separate a right answer from a confident wrong one
without labels — which is how 37.6% misled this effort once already. This run demonstrates the
pipeline works end to end on the new matcher; it says nothing about accuracy until
*Label 30 seconds of test-video-mv2* exists.
