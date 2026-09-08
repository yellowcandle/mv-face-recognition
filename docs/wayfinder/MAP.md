# Map: Face recognition pipeline → visualized → published on Cloudflare

Label: `wayfinder:map`
Charted: 2026-09-07

## Destination

All 5 source MVs processed with **fixed** face matching, their results visible in the
React viewer (face overlays + contestant timeline + analytics), verified locally against
real R2/KV via `wrangler dev`, and handed off as a **single deploy command the user runs**.

Two stages: **MVP** = MV #4 (`4-《全民造星IV》極限拍MV.mp4`, 135 MB, smallest) end-to-end.
**Complete** = all 5, with per-contestant screen-time analytics.

The map does **not** deploy. It ends at deploy-ready.

## Notes

**Domain**: InsightFace `buffalo_l` (512-d) + supervision/ByteTrack; Python pipeline in
`mvp-processor/`; React pnpm monorepo (`apps/admin` local, `apps/viewer` → Cloudflare Worker,
`apps/shared` Player); Cloudflare Worker + R2 (`mv-face-recognition-videos`) + KV (`METADATA_KV`).

**Skills every session should consult**: `grilling` + `domain-modeling` by default.
`ponytail` is active — take the laziest rung that holds.

**Standing constraints for this effort**:
- **Never run `wrangler deploy`.** Writes to R2 and KV are also outward pushes and need
  explicit confirmation. One confirmation point, at the end.
- CJK text rendered onto frames MUST use PIL + `/System/Library/Fonts/PingFang.ttc`.
  Never `cv2.putText` — it cannot render CJK.
- **`CLAUDE.md` and `DESIGN.md` are stale wherever they describe the frontend** (they still
  document the deleted SvelteKit app in `mvp-processor/`). `TODO.md` is accurate. Trust code.
- No webcam work. Only files in `source/videos/`.
- Never delete `metadata/contestant_info.csv`.

**Scope decisions settled while charting**:
- Fix matching *before* running the pipeline — reprocessing 1.3 GB of 4K is far more
  expensive than the fix.
- The gate for the full batch is **separation**, not recognition rate: matched-face cosine
  mean ≥0.45 while cross-person stays ≤0.2, against the measured baseline of mean 0.206 /
  max 0.510. Recognition rate is unfalsifiable without ground truth.
- Publish **`_1080p.mp4` + metadata**, never `_annotated.mp4`. Overlays are drawn by the JS
  layer.
- Iterate matching on `test-video-mv2` (30 s, has the before-number). MVP-publish MV #4.

## Decisions so far

<!-- one line per closed ticket -->

- [Measure within-person embedding separation](tickets/001-measure-within-person-embedding-separation.md):
  within-person max 0.646 vs mean 0.308 against cross-person 0.034 — max-cosine **clears** the
  gate, averaging **fails** it. Also: only 83 of 96 contestants have any usable reference, and
  11 byte-identical photo groups are filed under 2–4 contestants each.

- [Choose the matching strategy](tickets/002-choose-the-matching-strategy.md): max-cosine over
  per-photo references, averaging deleted; curation = dedupe + single-face photos only (no
  HDBSCAN); acceptance threshold **0.45 cosine** (`tolerance: 0.55`), provisional until ground
  truth exists; `recognize_faces_batch` **not** adopted. Added `CONTEXT.md` to kill the
  tolerance-vs-cosine inversion.

- [Decide the fate of contestants with no usable reference](tickets/011-decide-the-fate-of-contestants-with-no-usable-reference.md):
  sourced photos rather than accepting the gap. `ig_photos/` 741 → 964 photos; contestants with
  zero references 13 → **1** (only 67/Sarah, whose surviving footage is unusable split-screen
  IG Live). Best source is the show's own solo Pre-round clips, whose burned-in lower-third
  names the contestant. **`docs/wayfinder/assets/photo_embeddings.npz` is now stale.**

- [Choose the reference-embedding storage shape](tickets/003-choose-the-reference-embedding-storage-shape.md):
  one gitignored, regenerable `reference_embeddings.npz` keyed by **contestant number**, plus a
  committed manifest so a stale cache fails loudly. Legacy `{nickname}_embedding.npy` deleted,
  not migrated; `embedding_dim` → `reference_count`; HuggingFace stops holding embeddings.
  See [ADR 0001](../adr/0001-reference-embeddings-are-a-derived-cache.md).

- [Triage the embedding-convention call sites](tickets/004-triage-the-embedding-convention-call-sites.md):
  the blast radius is **11 sites, not ~40** — the count was inflated by two `.claude/worktrees/`
  repo copies. Live Python is only `face_detector.py` and `local_api.py` plus two artifact-
  producing scripts; 8 files are duplicates or cannot be imported at all and get deleted.

- [Migrate the reference-embedding convention](tickets/012-migrate-the-reference-embedding-convention.md):
  done. Matcher scores by max cosine over 663 per-photo references (94 contestants) from the new
  cache; averaging and 95 legacy `.npy` deleted; `face_detector.py` 629 → 439 lines; threshold
  0.68 → 0.55. Tests 19/19. Leave-one-out shows **no regression** (impostor @0.45 still 1.1%).

## Not yet specified

_(The reference-embedding migration is no longer fog — shape settled by ADR 0001, blast radius
enumerated by the triage. It is now specifiable work, not an open question.)_
- **Backing up the reference photos.** Raised while closing the storage-shape ticket and left
  unanswered: the 964 photos exist only on the user's Mac. Whether this belongs to this map at
  all is a scoping call the user has not yet made.
- Reprocessing `test-video-mv2` on the fixed matcher and judging it against the labelled
  ground truth — the go/no-go for the full batch. Needs the gate metric to exist first.
- **How far** reference-photo curation goes. The measurement settled *whether*: deduplicating
  the 11 cross-contestant identical-file groups is unambiguous. Everything past that — HDBSCAN
  clustering, dropping wrong-person faces from the 34.5% of photos that are group shots
  (Embedding Workbench T0.5) — is now *Choose the matching strategy*'s call, not fog.
- The single publish script that replaces the four stale upload scripts. Its contract comes
  from *Settle the KV and R2 publish contract*.
- MVP end-to-end for MV #4: process → publish locally → verify under `wrangler dev`.
- Compute for the remaining 4 MVs (local Apple Silicon vs reviving Modal). Undecidable until
  the MVP gives a real per-video wall time on 4K input.
- The deploy handoff itself: the exact command and the verification checklist handed to the user.

## Out of scope

- **`wrangler deploy`** — ruled out by the user. The map produces a command; the user runs it.
- The ~12 code-quality cleanups in `TODO.md` "Next" (shared `formatTime`, `useInterval`,
  capability props beyond what flagging removal needs, `Contestants.tsx` memoisation, …).
  Real, but past this destination.
- Restoring `scripts/modal_youtube_processor.py` cookie support and webhook progress, and
  reviving the disabled Ingestion page. Separate effort.
- Repairing the legacy `src/` ChromaDB tree. It is already broken
  (`debug_similarity.py` imports a `src.core.face_detector` that does not exist) and nothing
  in the live path uses it.
- Webcam / realtime capture. Permanently out per `CLAUDE.md`.
