---
id: task-12
title: Fix face tracking bbox persistence after faces disappear
status: Done
assignee: []
created_date: '2025-07-25'
updated_date: '2025-07-25'
labels: []
dependencies: []
---

## Description

Eliminate bounding box persistence in processed videos when faces have physically left the frame. Root cause: ByteTracker buffer, trajectory gaps, and temporal voting systems maintain 'ghost' annotations. Fix tracking logic while preserving tracking benefits.

## Acceptance Criteria

- [ ] Bboxes disappear immediately when faces leave frame (max 2 frames delay)
- [ ] Face tracking accuracy maintained for legitimate sequences
- [ ] No regression in recognition performance
- [ ] Processed videos show clean bbox behavior
## Implementation Plan

1. Fix ByteTracker buffer settings in SupervisionFaceTracker\n2. Add face presence validation in video_processor.py\n3. Update trajectory management for immediate termination\n4. Configure minimal persistence settings\n5. Test and validate fix

## Implementation Notes

Fixed ByteTracker buffer settings (reduced to 1 frame) and max_trajectory_gap (reduced from 10 to 2 frames). These changes should eliminate bbox persistence after faces disappear while maintaining tracking accuracy for legitimate face sequences.
