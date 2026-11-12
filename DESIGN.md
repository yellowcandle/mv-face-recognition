# MV Face Recognition — Design

Identify which of the 96 *King Maker* contestants appears when in a set of music videos, and
publish those results to a read-only viewer.

This file holds the terms it defines (Track, Reel, Coverage, screen names, marks), the system,
decisions, the visual language, the known state and the open TODOs. History is in git, the
glossary is [`CONTEXT.md`](CONTEXT.md), decisions are in `docs/adr/` (linked below), and the
active effort is [`docs/wayfinder/MAP.md`](docs/wayfinder/MAP.md).

## Terms

Summaries. `CONTEXT.md` is authoritative for Detection, Recognition, Match score, Band, Flag and
Label; Track, Claimed track (with misnamed and impostor), label set, Reel, Coverage and the screen
names are defined only in this file.

- **Detection**: a face found in a frame. A **recognition** is a detection matched to a contestant.
- **Track**: one face followed across frames by ByteTrack (`tracker_id`).
- **Match score**: raw cosine between a detection and a contestant's closest reference
  embedding. At or above the acceptance threshold (0.412) it is a recognition.
- **Band**: the coarse quality stamp shown on a detection, from its match score (`bandFor()`):
  清楚 (≥ 0.445) and 尚可 (≥ 0.412) are recognitions; 存疑 is everything below the threshold,
  including a detection with no score. A detection with an accepted flag shows 已核對 instead and
  has no band. Cut-offs are `band_cutoffs` in `processing_config.yaml`; where they come from is
  under Decisions.
- **Reel**: one music video, identified by its `video_id`. The five source MVs are numbered 1–5
  by their filename prefix ("reel 4" is `4-《全民造星IV》極限拍MV.mp4`); test clips are extra reels.
- **Coverage**: how well each contestant's reference set works, from `generate_coverage.py`:
  齊全 (good), 偏弱 (weak), 缺 (missing, no references); `classify_quality` in that file sets the
  criteria. 有相 means the contestant has references. This is a quality of the references, not a
  band.
- **Flag**: an admin's proposed correction of one detection's contestant, with a pending /
  accepted / rejected lifecycle. An accepted flag is laid over that detection when it is served;
  stored metadata is never rewritten.
- **Label**: a human verdict on a whole track, used as ground truth to measure accuracy:
  `contestant` (which one), `not_a_contestant`, `unsure` or `box_wrong`. A **label set** (defined
  here) is all the labels for one reel, tied to the metadata run they were made on. Flags correct what is
  shown; labels measure how often the pipeline is right. A label is one verdict per track, but
  on test-video-mv2 (ticket 017) 2 of 42 tracks mixed two contestants. A mixed track is labelled
  `unsure`, which leaves it out of precision; ticket 020 must report their count.
- **Claimed track**: a track the matcher named. It is **misnamed** when its label names a
  different contestant, and an **impostor** when its label is `not_a_contestant` (ticket 019).

Screen names (viewer: 首頁, 播放, 紀錄, 名冊; admin adds the rest):

| Name | Screen | Name | Screen |
|---|---|---|---|
| 首頁 | home, the reel list | 標註 | labelling (track verdicts) |
| 播放 | player with face overlays | 待核 | flag review queue |
| 紀錄 | per-reel appearance record | 參賽者 | contestant detail |
| 名冊 | cast roster | 處理 | processing jobs |
| 儀表 | admin dashboard | 向量 | embedding workbench |
| 管理 | system admin | | |

播放 also has an up-next queue, 待播. The 待核 screen is named for the mark on the flags it lists.

Marks: 待核 pending, 已核對 verified by a person, 作廢 void, 唯讀 read-only.

## System

```text
                                                      local runs (mvp-processor)
                                                                   │
                                                                   ▼
HF Jobs ──> HF bucket output/<video_id>/ ── copied by hand ──> local_output/ ──> local_api.py
                                                                   │
                                                                   ├─ publish:metadata:remote ──> KV METADATA_KV
                                                                   └─ upload-to-r2.js ──> R2 mv-face-recognition-videos

local_output/labels/   merged label store; nothing copies it to KV yet

worker/src/index.ts reads KV and R2 and serves:
  ├──> apps/viewer (public, read-only)
  └──> /admin (Cloudflare Access) ──> writes flags, label sets, jobs to KV;
                                      a job is dispatched to HF Jobs
```

