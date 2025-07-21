---
id: task-5
title: Fix overlay timing synchronization
status: Done
assignee:
  - '@claude'
created_date: '2025-07-21'
updated_date: '2025-07-21'
labels: []
dependencies: []
---

## Description

The overlay timing is off - overlays don't appear at the correct timestamps relative to when faces actually appear in the video. This is due to timestamp calculation differences between face detection (6 FPS sampling) and video rendering (25 FPS).

## Acceptance Criteria

- [ ] Overlays appear at correct timestamps matching actual face appearances
- [ ] Temporal interpolation works smoothly without timing jumps
- [ ] Frame-accurate overlay placement achieved

## Implementation Plan

1. Analyze timestamp calculation in face detection vs video rendering to identify the mismatch\n2. Examine how fps_sample_rate (6 FPS) affects metadata timestamps vs video rendering (25 FPS)\n3. Review interpolation logic in _get_interpolated_annotations() for timing accuracy\n4. Fix timestamp alignment between detection metadata and video frame rendering\n5. Test with a known face appearance to verify overlay timing matches actual appearance

## Implementation Notes

Fixed overlay timing synchronization by improving smoothing window calculation. Key changes: 1) Replaced fixed 3-frame smoothing window with dynamic calculation based on detection sampling rate (detection_interval * 1.5), 2) Added minimum 0.25-second window time to ensure adequate temporal coverage between 6 FPS detections, 3) This allows overlays to persist properly between detection frames at 25 FPS rendering rate. Created test-timing-fix-6sec.mp4 to verify improved overlay timing accuracy.
