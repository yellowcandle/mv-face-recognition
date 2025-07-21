---
id: task-6
title: Fix text label positioning in overlays
status: Done
assignee:
  - '@claude'
created_date: '2025-07-21'
updated_date: '2025-07-21'
labels: []
dependencies: []
---

## Description

Text labels are offset downward from the black background boxes in the video overlays. The text positioning logic doesn't properly center text within the background rectangles.

## Acceptance Criteria

- [ ] Text labels are properly centered within black background boxes
- [ ] No visual offset between text and background rectangle
- [ ] CJKV font rendering remains intact and properly positioned

## Implementation Plan

1. Analyze current text positioning logic in video_processor.py _draw_frame_annotations method\n2. Identify the specific calculation causing downward offset between text and background rectangle\n3. Fix text baseline calculation to properly center text within black background box\n4. Test positioning with CJKV characters to ensure font metrics work correctly\n5. Verify fix by reprocessing a small test segment

## Implementation Notes

Fixed text label positioning by redesigning the coordinate calculation logic. Key changes: 1) Replaced ad-hoc text_y calculation with proper background rectangle positioning (bg_top, bg_bottom, bg_left, bg_right), 2) Added bg_padding for consistent spacing around text, 3) Calculated text_baseline_y to properly center text within background rectangle using font baseline adjustment (0.8 factor), 4) Positioned background rectangle above face bounding box with proper bounds checking. Created test-positioning-fix-overlays.mp4 to verify the fix works correctly with CJKV font rendering intact.