- **Pipeline** (`mvp-processor/`): entry `src/process_video.py`, matching in
  `src/face_detector.py`, overlay timing in `src/video_processor.py`. Faces are 512-d
  InsightFace `buffalo_l` embeddings, tracked with supervision/ByteTrack. Matching is max-cosine
  over per-photo reference embeddings
  ([ADR 0001](docs/adr/0001-reference-embeddings-are-a-derived-cache.md)). Reference photos are
  read from `source/photo/contestants/ig_photos/contestant_{id}/`.
- **HF Jobs**: a 處理 job on the deployed admin, or `scripts/hf/jobs/submit.py` locally, runs
  `hf_pipeline.py` on Hugging Face. It reads sources, photos and model weights from the HF bucket
  `yellowcandle/mv-face-recognition` and writes metadata, embeddings and renditions to that
  bucket's `output/<video_id>/`. Nothing brings that output back: the Worker does not read it, and
  no script copies it into `local_output/`. A finished job is not live until someone copies it
  down and publishes.
- **Outputs per reel**: metadata (boxes as frame fractions `[x1,y1,x2,y2]`, `match_score` is the
  raw cosine; [ADR 0002](docs/adr/0002-face-boxes-are-frame-fractions.md)),
  `<reel>_embeddings.npz` with per-detection embeddings (not published yet), and renditions `_1080p` and
  `_720p` encoded with the imageio-ffmpeg binary.
- **Local serving**: `mvp-processor/src/local_api.py` reads `local_output/`.
- **Publish** has two separate steps, both reading `local_output/`. `publish:metadata:remote` and
  `upload-to-r2.js` push to production KV and R2. Get the user's confirmation before running either.
  - `npm run publish:metadata` is a dry run; `publish:metadata:remote` writes the
    `metadata_<video_id>`, `processed_videos_list`, `contestants_structured` and `embedding_*` KV
    keys that the Worker reads. It names the renditions' R2 objects but does not upload them.
  - `node scripts/upload-to-r2.js` (`--dry-run` to preview) uploads `_1080p` and `_720p` from
    `local_output/processed_videos/` to R2 `processed_videos/`.
  - Neither step writes labels or flags.
- **Admin**: one app, `apps/admin`, with two backends. The deployed `/admin` on the Worker is the
  default: flags, label sets and processing jobs are written to Worker KV there. The same app run locally with Vite talks to
  `local_api.py` and is needed for work that reads local files directly (the 向量 page's
  coverage and similarity rebuilds). It asks `/admin/api/system/status` which backend it is on (`useIsEdge`).
- **Worker** (`worker/src/index.ts`): public reads are read-only, enforced by
  `worker/tests/worker-is-read-only.test.mjs`. Admin writes (flags, label sets, processing jobs)
  live under `/admin` behind Cloudflare Access
  ([ADR 0005](docs/adr/0005-admin-writes-are-gated-on-the-worker.md)).
  The gate fails closed: 503 when Access is not configured, 401 without a token. Deployed
  processing jobs dispatch to HF Jobs ([ADR 0006](docs/adr/0006-admin-jobs-run-on-the-worker.md)),
  which needs the Worker secret `HF_TOKEN` (`wrangler secret put HF_TOKEN`; do not delete it).
- **Frontend**: pnpm monorepo with `apps/viewer` (public, read-only), `apps/admin` and
  `apps/shared`. Build with `npm run build:frontend`. Router:
  [ADR 0004](docs/adr/0004-keep-declarative-react-router.md).
- **Deploying is the user's call.** Do not run `wrangler deploy` (standing constraint in
  [`docs/wayfinder/MAP.md`](docs/wayfinder/MAP.md)).

## Decisions

