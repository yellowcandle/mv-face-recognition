# Map: Face recognition pipeline → visualized → published on Cloudflare

Label: `wayfinder:map`
Charted: 2026-09-07

## Destination

All 5 source MVs processed with **fixed** face matching, their results visible in the
React viewer (face overlays + contestant timeline + analytics), verified locally against
real R2/KV via `wrangler dev`, and handed off as a **single deploy command the user runs**.

Two stages: **MVP** = MV #4 (`4-《全民造星IV》極限拍MV.mp4`, 135 MB, smallest) end-to-end.
**Complete** = all 5, with per-contestant screen-time analytics.

The map does **not** deploy. It ends at deploy-ready.

## Notes

**Domain**: InsightFace `buffalo_l` (512-d) + supervision/ByteTrack; Python pipeline in
`mvp-processor/`; React pnpm monorepo (`apps/admin` local, `apps/viewer` → Cloudflare Worker,
`apps/shared` Player); Cloudflare Worker + R2 (`mv-face-recognition-videos`) + KV (`METADATA_KV`).

**Skills every session should consult**: `grilling` + `domain-modeling` by default.
`ponytail` is active — take the laziest rung that holds.

**Standing constraints for this effort**:
- **Never run `wrangler deploy`.** Writes to R2 and KV are also outward pushes and need
  explicit confirmation. One confirmation point, at the end.
- CJK text rendered onto frames MUST use PIL + `/System/Library/Fonts/PingFang.ttc`.
  Never `cv2.putText` — it cannot render CJK.
- **`CLAUDE.md` and `DESIGN.md` are stale wherever they describe the frontend** (they still
  document the deleted SvelteKit app in `mvp-processor/`). `TODO.md` is accurate. Trust code.
- No webcam work. Only files in `source/videos/`.
- Never delete `metadata/contestant_info.csv`.
- The PIL/PingFang rule above is now historical: nothing renders text onto frames (ticket 014
  deleted the annotated-render path). Overlays are drawn in the browser.

**State after ticket 014 (2026-09-17)** — read before touching the pipeline:
- **Only `test-video-mv2` is under the current metadata contract.** `5-《…》_metadata.json` and
  `test-unmatched_metadata.json` in `local_output/metadata/` are pre-014 (pixel boxes,
  threshold-relative scores); the pipeline's checks and `generate_coverage.py` warn and skip them.
  Reprocess, never migrate.
- Boxes are **frame fractions** and scores are **raw cosines**; the only surviving cosine named
  `confidence` is the flag record's, which 005 owns.
