---
id: 005
title: Choose the ground-truth labelling means
label: wayfinder:prototype
mode: HITL
blocked_by: []
status: open
assignee:
---

## Question

What does the user actually click to hand-label who appears when in `test-video-mv2`?

The user asked for the means to be provided. Before building anything, check whether the
admin app already *is* the labeller.

## Context

- **The admin flagging workflow is already a labelling tool.** `FaceOverlay.tsx` renders a
  clickable `<button>` per detected face over the video; `FlagDialog.tsx` opens with a
  contestant picker and supports batch selection; `local_api.py` persists to
  `local_output/flagged_faces.json` via `POST /api/faces/flag`, with
  `GET/PATCH/DELETE /api/faces/flagged/{id}`. That is: click a face → choose the correct
  contestant → saved to disk.
- So the likely answer is "reuse flagging, relabel the verb" — the lazy rung. Prototype that
  first and let the user react before building anything new.
- What flagging does **not** obviously give: faces the detector *missed* entirely (no box to
  click), and in/out interval labelling rather than per-frame marks. Decide whether the ground
  truth needs either. A per-frame "this box is contestant X / is nobody" set may be enough to
  compute the separation gate.
- Admin mode polls `GET /api/faces/detect?video_id=…&timestamp=…` every 200 ms
  (`Player.tsx:461-467`), so boxes are live as the video plays.
- `test-video-mv2` metadata already exists with 187 frames, 399 detections, 150 recognitions
  (`local_output/metadata/test-video-mv2_metadata.json`).
- **Watch out**: `face_location` is stored in 1920 detection space while
  `FaceOverlay.tsx:30-31` scales by `video_info.width` (3840), so the clickable boxes are
  currently at roughly half size and top-left biased. Labelling is unusable until that is
  resolved — see *Settle the bbox coordinate space*.

Deliverable: a rough prototype the user reacts to, and a decision on the labelling schema.