Each ADR records its alternatives.

- [ADR 0001](docs/adr/0001-reference-embeddings-are-a-derived-cache.md): reference embeddings are a
  derived cache, keyed by contestant number.
- [ADR 0002](docs/adr/0002-face-boxes-are-frame-fractions.md): face boxes are frame fractions in
  `[x1,y1,x2,y2]` order.
- [ADR 0004](docs/adr/0004-keep-declarative-react-router.md): the viewer and admin keep declarative
  React Router.
- [ADR 0005](docs/adr/0005-admin-writes-are-gated-on-the-worker.md): admin writes are allowed on
  the Worker, behind Access (supersedes
  [0003](docs/adr/0003-the-deployed-worker-is-read-only.md), which made the whole Worker
  read-only).
- [ADR 0006](docs/adr/0006-admin-jobs-run-on-the-worker.md): admin processing jobs run on the
  Worker, gated, dispatched to HF Jobs.
- Accepted flags show at read time as an overlay rather than by rewriting metadata, so rejecting a
  flag undoes it. See [`CONTEXT.md`](CONTEXT.md) "Accepted-flag overlay".
- `putFlag` keeps `video_id` and `status` in KV key metadata, so a public read lists keys and
  fetches only the flags accepted for that reel. This was chosen over a per-reel document, which
  would need its own write path (see the TODO "One accepted-flags document per reel"). If a flag's
  key metadata is missing or malformed, the Worker reads the flag anyway.
- Band cut-offs (`band_cutoffs`, commit `757741c7`,
  [ticket 019](docs/wayfinder/tickets/019-decide-the-batch-gate-on-labelled-ground-truth.md)):
  清楚 0.445 and 尚可 0.412, the latter also the acceptance threshold. They come from a
  leave-one-out sweep over the 638-reference cache after curation (`scripts/band_cutoffs.py`):
  p99 impostor 0.412, max impostor 0.445, genuine p05 0.377. So 清楚 clears every impostor pair
  observed and 尚可 is the 1% false-match boundary. This supersedes ticket 014's 0.585/0.451,
  measured before curation. Both stay provisional (see the ticket 020 gate below).
- Every detection's embedding is kept in `<reel>_embeddings.npz` (`frame_number`,
  `detection_index`, `embeddings`), so references and thresholds can be re-scored without
  re-detecting. The alternative, discarding them after matching, forces a paid re-detect for any
  reference or threshold change.
- `mvp-processor/scripts/rescore_run.py` re-scores a run from that file, keeping boxes and track
  ids. `run_source` copies `processing_date`, so labels and flags stay attached, but the run
  identity no longer says which references scored it (see the `rescore_run.py` caveat in Known
  state).
- `mvp-processor/scripts/carry_labels.py` moves a label set onto a newer run by box (same frame,
  IoU >= 0.5), because a reprocess renumbers tracker ids, and refuses a track that split or took
  another track's boxes.
- Face detection sets ONNX Runtime to 8 threads and loads only detection and recognition
  (`INSIGHTFACE_THREADS` overrides). ONNX Runtime's default thread count made 282 threads under
  the 8-CPU cap on HF `cpu-upgrade`; the fix cut 60 reel 4 frames there from 195s to 14s, with the same boxes and
  detection scores.
- scikit-learn is a direct dependency, for `cluster_unmatched.py`.
- Toolchain is locked at InsightFace 0.7.3, ONNX Runtime 1.23.0, OpenCV 4.11, supervision 0.31.4,
  lap 0.5.14, `trackers` 2.6.1, Pillow 13, rather than upgrading together, so a change in output
  can be traced to one package. Pillow 13 requires Python 3.11, so `mvp-processor` requires Python 3.11 or later.
- Ticket 020 gate (decided 2026-11-09): pooled precision >= 95% across the five reels, point
  estimate; precision = correct / (correct + misnamed + impostor). A pass confirms precision on the
  top-scoring claims; 0.412 stays provisional until the random draw is reported and is not clearly
  worse. A fail triggers the curation order under Pipeline and data. Rejected: a Wilson lower
  bound, a per-reel bar, the 0.2 impostor clause. Counts, tolerance and reporting are in
  [ticket 020](docs/wayfinder/tickets/020-sample-claimed-tracks-on-the-0-412-batch.md).
