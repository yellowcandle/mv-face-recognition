---
id: 009
title: Remove flagging from the public viewer
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: open
assignee:
---

## Question

How does the viewer lose flagging, and how does the endpoint get gated?

The user ruled this **blocking** for publish. It is an unauthenticated public write, not a
polish item.

- **UI**: a minimal `mode === 'viewer'` guard, or the capability-props refactor `TODO.md:24`
  already wants (annotation source, canFlag, timeline visibility)?
- **Endpoint**: add `verifyCloudflareAccess`, or drop the write path from the deployed worker
  entirely?

## Context

- `POST /api/faces/flag` is handled at `worker/src/index.ts:561-566` with **no**
  `verifyCloudflareAccess` call — unlike every `/api/admin/*` route, which is gated at
  `:116-169`. Anyone on the public internet can write to `METADATA_KV`.
- Viewer-mode UI that shouldn't be there: the "Flagged (n)" button and panel
  (`Player.tsx:526-531,844-889`), Batch Mode + "Flag Selected" (`:642-681`), and
  `FaceOverlay.tsx:62` whose tooltip literally reads *"Click to flag this face"*.
- Note the tension: **admin flagging is probably the ground-truth labelling tool**
  (ticket 005). Removing it from *viewer* must not weaken it in *admin*. The capability-props
  route handles that cleanly; a scattered conditional may not.
- Related viewer-mode leak: `handleToggleSource` (`Player.tsx:238`) points at
  `/source/videos/${filename}` (`:92`), a local-only path that 404s on the worker. Same class
  of problem — decide whether it rides along.
- Ponytail: the minimal guard is the lower rung, but `TODO.md` already committed to
  capability props and this is the second caller demanding it. Judge on the diff, not the
  principle.
