---
id: task-023
title: Fix overlay timing synchronization and readability issues
status: To Do
assignee: []
created_date: '2025-07-20'
updated_date: '2025-07-20'
labels: ['video-processing', 'face-recognition', 'overlay', 'synchronization']
dependencies: []
---

## Description

The baked face recognition overlays in processed videos have two critical issues:
1. **Timing synchronization problems** - overlays appear at wrong timestamps, not aligned with actual face positions
2. **Readability issues** - labels are switching around per frame, text positioning is unstable, and overlays are hard to read

This is a comprehensive fix to address both the timing desync and overlay readability problems in the video processing pipeline.

## Acceptance Criteria

- [ ] Overlay timing is accurately synchronized with face positions in videos
- [ ] Face recognition labels remain stable and don't jump around between frames
- [ ] Text positioning is consistent and readable throughout video playback
- [ ] Bounding boxes stay properly aligned with faces during movement
- [ ] Interpolation provides smooth transitions between detection keyframes
- [ ] CJKV font rendering is clear and has good contrast
- [ ] All 5 videos are reprocessed with corrected overlays
- [ ] Deployed videos show stable, properly timed overlays

## Implementation Plan

### Phase 1: Core Timing Fixes
1. Fix timestamp calculation mismatch between face detection and overlay rendering
2. Improve interpolation window strategy with better temporal smoothing
3. Ensure consistent frame timing throughout pipeline

### Phase 2: Readability Enhancements  
4. Implement face tracking stability system to prevent label switching
5. Stabilize label positioning to prevent jumping around
6. Improve visual readability with better contrast and fonts

### Phase 3: Testing & Deployment
7. Test with sample video segment to validate fixes
8. Reprocess all videos with corrected pipeline
9. Deploy and verify streaming works correctly

## Implementation Notes

(To be filled during implementation)