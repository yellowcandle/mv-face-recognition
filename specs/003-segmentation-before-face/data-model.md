# Phase 1: Data Model & Entities

**Feature**: Segmentation-Gated Face Recognition
**Date**: 2025-09-30

## Configuration Entities

### SegmentationConfig

**Purpose**: Configuration for person segmentation gating behavior

**Fields**:
- `enable_person_gating: bool` - Feature flag to enable/disable segmentation gating (default: `false`)
- `model_path: str` - Path to ONNX segmentation model (default: `"models/yolov8n-seg.onnx"`)
- `interval: int` - Frame interval for running segmentation (default: `15`, range: 5-30)
- `min_person_area: int` - Minimum pixel area to consider a person mask valid (default: `5000`)
- `expand_ratio: float` - Expansion factor for person bounding boxes (default: `1.2`, range: 1.0-1.5)
- `max_rois_per_frame: int` - Maximum ROIs to process per frame to bound compute (default: `20`)

**Validation Rules**:
- `interval` must be > 0 and <= 30 (no benefit beyond 1 second at 30fps)
- `min_person_area` must be >= 1000 (avoid tiny noise regions)
- `expand_ratio` must be >= 1.0 and <= 2.0 (1.0 = no expansion, 2.0 = double size)
- `max_rois_per_frame` must be > 0 and <= 50 (prevent memory explosion)

**State Transitions**: N/A (immutable config loaded at initialization)

**Relationships**:
- Used by: `PersonSegmenter`, `VideoProcessor`
- Loaded from: `config.json` root-level section

---

### FaceParsingConfig

**Purpose**: Configuration for face parsing validation of low-confidence detections

**Fields**:
- `enable_on_low_conf: bool` - Enable face parsing validation (default: `false`)
- `low_conf_threshold: float` - Confidence score below which to trigger validation (default: `0.5`, range: 0.0-1.0)
- `min_skin_ratio: float` - Minimum skin pixel ratio to accept face (default: `0.3`, range: 0.1-0.9)

**Validation Rules**:
- `low_conf_threshold` must be in range [0.0, 1.0]
- `min_skin_ratio` must be in range [0.1, 0.9] (0.1 = very lenient, 0.9 = very strict)
- If `enable_on_low_conf` is `true`, `low_conf_threshold` must be < 1.0 (otherwise no faces validated)

**State Transitions**: N/A (immutable config)

**Relationships**:
- Used by: `FaceParser`, `VideoProcessor`
- Loaded from: `config.json` root-level section

---

## Runtime Entities

### ROI (Region of Interest)

**Purpose**: Bounding box representing a person region for face detection

**Fields**:
- `x1: int` - Top-left X coordinate (pixels)
- `y1: int` - Top-left Y coordinate (pixels)
- `x2: int` - Bottom-right X coordinate (pixels)
- `y2: int` - Bottom-right Y coordinate (pixels)
- `confidence: float` - Segmentation confidence score (0.0-1.0)
- `area: int` - Pixel area (x2-x1) * (y2-y1)

**Validation Rules**:
- `x2 > x1` and `y2 > y1` (valid bounding box)
- `area >= min_person_area` (from SegmentationConfig)
- Coordinates must be within frame dimensions

**State Transitions**:
```
Created → Expanded (apply expand_ratio) → Cached → Expired/Invalidated
```

**Relationships**:
- Created by: `PersonSegmenter.segment()`
- Stored in: `ROICache`
- Used by: `VideoProcessor.detect_faces_in_roi()`

---

### ROICache

**Purpose**: Frame-indexed cache for reusing person regions between segmentation runs

**Fields**:
- `cache: Dict[int, List[ROI]]` - Frame index → list of ROIs
- `ttl_multiplier: int` - TTL as multiple of segmentation interval (default: `2`)
- `last_updated: Dict[int, int]` - Frame index → last update frame number

**Methods**:
- `update(frame_idx: int, rois: List[ROI])` - Store ROIs for given frame
- `get(frame_idx: int, interval: int) -> Optional[List[ROI]]` - Retrieve cached ROIs if not expired
- `is_expired(frame_idx: int, current_frame: int, interval: int) -> bool` - Check if cache entry is stale
- `clear()` - Clear all cache entries

**Cache Logic**:
```python
def get(self, frame_idx, interval):
    if frame_idx not in self.cache:
        return None  # Cache miss
    last_update = self.last_updated[frame_idx]
    if (frame_idx - last_update) > (interval * self.ttl_multiplier):
        del self.cache[frame_idx]  # Expired
        return None
    return self.cache[frame_idx]  # Cache hit
```

**Validation Rules**:
- Cache size bounded by video length (max ~1000 frames cached at 30fps, ~40KB memory)
- TTL prevents stale data in high-motion scenes

**State Transitions**:
```
Empty → Updated (ROIs stored) → Valid (within TTL) → Expired (beyond TTL) → Cleared
```

**Relationships**:
- Used by: `VideoProcessor`
- Populated by: `PersonSegmenter` output
- Triggers: Full-frame fallback when expired or empty

