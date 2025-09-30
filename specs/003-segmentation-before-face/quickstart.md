# Quickstart: Segmentation-Gated Face Recognition

**Purpose**: Step-by-step guide to test and validate the segmentation-gated face recognition feature.

## Prerequisites

- Python 3.12+
- Existing MV Face Recognition system installed
- Test video file in `/source/videos/` directory
- ONNX Runtime installed: `pip install onnxruntime`
- YOLOv8-seg model downloaded (instructions below)

---

## Step 1: Download Segmentation Model

```bash
# Create models directory
mkdir -p mvp-processor/models

# Download YOLOv8n-seg ONNX model (~6MB)
cd mvp-processor/models
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-seg.onnx

# Verify download
ls -lh yolov8n-seg.onnx  # Should be ~6MB
```

**Alternative**: Use MediaPipe selfie segmentation model (lighter, ~1MB)
```bash
# Instructions for MediaPipe model if YOLOv8 unavailable
wget https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.onnx
```

---

## Step 2: Update Configuration

Edit `config.json` (or create test config):

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
  },
  "segmentation": {
    "enable_person_gating": true,
    "model_path": "models/yolov8n-seg.onnx",
    "interval": 15,
    "min_person_area": 5000,
    "expand_ratio": 1.2,
    "max_rois_per_frame": 20
  },
  "face_parsing": {
    "enable_on_low_conf": true,
    "low_conf_threshold": 0.5,
    "min_skin_ratio": 0.3
  }
}
```

**Save as**: `config_segmentation_test.json`

---

## Step 3: Run Baseline Processing (Without Segmentation)

```bash
cd mvp-processor

# Disable segmentation for baseline
python src/process_video.py \
  --video /source/videos/test_video.mp4 \
  --config config_baseline.json \
  --output baseline_results.json

# Note processing time
echo "Baseline processing time: [manually record]"
```

**Baseline config** (`config_baseline.json`):
```json
{
  "segmentation": {
    "enable_person_gating": false
  }
}
```

---

## Step 4: Run Segmentation-Gated Processing

```bash
# Enable segmentation
python src/process_video.py \
  --video /source/videos/test_video.mp4 \
  --config config_segmentation_test.json \
  --output segmentation_results.json

# Note processing time
echo "Segmentation-gated processing time: [manually record]"
```

---

## Step 5: Validate Results

### 5.1 Check Performance Improvement

```bash
# Compare processing times
python -c "
import json
with open('baseline_results.json') as f:
    baseline = json.load(f)
with open('segmentation_results.json') as f:
    segmentation = json.load(f)

baseline_time = baseline['processing_time_seconds']
segmentation_time = segmentation['processing_time_seconds']
speedup = ((baseline_time - segmentation_time) / baseline_time) * 100

print(f'Baseline: {baseline_time:.2f}s')
print(f'Segmentation: {segmentation_time:.2f}s')
print(f'Speedup: {speedup:.1f}%')

# Target: 10-30% faster (NFR-001)
assert 10 <= speedup <= 50, f'Speedup {speedup:.1f}% outside expected range'
print('✓ Performance target met')
"
```

### 5.2 Check Recall Preservation (100%)

```bash
# Compare face detection counts
python -c "
import json
with open('baseline_results.json') as f:
    baseline = json.load(f)
with open('segmentation_results.json') as f:
    segmentation = json.load(f)

baseline_faces = sum(len(frame['faces']) for frame in baseline['frames'])
segmentation_faces = sum(len(frame['faces']) for frame in segmentation['frames'])

recall = (segmentation_faces / baseline_faces) * 100 if baseline_faces > 0 else 0

print(f'Baseline faces: {baseline_faces}')
print(f'Segmentation faces: {segmentation_faces}')
print(f'Recall: {recall:.1f}%')

# Target: 100% recall (NFR-002)
assert recall >= 99.5, f'Recall {recall:.1f}% below 100% target'
print('✓ Recall preservation verified')
"
```

### 5.3 Check Segmentation Metrics

```bash
# Verify segmentation cadence and ROI counts
python -c "
import json
with open('segmentation_results.json') as f:
    data = json.load(f)

total_frames = data['total_frames']
segmentation_runs = data.get('segmentation_runs', 0)
roi_count_avg = data.get('roi_count_avg', 0)
cache_hit_rate = data.get('cache_hit_rate', 0)

print(f'Total frames: {total_frames}')
print(f'Segmentation runs: {segmentation_runs}')
print(f'Avg ROIs per frame: {roi_count_avg:.1f}')
print(f'Cache hit rate: {cache_hit_rate:.1%}')

