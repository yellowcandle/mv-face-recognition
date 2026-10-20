---
id: 006
title: Label 30 seconds of test-video-mv2
label: wayfinder:task
mode: HITL
blocked_by: [018]
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

## The checklist (written 2026-09-21, once the labeller existed)

1. **Start the two local servers** (two terminals, from the repo root):
   ```
   cd mvp-processor && .venv/bin/python -m uvicorn src.local_api:app --port 8000
   pnpm --filter @mv/admin dev
   ```
2. **Open** `http://localhost:5173/labelling`. It lands on `test-video-mv2` by itself (the only
   video whose metadata is under the current contract; the others say so and refuse).
3. **Work the grid.** One verdict per face crop, in frame order:
   - **Contestant** — click a face, type a number or nickname, Enter. The sheet advances to the
     next unlabelled face by itself.
   - **Not a contestant** — the box is someone who is not one of the 96 (crew, background, an
     extra). This is the verdict that turns "the matcher named a stranger" into a number.
   - **Unsure** — cannot tell from this crop. It counts as labelled and decides nothing.
   - **Box is wrong** — the detector boxed something that is not a face.
   - Escape closes the sheet; the sheet's "Clear label" undoes one.
4. **Work in bursts.** Everything saves itself about half a second after each click (the rail shows
   *Saved HH:MM:SS*). Closing the tab and coming back picks up exactly where you left off —
   progress reads *n of 399 labelled*.
5. **Use the filters when it helps**: hide the ones you have done, or work one claimant at a time
   (the matcher claims 15 contestants here). "Apply to the N frames of this track" is a shortcut
   for a face that runs across frames — it asks to confirm the frame count, and shows you the
   frames first when a track holds more than one claimed contestant.
6. **Stop when the rail earns its numbers.** It refuses to colour the gate until there are enough
   labels to mean something (10 labelled minimum, 5 true matches, 3 impostor events). You do not
   need all 399 — you need enough that the mean and the worst impostor stop moving.

**Where it goes**: `local_output/labels/test-video-mv2_labels.json` — `labels/v1`, keyed by frame
plus detection index, pinned to this metadata run (`processing_date` 2026-09-21T01:40:44, 399
detections). It is **gitignored** and it is **invalidated by any reprocess** — the page will say
so with a banner rather than silently mismatching verdicts to boxes.

**Then**: *Decide the batch gate on labelled ground truth* computes the go/no-go from this file.

