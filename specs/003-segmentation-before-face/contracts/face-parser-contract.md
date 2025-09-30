# FaceParser Contract

## Purpose
Validate low-confidence face detections using skin segmentation to reduce false positives.

## Interface

### Constructor
```python
FaceParser(config: FaceParsingConfig)
```

**Preconditions**:
- `config.low_conf_threshold` in range [0.0, 1.0]
- `config.min_skin_ratio` in range [0.1, 0.9]

**Postconditions**:
- Configuration stored
- HSV skin color range initialized (no model loading required)

---

### validate_face(frame: np.ndarray, face_detection: FaceDetection) → bool
```python
def validate_face(self, frame: np.ndarray, face_detection: FaceDetection) -> bool:
    """
    Validate face detection using skin segmentation.

    Args:
        frame: Full video frame (HxWx3 BGR)
        face_detection: Face detection object with bbox and confidence

    Returns:
        True if face passes validation, False if rejected

    Raises:
        ValueError: If frame or face_detection invalid
    """
```

**Logic**:
```
IF face_detection.confidence >= config.low_conf_threshold:
    RETURN True  # High confidence, skip parsing

face_roi = extract_roi(frame, face_detection.bbox)
hsv_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
skin_mask = apply_skin_color_range(hsv_roi)
skin_ratio = count_nonzero(skin_mask) / roi_area

IF skin_ratio >= config.min_skin_ratio:
    RETURN True  # Sufficient skin pixels
ELSE:
    RETURN False  # Reject as false positive
```

**Preconditions**:
- `frame` is valid BGR frame
- `face_detection.bbox` within frame boundaries
- `face_detection.confidence` in range [0.0, 1.0]

**Postconditions**:
- Returns `True` if face passes validation (either high confidence or sufficient skin ratio)
- Returns `False` if face rejected (low confidence AND low skin ratio)
- `face_detection` object unchanged (validation does not modify)
- Computation time < 1ms per face

**Invariants**:
- High-confidence faces (>= threshold) always pass without parsing
- Parsing only applied to low-confidence detections

---

### compute_skin_ratio(frame: np.ndarray, bbox: Tuple[int, int, int, int]) → float
```python
def compute_skin_ratio(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """
    Compute skin pixel ratio within bounding box.

    Returns:
        Ratio of skin pixels to total pixels (0.0-1.0)
    """
```

**Preconditions**:
- `bbox = (x1, y1, x2, y2)` with `x2 > x1` and `y2 > y1`
- `bbox` within frame boundaries

**Postconditions**:
- Returns float in range [0.0, 1.0]
- 0.0 = no skin pixels, 1.0 = all pixels are skin

**Skin Color Range** (HSV):
```python
# Tuned for diverse skin tones
lower_skin = np.array([0, 20, 70], dtype=np.uint8)
upper_skin = np.array([20, 255, 255], dtype=np.uint8)
```

---

### get_validation_stats() → Dict[str, int]
```python
def get_validation_stats(self) -> Dict[str, int]:
    """
    Get statistics on validation decisions.

    Returns:
        Dict with keys: total_validated, passed, rejected, avg_skin_ratio
    """
```

---

## Error Handling

| Error Condition | Exception | Expected Behavior |
|----------------|-----------|-------------------|
| Invalid bbox (out of bounds) | `ValueError` | Log warning, return True (permissive) |
| Empty ROI | `ValueError` | Log warning, return True |
| Invalid frame shape | `ValueError` | Raise immediately |
| Confidence out of range | `ValueError` | Clamp to [0, 1], log warning |

---

## Contract Tests

### test_face_parser_initialization
- Given: Valid FaceParsingConfig
- When: FaceParser created
- Then: No exception, config stored

### test_high_confidence_skips_parsing
- Given: Face with confidence=0.8, threshold=0.5
- When: validate_face() called
- Then: Returns True without parsing (fast path)

### test_low_confidence_triggers_parsing
- Given: Face with confidence=0.3, threshold=0.5
- When: validate_face() called
- Then: Parsing executed, skin_ratio computed

### test_sufficient_skin_ratio_passes
- Given: Face with confidence=0.3, skin_ratio=0.6, min_skin_ratio=0.3
- When: validate_face() called
- Then: Returns True

### test_insufficient_skin_ratio_rejects
- Given: Face with confidence=0.3, skin_ratio=0.1, min_skin_ratio=0.3
- When: validate_face() called
- Then: Returns False

### test_compute_skin_ratio_valid_face
- Given: Frame with face region containing skin pixels
- When: compute_skin_ratio() called
- Then: Returns ratio in [0.1, 0.9] range

### test_compute_skin_ratio_no_skin
- Given: Frame with non-face region (e.g., text overlay)
- When: compute_skin_ratio() called
- Then: Returns ratio < 0.1

### test_validation_performance
- Given: 100 low-confidence faces
- When: validate_face() called on each
- Then: Average time < 1ms per face

---

## Performance Requirements

- **High-confidence path**: ~0.01ms (comparison only)
- **Parsing path**: < 1ms per face (HSV conversion + thresholding)
- **Memory**: Negligible (no model loading, OpenCV operations only)

---

## Tuning Parameters

### Skin Color Range (HSV)
- **Lower bound**: [0, 20, 70] (Hue 0°-20°, low saturation/value filter)
- **Upper bound**: [20, 255, 255] (covers orange-brown skin tones)
- **Rationale**: Conservative range to handle diverse skin tones and lighting

### min_skin_ratio Recommendations
- **0.2**: Very lenient, accepts most faces including partial occlusions
- **0.3**: Default, balanced precision/recall
- **0.5**: Strict, rejects heavily occluded or non-frontal faces

---

## Limitations

- **Lighting sensitivity**: Extreme lighting (very dark/bright) may affect HSV thresholding
- **Skin tone coverage**: Tuned for common skin tones; may need adjustment for edge cases
- **Occlusions**: Masks, hands, or hair covering face reduce skin_ratio
- **Non-face objects**: Some objects (wood, certain fabrics) may have skin-like HSV values

**Mitigation**: Low confidence threshold (< 0.5) means most valid faces pass without parsing

---

## Dependencies

- `opencv-python` (cv2.cvtColor, HSV operations)
- `numpy` (array operations)