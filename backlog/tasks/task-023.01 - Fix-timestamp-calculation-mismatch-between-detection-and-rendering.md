---
id: task-023.01
title: Fix timestamp calculation mismatch between detection and rendering
status: To Do
assignee: []
created_date: '2025-07-20'
updated_date: '2025-07-20'
labels: ['video-processing', 'synchronization', 'timestamp']
dependencies: []
parent: task-023
---

## Description

The core timing synchronization issue stems from a mismatch in how timestamps are calculated:
- **Face detection**: Uses sampled frames at 6fps with `timestamp = frame_count / fps` on actual video frame positions
- **Overlay rendering**: Processes ALL frames sequentially with `current_timestamp = frame_count / fps` starting from 0

This fundamental mismatch causes overlays to appear at wrong times relative to when faces were actually detected.

## Acceptance Criteria

- [ ] Overlay rendering uses same timestamp calculation method as face detection
- [ ] Frame timing is consistent between detection and rendering phases
- [ ] Overlay timestamps accurately match the original video frame positions
- [ ] No systematic timing offset between overlays and face positions

## Implementation Plan

1. Analyze current timestamp calculation in both `extract_frames()` and `process_video_with_annotations()`
2. Modify overlay rendering to use actual video frame positions instead of sequential counting
3. Ensure frame sampling alignment between detection and rendering phases
4. Test timestamp accuracy with known video segments

## Implementation Notes

(To be filled during implementation)