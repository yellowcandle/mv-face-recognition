# Plan: Stage 6 — Annotated Video Output

## Status: COMPLETE

## What was implemented

### 1. `create_annotated_video` method (video_processor.py) ✅
- Re-reads source video frame-by-frame with `cv2.VideoCapture`
- Draws bounding boxes + labels using recognition data from `frame_data`
- Carry-forward: reuses last known recognitions between sampled frames
- Confidence fades over ~30 frames from last sample point
- Writes to temp file via `cv2.VideoWriter`, then muxes audio with MoviePy
- Output: `{output_name}_annotated.mp4`

### 2. Pipeline integration (process_video.py) ✅
- Called after format conversion in `process_video()`
- Adds annotated video path to `upload_package`
- `--no-annotate` CLI flag to skip annotation
- Graceful failure: logs warning if annotation fails, doesn't break pipeline

### 3. Config UI design (untitled.pen) ✅
- Designed in Pencil instead of bare YAML config
- 4 cards: General Settings, Label & Box Appearance, CJK Text Rendering, Carry-Forward Behavior
- Config values still read from `processing_config.yaml` `annotated_video:` block

### 4. Key details ✅
- **CJK text**: Pillow `ImageDraw` with PingFang/NotoSansCJK fonts, cv2.putText fallback
- **Carry-forward**: Last recognition persists, confidence fades over 30 frames
- **Audio**: cv2.VideoWriter (video-only) + MoviePy audio mux
- **Memory**: Frame-by-frame processing, no full video in memory
