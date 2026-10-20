---
id: 018
title: Build the crop-grid labeller and the labels file
label: wayfinder:task
mode: AFK
blocked_by: []
status: closed
assignee: claude
---

## Question

Execute what *Choose the ground-truth labelling means* settled. Nothing left to decide — the
means, the verdicts, the unit and the storage are all fixed by its Resolution; this builds them.

## The contract (settled, do not redesign)

`local_output/labels/<video_id>_labels.json`, local-only, gitignored like the rest of
`local_output/`:

```jsonc
{ "schema": "labels/v1",
  "video_id": "test-video-mv2",
  "labelled_at": "2026-09-17T…",
  "source": { "processing_date": "…", "detections": 399 },
  "labels": [ { "frame_number": 0, "detection_index": 0, "verdict": "contestant", "contestant_id": "33" },
              { "frame_number": 3, "detection_index": 0, "verdict": "not_a_contestant" } ] }
```

- Verdicts: `contestant` (with `contestant_id`), `not_a_contestant`, `unsure`, `box_wrong`.
- Keyed by `frame_number` + `detection_index` — the index into `frame_data[].detections[]`.
- `source` pins the metadata run (`video_info.processing_date` and the detection count). **A
  reader must refuse labels whose `source` does not match the metadata it is reading**, loudly —
  a reprocess renumbers and re-scores detections.
- An absent entry means "not labelled", never a verdict.

## Build

1. **A labeller page in `apps/admin`** (local-only app; it never deploys) that loads a processed
   video's detections, shows one crop per detection, and records a verdict per detection:
   - contestant picker (search by number / nickname / name), then the three other verdicts;
   - progress ("n of 399 labelled"), filter by claimed name/number, "unlabelled only";
   - keyboard: choose, move to next unlabelled, Escape to cancel;
   - resume: reopening a video must pick up labels already on disk.
2. **The labels file** read/written through `local_api.py` (`GET`/`PUT /api/labels/{video_id}`),
   written atomically the way `_save_flags` already does (temp + replace).
3. **Crops**: either on demand from `local_api` (decode the frame from the `_1080p.mp4` rendition,
   crop by the stored fractions — no files to manage, works for every video) or pre-extracted per
   video. On-demand is the likely better rung, but measure the cost first: the prototype's
   pre-extraction took ~2 min for 399 crops through 187 ffmpeg calls.
4. **Keep the prototype's right-hand rail idea**: the live count of verdicts and the gate numbers
   the labels produce, so a labeller can see the run converging.
5. **Offer a bulk "apply to this track" action**, now that tracks are worth using: *Fix the
   tracker's inverted matching threshold* took the id coverage from 119 fragments (111 of them a
   single frame) to **42 tracks, longest 19**, over 399 detections at threshold 0.8. Measured
   caveats, so the action is built with a review step rather than as a shortcut for truth:
   **2 of the 42 tracks claim two different contestants across their frames** (track 1 holds both
   Jackie and 阿妹; track 55 both Day and Sinnie), **9 contestants are spread over 2–4 tracks**
   because a track breaks at every cut, and **162 detections still carry no track at all**. The
   stored label stays per detection — that is what ticket 005 decided. Apply-to-track is a
   convenience with an "apply to the N frames of this track" confirmation, never the unit of
   truth.

## Reference implementation

The prototype at `docs/wayfinder/assets/labelling-prototype/index.html` is the interactive spec —
its grid, popover, verdict set and live state panel are what the user reacted to and approved. It
is throwaway: do not import it, do not ship it, and delete it once this ticket lands (it is kept
only as the record of what was decided).

## Context

- **Bboxes are frame fractions** and scores raw cosines (ticket 014, `CONTEXT.md`); the labeller
  must not rescale anything.
- **Flagging is untouched.** `local_output/flagged_faces.json` and the flag routes keep working
  for their own purpose; labels are a separate file. Ticket 015 removes the flagging *write path
  from the deployed worker* — unrelated to this, but the two touch `local_api.py` and
  `apps/admin`, so do not run them in parallel.
- **No new dependencies.** The admin app already has React, Vite and TanStack Query; the labels
  endpoint belongs beside the existing local API endpoints.
- Leave a runnable check behind: a label round-trip that survives a save/load, and a refusal case
  — labels whose `source` does not match the metadata must not load.
- **Acceptance**: the user can label `test-video-mv2` end to end in the admin app, close it, reopen
  it and find their verdicts, and the file on disk matches the schema above.

## Resolution

