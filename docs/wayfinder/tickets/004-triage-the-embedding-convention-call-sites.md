---
id: 004
title: Triage the embedding-convention call sites
label: wayfinder:task
mode: AFK
blocked_by: [002]
status: closed
assignee: claude
---

## Question

Of the ~40 places that depend on `{nickname}_embedding.npy` or on one-vector-per-contestant,
which are **live** (must migrate), which are **dead** (delete), and which are **archive**
(leave alone)? Produce the actual blast radius, so the migration isn't sized by a grep count.

## Context

Ponytail applies hard here: deletion beats migration. Early evidence that most of this list is
already dead —

- **Live, must migrate**: `mvp-processor/src/face_detector.py:105,118,124,149,349`;
  `mvp-processor/src/local_api.py:52-53,189`; `mvp-processor/scripts/generate_coverage.py:48`;
  `mvp-processor/scripts/compute_similarity.py:54,59,68`;
  `mvp-processor/tests/unit/test_face_detector.py:376-398,426-429,444-460` (asserts `(512,)`).
- **Dead — verify then delete**: `face_detector.py:494-558`
  (`regenerate_embeddings_from_contestant_photos`, zero callers);
  `compare_recognition.py` (references deleted `src.recognition.face_recognizer`, and *writes a
  new file* at `:42-81`); `scripts/debug_similarity.py` (imports nonexistent
  `src.core.face_detector`); `scripts/fix_embeddings.py` and `scripts/debug/fix_embeddings.py`
  (identical duplicates); root-level duplicates of `check_stored_embeddings.py` and
  `batch_process_videos.py`.
- **Archive — leave alone**: the whole legacy `src/` ChromaDB tree
  (`src/database/chroma_setup.py`, `src/core/face_matcher.py` which hardcodes
  `Alice_embedding.npy` at `:336`, `src/integrations/huggingface_xet.py`,
  `src/services/enhanced_video_processor.py:1042`), `archive/gradio/*`,
  `scripts/archive/*`. Out of scope per the map.
- **Also depends on the path bug**: `regenerate_embeddings_insightface.py:64`,
  `face_detector.py:132`, `local_api.py:52`, `validate_embeddings.py:251` all read the dead
  `photos/` pointer directory. Repointing to `ig_photos/` is required regardless of which
  storage shape wins.
- Docs carrying the stale convention: `CLAUDE.md:42`, `DESIGN.md:55,579,809`, `TODO.md:21`,
  `.serena/memories/code_style_conventions.md:107`, and
  `source/photo/contestants/metadata/embedding_manifest.json`.

Output: a migrate / delete / ignore list with file:line, and a one-line justification each.

## Resolution

**The blast radius is 11 sites, not ~40.** The grep count was inflated by two `.claude/worktrees/`
checkouts, which are full untracked copies of the repo and duplicated every hit. Liveness was
established mechanically, not by reading: import reachability from the real entry points
(`main.py`, `local_api.py`, `process_video.py`) resolves to **9 Python modules total**, of which
exactly two touch the convention. The rest is standalone tooling, judged by whether it produces
an artifact something live consumes.

### MIGRATE — 11 sites

**Python, on the live import graph**
- `mvp-processor/src/face_detector.py:104-155` — loads `{nickname}_embedding.npy`, `.flatten()`s
  at `:110` **before** the `shape[0] != 512` test at `:118`, and averages at `:149`. The photo
  fallback at `:132` reads the dead `photos/` pointer directory. Loader and fallback must change
  together or the pipeline silently recognises nobody.
- `mvp-processor/src/face_detector.py:279-294` — the hot loop. Already builds a *flat*
  `known_encodings` with a parallel `known_names`, so it becomes max-cosine by emitting one
  entry per photo. Smallest part of the change.
- `mvp-processor/src/local_api.py:52-53,189` — `EMBEDDINGS_DIR` and `has_embedding` keyed by
  nickname. Serves `/api/contestants`, which `useContestants` calls from both apps.

**Python, not imported but live by artifact**
- `mvp-processor/scripts/generate_coverage.py:46-58` — `check_embedding()` by nickname; emits
  `coverage.json`, fetched by `apps/shared/hooks/useCoverage.ts:8`.
