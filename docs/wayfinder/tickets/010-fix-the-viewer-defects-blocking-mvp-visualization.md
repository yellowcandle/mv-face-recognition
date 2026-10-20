---
id: 010
title: Fix the viewer defects blocking MVP visualization
label: wayfinder:task
mode: AFK
blocked_by: []
status: closed
assignee: claude
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

## Resolution

**Fixed 2026-09-09.** Both defects, plus the CJK encoding issue the ticket flagged as minor —
which turned out to be part of defect 1, not separate.

### Defect 1 — clicking any card opened the first video

- `apps/viewer/src/pages/PlayerPage.tsx` now reads `useSearchParams()` and passes
  `initialVideoId` to the Player.
- `apps/shared/components/Player/Player.tsx` takes an optional `initialVideoId` prop and selects
  via `pickInitialVideo(videos, initialVideoId)` instead of `videos[0]`. Optional with a `null`
  default, so the admin app's `<Player mode="admin" …>` is unchanged.
- `apps/viewer/src/pages/Home.tsx:27` now wraps the id in `encodeURIComponent`. **This was not
  cosmetic**: every one of the 5 MV ids contains CJK, spaces and `《》`, so the raw link produced a
  query string that would not round-trip. The fix is only correct *because* both halves changed —
  `URLSearchParams.get` decodes, so the value arrives ready to compare against `Video.id`.
- `apps/shared/hooks/useViewerMetadata.ts:15` encodes the id on the metadata fetch, matching
  `Player.tsx:111,127` which already did.

### Defect 2 — analytics rows labelled with ids

`Analytics.tsx` mapped `nickname: key`, and `contestant_timeline` is keyed by id string
(`"33"`, `"88"`). Now reads `info.contestant_info.nickname` / `.name`, the same source
`ContestantTimeline.tsx:123` already used correctly. The row `key` moved from `s.nickname` to a
new `s.id`, since nicknames are not unique and are not stable (per `CONTEXT.md`).

### The runnable check

`apps/shared/components/Player/pickInitialVideo.ts` + `.test.ts`, run by `npm test` in
`apps/shared` (`node --test`). **Zero new dependencies** — the workspace had no test tooling at
all, and Node 26 strips types natively, so adding vitest + jsdom + testing-library for two small
fixes was not warranted. 4 tests, all passing: requested-video selection, the encode/decode round
trip on a real CJK id, fallback on absent/unknown id, and the empty list.

The rule is extracted rather than inlined for one reason: if it is ever "simplified" back to
`videos[0]`, 4 of the 5 published MVs silently become unreachable again — which is this defect.

`tsconfig.json` in all three apps gained `allowImportingTsExtensions` (they already set
`noEmit`), because Node's ESM resolver needs the explicit `.ts` in the test's import and `exclude`
globs do not reach across into `../shared`.

### Verified

- `node --test` in `apps/shared`: **4/4 pass**.
- `npx tsc -b` in `apps/viewer` and `apps/admin`: **both clean**.
- `npm run build` in `apps/viewer`: **succeeds**, 110 modules.

### Deliberately not touched

- **`Analytics.tsx:23`** does `videoId.match(/^(\d+)/)?.[1]` — the numeric-prefix rule. That is
  *Settle the KV and R2 publish contract*'s decision, not this ticket's.
- **`Analytics.tsx:135`** badges on `avgConfidence > 0.4 / > 0.25`. *Settle what match confidence
  means on the wire* already established those thresholds are unreachable and ruled they get
  retuned to band cutoffs in *Rewrite the metadata contract*. Changing them here would collide.
- **The worker's mock** (`index.ts:1822-1852`), which the ticket suggested checking. Also
  *Settle the KV and R2 publish contract*'s call — it is parked awaiting four answers.
