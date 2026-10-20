---
id: 005
title: Choose the ground-truth labelling means
label: wayfinder:prototype
mode: HITL
blocked_by: [014]
status: closed
assignee: claude
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

## Prototype (built 2026-09-17, deleted 2026-09-21)

Kept here as the record of what was decided. It was throwaway and *Build the crop-grid labeller
and the labels file* (018) replaced it with the real labeller in `apps/admin` at `/labelling`.

**`docs/wayfinder/assets/labelling-prototype/index.html`** — opened by double-clicking; no
server, no build, no persistence. 399 real crops from the reprocessed clip, extracted from the
1080p rendition against the ticket-014 metadata.

Three tabs:

1. **The choice** — the real material (399 boxes, 139 matched, 260 unmatched, 15 contestants,
   cosines 0.451–0.643) and the cost of each labelling unit: 399 per-detection labels, 187 per
   frame, or 119 per track — that last one covering only **129 of the 399 boxes**, because the
   tracker refuses to track most of them (see *Fix the tracker's inverted matching threshold*).
   It also prints the shape the admin flag store writes today and what it lacks: no
   `frame_number`, no `tracker_id`, a `status` lifecycle ground truth does not want, and a
   `confidence` field holding a cosine (meaningless for the "not a contestant" verdict).
2. **Hard cases** — six real ones to react to: a confident match, one that scraped over the bar
   at 0.451, a five-face frame where four boxes are unnamed, an unmatched box mid-shot, the
   longest run of one face (four frames), and a face the detector missed entirely (which no
   label can attach to, because no box exists).
3. **Label the real set** — the whole set, clickable: click a face → pick a contestant or a
   verdict → next face. The right-hand rail is live: counts, the labels JSON, and the gate the
   labels would unlock (true-match cosine mean ≥ 0.45, worst impostor ≤ 0.2).

Nothing is written to disk; the export button downloads the labels JSON held in memory.

## Resolution

**Settled 2026-09-17, with the user**, against the prototype above. Four answers:

1. **Means — the crop grid**, not the admin player. One pass over the face crops, click a face →
   type a number or nickname → next. The player stays available as a viewing surface; the grid is
   where the labelling happens, because judging "is this 阿妹?" needs the face, not the video
   position. The prototype is a working demonstration, not yet a tool: it holds labels in memory
   and loads one hard-coded video.
2. **Verdicts — four**: a **contestant**, **not a contestant**, **unsure**, or **box is wrong**.
   The last two keep a judgement out of the arithmetic (unsure) and separate a *detector* error
   from a *matcher* error (box wrong) — which matters, because the gate is about matching, and a
   bad box is a different failure being blamed on the matcher.
3. **Unit — one label per detection.** Not per track: the tracker found **119 tracks for 399
   boxes, 111 of them a single frame, and left 270 boxes untracked entirely**, so a track covers
   only 129 of the boxes. Per-frame labels would have been 187 instead of 399, but cannot say
   *which* box is wrong once a frame holds more than one face — and **108 of 187 frames do** (up
   to five).
4. **Storage — a new labels file; flagging untouched.** Ground truth is a verdict, not a proposal
   awaiting review: reusing the flag store would drape a `status: pending` lifecycle over it, lose
   the frame identity (a flag keys on `timestamp` + `bbox`), and attach a cosine to verdicts that
   have none. `local_output/flagged_faces.json` keeps doing its own job.

**Missed faces: not now.** They are outside the detection set entirely — a face with no box cannot
be labelled by any verdict — and the separation gate does not need them. Worth recording that the
stored frames all contain at least one detection, so nothing in the current data even reveals how
many faces are being missed; that is a detector-recall question for another day.

### The schema this settles

`local_output/labels/<video_id>_labels.json`, local-only, written by the labeller:

```jsonc
{ "schema": "labels/v1",
  "video_id": "test-video-mv2",
  "labelled_at": "2026-09-17T…",
  "source": { "processing_date": "…", "detections": 399 },   // the run these labels describe
  "labels": [ { "frame_number": 0, "detection_index": 0, "verdict": "contestant", "contestant_id": "33" },
              { "frame_number": 3, "detection_index": 0, "verdict": "not_a_contestant" },
              { "frame_number": 4, "detection_index": 0, "verdict": "unsure" },
              { "frame_number": 5, "detection_index": 0, "verdict": "box_wrong" } ] }
```

- **Keyed by `frame_number` + `detection_index`** — the index into
  `frame_data[].detections[]`. Both are stable for a given metadata file and need no float
  comparison, which is what a `timestamp` + `bbox` key forces.
- **`source` pins the run.** A reprocess renumbers detections and re-scores them, so labels from a
  previous run must be refused loudly rather than silently attached to whatever box now sits at
  that index. This is the same stale-artifact failure the effort has already paid for twice
  (the averaged-embedding cache, the stale metadata).
- **Verdict vocabulary**: `contestant` | `not_a_contestant` | `unsure` | `box_wrong`. The
  prototype uses the shorthand `nobody` / `boxwrong`; the real file spells them out.
- A detection with **no label** is simply not labelled — absence is not a verdict.

### Evidence behind the answers

- 399 detections, 139 named, **260 unnamed** — "not a contestant" is the only way to turn those
  into a rate rather than a residue.
- Accepting the matcher's word on all 139 is exactly the mistake that made "34.8% recognition"
  unreadable: it cannot distinguish right answers from confident wrong ones. Every verdict here
  produces one of the gate's two numbers: the cosine of a true match, or the cosine of an
  impostor the matcher named anyway.
- The prototype's live gate panel already demonstrates the arithmetic on real scores, including
  what a wrong "named" box does to the impostor maximum.

### Consequence

Building the real labeller and the labels file is **[Build the crop-grid labeller and the labels
file](018-build-the-crop-grid-labeller-and-the-labels-file.md)**, which is what
*Label 30 seconds of test-video-mv2* now waits on. The tracker's unusable `tracker_id`
(*Fix the tracker's inverted matching threshold*, 017) is **not** a blocker — per-detection
labelling needs no tracks — but it is what would later turn 399 clicks into ~42.


