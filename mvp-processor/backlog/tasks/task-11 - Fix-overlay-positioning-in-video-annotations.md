---
id: task-11
title: Fix overlay positioning in video annotations
status: Done
assignee:
  - '@agent3'
created_date: '2025-07-22'
updated_date: '2025-07-23'
labels: []
dependencies: []
---

## Description

Face recognition overlay positions are incorrect in the processed videos. The bounding boxes and text labels are not properly aligned with the detected faces. This was supposedly fixed before but the issue has returned.

## Acceptance Criteria

- [ ] ✓ Bounding boxes accurately surround detected faces
- [ ] ✓ Text labels are positioned correctly relative to faces
- [ ] ✓ Overlay positioning is consistent across all video frames
- [ ] ✓ No misaligned or floating text labels
- [ ] ✓ Face recognition overlays match the actual face locations in the video
## Implementation Plan

1. Investigate overlay coordinate system and scaling\n2. Check face detection coordinates vs video overlay coordinates\n3. Examine bounding box calculation and text positioning\n4. Verify coordinate transformations between detection and rendering\n5. Fix alignment issues in supervision annotators\n6. Test overlay positioning accuracy

## Implementation Notes

FIXED: Overlay positioning issue in video annotations

## Approach Taken
- Identified coordinate system mismatch between face detection and overlay rendering phases
- Face detection coordinates stored in detection frame coordinate system (resize_width=1920px)
- Video rendering was incorrectly applying scaling factors as if coordinates were in original video coordinate system

## Root Cause
The issue was in _draw_frame_annotations() method in video_processor.py:
- Face detection happens on resized frames (resize_width from config)
- Overlay rendering reads original video and scales to target resolution
- Scaling calculation didn't account for detection frame resize

## Features Implemented
- Enhanced _draw_frame_annotations() with proper coordinate transformation
- Added original video dimensions parameters to fix calculation
- Implemented two-step transformation: detection_coords -> original_coords -> target_coords
- Added fallback logic for cases without original dimensions

## Technical Decisions
- Maintained backward compatibility with existing overlay rendering interface
- Added comprehensive unit test to prevent regression
- Used precise mathematical transformation rather than approximation

## Modified Files
- /mvp-processor/src/video_processor.py (coordinate transformation fix)
- /mvp-processor/tests/unit/test_video_processor.py (regression test)

## Testing
- Created comprehensive unit test covering coordinate transformation logic
- Verified fix works with 720p, 1080p, and custom resolution outputs
- Test validates face center positioning within 5-pixel accuracy
- Manual testing with test-video-mv2.mp4 confirmed correct overlay alignment
