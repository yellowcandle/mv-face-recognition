# Embedding Workbench

## Problem

Face recognition accuracy is ~1% (23/2,349 faces recognized in a typical video). Root causes:
1. Reference photos are Instagram screenshots — poor quality for face embeddings
2. No way to visually evaluate embedding quality or identify confusion pairs
3. No feedback loop: detected faces can't be curated back into reference material
4. Triple-naming mess: `Carina` / `李晞彤` / `contestant_15` embeddings coexist with unclear provenance

## Solution

Replace the existing `/admin` page with an **Embedding Workbench** — a unified admin tool for managing, evaluating, and improving face recognition embeddings.

## Scope

### In Scope
- **Coverage Dashboard**: Grid of 96 contestants color-coded by embedding quality
- **Contestant Detail View**: Side-by-side reference photos vs detected faces from videos
- **Confusion Matrix**: Pairwise similarity heatmap to identify easily-confused contestants
- **Unmatched Face Browser**: Clustered view of detected-but-unrecognized faces for assignment
- **Embedding Curation Flow**: Approve video face crops as new reference material → regenerate embeddings
- **Photo Upload**: Upload clean reference photos per contestant
- **Backend Pipeline Changes**: Save face embeddings (not just bboxes) during video processing

### Out of Scope
- End-user facing gallery (separate concern)
- Webcam-based recognition
- Real-time processing UI

## Architecture

### Two Layers

**Layer 1: Python (offline precomputation)**
- `generate_coverage.py` → `coverage.json` (scan embeddings, aggregate metadata confidence)
- `compute_similarity.py` → `similarity_matrix.json` (96×96 pairwise cosine similarity)
- Modified video processor → saves face embeddings for unmatched faces
- `cluster_unmatched.py` → `clusters.json` (HDBSCAN on unmatched face embeddings)

**Layer 2: SvelteKit (local admin UI)**
- Reads precomputed JSONs for dashboards
- On-demand face crops via `<canvas>` + `<video>` seek (no stored crops needed)
- Photo upload + embedding regeneration triggers
- Replaces existing `/admin` route

### Face Crop Workflow (Hybrid)
- **Browse**: Client-side canvas extracts face crop from video at timestamp using bbox coordinates (fast preview)
- **Commit**: When user approves a face crop as reference material, Python extracts high-res crop and adds to embedding reference set

## Priority

| Priority | Feature | Impact | Effort |
|----------|---------|--------|--------|
| P0 | Clean up triple-naming in embeddings | Removes confusion | Low |
| P1 | Coverage dashboard (Tab 1) | Visibility into the problem | Medium |
| P1 | Confusion matrix (Tab 3) | Find worst embedding pairs | Medium |
| P2 | Contestant detail + canvas crops (Tab 2) | Curate better references | High |
| P3 | Unmatched face clustering (Tab 4) | Biggest accuracy boost | High |

## Data Flow

```
contestant_info.csv ─────────┐
                              │
embedding files (.npy) ──────┤
                              ├──▶ generate_coverage.py ──▶ coverage.json
metadata/*.json ─────────────┤
                              │
                              └──▶ compute_similarity.py ──▶ similarity_matrix.json

video processing pipeline ──▶ saves unmatched face embeddings
                              │
                              └──▶ cluster_unmatched.py ──▶ clusters.json

SvelteKit /admin reads: coverage.json, similarity_matrix.json, clusters.json, metadata/*.json
SvelteKit /admin streams: videos from local/R2 for on-demand canvas crops
```
