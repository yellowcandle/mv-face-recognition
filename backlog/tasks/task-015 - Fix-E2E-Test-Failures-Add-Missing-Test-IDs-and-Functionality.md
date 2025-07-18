---
id: task-015
title: Fix E2E Test Failures - Add Missing Test IDs and Functionality
status: To Do
assignee: []
created_date: '2025-07-16'
labels:
  - frontend
  - testing
  - e2e
dependencies: []
---

## Description

Fix all 60 failing E2E tests by adding missing data-testid attributes and implementing missing functionality expected by the test suite. The tests are failing because the video player implementation lacks proper test IDs and some expected UI elements.

## Acceptance Criteria

- [ ] All video player elements have proper data-testid attributes matching test expectations
- [ ] Video selection dropdown shows actual video titles and works with tests
- [ ] Face recognition overlay canvas has proper test ID and functionality
- [ ] Timeline markers for face detections are visible and interactive
- [ ] Export dialog and functionality is implemented
- [ ] Confidence filter controls are available and functional
- [ ] Contestant search functionality is implemented
- [ ] Mobile responsive features work correctly with mobile menu button
- [ ] Error handling UI for video loading failures is implemented
- [ ] All 60 E2E tests pass successfully across all browsers (Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Mobile)
