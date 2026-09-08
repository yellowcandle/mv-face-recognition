---
id: 006
title: Label 30 seconds of test-video-mv2
label: wayfinder:task
mode: HITL
blocked_by: [005]
status: open
assignee:
---

## Question

Produce the ground-truth labels. Only the user can do this — the agent cannot identify these
faces.

Done when a labelled set exists on disk that the separation gate can be computed against, and
its location and schema are recorded in the resolution.

## Context

- 30 s, 766 frames, 187 processed frames, 14 contestants currently claimed.
- This is the **denominator** every later accuracy claim depends on. Without it, "37.6%
  recognition" cannot distinguish right answers from confident wrong ones — which is exactly
  how the current number misled the effort once already.
- Deliver a precise checklist to the user, then get out of the way.
- Keep it to 30 s. The instinct to label more should be resisted until the gate proves it is
  needed.