- Loose ends deliberately left: `worker/src/index.ts.backup` (91 KB tracked stale copy of the
  worker, still carrying the deleted names), and `_annotated.mp4` files on disk
  (`local_output/processed_videos/test-video-mv2_annotated.mp4`, 91 MB, plus 708 MB at the repo
  root — 007's open question 4).
- Nothing from 014 is committed; the tree also carries the user's own in-flight edits.

**State after tickets 015 + 016 (2026-09-17/20)** — the deployed Worker is read-only, and that is
enforced, not just intended:
- Every flagging route and every admin/settings/upload route is **deleted** (404); the API switch
  is **8 routes, all reads**. `worker/tests/worker-is-read-only.test.mjs` (`npm test` in `worker/`)
  drives every route × every method × two bodies and fails on any KV write, R2 write or outbound
  fetch — including on a route that validates its input first, which is how the first version of
  that check missed `/admin/upload-video`.
- The Player's `canFlag = mode === 'admin'` is the single switch for every flag affordance, and the
  viewer does not fetch the flag route at all. The "show original" toggle is gone (it pointed at
  `/source/videos/`, served by nothing).
- `worker/embedded-assets.js` embeds the current viewer build, so the deploy bundle is not pre-014.
- **One action outstanding for the user: `wrangler secret delete HF_TOKEN`** — the route that used
  it is gone, so the secret is dead weight. Flagged, deliberately not run.
- **Tracks are usable but not truth** (ticket 017): `minimum_matching_threshold` 0.3 → 0.8 puts ids
  on 237 of the 399 detections as 42 tracks (longest 19), but 162 detections still carry none,
  **2 of the 42 tracks hold two different contestants**, and 9 contestants span 2–4 tracks. Any
  apply-to-track affordance needs a confirmation step; labels stay per detection.

**Scope decisions settled while charting**:
- Fix matching *before* running the pipeline — reprocessing 1.3 GB of 4K is far more
  expensive than the fix.
- The gate for the full batch is **separation**, not recognition rate: matched-face cosine
  mean ≥0.45 while cross-person stays ≤0.2, against the measured baseline of mean 0.206 /
  max 0.510. Recognition rate is unfalsifiable without ground truth.
- Publish **`_1080p.mp4` + metadata**, never `_annotated.mp4`. Overlays are drawn by the JS
  layer.
- Iterate matching on `test-video-mv2` (30 s, has the before-number). MVP-publish MV #4.

## Decisions so far

<!-- one line per closed ticket -->

- [Measure within-person embedding separation](tickets/001-measure-within-person-embedding-separation.md):
  within-person max 0.646 vs mean 0.308 against cross-person 0.034 — max-cosine **clears** the
  gate, averaging **fails** it. Also: only 83 of 96 contestants have any usable reference, and
  11 byte-identical photo groups are filed under 2–4 contestants each.

- [Choose the matching strategy](tickets/002-choose-the-matching-strategy.md): max-cosine over
  per-photo references, averaging deleted; curation = dedupe + single-face photos only (no
  HDBSCAN); acceptance threshold **0.45 cosine** (`tolerance: 0.55`), provisional until ground
  truth exists; `recognize_faces_batch` **not** adopted. Added `CONTEXT.md` to kill the
  tolerance-vs-cosine inversion.

- [Decide the fate of contestants with no usable reference](tickets/011-decide-the-fate-of-contestants-with-no-usable-reference.md):
  sourced photos rather than accepting the gap. `ig_photos/` 741 → 964 photos; contestants with
  zero references 13 → **1** (only 67/Sarah, whose surviving footage is unusable split-screen
  IG Live). Best source is the show's own solo Pre-round clips, whose burned-in lower-third
  names the contestant. **`docs/wayfinder/assets/photo_embeddings.npz` is now stale.**

- [Choose the reference-embedding storage shape](tickets/003-choose-the-reference-embedding-storage-shape.md):
  one gitignored, regenerable `reference_embeddings.npz` keyed by **contestant number**, plus a
  committed manifest so a stale cache fails loudly. Legacy `{nickname}_embedding.npy` deleted,
  not migrated; `embedding_dim` → `reference_count`; HuggingFace stops holding embeddings.
  See [ADR 0001](../adr/0001-reference-embeddings-are-a-derived-cache.md).

- [Triage the embedding-convention call sites](tickets/004-triage-the-embedding-convention-call-sites.md):
  the blast radius is **11 sites, not ~40** — the count was inflated by two `.claude/worktrees/`
  repo copies. Live Python is only `face_detector.py` and `local_api.py` plus two artifact-
  producing scripts; 8 files are duplicates or cannot be imported at all and get deleted.

- [Migrate the reference-embedding convention](tickets/012-migrate-the-reference-embedding-convention.md):
  done. Matcher scores by max cosine over 663 per-photo references (94 contestants) from the new
  cache; averaging and 95 legacy `.npy` deleted; `face_detector.py` 629 → 439 lines; threshold
  0.68 → 0.55. Tests 19/19. Leave-one-out shows **no regression** (impostor @0.45 still 1.1%).

- [Settle the bbox coordinate space](tickets/008-settle-the-bbox-coordinate-space.md): boxes
  become **frame fractions in `[x1,y1,x2,y2]`**, field renamed `bbox` — no consumer scales by any
  width. The ticket's favoured option was based on a false premise: `_1080p.mp4` is **2592** wide,
  not 1920, and **MV #4 is 16:9 while test-video-mv2 is 2.4:1**, so no single declared width could
  hold. Both consumers were wrong (50% and 74%), not one. Also settled: the `[t,r,b,l]` round trip
  deletes (4 conversions), `frame_data[].recognitions` → `detections` carrying **all 399** not 139,
  and `_annotated.mp4` is dropped. See [ADR 0002](../adr/0002-face-boxes-are-frame-fractions.md).

- [Settle what match confidence means on the wire](tickets/013-settle-what-match-confidence-means-on-the-wire.md):
  the wire carries the **raw cosine** as `match_score`; `match_confidence` is deleted, not
  rescaled. Decoded, the stored values were cosines **0.451–0.643** being rendered as **0.1%–35%**
  — so `Flagging.tsx`'s green-at-0.8 needed cosine 0.89 and **no recognition could ever be
  anything but red**, and `generate_coverage.py`'s thresholds never fired at all. Also: the three
  duplicate confidence fields collapse to one, `det_score` starts being stored, display becomes
  **bands** (cutoffs from measured impostor rate, provisional until ground truth) rather than a
  percentage, six dead config knobs are deleted, and `recognition_config` stops hardcoding a
  `min_confidence: 0.5` that matched neither the config (0.6) nor the run (0.0). No ADR —
  `CONTEXT.md` had already defined match score as a cosine; the code just ignored it.

- [Fix the viewer defects blocking MVP visualization](tickets/010-fix-the-viewer-defects-blocking-mvp-visualization.md):
  fixed. `?video=` routing works (`PlayerPage` reads the param, `Player` takes `initialVideoId`),
  and analytics rows show names instead of ids. The "minor" CJK encoding note was **part of
  defect 1**, not separate — every MV id has CJK, spaces and `《》`, so the link and the lookup had
  to change together. Runnable check left behind with **zero new dependencies** (`node --test`,
  Node 26 strips types); the workspace had no test tooling at all.

- [Remove flagging from the public viewer](tickets/009-remove-flagging-from-the-public-viewer.md):
  the flagging write path is **deleted** from the deployed worker, not gated — because the gate
  does not exist. `verifyCloudflareAccess` returns `verified: true` whenever `CF_ACCESS_AUD` is
  unset, and it is unset, so **all nine** `/api/admin/*` call sites are decorative in production
  and the flag route was never the anomaly. Nothing deployed writes flags anyway: `apps/admin`
  proxies to `localhost:8000`, and two of the three endpoints its Flagging page calls exist only
  in `local_api.py`. The viewer loses the UI behind one derived `canFlag = mode === 'admin'`
  (six sites, none previously guarded — including a `useFlaggedFaces` fetch on every viewer page
  load); the capability-props refactor stays out of scope. The `/source/videos/` "show original"
  toggle, which blanks the video on the worker, rides along. See
  [ADR 0003](../adr/0003-the-deployed-worker-is-read-only.md).

- [Rewrite the metadata contract](tickets/014-rewrite-the-metadata-contract.md): done, one
  reprocess carrying 008 + 013. Boxes are **frame fractions** `[x1,y1,x2,y2]` and scores are **raw
  cosines** (`match_score`), every one of the 399 detections stored (260 unmatched carry only
  `det_score`); baseline reproduced exactly — 139 recognitions, cosines min 0.4511 / median 0.5076
  / max 0.6434. Band cutoffs measured, not guessed: **0.585 / 0.451** (7 of 663 impostor pairs at
  or above 0.451; nothing at or above 0.585 — the 0.1% point is below what 663 pairs can
  resolve). Four things the tickets did not know: InsightFace emits boxes outside the frame (now
  clamped), ByteTrack was activating on the rescaled confidence so `tracker_id` coverage changes,
  `generate_coverage.py` had been reporting all zeros (nickname-vs-number key mismatch) and read
  a key nothing writes, and **`.gitignore`'s Python-template `lib/` rule was silently ignoring the
  new `apps/shared/lib/bands.ts`** — the band helper would never have been committed. Verified by
  a new contract check that crops the same box out of the source, the 1080p and the 720p rendition
  and compares pixels, plus screenshots of the admin player with boxes on faces.

- [Choose the ground-truth labelling means](tickets/005-choose-the-ground-truth-labelling-means.md):
  settled with the user against a working prototype of the real 399 detections. Label in a **crop
  grid** (one pass over face crops, not scrubbing the player), **one label per detection** — not
  per track, because the tracker covered only 129 of the 399 boxes — with four verdicts
  (**contestant / not a contestant / unsure / box wrong**), no missed faces yet, and stored in a
  **new `labels/v1` file** keyed by frame + detection index with the source run pinned, leaving
  flagging untouched. Ground truth is a verdict, not a `status: pending` flag.
  Builds as [Build the crop-grid labeller and the labels file](tickets/018-build-the-crop-grid-labeller-and-the-labels-file.md);
  the tracker's unusable ids are [Fix the tracker's inverted matching threshold](tickets/017-fix-the-trackers-inverted-matching-threshold.md),
  not a blocker.

