---
id: 009
title: Remove flagging from the public viewer
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: closed
assignee: claude
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

## Resolution

**The flagging write path is deleted from the deployed worker; the viewer loses the flagging
UI behind one derived `canFlag`; the "show original" toggle rides along.**

### The ticket's premise was false

`/api/faces/flag` is *not* the odd one out. `verifyCloudflareAccess`
(`worker/src/index.ts:117-122`) opens with

```ts
if (!env.CF_ACCESS_AUD || env.ENVIRONMENT === 'development') {
  return { verified: true, email: 'dev@localhost' };
}
```

and **`CF_ACCESS_AUD` is set nowhere** — `wrangler.toml:23-26` still carries it as a
commented-out *how to set this up* block (`wrangler secret put CF_ACCESS_AUD`). `ENVIRONMENT`
is `"production"`, so it is the first clause that fires. All **nine** `verifyCloudflareAccess`
call sites (`:1178, 1262, 1309, 1377, 1443, 1517, 1601, 1658, 1742`) return `verified: true`
unconditionally in production. Adding the same call to the flag route would have changed
nothing. Gating was never the fix.

### Nothing deployed writes flags

`apps/admin` proxies to `localhost:8000` (`apps/admin/vite.config.ts:17`) — `local_api.py`,
never the worker. And admin's Flagging page calls `POST /api/faces/flag/update`
(`Flagging.tsx:87`) and `DELETE /api/faces/flagged/{id}` (`:66`); **neither route exists in the
worker**. They exist only at `local_api.py:450-488`. The flag review loop has always been
local-only, so deleting the worker's copy costs nothing.

### Decisions

1. **Delete the flagging write path from the worker** (option a). `/faces/flag`,
   `/faces/flagged`, `/faces/thumbnail` and `/admin/flagged/approve` go, with
   `handleFaceFlag`, `handleGetFlaggedFaces`, `handleGetThumbnail`, `handleFlaggedApprove`,
   the `FlagData` / `FlagRecord` interfaces and the `flagged_*` KV keys they write.
   Rejected: **provisioning Cloudflare Access** — a real problem, but it is about the *other
   eight* routes, split out as *Decide the fate of the remaining ungated admin routes*.
   Rejected: **adding `verifyCloudflareAccess` to the flag route** — a no-op that looks
   like a fix.

2. **One derived local, not capability props** (option i). `const canFlag = mode === 'admin'`
   at the top of `Player.tsx`, then `{canFlag && …}` at the six sites. Rejected: the
   `TODO.md:24` capability-props refactor — it touches the same six lines, *plus* the prop
   contract and both call sites, and the map already ruled the `TODO.md` "Next" cleanups out
   of scope. It stays exactly as easy to do later.

3. **The `/source/videos/` leak rides along.** `getVideoSource` (`Player.tsx:90-98`) returns
   `/source/videos/${filename}` for "show original", a path the worker does not serve, so in
   the deployed viewer that button blanks the video. Same shape of bug, same one-line guard.

### What was not guarded before

None of it. `mode` was already branched 4× (`:75, 467, 629, 687`) but no flag surface was
among them: the "Flagged (n)" button (`:529-534`), Batch Mode + "Flag Selected" (`:644-684`),
`handleFaceClick`'s dialog branch (`:313-316`), `FaceOverlay.tsx:62` ("Click to flag this
face"), `DetectionBar.tsx:62`, and `useFlaggedFaces` at `:33`, which fired on **every viewer
page load** and would 404 once the route is gone.

### Follow-ups

- Execution: *Remove the flagging write path and gate the admin-only player affordances*
  (ticket 015).
- Newly surfaced: *Decide the fate of the remaining ungated admin routes* (ticket 016).
- [ADR 0003](../../adr/0003-the-deployed-worker-is-read-only.md).
- `CONTEXT.md` gained **Flag**, **Viewer** and **Admin** — the split both decisions turn on
  had no name, which is why an admin-only write path shipped to the public app unnoticed.
