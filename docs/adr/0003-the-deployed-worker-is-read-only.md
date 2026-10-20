---
status: accepted
---

# The deployed worker is read-only

The Cloudflare Worker serves the **viewer** and nothing else. It reads metadata from KV and
video from R2. It accepts **no** writes. Everything that writes — flagging, reprocessing, the
embedding workbench — belongs to the **admin** app, which runs on localhost against
`local_api.py` and is never deployed.

## Context

`POST /api/faces/flag` was an unauthenticated public write to `METADATA_KV`. The obvious fix
was to gate it the way `/api/admin/*` routes are gated. Investigation showed there is no such
gate: `verifyCloudflareAccess` (`worker/src/index.ts:117-122`) short-circuits to
`{ verified: true }` whenever `CF_ACCESS_AUD` is unset, and it is unset — `wrangler.toml:23-26`
still carries it as a commented-out setup recipe. All nine call sites were decorative.

Separately, no deployed code ever called the worker's flagging routes. `apps/admin` proxies to
`localhost:8000`, and two of the three endpoints its Flagging page uses
(`POST /api/faces/flag/update`, `DELETE /api/faces/flagged/{id}`) exist only in `local_api.py`
and were never implemented in the worker at all. The worker's flagging code was a half-built
copy of a feature that lives somewhere else.

## Considered options

- **Add `verifyCloudflareAccess` to the flag route.** Rejected: it would have changed nothing.
  A call to a function that returns `verified: true` unconditionally is worse than no call,
  because it reads as protection.
- **Provision Cloudflare Access, then gate.** Rejected *for this decision*, not dismissed:
  it makes the user create an Access application and put two secrets, to protect a route no
  deployed client calls. It remains the open question for the routes that do have a purpose
  (ticket 016).
- **Delete the flagging write path from the worker.** Chosen. It closes the hole without
  anything to provision, and removes ~250 lines that duplicated `local_api.py` badly.

## Consequences

- **A route with no deployed caller gets deleted, not gated.** That is the rule this ADR
  establishes, and ticket 016 applies it to the remaining `/admin/*` routes.
- **The viewer's flag UI had to go with it**, because the shared `Player` renders admin
  affordances in both modes. Guarded by one derived `canFlag = mode === 'admin'`.
- **Admin flagging is untouched.** It keeps working against `local_api.py`, which matters
  because ticket 005 may adopt it as the ground-truth labelling tool.
- **Flag data does not survive a deploy** and never did — `flagged_faces.json` lives in
  `local_output/`. If flags ever need to outlive the Mac they are made on, that is a new
  decision, not a regression from this one.
- **The KV keys `flagged_face_*`, `flagged_thumbnail_*` and `flagged_faces_index` become
  orphaned** in the production namespace. Nothing reads them after this; clearing them is
  a write to KV and needs the map's usual explicit confirmation.
- **This constrains what the viewer can ever be.** Any future viewer feature that writes —
  public voting, corrections from viewers, saved playlists — reopens this ADR rather than
  slipping in beside it.
