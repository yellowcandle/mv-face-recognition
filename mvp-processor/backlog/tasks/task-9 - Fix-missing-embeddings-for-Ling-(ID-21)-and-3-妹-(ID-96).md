---
id: task-9
title: 'Fix missing embeddings for Ling (ID: 21) and 3 妹 (ID: 96)'
status: Done
assignee:
  - '@swong'
created_date: '2025-07-22'
updated_date: '2025-07-23'
labels: []
dependencies: []
---

## Description

Two contestants are missing their face embeddings, causing the system to load only 94 out of 96 contestants. This reduces recognition accuracy and completeness.

## Acceptance Criteria

- [ ] All 96 contestants have valid embeddings
- [ ] System loads 96 face encodings instead of 94
- [ ] No 'No embedding found' warnings in logs
- [ ] Ling (ID: 21) and 3 妹 (ID: 96) can be recognized in videos
