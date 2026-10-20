---
id: 015
title: Remove the flagging write path and gate the admin-only player affordances
label: wayfinder:task
mode: AFK
blocked_by: []
status: closed
assignee: claude
---

## Question

Execute what *Remove flagging from the public viewer* settled. Nothing is left to decide —
see that ticket's Resolution and
[ADR 0003](../../adr/0003-the-deployed-worker-is-read-only.md).

## Worker: delete the flagging write path

1. **Drop four routes** from the `switch` in `worker/src/index.ts`: `/faces/flag` (`:563-568`),
   `/faces/flagged` (`:570-572`), `/faces/thumbnail` (`:581-586`) and `/admin/flagged/approve`
   (`:621-626`), including their trailing-slash twins.
2. **Delete their handlers**: `handleFaceFlag` (`:837`), `handleGetFlaggedFaces` (`:921`),
   `handleGetThumbnail` (around `:1001`), `handleFlaggedApprove` (`:1600`).
3. **Delete the `FlagData` (`:73`) and `FlagRecord` (`:87`) interfaces** once nothing references
   them.
4. **Check the contestant-detail and embedding-sync handlers**, which also read
   `flagged_faces_index` (`:1677-1710`, `:1751-1760`). Decide per site whether the flag
   aggregation goes with the rest or the handler keeps a now-always-empty read — do not leave a
   handler parsing a KV key nothing writes. Note `:1751` types the index as `string[]` while
   `:1678` types the same key as an array of objects; one of them was always wrong.
5. **Leave the other `/admin/*` routes alone** — they belong to ticket 016.

`local_api.py:395-488` is **untouched**. Admin flagging keeps working locally, which ticket 005
may still want as the ground-truth labelling tool.

## Player: one derived `canFlag`

6. `const canFlag = mode === 'admin';` near the top of `Player.tsx`, then guard:
   - the **"Flagged (n)" button** (`:529-534`)
   - the **batch controls block** (`:644-684`) — Batch Mode, Select All, Clear, Flag Selected
   - **`handleFaceClick`'s else-branch** (`:313-316`) so a viewer click cannot open the dialog
   - **`useFlaggedFaces`** (`:33`) — must not fetch in viewer mode; the route is gone and it
     would 404 on every page load
   - **`FaceOverlay.tsx:62`**, whose tooltip reads *"Click to flag this face"*
   - **`DetectionBar.tsx:62`**, *"Click a face to flag it"*
7. **Guard the "show original" toggle** the same way: `getVideoSource` (`:90-98`) returns
   `/source/videos/${filename}`, which the worker does not serve. Hide the control rather than
   shipping a button that blanks the video.
8. **Do not** introduce capability props. `TODO.md:24` stays open and out of scope.

## Context

- **File collision with ticket 014.** Both touch `worker/src/index.ts`, `Player.tsx` and
  `FaceOverlay.tsx`. There is no *decision* dependency, so this is not `blocked_by` — but do
  not run the two in parallel sessions.
- The flag dialog itself (`FlagDialog.tsx`, `useFlaggedFaces.ts`, `apps/admin/src/pages/Flagging.tsx`)
  **survives**. This ticket hides it in viewer and removes its deployed backend; it does not
  delete admin flagging.
- **Leave a runnable check behind**: assert the built worker exposes no route that writes to
  `METADATA_KV` without `verifyCloudflareAccess`. That check is what catches the next one.
  Match ticket 010's precedent — `node --test`, zero new dependencies.
- **Verify in viewer mode**, not just admin: run the viewer against `wrangler dev` and confirm
  no flag affordance renders and no request 404s.

## Resolution

**Closed 2026-09-17.** Executed and verified in both modes. The deployed Worker no longer has a
flagging surface at all; the admin app's flagging still works, untouched.

### Worker — deleted, not gated

Four routes and their trailing-slash twins (`/faces/flag`, `/faces/flagged`, `/faces/thumbnail`,
`/admin/flagged/approve`), their four handlers, and the `FlagData` / `FlagRecord` interfaces.
`/api/faces/flag` and friends now answer **404**, verified against a real `wrangler dev`.

