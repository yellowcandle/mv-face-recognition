---
id: task-021.02
title: Implement Apple Silicon Metal/MPS hardware acceleration
status: Done
assignee: []
created_date: '2025-07-20'
updated_date: '2025-07-20'
labels: []
dependencies: []
parent_task_id: task-021
---

## Description

Add Apple Silicon Neural Engine and Metal Performance Shaders acceleration to face detection pipeline for 4-6x performance improvement

## Acceptance Criteria

- [ ] InsightFace model is configured with Metal backend
- [ ] Hardware acceleration auto-detection works for Apple Silicon/CUDA/CPU
- [ ] Face detection processing speed is improved 4-6x on Apple Silicon
- [ ] Memory management is optimized for unified memory architecture
- [ ] Fallback to CPU works when Metal acceleration fails
