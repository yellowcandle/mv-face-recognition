# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Operator (primary, local):** the person running the pipeline and keeping the results honest — flagging wrong identifications, reprocessing videos, managing embeddings. Works alone in `apps/admin` on localhost. (Inferred from repo structure and CONTEXT.md voice; interview unavailable, see note below.)
- **Fan audience (public):** viewers of the music videos who want to see who appears when. Read-only users of `apps/viewer`; anything they can do, an anonymous stranger can do. (Inferred from product-plan/product-overview.md.)
- Both audiences read the same recognition data; only the operator ever writes.

> **Note on inference:** this session had no working question mechanism (the supervisor interview channel is unavailable). Facts marked "(Inferred …)" come from repository evidence and the documented brief, not user confirmation. Treat them as hypotheses until confirmed.

## Product Purpose

Automatically identify which of the 96 *King Maker* (全民造星) contestants appears at each moment in a set of music videos, and publish those results:

- to a **public viewer** (`apps/viewer`) with real-time face overlays, thumbnails, and per-contestant timelines during playback;
- to a **local admin app** (`apps/admin`) where flags, reprocessing, and embedding work happen.

Success means a fan can watch a video and know who is on screen at any instant, and the operator can correct and improve that data over time.

## Positioning

The product's mechanism that a neighboring product could not truthfully copy: **dense, frame-synced face metadata computed offline and served read-only**, so recognition quality and correction workflow are separated from playback. Every stored face box is expressed in **frame fractions** (resolution-independent), and every match is a raw **cosine match score** compared against measured false-match-rate bands — numbers stay comparable across runs. The viewer is dumb and safe (public, read-only); all writes live in a local-only admin surface that is never deployed.

## Operating Context

- **Content domain:** 96 contestants from the show *King Maker* (全民造星); contestant numbers (編號 1–96) are the stable identifier; nicknames are unstable and may contain spaces or CJK characters. Reference photos come from Instagram (`source/photo/contestants/ig_photos/contestant_{id}/`).
- **Pipeline:** Python processing stack (InsightFace detection, ByteTrack tracking, ChromaDB/embedding matching), dense metadata output, Cloudflare Worker + R2 serving.
- **Deployment:** production URL `https://mv-face-recognition-api.herballemon.workers.dev/`. Admin is local-only (`local_api.py` + Vite, never deployed). Video IDs with CJK/space characters must round-trip end-to-end.
- **Terminology is contractual:** CONTEXT.md is the glossary and must be honored — *reference photo / reference embedding / reference set / match score / detection score / band / acceptance threshold / detection / recognition / flag / contestant / viewer / admin / frame fraction / bounding box / detection space*. Several of these have caused real bugs when renamed.

## Capabilities and Constraints

- **Viewer (apps/viewer):** read-only; displays recognitions; never writes. Served by the Cloudflare Worker with embedded assets.
- **Contestant thumbnail gallery (viewer, public):** the 96 contestants shown as face thumbnails, built from the reference photos on hand (3–20 per contestant, median 9). Served as cropped 320/640 px WebP derivatives from R2; the Instagram originals are archival inputs for embeddings and are never served. One portrait per contestant is chosen explicitly so the gallery is stable across reruns. (Owner statement, 2026-10-20.)
- **Admin (apps/admin):** every write operation — flagging (a human-proposed correction with pending/accepted/rejected lifecycle), reprocessing, embedding workbench. Local-only.
- **Shared (apps/shared):** components/hooks/types shared by viewer and admin.
- **Recognition pipeline:** frame-difference detection, IoU face tracking, parallel batching, dense metadata generation for 60 fps playback sync; HuggingFace XET storage for embeddings.
- **Scores:** match score is raw cosine (−1…1, higher = more similar, never rescaled); bands derive from measured false-match rate and are provisional until ground-truth labels exist. Detection score says only that a region *is* a face.
- **Known gaps:** publish path is broken in the middle (worker reads KV keys no script writes; deploy would serve fallback videos/mock metadata — see DESIGN.md TODO). Admin video-ingestion page is disabled until its backend exists. Automatic reprocessing after embedding updates is not implemented.
- **Open decision (unanswered):** which app scope Impeccable should target for design work — `apps/viewer`, `apps/admin`, or the whole monorepo from root. Context loading requires this choice before design commands run; init recorded product truth at root regardless.

## Brand Commitments

None established beyond the working name "MV Face Recognition". The show *King Maker* (全民造星) is third-party content, not a brand owned by this project; no visual identity, logo, or voice commitments are documented anywhere in the repo.

## Evidence on Hand

- `CONTEXT.md` — the project glossary (language is contractual).
- `product-plan/product-overview.md`, `product-plan/product-roadmap.md`, `product-plan/data-model/`, `product-plan/design-system/`.
- `DESIGN.md` — architecture and decision log (47 KB; frontend sections partially stale).
- `metadata/contestant_info.csv` — the 96 contestants (Traditional Chinese).
- `docs/wayfinder/MAP.md` — active effort map with 10 open decision tickets.
- Real assets: contestant reference photos, processed video metadata (`local_output/metadata/`, `metadata/`), flags (`local_output/flagged_faces.json`), `dashboard.png`/`workbench.png` screenshots.
- Absences future work must not fabricate: no testimonials, no press, no usage numbers, no user research.

## Product Principles

1. **The data is the product; the UI explains it honestly.** Raw cosines, measured bands, frame fractions — never dress numbers up as certainty they don't have.
2. **Writes stay home.** Anything that mutates data belongs to the local admin; the public surface is provably read-only.
3. **Terminology is contractual.** Use the CONTEXT.md glossary verbatim; renaming terms has caused real bugs.
4. **Stable identifiers over display names.** Contestant numbers, not nicknames, are the anchor; video IDs must round-trip even with CJK and spaces.
5. **Correction is a human loop.** Flags are proposals with a lifecycle; the system improves through accepted flags, not silently.

## Accessibility & Inclusion

No product-specific accessibility requirement is documented in the repo. (Interview unavailable; treat WCAG-level basics as a floor for any future design work, but this is not a confirmed commitment.)