- `mvp-processor/scripts/compute_similarity.py:54,59,68` — `load_embeddings()` by nickname and
  `np.stack` (breaks on ragged sets); emits `similarity_matrix.json` and `top_pairs.json`,
  fetched by `apps/shared/hooks/useSimilarity.ts:8,19`.
- `apps/admin/public/data/{coverage,similarity_matrix,top_pairs}.json` — git-tracked outputs of
  the two scripts above. Must be regenerated, not hand-edited.

**Tests**
- `mvp-processor/tests/unit/test_face_detector.py:375-460` — writes `{nickname}_embedding.npy`
  and asserts `face_encodings["1"].shape == (512,)`. That assertion encodes the old contract.
- `mvp-processor/tests/conftest.py:81-88,120,331` — `embeddings_path` / `embeddings_cache`
  fixtures.

**TypeScript**
- `apps/shared/types/index.ts:6-7` — `has_embedding`, `embedding_dim` → `reference_count`.
- `apps/admin/src/pages/EmbeddingWorkbench.tsx:306` — the **only** reader of `embedding_dim`.
- `apps/admin/src/pages/Contestants.tsx:176,235` — `has_embedding` display gates.
- `worker/src/index.ts:49` and its ~96 hardcoded contestant rows at `:353-448`.

### DELETE

**Byte-identical duplicates** (verified by md5, delete the root/debug copy):
- `check_stored_embeddings.py` == `scripts/check_stored_embeddings.py`
- `scripts/fix_embeddings.py` == `scripts/debug/fix_embeddings.py`
- `scripts/debug_similarity.py` == `scripts/debug/debug_similarity.py`

**Cannot be imported at all** — they reference modules that do not exist
(`src.core.detector`, `src.recognition.face_recognizer`):
- `generate_embeddings.py` — also *writes* the averaged convention we are removing
- `demo_feature_fix.py`
- `face_detect.py`
- `scripts/modal_hf_processor.py` — imports `src.face_detector`; only `src/core/face_detector.py`
  exists, so this is broken

**Superseded**
- `face_detector.py:425-558` `regenerate_embeddings_from_contestant_photos` — its only caller is
  `scripts/modal_hf_processor.py:172`, which is itself broken, so it has **zero live callers**.
  (This corrects the ticket's claim of "zero callers" — there is one, it just does not run.)
- `scripts/regenerate_embeddings_insightface.py:64`, `scripts/validate_embeddings.py:251` — both
  read the dead `photos/` directory; superseded by the cache regenerator from ADR 0001.
- `batch_process_videos.py` (root) — **not** identical to `scripts/archive/batch_process_videos.py`
  (different md5), so check before deleting; the archived copy is the keeper.

### DECIDE, do not delete blindly
- `face_detector.py:333-399` `recognize_faces_batch` — *Choose the matching strategy* declined to
  adopt it, but it is **not** untested: `test_face_detector.py:311,331,358` exercise it. Deleting
  the function means deleting those tests too. Keeping dead-but-tested code is also a choice.
  Flagging rather than assuming.

### IGNORE — archive, out of scope per the map
- The whole legacy `src/` ChromaDB tree. **Note:** `src/core/face_detector.py` *does* exist (214
  lines, real), so `scripts/debug_similarity.py` imports fine — this ticket previously claimed it
  imported a nonexistent module. It is still archive, just not broken.
- `backend/` — an importable FastAPI app (`backend/app/core/config.py` etc. all exist), but not
  part of the live architecture and referenced only by `scripts/package.json:10`.
- `archive/gradio/*`, `scripts/archive/*`.
- `.claude/worktrees/{buzzing-swinging-summit,zazzy-roaming-stroustrup}/` — untracked full repo
  copies. Never edit; they are what inflated the original count.

### Docs carrying the stale convention
`CLAUDE.md:42`, `DESIGN.md:55,579,809`, `TODO.md:21`,
`.serena/memories/code_style_conventions.md:107`,
`source/photo/contestants/metadata/embedding_manifest.json`.
