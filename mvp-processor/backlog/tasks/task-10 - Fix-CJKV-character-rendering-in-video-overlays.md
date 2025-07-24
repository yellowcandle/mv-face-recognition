---
id: task-10
title: Fix CJKV character rendering in video overlays
status: Done
assignee:
  - '@swong'
created_date: '2025-07-22'
updated_date: '2025-07-23'
labels: []
dependencies: []
---

## Description

Chinese, Japanese, Korean, and Vietnamese characters are displaying as ??? in video overlays instead of proper Unicode characters. This was supposedly fixed before but the issue has returned.

## Acceptance Criteria

- [ ] Chinese characters display correctly in video overlays
- [ ] Japanese characters display correctly in video overlays
- [ ] Korean characters display correctly in video overlays
- [ ] Vietnamese characters display correctly in video overlays
- [ ] No ??? symbols appear in place of CJKV text
- [ ] Font rendering works consistently across all processed videos
