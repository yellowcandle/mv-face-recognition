---
id: task-031
title: Fix overlay positioning issue in video annotations
status: In Progress
assignee:
  - '@agent3'
created_date: '2025-07-23'
updated_date: '2025-07-23'
labels: []
dependencies: []
---

## Description

The bounding boxes and text labels are misaligned with the actual face locations in the processed videos. This was supposedly fixed before but the issue has returned.

## Acceptance Criteria

- [ ] Overlays properly align with detected faces
- [ ] Bounding boxes accurately position around faces
- [ ] Text labels position correctly relative to faces
- [ ] Coordinate transformations work correctly between detection and rendering
- [ ] Overlay positioning remains stable across video frames

## Implementation Plan

1. Investigate overlay coordinate system and scaling\n2. Check face detection coordinates vs video overlay coordinates\n3. Examine bounding box calculation and text positioning\n4. Verify coordinate transformations between detection and rendering\n5. Fix alignment issues in supervision annotators\n6. Test overlay positioning accuracy