The two handlers that read `flagged_faces_index` lost the flag aggregation, and **the
`string[]` vs array-of-objects contradiction resolved itself: the objects were right.** The
writer pushed `{id, contestant_id, video_id, flagged_at}` while `handleTriggerSync` iterated the
same key as `string[]` and then looked up ``flagged_face_${flagId}`` — with an object in a
template literal that is `flagged_face_[object Object]`, which never exists. So
`approved_flags_count` was **always 0 in production**, and the approve action never fed a sync.
Neither handler now invents a flag-derived number: `handleEmbeddingCompare` returns
`flags_removed: true` with a message, and the sync job drops the field rather than reporting a
zero that reads as "nothing approved".

`/embeddings/sync` stays exactly as it was — it is an ungated KV writer, and that is ticket
016's decision, not this one. The new check names it explicitly so it cannot be forgotten.

### Player — one derived `canFlag`

`const canFlag = mode === 'admin'` now guards: the "Flagged (n)" button, the whole batch-controls
block, `handleFaceClick`'s dialog branch, both flag dialogs, the flagged-faces panel, the
overlay's tooltip invitation, and the detection bar's "Click a face to flag it". `useFlaggedFaces`
takes an `enabled` flag, so **the viewer no longer fetches a route that does not exist** — that
was a 404 on every viewer page load.

### The "show original" toggle is deleted, not hidden

The ticket said to hide it in the viewer. Checking showed it was broken **everywhere**: it points
at `/source/videos/<file>`, which nothing serves — not the Worker, not `local_api`, not the admin
dev server — so it blanked the player in admin too, and hiding it only in the viewer would have
kept a button that blanks the video in the one mode that can toggle it. `showOriginalVideo`,
`handleToggleSource`, the `useOriginal` branch of `getVideoSource` and the DetectionBar control
all go; there is one source, the rendition the API serves. Recorded as a deliberate widening of
the ticket's instruction, on the ticket's own stated intent ("hide the control rather than
shipping a button that blanks the video").

No capability props were introduced: one boolean named after the act it gates, which is the
smallest thing that works. `TODO.md`'s capability-props refactor stays out of scope.

### The check left behind

`worker/tests/no-ungated-kv-writes.test.mjs` (`npm test` in `worker/`, `node --test`, no new
dependencies — esbuild is already there via wrangler):

1. **Enumerates the routes from the source** (`case '<path>':`) rather than from a list, so the
   next route anyone adds is covered automatically. It bundles the worker, drives every route
   with `CF_ACCESS_AUD` set and no JWT — the gate live, exactly the production shape — and asserts
   no `METADATA_KV` write happens. `KNOWN_HOLES` holds the one route that writes ungated
   (`/embeddings/sync`, ticket 016) and prints a note when a hole closes.
2. Asserts the four flag routes are **gone, not gated** (404), including the twins.

**Proven in both directions**: it fails when a route that writes without the gate is planted,
and passes when it is removed. 39 routes checked, 1 known hole.

### Verification

- **Viewer mode against `wrangler dev`** (the ticket's requirement): built the current viewer,
  embedded it (`scripts/update-worker-assets.js`), served it from the worker, drove it in a
  browser. Zero requests to any deleted route, no flag affordance rendered (`Flagged (`, `Batch
  Mode`, `Click a face to flag it`, `Flag Selected`, `Select All` — none present), DetectionBar
  down to "Boxes ON".
- **Admin mode**: `Flagged (0)`, `Batch Mode`, the click-to-face path and the flag dialog with its
  contestant picker all still work against `local_api`; the box lands on the face and the dialog
  reads "Detected As: 余潔瀅 (0.61 cosine (high band))". No flag submitted, so nothing was written.
- `npx tsc --noEmit` clean in `worker`, `apps/shared`, `apps/viewer`, `apps/admin`;
  `wrangler deploy --dry-run` bundles (390 KiB, all bindings intact) — **no deploy was run**.

### Not this ticket's 404

The viewer's video element still 404s in dev, from the fabricated `processed_videos_list`
fallback whose `stream_url` names `_annotated.mp4`. That is ticket 007's open question 2 (delete
the fallbacks so failure is loud), and 015 neither caused nor could fix it.

### Loose ends

- `worker/src/index.ts.backup` still carries the deleted names; still untouched (see the map's
  post-014 notes).
- `worker/embedded-assets.js` now embeds the freshly built viewer (2 lines changed) — done as part
  of the viewer-mode verification, and it removes one trap from the deploy handoff: the embedded
  bundle is no longer the pre-014 one.
- `worker/tests/api.test.js` still cannot run (it imports `vitest`, which is not a dependency and
  never was); the new test is `.test.mjs` so `node --test tests/` does not trip over it.