---

### FaceDetection (Extended)

**Purpose**: Face detection result with optional parsing validation metadata

**Existing Fields** (unchanged):
- `bbox: (x1, y1, x2, y2)` - Face bounding box
- `confidence: float` - Detection confidence
- `embedding: np.ndarray` - Face embedding vector
- `timestamp: float` - Frame timestamp

**New Fields** (additive, optional):
- `roi_source: Optional[ROI]` - Source person ROI (if segmentation-gated)
- `parsing_validated: Optional[bool]` - Whether face parsing was applied
- `skin_ratio: Optional[float]` - Skin pixel ratio (if parsed)

**Validation Rules**:
- If `parsing_validated` is `True`, `skin_ratio` must be present
- If `roi_source` is `None`, face was detected in full-frame mode
- New fields are `None` when feature is disabled (backward compatible)

**State Transitions**: N/A (immutable detection result)

**Relationships**:
- Created by: `FaceDetector.detect_faces_in_roi()`
- Optionally validated by: `FaceParser.validate_face()`
- Consumed by: Metadata generator (existing pipeline)

---

## Logging & Metrics Entities

### SegmentationMetrics

**Purpose**: Per-video observability metrics for segmentation pipeline

**Fields**:
- `total_frames: int` - Total frames processed
- `segmentation_runs: int` - Number of segmentation inferences
- `roi_counts: List[int]` - ROI count per segmentation run
- `cache_hits: int` - Number of cache hits
- `cache_misses: int` - Number of cache misses
- `full_frame_fallbacks: int` - Fallbacks to full-frame detection
- `faces_parsed: int` - Number of faces validated via parsing
- `faces_rejected: int` - Faces rejected by parsing
- `processing_time_seconds: float` - Total processing time

**Computed Metrics**:
- `segmentation_cadence_avg: float` = `total_frames / segmentation_runs`
- `roi_count_avg: float` = `mean(roi_counts)`
- `cache_hit_rate: float` = `cache_hits / (cache_hits + cache_misses)`
- `parsing_rejection_rate: float` = `faces_rejected / faces_parsed`

**Output Format** (JSON):
```json
{
  "video_id": "video_001.mp4",
  "total_frames": 300,
  "segmentation_runs": 20,
  "roi_count_avg": 3.5,
  "cache_hit_rate": 0.85,
  "processing_time_seconds": 12.4,
  "speedup_vs_baseline_pct": 23.5
}
```

**Relationships**:
- Collected by: `VideoProcessor`
- Logged via: Python logging framework (FR-008)
- Exported to: JSON metrics file for analytics

---

## Metadata Schema Extensions (Additive)

**Existing Schema** (preserved, FR-005):
```json
{
  "video_id": "...",
  "frames": [
    {
      "frame_idx": 0,
      "timestamp": 0.0,
      "faces": [
        {
          "bbox": [x1, y1, x2, y2],
          "confidence": 0.95,
          "contestant_id": 42
        }
      ]
    }
  ]
}
```

**New Optional Fields** (additive):
```json
{
  "segmentation_enabled": true,
  "segmentation_config": {
    "interval": 15,
    "min_person_area": 5000
  },
  "frames": [
    {
      "frame_idx": 0,
      "roi_count": 3,  // NEW: optional
      "faces": [
        {
          "bbox": [x1, y1, x2, y2],
          "confidence": 0.95,
          "contestant_id": 42,
          "roi_gated": true,  // NEW: optional
          "parsing_validated": false  // NEW: optional
        }
      ]
    }
  ]
}
```

**Backward Compatibility**:
- All new fields are optional
- Old metadata readers ignore unknown fields
- New readers gracefully handle missing fields with defaults

---

## Data Flow Diagram

```
[VideoProcessor]
    ↓ (every K frames)
[PersonSegmenter] → List[ROI]
    ↓
[ROICache] ← store
    ↓ (retrieve with TTL check)
[detect_faces_in_roi()] → List[FaceDetection]
    ↓ (if confidence < threshold)
[FaceParser] → skin_ratio
    ↓ (filter by min_skin_ratio)
[MetadataGenerator] → JSON output
```

---

## Entity Relationships Summary

```
SegmentationConfig ──> PersonSegmenter ──> ROI ──> ROICache
                                             ↓
FaceParsingConfig ──> FaceParser      VideoProcessor
                          ↓                  ↓
                    FaceDetection ──> MetadataGenerator ──> JSON
                                             ↓
                                   SegmentationMetrics ──> Logs
```

---

## Phase 1 Completion Checklist

- [x] Configuration entities defined (SegmentationConfig, FaceParsingConfig)
- [x] Runtime entities defined (ROI, ROICache, FaceDetection extensions)
- [x] Validation rules documented for all fields
- [x] State transitions specified where applicable
- [x] Relationships mapped between entities
- [x] Metadata schema extensions defined (additive, backward compatible)
- [x] Logging/metrics entities specified (SegmentationMetrics)
- [x] Data flow diagram created

**Status**: ✅ Ready for contract generation and test scaffolding