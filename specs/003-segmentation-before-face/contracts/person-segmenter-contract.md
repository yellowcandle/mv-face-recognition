# PersonSegmenter Contract

## Purpose
Perform person segmentation on video frames and extract person bounding boxes for face detection gating.

## Interface

### Constructor
```python
PersonSegmenter(config: SegmentationConfig)
```

**Preconditions**:
- `config.model_path` points to valid ONNX model file
- ONNX Runtime is installed

**Postconditions**:
- Model loaded into memory
- Inference session created (CPU or GPU based on availability)

**Throws**:
- `FileNotFoundError` if model file not found
- `RuntimeError` if ONNX Runtime initialization fails

---

### segment(frame: np.ndarray) → List[ROI]
```python
def segment(self, frame: np.ndarray) -> List[ROI]:
    """
    Run person segmentation on frame and return person bounding boxes.

    Args:
        frame: Input frame (HxWx3 BGR format)

    Returns:
        List of ROI objects representing detected people

    Raises:
        ValueError: If frame is invalid (empty, wrong shape, wrong dtype)
    """
```

**Preconditions**:
- `frame` is valid numpy array with shape (H, W, 3) and dtype uint8
- `frame` is not empty (H > 0, W > 0)

**Postconditions**:
- Returns list of ROI objects (may be empty if no people detected)
- All returned ROIs have `area >= config.min_person_area`
- All ROIs expanded by `config.expand_ratio`
- ROI coordinates clamped to frame boundaries
- Maximum `config.max_rois_per_frame` ROIs returned (sorted by confidence)

**Invariants**:
- ROIs do not overlap more than 50% (NMS applied)
- ROIs are sorted descending by confidence score
- Each ROI satisfies: `x2 > x1` and `y2 > y1`

**Performance**:
- Target: < 10ms per frame on CPU (YOLOv8n-seg nano model)
- GPU acceleration used if available (< 5ms)

---

### get_model_info() → Dict[str, Any]
```python
def get_model_info(self) -> Dict[str, Any]:
    """
    Return metadata about loaded segmentation model.

    Returns:
        Dict with keys: model_path, input_shape, backend, device
    """
```

**Postconditions**:
- Returns dict with model metadata
- `backend` is one of ["CPUExecutionProvider", "CUDAExecutionProvider", "CoreMLExecutionProvider"]

---

## Error Handling

| Error Condition | Exception | Expected Behavior |
|----------------|-----------|-------------------|
| Model file not found | `FileNotFoundError` | Fail fast at initialization |
| Invalid frame shape | `ValueError` | Log error, return empty list |
| Inference timeout (>1s) | `TimeoutError` | Log warning, return empty list |
| ONNX Runtime error | `RuntimeError` | Log error, return empty list |
| No persons detected | N/A | Return empty list (valid state) |

---

## Contract Tests

### test_person_segmenter_initialization
- Given: Valid config with model path
- When: PersonSegmenter initialized
- Then: No exception raised, model_info returned

### test_segment_valid_frame
- Given: Valid BGR frame (640x480x3)
- When: segment(frame) called
- Then: Returns list of ROIs, all ROIs have valid coordinates

### test_segment_returns_filtered_rois
- Given: Frame with small and large person masks
- When: segment(frame) called
- Then: Only ROIs >= min_person_area returned

### test_segment_respects_max_rois
- Given: Frame with 30 detected people, max_rois_per_frame=20
- When: segment(frame) called
- Then: Returns exactly 20 ROIs (top confidence)

### test_segment_expands_rois
- Given: Frame with detected person at (100, 100, 200, 300)
- When: segment(frame) called with expand_ratio=1.2
- Then: Returned ROI expanded by 10% on each side

### test_segment_handles_invalid_frame
- Given: Empty frame or wrong shape
- When: segment(frame) called
- Then: ValueError raised or empty list returned

### test_segment_performance
- Given: 640x480 frame
- When: segment(frame) called 10 times
- Then: Average inference time < 10ms per frame

---

## Dependencies
- `onnxruntime` or `onnxruntime-gpu`
- `numpy`
- `cv2` (for frame preprocessing)

## Model Requirements
- Input: RGB image, shape (1, 3, H, W), dtype float32, range [0, 1]
- Output: Segmentation masks, shape (1, 1, H, W) or bounding boxes
- Format: ONNX (YOLOv8-seg or compatible architecture)