- [Remove the flagging write path and gate the admin-only player affordances](tickets/015-remove-the-flagging-write-path-and-gate-admin-affordances.md):
  done, both modes verified against a real `wrangler dev`. Four routes and their handlers are
  **deleted, not gated** (404); `canFlag = mode === 'admin'` guards every flag affordance and the
  viewer no longer fetches the flag route at all. The two `flagged_faces_index` readers lost their
  flag aggregation, which settled the ticket's typing contradiction — the array-of-objects was
  right, so `approved_flags_count` had been **always 0 in production**, with the approve action
  never feeding a sync. The "show original" toggle was **broken in every mode**, not just the
  viewer (`/source/videos/` is served by nothing), so it is deleted rather than hidden. A new
  `node --test` guard enumerates routes from the source and fails if any writes `METADATA_KV`
  without the access gate — proven by planting one; `/embeddings/sync` is the single known hole
  and stays for ticket 016.

- [Decide the fate of the remaining ungated admin routes](tickets/016-decide-the-fate-of-the-remaining-ungated-admin-routes.md):
  ruled with the user — **delete them all**, 015's precedent. The ticket knew of eight call sites;
  walking every handler for side effects found **twelve routes with no caller, four ungated
  writers**, the worst being `/admin/upload-video`, which pushed a posted file to HuggingFace with
  the Worker's `HF_TOKEN`. Twelve routes, twelve handlers, `verifyCloudflareAccess` and its result
  type are gone; the switch went 39 routes → **8, all reads**. The deployed Worker is now read-only
  without exception, and the guard is a new `worker-is-read-only.test.mjs` that drives every route
  × every method × two bodies and asserts no KV write, no R2 write, **no outbound fetch** — the
  depth being the fix for the 015 version, which missed the upload route and `/settings` because it
  only sent GET/POST with `{}`. `HF_TOKEN` is flagged for `wrangler secret delete` at the
  confirmation point.
