# Tasks: Embedding Workbench

## Phase 0: Backend Precomputation Scripts

### T0.1: Clean up triple-naming in embeddings
- **Priority**: P0
- **What**: Audit all `.npy` files in `source/photo/contestants/` — normalize to a single canonical naming scheme (e.g. `contestant_{number}_embedding.npy`)
- **Update**: `contestant_info.csv` if needed, ChromaDB entries, HuggingFace uploads
- **Risk**: Breaking change for existing metadata references

### T0.2: Create `generate_coverage.py`
- **Priority**: P1
- **What**: Script that scans embeddings dir + metadata JSONs → outputs `coverage.json`
- **Output format**:
  ```json
  {
    "contestants": [
      {
        "id": "1", "name": "...", "nickname": "...",
        "has_embedding": true,
        "embedding_dim": 512,
        "avg_confidence": 0.31,
        "detection_count": 5,
        "quality": "good|weak|missing"
      }
    ],
    "summary": { "total": 96, "good": 40, "weak": 38, "missing": 18 }
  }
  ```
- **Location**: `mvp-processor/scripts/generate_coverage.py`

### T0.3: Create `compute_similarity.py`
- **Priority**: P1
- **What**: Load all 96 embeddings → compute 96×96 pairwise cosine similarity matrix → output `similarity_matrix.json`
- **Output**: `{ "labels": [...], "matrix": [[...]] }` — row-major, values 0.0–1.0
- **Also output**: `top_pairs.json` — sorted list of highest confusion pairs
- **Location**: `mvp-processor/scripts/compute_similarity.py`

### T0.4: Modified video processor — save unmatched face embeddings
- **Priority**: P2
- **What**: During video processing, when a detected face has no match above threshold, save its encoding vector to a separate directory
- **Output**: `unmatched_faces/{video_id}/face_{frame}_{idx}.npy` + `unmatched_index.json`
- **File**: `mvp-processor/src/process_video.py` — modify processing loop

### T0.5: Create `cluster_unmatched.py`
- **Priority**: P3
- **What**: HDBSCAN clustering on unmatched face embeddings → `clusters.json`
- **Output**: `{ "clusters": [{ "id": 0, "face_count": 12, "face_ids": [...], "centroid": [...] }] }`
- **Depends on**: T0.4

## Phase 1: SvelteKit Route + Tab Navigation

### T1.1: Create `/embedding-workbench` route with tab navigation
- **What**: New SvelteKit route with 4 tabs matching designs: Coverage | Detail | Confusion | Unmatched
- **File**: `mvp-processor/src/routes/embedding-workbench/+page.svelte`
- **Design ref**: All 4 frames share the same tab bar (node IDs: `XFOE6`, `qsdCT`, `VnEhv`, `3vhZL`)
- **Loads**: `coverage.json` on mount (other JSONs loaded per-tab)

### T1.2: Add to navigation
- **File**: `mvp-processor/src/routes/+layout.svelte`
- **What**: Add "Embedding Workbench" to nav (icon: 🧬 or similar), in the admin/operational section
- **Depends on**: T1.1

## Phase 2: Coverage Dashboard (Tab 1)

### T2.1: Stats row — 3 metric cards
- **Design ref**: `XFOE6` top section
- **What**: Coverage (X/96, Y%), Avg Confidence, Recognition Rate
- **Data**: `coverage.json` → `summary`

### T2.2: Contestant grid with color coding
- **Design ref**: `XFOE6` grid section
- **What**: 4-column grid of tiles, each showing number + nickname
- **Color**: Green (good), Orange (weak), Red (missing) via `quality` field
- **Click**: Navigate to Detail tab with contestant selected

### T2.3: Legend + Regenerate All button
- **Design ref**: `XFOE6` header + legend
- **What**: Header with "Regenerate All" action button, legend showing color meanings

## Phase 3: Contestant Detail (Tab 2)

### T3.1: Left panel — reference sources + upload
- **Design ref**: `qsdCT` left panel (340px)
- **What**: Show current reference photos (from HuggingFace/local), upload button, confidence distribution histogram
- **Histogram**: Bar chart of confidence values from metadata

### T3.2: Right panel — detected face cards
- **Design ref**: `qsdCT` right panel
- **What**: Grid of face crop cards from video detections — each shows canvas-extracted face thumbnail, confidence, video/timestamp, Use/Skip actions
- **Canvas crop**: Seek `<video>` to timestamp → extract bbox region via canvas (no stored crops)

### T3.3: Confused With section
- **Design ref**: `qsdCT` bottom right
- **What**: List of top-N most similar contestants from `similarity_matrix.json`
- **Data**: Read row for selected contestant, sort by similarity descending

### T3.4: Regenerate Embedding action
- **What**: Button triggers Python embedding regeneration for selected contestant
- **Flow**: Calls backend endpoint → runs InsightFace → updates .npy + ChromaDB + HuggingFace

## Phase 4: Confusion Matrix (Tab 3)

### T4.1: Heatmap visualization
- **Design ref**: `VnEhv` left panel
- **What**: 96×96 grid with orange intensity = similarity. Diagonal brightest.
- **Data**: `similarity_matrix.json`
- **Render**: Canvas-based (too many cells for DOM), hover shows pair info

### T4.2: Top Confusion Pairs sidebar
- **Design ref**: `VnEhv` right panel (320px)
- **What**: Sorted list of highest-similarity pairs with names + scores
- **Click**: Opens Detail tab for the selected contestant

## Phase 5: Unmatched Faces (Tab 4)

### T5.1: Info banner + cluster cards
- **Design ref**: `3vhZL`
- **What**: Show total unmatched count + cluster count, then grid of cluster cards
- **Each card**: Cluster name, face count, thumbnail grid with "+N" overflow

### T5.2: Assignment flow
- **Design ref**: `3vhZL` assignment state
- **What**: Dropdown to assign cluster to contestant, "Add to Embedding" button
- **Flow**: Assignment → triggers embedding regeneration including these face crops
- **Depends on**: T0.4, T0.5
