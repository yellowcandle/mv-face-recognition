---
id: 004
title: Triage the embedding-convention call sites
label: wayfinder:task
mode: AFK
blocked_by: [002]
status: open
assignee:
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
