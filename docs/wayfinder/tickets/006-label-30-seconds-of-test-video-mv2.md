---
id: 006
title: Label 30 seconds of test-video-mv2
label: wayfinder:task
mode: HITL
blocked_by: [018]
status: closed
assignee: omp
---

## Question

Produce the ground-truth labels. Only the user can do this — the agent cannot identify these
faces.

Done when a labelled set exists on disk that the separation gate can be computed against, and
its location and schema are recorded in the resolution.

## Context

- 30 s, 766 frames, **399 detections**, but the label unit is **42 tracks**: 237 of the 399
  detections are tracked (`tracker_id >= 0`) and labelable; the other 162 are untracked
  (`tracker_id < 0`) and are not shown. The matcher claims 15 contestants across them.
- The metadata was **reprocessed on 2026-10-21** (`processing_date` 2026-10-21T10:24:39). The
  old `labels/v1` file (5 per-detection verdicts, pinned to the 2026-09-21 run) is ignored and
  left on disk; the first v2 save replaces it.
- The labeller is `labels/v2`, **one verdict per track**, since commit `5c8a1299`
  (`feat(labels): label tracks instead of detections`). The gate is computed over labelled
  tracks, one cosine per track (the representative detection's `match_score`).
- This is the **denominator** every later accuracy claim depends on. Without it, "37.6%
  recognition" cannot distinguish right answers from confident wrong ones — which is exactly
  how the current number misled the effort once already.
- Deliver a precise checklist to the user, then get out of the way.
- Keep it to 30 s. The instinct to label more should be resisted until the gate proves it is
  needed.

## The checklist (v2, rewritten 2026-10-31)

1. **The two local servers are already running** in the `mv-face-labelling` Rex panes
   (`Backend :8000`, `Admin :5173`). If not:
   ```
   cd mvp-processor && .venv/bin/python -m uvicorn src.local_api:app --port 8000
   pnpm --filter @mv/admin dev
   ```
2. **Open** `http://localhost:5173/admin/labelling` (the Vite base is `/admin/`). It lands on
   `test-video-mv2` by itself — the only video whose metadata is under the current contract.
   The old `labels/v1` file is flagged as ignored in a banner; that is expected.
3. **Work the 42 track cards.** One verdict per track:
   - **Contestant** — click the track, then either hit **Accept matcher's claim** (takes the
     matcher's plurality claim in one click) or type a number or nickname, Enter. The sheet
     advances to the next unlabelled track by itself.
   - **Not a contestant** — the track is someone who is not one of the 96 (crew, background, an
     extra). This is the verdict that turns "the matcher named a stranger" into a number.
   - **Unsure** — cannot tell from this crop. It counts as labelled and decides nothing.
   - **Box is wrong** — the detector boxed something that is not a face.
   - Escape closes the sheet; the sheet's "Clear label" undoes one.
4. **Work in bursts.** Everything saves itself about half a second after each click (the header
   shows *Saved HH:MM:SS*). Closing the tab and coming back picks up exactly where you left
   off — progress reads *n of 42 tracks labelled*.
5. **Use the filters when it helps**: hide the ones you have done, filter by verdict, or search
   by tracker id / claimed contestant (15 contestants are claimed here).
6. **Stop when the rail earns its numbers.** It refuses to colour the gate until there are
   enough tracks labelled (**10 labelled tracks minimum, 5 true matches, 3 impostors**). You do
   not need all 42 — you need enough that the mean and the worst impostor stop moving.

**Where it goes**: `local_output/labels/test-video-mv2_labels.json` — `labels/v2`, keyed by
`tracker_id`, pinned to this metadata run (`processing_date` 2026-10-21T10:24:39, 399 detections).
It is **gitignored** and **invalidated by any reprocess** — the page says so with a banner
rather than silently mismatching verdicts to tracks. The first save replaces the old v1 file.

**Then**: *Decide the batch gate on labelled ground truth* computes the go/no-go from this file.

## Resolution (2026-10-31)

Retired, not failed. All five MVs were reprocessed on 2026-10-21, so the batch compute this gate
was meant to guard had already been spent; the user labelled `test-video-mv2` to **35/42 tracks**
and went on to label the real MVs (MV #4 73, MV #5 2, MV #1 3) rather than chase the 30 s clip.

What the labels say on `test-video-mv2` (35/42):

- **25 true matches**, mean cosine **0.542** — the matched side clears the 0.45 gate.
- **10 missed** — the matcher left the track unnamed but the face is a contestant (a miss, not a
  false match).
- **0 impostors** — every `not_a_contestant` verdict landed on a track the matcher never named, so
  no false claim was found. Only two claimed tracks were still unlabelled (38: claim 13, cos
  0.5454; 163: claim 5, cos 0.4657), which caps impostors at 2: the ≥3-impostor minimum is
  **structurally unreachable** on this clip.

The lesson for *Decide the batch gate on labelled ground truth*: the ≥3-impostor rule cannot be
satisfied by labelling unnamed tracks; only a **wrong claim** is an impostor. With no wrong claims,
the cross-person side has no data, and that absence is the result — the matcher's claims here are
clean.

Labels remain on disk as `labels/v2` ground truth: `local_output/labels/<video_id>_labels.json`.