- [Fix the tracker's inverted matching threshold](tickets/017-fix-the-trackers-inverted-matching-threshold.md):
  `minimum_matching_threshold` 0.3 → **0.8** (the library default). The value is a *cost ceiling on
  `1 − IoU`*, so 0.3 meant "only IoU ≥ 0.7" while its name read as a quality floor — the same
  inversion class as the old `tolerance`/cosine mixup. Measured across 0.3/0.5/0.8/0.9: tracks
  119/81/42/36, one-frame 111/48/7/3, untracked 270/221/162/144. The offline replay **predicted the
  pipeline exactly** (237 ids, 42 tracks). Recognitions unchanged (139/399, cosines 0.4511–0.6434).
  Track quality now measured: 2 of 42 tracks hold two contestants, 9 contestants span 2–4 tracks —
  a labelling shortcut with a review step, never truth.
- [Build the crop-grid labeller and the labels file](tickets/018-build-the-crop-grid-labeller-and-the-labels-file.md):
  done and driven end to end. A real admin page at `/labelling` (crop grid in frame order, four
  verdicts, searchable contestant picker, live rail with the gate, apply-to-track behind a
  frame-count confirmation, debounced autosave, resume from disk) plus `GET`/`PUT
  /api/labels/{video_id}` and an on-demand `GET /api/faces/crop` (measured: 375 ms per frame decode,
  cached, ~70 s of work and 1.7 MB for all 399 crops — against 2 min and 2.7 MB pre-extracted).
  The refusals are the point: labels whose `source` does not match the metadata return **409**
  rather than attaching verdicts to whatever box now sits at that index. Found by running it, not
  reading it: the first version **took the whole admin app down** on `/labelling`, because it
  auto-selected `videos[0]` — which is still pre-014 metadata — and React unmounted the root
  silently; the page now probes for the first labelable video and refuses pre-contract metadata
  with a sentence naming the missing field. `local_output/labels/` is gitignored (the ticket's
  premise about `local_output` was wrong; the rule was added for labels alone).
- [Settle the KV and R2 publish contract](tickets/007-settle-the-kv-and-r2-publish-contract.md):
  settled and confirmed. Full video id replaces the numeric-prefix key rule at five sites; the
  hardcoded video list and "Ivy So" mock are deleted so missing keys 404 with the key name; thumbnails
  published with relative paths, no galleries; the four upload scripts collapse into
  `scripts/publish.js` reading `local_output/`; R2 keys `processed_videos/<video_id>_{1080p,720p}.mp4`.
  The worker-side key and fallback changes are implementation work, not decisions.

## Not yet specified

- **Backing up the reference photos.** Raised while closing the storage-shape ticket and left
  unanswered: the 964 photos exist only on the user's Mac. Whether this belongs to this map at
  all is a scoping call the user has not yet made.
- **How far** reference-photo curation goes. The measurement settled *whether*: deduplicating
  the 11 cross-contestant identical-file groups is unambiguous. Everything past that — HDBSCAN
  clustering, dropping wrong-person faces from the 34.5% of photos that are group shots
  (Embedding Workbench T0.5) — is now *Choose the matching strategy*'s call, not fog.
- The single publish script that replaces the four stale upload scripts. Its contract comes
  from *Settle the KV and R2 publish contract*.
- MVP end-to-end for MV #4: process → publish locally → verify under `wrangler dev`. The local
  half is now proven on `test-video-mv2` (admin player + `local_api`, boxes on faces — ticket
  014); what remains is doing it for MV #4 and doing it through the *worker* under `wrangler dev`.
- Compute for the remaining 4 MVs (local Apple Silicon vs reviving Modal). The wall time is now
  real rather than estimated, from the 014 reprocess of the 30 s clip on this M2: **~3 min
  detect+recognize** (192 frames, 187 stored) plus **~7.5 min transcoding** (1080p 5 min, 720p
  2.5 min) — and note **MV #4 is 1920×1080, not 4K**, so its wall time will *not* extrapolate to
  MVs 1/2/3, which are 3840×1600. MV #5 is also 1080p.
- The deploy handoff itself: the exact command and the verification checklist handed to the user.
  One trap already retired: `scripts/update-worker-assets.js` embeds `apps/viewer/dist`, and both
  were rebuilt and re-embedded while verifying ticket 015 — the embedded bundle is current. One
  item still rides with it: `wrangler secret delete HF_TOKEN` (ticket 016), plus deciding whether
  the `MODAL_JOBS` binding and Modal secrets should come out of `wrangler.toml`.
- **Whether the local-only artifacts need to outlive the Mac they are made on.**
  `metadata/contestant_info.csv` aside, everything valuable here lives in `local_output/`: the 964
  reference photos' source images, `flagged_faces.json`, and now
  `local_output/labels/<video_id>_labels.json` — the ground truth *Choose the ground-truth
  labelling means* settled on, which took a human pass over the video to produce and which a
  reprocess invalidates. ADR 0003 makes local-only the permanent shape rather than an accident, so
  this is the same unanswered backup question as the reference photos, one entry up.

## Out of scope

- **`wrangler deploy`** — ruled out by the user. The map produces a command; the user runs it.
- The ~12 code-quality cleanups in `TODO.md` "Next" (shared `formatTime`, `useInterval`,
  capability props beyond what flagging removal needs, `Contestants.tsx` memoisation, …).
  Real, but past this destination.
- Restoring `scripts/modal_youtube_processor.py` cookie support and webhook progress, and
  reviving the disabled Ingestion page. Separate effort.
- Repairing the legacy `src/` ChromaDB tree. It is already broken
  (`debug_similarity.py` imports a `src.core.face_detector` that does not exist) and nothing
  in the live path uses it.
- Webcam / realtime capture. Permanently out per `CLAUDE.md`.