**Closed 2026-09-21.** Built and driven end to end. The labeller is a real admin page, the labels
file is real, and the user can start labelling.

### What landed

- **`apps/admin/src/pages/Labelling.tsx`** (new, ~1,400 lines) at route `/labelling`, with a nav
  entry after Flagging. Video picker, a paginated grid of face crops in frame order (120 per page
  of the 399), a label sheet with a searchable contestant picker and the four verdicts, progress
  and three filters (claimed text, verdict, unlabelled-only), a live rail (verdict counts, the
  gate numbers, the labels-file panel), apply-to-track behind an explicit frame-count
  confirmation, debounced autosave with a saving/saved/failed indicator, and resume from disk.
- **`local_api.py`**: `GET`/`PUT /api/labels/{video_id}` (+ `GET /api/labels`), and
  `GET /api/faces/crop` for the crops.
- **`mvp-processor/tests/unit/test_local_api_labels.py`** (new, 10 tests).

### The labels file, as built

`local_output/labels/<video_id>_labels.json`, written atomically (temp + replace) exactly as
`_save_flags` does, `schema: "labels/v1"`, keyed by `frame_number` + `detection_index`, with
`source: {processing_date, detections}` pinning the run. Verified over HTTP:

```
PUT  → {"saved":true,"count":2,…}     GET → the same two verdicts back
PUT with a stale source → 409 "Refusing labels for metadata run {…2000-01-01…}"
GET with a stale file   → 409 "…made against a different metadata run"
```

The four refusals that keep it honest — unknown frame, out-of-range detection index, unknown
verdict, contestant verdict without an id (and a non-contestant verdict carrying one) — all return
400 and **leave the file untouched**.

### Crops: on demand, measured first

The ticket asked for the measurement. One frame decode + crop is **375 ms**; caching per frame
means 187 decodes cover all 399 crops (**≈70 s** of work, spread across the session as tiles come
into view, ~4 KB per crop, **1.7 MB** held in memory) against the prototype's **2 min and 2.7 MB
on disk** for a pre-extracted set. On-demand wins on both counts and needs no files, so it works
for every future video. Measured live: first crop 0.52 s, second 1.8 ms — a 300× cache hit.

### The bug found by running it, not by reading it

The first version **took the whole admin app down** on `/labelling`: a blank screen, no header, no
sidebar. `frame_data[].detections.forEach` threw because the page auto-selected `videos[0]`, which
is `5-《全民造星IV》…` — whose metadata is **pre-ticket-014** (`recognitions`, pixel boxes). The map's
own notes say only `test-video-mv2` is under the current contract. React unmounted the root on the
uncaught render error, and the failure was **completely silent** to both CDP listeners and console
capture; it took a temporary error boundary to see the stack. Two lessons recorded on the issue:
the page now (a) probes the video list and lands on the first *labelable* video — today
`test-video-mv2` — marking the others stale, and (b) refuses pre-contract metadata with a sentence
naming the missing field, instead of inventing detections. `/admin`, `/flagging` and `/player`
always rendered, which is how the route was cleared first.

### Verification

- **Through the UI, end to end**: loaded `/labelling` → auto-selected `test-video-mv2`, 399 tiles,
  bands and claims correct → opened a tile, picked a contestant through the picker → *Saved
  02:02:24* → the file on disk held exactly that verdict with the right `source` → **reloaded** and
  the verdicts came back as chips with "2 of 399 labelled".
- `test_local_api_labels.py` 10/10; `tsc --noEmit` clean in admin, shared, viewer and worker.
- The two labels used for the check were **test data and have been deleted** — the file now reads
  `count: 0`, so the user's session starts from an empty, valid label set.
- The throwaway prototype (`docs/wayfinder/assets/labelling-prototype/`) is **deleted** as the
  ticket required, and ticket 005's pointer to it now says so.

### Notes for the next session

- **`local_output/labels/` is now in `.gitignore`.** The ticket said labels were "gitignored like
  the rest of `local_output`" — that premise was wrong (most of `local_output` is
  untracked-but-*not*-ignored, and five artifacts are tracked outright), so the rule was added for
  labels alone, following the ticket's stated intent. Worth knowing: this makes the labels *more*
  local-only, and they are irreplaceable human work — see the map's open question about whether
  local-only artifacts need to outlive this Mac.
- The page reads `/api/labels/{video_id}` and blocks with a banner on 409 rather than starting
  over; a reprocess therefore makes the user's labelling visibly invalid rather than silently
  mis-indexed.

