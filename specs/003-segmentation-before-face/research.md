# Phase 0: Research & Technical Decisions

**Feature**: Segmentation-Gated Face Recognition
**Date**: 2025-09-30

## Research Questions

### 1. Person Segmentation Model Selection

**Decision**: Use lightweight ONNX-compatible person segmentation model (YOLOv8-seg or MediaPipe Selfie Segmentation)

**Rationale**:
- ONNX Runtime provides cross-platform CPU/GPU execution without PyTorch dependency overhead
- YOLOv8-seg nano/small variants: ~3-6ms inference on CPU, excellent person detection
- MediaPipe Selfie Segmentation: optimized for real-time person masks, WebAssembly compatible
- Both support bounding box extraction from segmentation masks
- Performance target: <10ms per frame to stay within 10-30% speedup budget

**Alternatives Considered**:
- **Mask R-CNN**: Too heavy (100-200ms per frame), defeats performance goal
- **DeepLabV3**: Good quality but 30-50ms inference, borderline for real-time
- **PyTorch Detectron2**: Requires full PyTorch runtime, heavier deployment

**Integration Points**:
- Load ONNX model once at VideoProcessor initialization
- Run inference every K frames (10-20), extract person bounding boxes
- Expand boxes by configurable `expand_ratio` to avoid cropping faces at edges

---

### 2. ROI Cache Design Pattern

**Decision**: Frame-indexed dictionary with adaptive TTL (2x segmentation interval)

**Rationale**:
- Simple dict keyed by `frame_index`: `{frame_idx: [(x1,y1,x2,y2), ...], ...}`
- TTL = 2x interval ensures cache reuse between segmentation runs
- Fallback to full-frame when cache expires or no ROIs found
- Memory overhead negligible: 96 cached frames at 30fps = 3.2 seconds, ~4KB data

**Alternatives Considered**:
- **LRU Cache with size limit**: Over-engineering for sequential video processing
- **Motion-based invalidation**: Requires optical flow, adds complexity and latency
- **Per-ROI TTL**: Finer-grained but complicates tracking logic

**Edge Case Handling**:
- No ROIs found: fallback to full-frame detection (FR-002)
- Heavy motion: tracker detects large displacement → force re-segmentation
- Dense scenes: cap max ROIs per frame (e.g., 20) to bound compute

---

### 3. Face Parsing for Low-Confidence Validation

**Decision**: Optional post-processing with lightweight skin segmentation (OpenCV HSV thresholding)

**Rationale**:
- Confidence threshold < 0.5 triggers validation (clarified in spec)
- OpenCV HSV-based skin detection: <1ms, no model loading
- Compute skin pixel ratio in face bounding box
- Reject/down-weight if skin_ratio < configurable threshold (e.g., 0.3)
- Does NOT modify embeddings (FR-004), only influences acceptance logic

**Alternatives Considered**:
- **Face parsing models (BiSeNet, FaceParsing)**: 10-20ms per face, too slow
- **Embedding adjustment**: Breaks compatibility with existing face database
- **Always-on validation**: Wastes compute on high-confidence detections (>0.5)

**Implementation Strategy**:
- Extract face ROI from frame
- Convert BGR → HSV, apply skin color mask
- Count skin pixels / total pixels
- Log validation results for observability

---

### 4. Configuration Schema Extension

**Decision**: Extend existing `config.json` with segmentation section

**Current Config Structure** (from `video_processor.py`):
```json
{
  "video": {
    "fps_sample_rate": 2,
    "max_frames": 1000,
    "resize_width": 640
  },
  "face_detection": {
    "confidence_threshold": 0.5,
    "nms_threshold": 0.4
  }
}
```

**New Schema** (additive):
```json
{
  "segmentation": {
    "enable_person_gating": false,
    "model_path": "models/yolov8n-seg.onnx",
    "interval": 15,
    "min_person_area": 5000,
    "expand_ratio": 1.2,
    "max_rois_per_frame": 20
  },
  "face_parsing": {
    "enable_on_low_conf": false,
    "low_conf_threshold": 0.5,
    "min_skin_ratio": 0.3
  }
}
```

**Backward Compatibility**:
- Defaults to `enable_person_gating: false` (FR-001)
- Existing pipelines unaffected unless explicitly enabled
- All thresholds configurable (FR-007)

---

### 5. Integration with Existing Face Detection Pipeline

**Code Reference Points** (from spec input):
- `EnhancedVideoProcessor`: ~line 1002 calls `detect_faces()`
- `Real-time VideoProcessor (RTVP)`: ~line 363 calls `detect_faces()`