- Portraits are requested through `/cdn-cgi/image` at 64/256/512px via `portraitSrc`
  (`apps/shared/lib/portrait.ts`). Cloudflare Stream stays parked until viewers report playback
  problems.

## Visual language — 點唱單 / 存根

The viewer and the admin share one look: a carbonless request slip. The product
files a name against a timestamp, and a radio dedication slip is that object. The viewer is the
**第二聯 (copy 2)**, public and read-only. The admin is the **存根 (office copy)**, the writable
stub. Values live in the CSS (`apps/viewer/src/app.css`, `apps/admin/src/app.css`) and in
`apps/*/.impeccable/surfaces/`; designs are in `webui.pen` (gitignored).

- Type: `LXGW WenKai TC` for text, `JetBrains Mono` for figures. Weight 400; 700 for active states,
  the primary button and the wordmark. Sizes 12, 13, 14, 15, 18, 28, 32 px (wordmark 16 px).
  Nothing under 12 px.
- Muted text uses ink-muted, not the `--color-ledger` token, which fails contrast on paper.
- Radii: 6 px on controls, 4 px on faces, 2 px on stamps. No shadows except modals. Flat 1 px rules.
- A band is a stamp, not a colour: `bandFor()` maps to 清楚 / 尚可 / 存疑. Tones live on
  `BAND_STAMP` in `apps/shared/lib/bands.ts`. The raw cosine sits beside the stamp, not only in a
  tooltip.
- States are the marks listed under Terms. 已核對 and 作廢 (human decisions) tilt; band and
  quality stamps are upright (`Stamp.tsx`).
- Red means action, selection or missing. 偏弱 is muted.
- The viewer is read-only: it carries a 唯讀 stamp, and `worker/tests/worker-is-read-only.test.mjs`
  fails on any public write.
- No spine, folio numbers or tracked Latin labels. Page hints sit under the title.
- Icons: `lucide-react`.
- The viewer is mobile-first down to 320 px (2026-11-12). Gutters are `px-4` and become `sm:px-14`.
  Side columns (首頁 tally, 播放 queue) stack below the main column until `lg`. The header shows
  `MV` and drops the nav icons below `sm`. 紀錄 drops 最高 and 出現時段 on phones, and the page
  scrolls instead of the table. `Masthead` wraps its right slot; `fill` gives it a full line on
  phones (for selects and button rows).
- The admin is mobile-first too (2026-11-12). Below `lg` the sidebar is a top bar with a 選單
  disclosure (`AdminLayout`), and two-pane pages stack. Phone-hidden columns: 紀錄 最高分/出場時段,
  參賽者 參考相/出場 (both still in the filing card), 管理 長度/尺寸 (串流 below `xl`). 參賽者's
  filing card is a full-screen sheet below `lg`. 向量's heatmap scrolls sideways (fixed canvas).
- The 標註 sheet is docked, so it is a labelled region, not a modal: no focus trap, and closing it
  moves focus nowhere, so that Esc then Backspace can't clear a tile's label.

## Known state

- Test clips are hidden from the viewer; the admin shows them (`useVideos` / `isTestClip`).
- On the deployed admin, local-only actions (the 向量 rebuild buttons, which read local files; the
  local write footer) are disabled (`useIsEdge`).
- Labels: `local_output/labels/<video_id>_labels.json` holds 207 labels (reels 1-5: 29, 44, 11,
  101, 22), all bound to the 2026-11-06 runs. It is the merged set from ticket 020 (local plus KV,
  carried by `carry_labels.py`). No script writes label sets to KV yet, and publish writes no
  `labels_<video_id>` KV key. Until the publish-first step 2, the deployed admin's labels bind to
  the older runs.
- A label set records the metadata run it was made on (`processing_date` plus detection count).
  When either differs from the reel's current metadata, the Worker refuses the labels with a 409,
  on both load and save, because a reprocess renumbers tracks and the labels would land on the
  wrong faces.