# Expected cadence: ~15 frames (interval setting)
expected_runs = total_frames // 15
assert abs(segmentation_runs - expected_runs) <= 2, 'Segmentation cadence incorrect'
print('✓ Segmentation cadence verified')

# Expected cache hit rate: >80% (reuse between intervals)
assert cache_hit_rate >= 0.8, f'Cache hit rate {cache_hit_rate:.1%} too low'
print('✓ Cache performance verified')
"
```

---

## Step 6: Visual Validation (Optional)

### Draw Segmentation ROIs on Frames

```bash
python scripts/visualize_segmentation.py \
  --video /source/videos/test_video.mp4 \
  --results segmentation_results.json \
  --output debug_frames/

# Review output frames in debug_frames/ directory
# Verify:
# - Person ROIs accurately cover people in frame
# - ROIs expanded appropriately (not cropping faces)
# - No missed faces outside ROIs
```

### Check Face Parsing Rejections

```bash
# Extract low-confidence faces that were validated
python -c "
import json
with open('segmentation_results.json') as f:
    data = json.load(f)

parsed_count = 0
rejected_count = 0
for frame in data['frames']:
    for face in frame['faces']:
        if face.get('parsing_validated'):
            parsed_count += 1
            if not face.get('accepted', True):
                rejected_count += 1

print(f'Faces parsed: {parsed_count}')
print(f'Faces rejected: {rejected_count}')
print(f'Rejection rate: {rejected_count/parsed_count*100:.1f}%' if parsed_count > 0 else 'N/A')

# Expected: ~5-15% rejection rate for low-confidence detections
"
```

---

## Step 7: Integration Test (Full Pipeline)

```bash
# Run end-to-end pipeline with segmentation enabled
cd ..
python scripts/run_full_pipeline.py \
  --config mvp-processor/config_segmentation_test.json \
  --input source/videos/test_video.mp4

# Verify:
# - Processing completes without errors
# - Metadata generated successfully
# - Frontend can load and display results
# - Video player shows annotated faces correctly
```

---

## Step 8: Cleanup

```bash
# Remove test results
rm baseline_results.json segmentation_results.json
rm -rf debug_frames/

# Keep model file for future use
# DO NOT delete: mvp-processor/models/yolov8n-seg.onnx
```

---

## Expected Outcomes

After completing the quickstart, you should observe:

1. **Performance**: 10-30% faster processing time compared to baseline ✓
2. **Quality**: 100% recall preservation (no missed faces) ✓
3. **Segmentation**: ~15 frame interval, 80%+ cache hit rate ✓
4. **Parsing**: Optional low-confidence validation working ✓
5. **Integration**: Full pipeline compatible with existing system ✓

---

## Troubleshooting

### Issue: ONNX model not found
**Solution**: Verify model path in config matches actual file location
```bash
ls -l mvp-processor/models/yolov8n-seg.onnx
```

### Issue: Segmentation too slow (>10ms per frame)
**Solution**: Try smaller model or reduce input resolution
```bash
# Use YOLOv8n-seg (nano) instead of YOLOv8s-seg (small)
# Or install GPU-accelerated ONNX Runtime:
pip install onnxruntime-gpu
```

### Issue: Recall < 100% (missing faces)
**Solution**: Increase expand_ratio or reduce min_person_area
```json
{
  "segmentation": {
    "expand_ratio": 1.5,
    "min_person_area": 2000
  }
}
```

### Issue: Cache hit rate < 80%
**Solution**: Check interval and TTL settings, ensure video is not extremely high motion
```bash
# Increase interval for more cache reuse
"interval": 20
```

### Issue: Too many false positives in face parsing
**Solution**: Increase min_skin_ratio threshold
```json
{
  "face_parsing": {
    "min_skin_ratio": 0.4
  }
}
```

---

## Next Steps

After validating the feature:

1. **Test on Production Videos**: Run on full MV video dataset
2. **Benchmark Performance**: Measure speedup across video corpus
3. **Tune Parameters**: Adjust thresholds based on results
4. **Deploy**: Enable in production config after validation
5. **Monitor**: Track segmentation metrics in analytics dashboard

---

## Acceptance Criteria Checklist

- [ ] Segmentation model downloaded and loaded successfully
- [ ] Baseline processing completes without segmentation
- [ ] Segmentation-gated processing achieves 10-30% speedup
- [ ] Recall maintains 100% vs baseline (no missed faces)
- [ ] Segmentation cadence matches config interval (~15 frames)
- [ ] Cache hit rate >= 80%
- [ ] Face parsing validation working for low-confidence detections
- [ ] Full pipeline integration successful
- [ ] Metadata schema compatible with existing system
- [ ] Frontend displays results correctly

**Status**: ✅ All criteria met = Feature ready for production