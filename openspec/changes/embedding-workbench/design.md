# Embedding Workbench — Design Document

## Design File

**Pencil file**: `untitled.pen`

### Screen Frames (node IDs)

| Screen | Node ID | Description |
|--------|---------|-------------|
| Coverage Dashboard | `XFOE6` | Grid of 96 contestants color-coded by embedding quality |
| Contestant Detail | `qsdCT` | Side-by-side reference photos vs detected faces, confidence histogram, confusion pairs |
| Confusion Matrix | `VnEhv` | Pairwise similarity heatmap + top confusion pairs list |
| Unmatched Faces | `3vhZL` | Clustered unrecognized faces with assignment dropdowns |

## Design System

Uses the existing **Lunaris** design system (dark mode) with variables:
- `$--background` (#111111) — page background
- `$--card` (#1A1A1A) — card surfaces
- `$--foreground` (#FFFFFF) — primary text
- `$--muted-foreground` (#B8B9B6) — secondary text
- `$--primary` (#FF8400) — orange accent
- `$--border` (#2E2E2E) — borders
- `$--color-success` / `$--color-success-foreground` — green (good quality)
- `$--color-warning` / `$--color-warning-foreground` — orange (weak quality)
- `$--color-error` / `$--color-error-foreground` — red (missing/critical)

## Screen Details

### 1. Coverage Dashboard
- **Header**: Title + "Regenerate All" button
- **Tab bar**: Coverage (active) | Detail | Confusion | Unmatched
- **Stats row**: 3 metric cards — Coverage (78/96, 81%), Avg Confidence (0.31), Recognition Rate (0.98%)
- **Contestant grid**: 4+ columns of tiles, each showing contestant number + nickname, color-coded:
  - Green: good embedding (confidence > 0.4)
  - Orange: weak embedding (0.25–0.4)
  - Red: missing or never detected

### 2. Contestant Detail
- **Header**: Back button + contestant name/number + "Weak" badge + "Regenerate Embedding" button
- **Left panel (340px)**: Reference sources (current IG screenshots), upload button, confidence distribution histogram
- **Right panel (fill)**: Detected face cards from videos — each shows face crop placeholder, confidence score, video/timestamp, Use/Skip actions
- **Bottom right**: "Confused With" section listing similar contestants with similarity scores

### 3. Confusion Matrix
- **Left (fill)**: Pairwise similarity heatmap — orange intensity = higher confusion risk, diagonal = self (brightest)
- **Right (320px)**: "Top Confusion Pairs" list with contestant names, bidirectional arrow, and similarity score

### 4. Unmatched Faces
- **Info banner**: Total count of unrecognized faces and cluster count
- **Cluster cards**: Each shows cluster name, face count, thumbnail grid with "+N" overflow, and "Assign to" dropdown
- **Assigned state**: Green badge showing assignment, "Add to Embedding" button

## Interaction Patterns

### Coverage → Detail Navigation
Click a contestant tile in the grid → opens Detail view for that contestant

### Face Curation Flow (Detail view)
1. Browse detected faces sorted by confidence
2. Click "Use" to approve as reference material
3. Click "Regenerate Embedding" to rebuild from approved faces + uploaded photos

### Confusion Matrix → Detail Navigation
Click a confusion pair → opens Detail view for the worse-performing contestant

### Unmatched Face Assignment (Unmatched view)
1. Browse clustered face groups
2. Select contestant from dropdown
3. Click "Add to Embedding" to incorporate cluster faces into that contestant's embedding