- `rescore_run.py` does not record which references scored the run. Do not run it on a labelled
  run until it writes its own run identity: precision measured after a rescore cannot name the
  references it used.
- Accepted flags match on exact boxes, so a reprocess can detach them silently. As of 2026-11-09
  the flags to re-check are Marf on reel 1, 榛綦 and Alice on reel 3. Labels already have a
  carrier (`carry_labels.py`); flags do not yet (see the TODO "Carry accepted flags onto a new
  run").
- Reel 1's local `_1080p.mp4` was rebuilt on 2026-11-01 and reads its full duration (264.5 s). Whether the R2 copy
  is the rebuilt file is unchecked until the next `upload-to-r2`.
- The published reel list carries `duration` and `height`. `height` is the served rendition's
  (1080 for `_1080p` encodes), so the public 首頁 reads "1080P" while local dev reads the source's.
- A 處理 job on the deployed admin has a mode: `initial` (process a reel, on CPU),
  `embedding-update` (rebuild the reference cache, on GPU) or `coverage-refresh` (refused on the
  deployed Worker). An `initial` job must name a reel. The Worker refuses it: coverage reaches KV only
  `publish:metadata`. Every job is a paid HF run
  ([ADR 0006](docs/adr/0006-admin-jobs-run-on-the-worker.md)). A deployed `initial` or
  `embedding-update` job cannot go live without a manual copy until the pull-back script exists.
  A new reference set changes nothing until a reel is re-scored (`rescore_run.py`, see its caveat) or reprocessed.
- Accepted-flag limits: a flag covers one detection, not its track. Cross-reel figures
  (`contestants_structured`, `embedding_coverage`) stay as published until the next publish.
  The Worker reads at most 200 flags per request (`FLAG_READ_CEILING`). Past 200, the remaining
  flags are not read: a warning is logged and those corrections are missing from what is served.
  The 200 is not per reel: an unfiltered read (`readFlagOverlay(env, null)`) counts accepted
  flags across all reels, plus flags with missing key metadata, and which flags fall past 200
  depends on KV key order. Every public read costs one KV list per 1000 flag keys.
- Admin playback polls `/api/faces/detect` every 200 ms while playing (`startPolling` in
  `Player.tsx`, admin mode only). Each call runs `readFlagOverlay`, at least one KV list per poll.
  On any error it serves detections without the accepted flags and only logs a warning, so a
  failed read looks like flags missing.
- Licence: InsightFace's README says its pretrained models, including `buffalo_l`, are for
  non-commercial research, and commercial use needs a licence from InsightFace (its code is MIT).
- Privacy: the reference photos are public (contestants' public Instagram), and the people named
  are contestants on a broadcast show. A misidentification is corrected with a flag; there is no
  separate takedown route. The public `/embedding/coverage`, `/embedding/similarity` and
  `/embedding/top-pairs` routes serve only aggregates (`embedding_coverage`,
  `embedding_similarity_matrix`, `embedding_top_pairs`); no per-photo vectors are served.
- Cloudflare runs on the herballemon account (the `herballemon.workers.dev` subdomain). The plan is
  not readable with wrangler's token (billing scope), but KV analytics show 2,838-2,848 list calls a
  day from 2026-10-31 to 2026-11-03, all HTTP 200. The Free plan caps lists at 1,000 a day, so KV
  is on a paid allowance (Workers Paid: 1M lists a month included). Checked 2026-11-09. A steady
  ~2,840 a day is one list every ~30 s, which matches a page left open and polling; normal days run
  0-50.
- The reference photos, `local_output/` (the only publish source) and the merged label sets exist
  on one Mac with no backup; the HF bucket holds copies of photos and promoted runs only. After
  step 2 above, KV holds a second copy of the labels, which reduces the risk for them only.
- Group-photo rescue was tried and not adopted: it added references but changed no labelled track
  outcome.

## TODO

### Flags and admin UI

- [ ] Store a decision time on flags; 最近核對 (the dashboard's recently-decided list) can only
      sort by filing time.
- [ ] Add a warning to the deployed 處理 screen that job output stays in the HF bucket until the
      pull-back script exists.
- [ ] One accepted-flags document per reel, so a read is one get instead of a list per 200 ms
      poll, and the 200 limit stops being a global count (see Known state, `FLAG_READ_CEILING`).
      KV has no compare-and-swap, so concurrent accepts can race.
- [ ] The local API's `/api/contestants/N/thumb/face` returns full 2048 px stills, and returns
      HTTP 200 even for a contestant with no references, so 缺 contestants get an image (the
      deployed copy is a 512px WebP crop).
- [ ] 名冊 counts 67 (Sarah) and 77 (TABI) as 有相 although they have no references.
- [ ] Viewer 播放 queue re-lists anyone absent for one frame; its `R2` footer is hardcoded.
- [ ] Viewer 首頁 treats a videos error as empty. Similarity errors show the no-data message.
- [ ] 標註 rail keeps the previous video's labels while blocked. Appearance errors on 參賽者 read
      as 沒有出場.
- [ ] Draw and implement designs for states still only styled by analogy.
- [ ] Viewer 播放 `待播` thumbnails seek the video one at a time: pre-make crops into R2 at
      publish, which `/api/faces/crop` already serves.

### Pipeline and data

Publish first, in order: (1) with the user's go, publish the 2026-11-06 runs
(`publish:metadata:remote` + `upload-to-r2.js`); (2) write the 207 merged labels to KV, one
`labels_<video_id>` per reel (about 5 `wrangler kv key put` calls, no script yet); (3) re-check
Marf (reel 1), and 榛綦 and Alice (reel 3), in 播放; (4) label ticket 020 on the deployed admin.
After that, KV is the only label writer.

If pooled precision is below 95% (ticket 020), these run in order: photo sync -> HF output
pull-back (only when the reprocess ran on HF Jobs; `rescore_run.py` runs locally) -> rescore or
reprocess -> carry labels (`carry_labels.py`) and flags -> publish. On a fail:

- [ ] Reference photos exist both locally and in the HF bucket, with no sync. A local reference
      change does not reach a deployed 處理 run.
- [ ] Bring HF Jobs output back: a script that copies `output/<video_id>/` from the HF bucket into
      `local_output/`, so a deployed 處理 run can be published.
- [ ] After a reference-set or threshold change, re-score with `rescore_run.py` instead of a paid
      reprocess; keep reprocessing for detector or tracker changes. Needs: the `_embeddings.npz`
      present for every reel, a model-version stamp pairing it with the references, and a run
      identity for a rescore so the `processing_date` 409 can tell it from a reprocess.
- [ ] Carry accepted flags onto a new run the way `carry_labels.py` carries labels (same frame,
      IoU >= 0.5, refuse when ambiguous). Report flags that don't carry in the `publish:metadata`
      dry run, and have `:remote` refuse to publish until they are resolved. Needed on the
      reprocess path (curation, InsightFace upgrade), not for the 2026-11-06 publish, where
      re-checking the 3 flags in 播放 is enough.

Not conditional on a fail:

- [ ] Publish the 2026-11-06 runs and write the merged 207 labels to KV (steps 1 and 2 above).
      Publishing detaches accepted flags whose boxes moved, hence step 3. Before any later
      reprocess, export KV labels, carry them with `carry_labels.py`, and write them back.
- [ ] Copy `local_output/labels/` to the HF bucket. No longer urgent once the labels are in KV,
      which then holds a second copy; the full backup is the TODO below.
- [ ] Ticket 020: label the sample in `local_output/labelling/ticket-020-sample.json`, extended
      with ~10 randomly drawn claimed tracks per reel (fixed seed, reusing existing labels), on
      the deployed admin after the publish, and record the result against the gate. See
      [ticket 020](docs/wayfinder/tickets/020-sample-claimed-tracks-on-the-0-412-batch.md).
- [ ] Variable frame rate sources: overlay time is `frame_count / fps` (`video_processor.py`) but
      the encode keeps source timestamps, so a VFR reel would drift (1.4s on a synthetic clip).
      Check `r_frame_rate` against `avg_frame_rate` before adding a reel.
- [ ] Root `requirements.txt` keeps Pillow below 13 because `gradio` caps it. Only
      `DEPLOYMENT_GUIDE.md` mentions that file and CI does not install it; retire it or drop gradio.
- [ ] Unmatched embeddings still go to `../data/unmatched_faces`, which is lost with an HF Job's
      temporary checkout.
- [ ] Back up the reference photos and local-only artifacts (`local_output/`, local label files).

### Face toolchain review

Checked 2026-11-05; latest: InsightFace 2.1, ONNX Runtime 1.31.1, OpenCV 5.0.

- [ ] Upgrade to InsightFace 2.1, keeping `buffalo_l`. On 120 reel 4 frames on CPU all 251 faces
      match 0.7.3 in boxes and scores, embedding cosine >= 0.99999. Full reel 4 against the
      labelled 21 October run (historical: made before the 2026-11-06 runs): of 6,339 detections,
      6,248 have the same box, 6,333 the same track and 6,327 the same name, matched by position.
      Parity bar for adopting: all 6,339 detections match by position, or the run's labels give
      the same precision. Still to do: one GPU job. 2.1 no longer brings in scikit-learn or
      `opencv-python-headless`. Carry labels and flags first (see the TODOs "Publish the
      2026-11-06 runs" and "Carry accepted flags onto a new run").
- [ ] Test `raccoon_l` and PersonAnalysis (face plus body) on one reel against the 標註 labels.
      Adopting one means new references, all 5 reels reprocessed, bands recalibrated, and accepted
      flags re-checked.
- [ ] Check whether Ultralytics and PyTorch can go: no import in `src`, `scripts/hf` or
      `scripts/publish`; tests and other scripts not checked.
- [ ] Run `pip-audit`; advisories not checked.
- [ ] Licence (see Known state): get it checked if the public site is or may become commercial.

### Code health

- [ ] Data paths are cwd-relative `Path("../...")` (`local_api.py`, `process_video.py`,
      `mvp-processor/scripts/*`), so they break when run from the repo root. Anchor them on
      `Path(__file__)` in one shared module.
- [ ] Not in `processing_config.yaml`: track activation 0.25 (`process_video.py`), cluster
      `distance_threshold=0.8` (`cluster_unmatched.py`), `det_size` 640 (`face_detector.py`).
- [ ] `FaceRecognizer.recognize_faces_batch` (`face_detector.py`) has no production caller;
      [ticket 002](docs/wayfinder/tickets/002-choose-the-matching-strategy.md) chose not to adopt
      it. Delete it and its tests (`test_face_detector.py`).
- [ ] `Player.tsx`: `mode === 'admin' | 'viewer'` branches could be capability
      props; the single and batch flag POSTs are near copies and the batch one awaits
      sequentially.
- [ ] `Contestants.tsx`: derive `stats` from `appearances` instead of resetting parallel state
      in three places.
- [ ] `ContestantTimeline`: move the playhead into its own component so `currentTime` stops
      re-rendering every row.
- [ ] Cache the flag overlay in-isolate, or lower the admin poll rate, and make a failed overlay
      read visible (a header or the admin UI), not only a log line.

### Tests

- [ ] Root `tests/` has 140 failures and 17 errors, recorded as a baseline in
      `.github/workflows/test.yml`; `mvp-processor` unit tests pass (124, plus one error where
      `pytest-benchmark` is missing). Make both suites gating.
- [ ] No tests for the Player, `apps/admin` or `apps/viewer` pages; `apps/shared` has tests for
      its `lib/` and a few components only.

### Later

- [ ] Error tracking and retry alerts for processing jobs.
- [ ] Rate limiting and an input-validation pass on Worker endpoints (`RateLimitError` exists in
      `worker/src/lib/errors.ts`, nothing applies it).
- [ ] Touch and accessibility pass on the video player.
