---
id: 010
title: Fix the viewer defects blocking MVP visualization
label: wayfinder:task
mode: AFK
blocked_by: []
status: open
assignee:
---

## Question

Two confirmed defects sit directly in the MVP path. Fix them so the MVP video can actually be
looked at.

1. **Clicking any video card opens the first video.** `Home.tsx` links to
   `/player?video=${video.id}`, but `PlayerPage.tsx` (9 lines) never reads the query param —
   no `useSearchParams` anywhere in `apps/viewer/src`. `Player.tsx:77-81` then auto-selects
   `videos[0]`. With 5 MVs published, 4 are unreachable from the home page.
2. **Analytics rows are labelled with contestant ids, not names.** `contestant_timeline` is
   keyed by id string (`"33"`, `"88"`), and `Analytics.tsx:40` does `nickname: key`, so the
   table shows numbers. `ContestantTimeline.tsx:123` gets this right via
   `contestant_info.nickname` — copy that.

Note *why* defect 2 survived: the worker's mock metadata (`index.ts:1841`) keys by nickname
while real pipeline output keys by id, so the two disagree and the mock hid the bug. Worth
checking whether the mock should just be deleted (see ticket 007).

## Context

- No decision to make here — this is execution, allowed under the map's Notes.
- `local_output/metadata/test-video-mv2_metadata.json` was verified to match the
  `VideoMetadata` contract in `apps/shared/types/index.ts:78-91` exactly (a superset: it also
  carries `timeline_markers`, `thumbnails`, `recognition_config`, and a per-recognition
  `tracker_id`). So the frontend can be fixed and tested against real data now, before any
  reprocessing.
- Minor, fold in if trivial: `useViewerMetadata.ts:15` builds its URL without
  `encodeURIComponent` while `Player.tsx:111,127` encode — inconsistent for CJK/space ids,
  and every one of the 5 MVs has CJK in its id.
- Leave a runnable check behind for the `?video=` routing.