**Integration Strategy**:
```python
# Pseudo-code for video_processor.py modification
class VideoProcessor:
    def __init__(self, config):
        self.segmenter = PersonSegmenter(config) if config["segmentation"]["enable_person_gating"] else None
        self.roi_cache = ROICache(ttl_multiplier=2)

    def process_frame(self, frame, frame_idx):
        # Step 1: Get ROIs (from cache or segmentation)
        if self.segmenter and frame_idx % self.segmenter.interval == 0:
            rois = self.segmenter.segment(frame)
            self.roi_cache.update(frame_idx, rois)
        else:
            rois = self.roi_cache.get(frame_idx, default_full_frame=True)

        # Step 2: Run face detection within ROIs
        all_faces = []
        for roi in rois:
            faces = self.detect_faces_in_roi(frame, roi)
            all_faces.extend(faces)

        # Step 3: Optional face parsing validation
        if self.face_parser:
            all_faces = [f for f in all_faces if self.validate_face(frame, f)]

        return all_faces
```

**Performance Implications**:
- Segmentation overhead: ~5ms every 15 frames = 0.33ms/frame amortized
- Face detection speedup: ~30-50% fewer pixels to scan (person regions only)
- Net expected gain: 10-30% overall pipeline speedup (NFR-001)

---

### 6. Testing Strategy

**Test Categories**:

1. **Unit Tests** (pytest):
   - `test_person_segmenter.py`: model loading, inference, bbox extraction
   - `test_roi_cache.py`: cache hit/miss, TTL expiry, fallback logic
   - `test_face_parser.py`: skin segmentation, threshold validation

2. **Contract Tests**:
   - `test_segmentation_config.py`: config schema validation, defaults
   - Verify backward compatibility (old configs still work)

3. **Integration Tests**:
   - `test_segmentation_pipeline.py`: end-to-end video processing
   - Verify 100% recall vs. baseline (NFR-002)
   - Measure performance improvement (NFR-001: 10-30% faster)
   - Test edge cases: no ROIs, dense scenes, cache expiry

4. **Performance Benchmarks**:
   - Baseline: full-frame detection on test videos
   - Segmentation-gated: measure processing time, recall, precision
   - Log ROI counts, segmentation cadence (FR-008)

---

## Technical Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Segmentation model misses people → recall < 100% | HIGH | Fallback to full-frame when no ROIs, expand_ratio safety margin |
| Segmentation overhead > detection savings | MEDIUM | Use lightweight model (YOLOv8n), low interval frequency |
| ROI expansion crops faces at boundaries | MEDIUM | Configurable expand_ratio (default 1.2 = 20% padding) |
| Face parsing false negatives (non-skin tones) | LOW | Only applies to low-conf (<0.5), tunable min_skin_ratio |
| Config complexity confuses users | LOW | Sensible defaults, feature flag for easy disable |

---

## Dependencies & Model Requirements

**New Dependencies**:
- `onnxruntime` or `onnxruntime-gpu` (1.16+)
- Pre-trained ONNX models:
  - YOLOv8n-seg.onnx (~6MB) OR MediaPipe selfie segmentation (~1MB)
  - Downloaded during setup or bundled in `models/` directory

**Existing Dependencies** (no changes):
- OpenCV 4.8+ (already in requirements.txt)
- NumPy 1.24+ (already in requirements.txt)

**Model Hosting**:
- Store in `mvp-processor/models/` (Git LFS for >10MB files)
- Or download on first run from HuggingFace/GitHub releases

---

## Logging & Observability (FR-008)

**Log Points**:
```python
logger.info(f"Segmentation: {len(rois)} ROIs found at frame {frame_idx}, cadence={interval}")
logger.info(f"Face parsing: {rejected_count}/{total_count} faces rejected (low skin ratio)")
logger.info(f"ROI cache: {hit_rate:.1%} hit rate, {miss_count} misses, {fallback_count} full-frame fallbacks")
```

**Performance Metrics**:
- Track per-video: total_frames, segmentation_runs, roi_count_avg, processing_time
- Compare against baseline: speedup_percentage, recall_percentage
- Export to JSON for analytics dashboard

---

## Phase 0 Completion Checklist

- [x] Person segmentation model selected (YOLOv8-seg ONNX)
- [x] ROI cache pattern designed (frame-indexed dict, adaptive TTL)
- [x] Face parsing approach defined (OpenCV HSV skin segmentation)
- [x] Configuration schema extended (backward compatible)
- [x] Integration points identified (VideoProcessor.process_frame)
- [x] Testing strategy outlined (unit, contract, integration, performance)
- [x] Dependencies documented (onnxruntime, model files)
- [x] Observability plan defined (logging, metrics)

**Status**: ✅ Phase 0 Complete - Ready for Phase 1 (Design & Contracts)