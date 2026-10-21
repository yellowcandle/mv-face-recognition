# Refactor plan — whole codebase

Three read-only audits (architecture, data contract, frontend) plus measured baselines.
Nothing here is done yet; each section ends with a gate that proves it.

## Baseline (measured 2026-10-21, `main` @ `4f631755`)

| Signal | Value |
| --- | --- |
| `uv run mypy .` | **829 errors in 108 files** (159 checked) |
| `ruff check` | **75 errors** (74 E712, 20 F841, 20 E722, 16 E402, 12 F401, 6 F821, 2 E741) |
| root `uv run pytest tests/` | **140 failed · 120 passed · 34 errors** — pre-existing |
| `mvp-processor` unit+contract | **26 failed · 62 passed · 1 error** — pre-existing |
| Frontend | `tsc` clean (viewer, admin, worker); worker tests 3/3 |
| Python size | `src/` 9,138 lines · `backend/` 5,565 · `mvp-processor/src/` 5,274 · `scripts/` 10,238 · 24 root scripts |
| Frontend size | `apps/admin` 3,914 · `apps/shared` 2,308 · `worker` 1,882 · `apps/viewer` 1,008 |

Neither pytest suite has been green in living memory; the failures are a *baseline*, not a
regression, and `mypy .` could not even finish before this work (duplicate-module abort).

---

## Workstream A — collapse the Python trees

**Finding.** Four video processors and three face detector/matcher pairs exist:

| File | Lines | Verdict |
| --- | --- | --- |
| `mvp-processor/src/video_processor.py` | 562 | **LIVE** — `run-full-pipeline.cjs` → `process_video.py` |
| `video_processor.py` (root) | 34 | shim that importlib-loads the mvp file — delete |
| `src/services/video_processor.py` | 111 | **DEAD** — docstring says "placeholder", `process()` returns its input |
| `src/services/enhanced_video_processor.py` | 1,217 | duplicate — only the Modal/legacy batch path |
| `src/services/realtime_video_processor.py` | 481 | duplicate — only the FastAPI backend |
| `backend/app/services/video_processor.py` | 487 | **DEAD** — no consumer outside `backend/` |

Detection/matching: `mvp-processor/src/face_detector.py` (466, **LIVE**) vs `src/core/face_detector.py`
(214) + `src/core/face_matcher.py` (369) vs `backend/app/services/face_{detector,matcher}.py`
(379+476) — three implementations of the same job. `src/recognition/` contains no `.py` files.

`backend/` (5,565 lines) is a **dead deployment path**: nothing deploys it (`fly.toml` uses
buildpacks, `Procfile`'s `gunicorn app:app` points at nothing, CI is disabled). `src/` (9,138
lines) is legacy, kept alive only by root `tests/` and `backend/`'s lazy imports. Root `src/`
and `backend/` also own **most of the product-code mypy debt** (Workstream F), so deleting them
removes the errors instead of fixing them.

**Steps.** (1) Delete `backend/`, the root `video_processor.py` shim, `src/services/video_processor.py`
and empty `src/recognition/`. (2) Point the root test suite at `mvp-processor/src/` or delete the
tests that only exercise `src/`. (3) Reduce `src/` to what `scripts/publish/build_read_model.py`
and the frontend actually import, then move it under `mvp-processor/` as the one package.
(4) One CLI: `process_video.py`; delete the 13 dead root scripts and the 4 byte-identical
`scripts/` duplicates.

**Gate.** `grep -rn "video_processor" --include=*.py | wc -l` returns ≤ 3 files; `uv run mypy .`
still runs; the pipeline produces a `metadata.json` for one reel.
**Risk.** Medium — `src/` deletion is large. Sequence it last, after the contract work.

**Executed 2026-10-22 — first deletion.** `backend/` (30 files), its `Dockerfile`, the
Heroku `Procfile`, and the root `video_processor.py` shim are gone. Evidence gathered
first: nothing in the repo imported `backend/`, it had no tests, `fly.toml` builds from
buildpacks (so the Dockerfile was unused), and the `Procfile` pointed at the `app.py`
that had already been deleted.

| Signal | Before | After |
| --- | --- | --- |
| mypy (project venv) | 824 errors / 106 files | **488 / 74** |
| ruff | 73 | **66** |
| root pytest | 140F / 120P / 17E | unchanged |
| mypy on `scripts/hf`+`scripts/publish` | 0 | 0 (ratchet holds) |

Two findings worth keeping:

- **`src/services/video_processor.py` is not unimported.** The audit called it dead (it
  is a placeholder that returns its input), but three test modules import it, so deleting
  it broke collection. It is restored; removing it and its tests has to be one change,
  which belongs to Workstream F's quarantine.
- **Deleting files poisons mypy's incremental cache.** After the deletion `mypy .` aborts
  with `AssertionError: Cannot find module for google` (a `google` namespace-package
  resolution bug) even though `--no-incremental` reports normally. `rm -rf .mypy_cache`
  clears it. Anyone deleting a tree should do it first, and CI starts cold so it is
  unaffected.

**Executed 2026-10-22 — A(2) + A(4).** The 29 legacy root test modules are gone (every one
imported `src/` APIs that moved or were deleted; 140 failures, 17 errors). The root suite is
now exactly `tests/contract/test_publish_contract.py` (3 tests, green) and the baseline is
0 failed / 0 errors / ≥3 passed. 18 dead root scripts went with them: two byte-identical
`scripts/` copies, two deprecated/duplicated Modal wrappers, the `hello`/`main` scaffold, a
launcher for the deleted `app.py`, and eleven unreferenced probes. Verified first that no
executable file imported any of them (only stale markdown).

| Signal | Before A(2)+A(4) | After |
| --- | --- | --- |
| root pytest | 140F / 120P / 17E | **0F / 3P / 0E** |
| ruff | 66 | **27** |
| mypy repo-wide (isolated) | 259 | **202** |
| root Python scripts | 44 | 26 |

**A(3) executed 2026-10-22 — B + Modal retirement (user decision).** The unreachable half of
`src/` is deleted: CLI, Streamlit UI, middleware, encryption/validation/compliance/logging,
face tracker, task manager, the placeholder processor, the unused models, and the
`mv-face-recognition` console script that was the CLI's only reference. What remains is the
7-module closure (~2.9k lines) the utility scripts need. `src/models/` is trackable now:
`.gitignore` had `models/` (any depth), which also hid `src/models` — those files had never
been committed.

The Modal surface is retired in full, as chosen: `modal_pipeline.py`, the six `scripts/modal_*`
entry points, `process_videos_modal.sh`, `test_modal_pipeline.py`, `MODAL_PROCESSING_SETUP.md`
and `docs/MODAL_PIPELINE.md`; `modal`, `streamlit`, `PyQt6` and `nicegui` leave `pyproject.toml`
(`uv.lock` updated). The `scripts/modal_youtube_processor.py` restore-or-retire question is
therefore closed as **retired**.

| Signal | After A(2)+A(4) | After A(3) |
| --- | --- | --- |
| `src/` | 9,138 lines | **~2.9k lines / 7 modules** |
| mypy repo-wide (isolated) | 202 | **69** |
| ruff | 27 | **15** |
| Modal entry points | 7 | **0** |

Verified: `src` imports resolve statically (no relative or `src.*` target missing); the
restored embedding round-trips through `DetectedFace.to_dict/from_dict`; mvp 100 passed,
worker 6/6, both web checks, root 3 passed, gate exit 0. The 31 remaining mypy errors under
`src/` are the tracked debt of `face_detector/face_matcher/detection/hardware_acceleration`.

**A(3) completed 2026-10-22 — full drop.** The 7-module closure went with its consumers:
`src/` is deleted, along with the HF-upload scripts, `fix_embeddings`/`init_database`,
`setup_hardware_acceleration`, the Chroma benchmarks and debug probes, `compare_recognition.py`
and `inspect_npy.py`. The root project is now `package = false` with only the dependencies the
retained `scripts/hf` and embedding checks use. `tracker_id` is also gone from the contract:
the pipeline still tracks faces for the annotated video, but the field is not stored, served or
published, and `validate_payload` rejects it.

---

## Workstream B — one metadata contract

**Finding.** Three generations ship, and the publisher silently normalises them:

| Gen | Shape | Reels | Gaps |
| --- | --- | --- | --- |
| A legacy | `frame_results[].faces[]`, **pixel** bbox, `detection_confidence`/`recognition_confidence` | 1–3 | no `detections`, no counts, no ids/tracker, no `recognition_config`, no `video_info.duration` |
| B current | `frame_data[].detections[]` | 4 | complete; publisher drops `timeline_markers`/`thumbnails` |
| C recognitions | `recognitions[]`, `face_location` in **`[top,right,bottom,left]`** px | 5 | unmatched faces unrecoverable; `det_score` synthesised as `0.0`; `recognition_config` wrong shape |

Consumers read fields the payload may not carry: `contestant_timeline[].contestant_info.id`,
`processing_summary.recognition_rate`, `video_info.duration`. `tracker_id` is carried and
never rendered.

**Cutoff disagreement.** `bands.ts:20` (0.585/0.451), `processing_config.yaml:37,42-43`
(0.45), and reel 4's metadata all agree — but **reel 5 publishes
`recognition_config = {tolerance: 0.68, min_confidence: 0.5}`**, the stale shape, and all of
reel 5's stored confidences (0.150–0.466) fall *below* its own declared `min_confidence`. Also
`bands.ts:11` documents 0.45 while the constant is 0.451, so [0.450, 0.451) is accepted but
banded **low**.

**Steps.** (1) Declare the contract once — a JSON Schema or a single TypedDict pair — and
validate in `build_read_model.py`, failing the publish on a mismatch instead of copying
`recognition_config` verbatim (`:294`). (2) Backfill the three missing fields; drop or render
`tracker_id`. (3) Reconcile 0.45 vs 0.451 in one place. (4) Regenerate reels 1–3 with the
current pipeline (see Workstream F), which retires generation A entirely.

**Gate.** A contract test asserts each published `metadata_dense_*` validates; publishing a
reel with a stale `recognition_config` fails loudly.
**Risk.** Low for validation, medium for the reprocess.

**Executed 2026-10-22 — B(2) backfill.** The publisher derived the three fields the apps
read unconditionally (`apps/shared/types`): `video_info.duration` (from `fps` ×
`frame_count` — no generation stored it), `processing_summary.recognition_rate`, and
`contestant_timeline[].contestant_info.id`; `validate_payload` now fails a publish that
omits them. Contract tests (`tests/contract/test_publish_contract.py`) run the real
normaliser over every reel on disk and over a synthetic stale-config doc. Evidence:
dry run stages all 5 reels, each validating; `uvx ruff@0.7.3` clean on `scripts/publish`;
pinned mypy clean; 3/3 new contract tests pass. Reel 5's stale `recognition_config`
continues to be normalised (not failed) per the documented `normalise()` behaviour.

**Executed 2026-10-22 — B(4)/F(4) reprocess + generation-A retirement.** Reels 1–3 were
reprocessed locally with `mvp-processor/src/process_video.py --local-only` (24, 24 and 27
minutes wall clock; detection then 1080p + 720p encodes). Matched detections per reel:
**626 / 776 / 1659**, against **23 / 17 / 58** in the legacy files (reels 4–5 were already
1131 / 1448). The ten generation-A files (17 MB, `metadata/[1-5]-*`) and `convert_legacy()`
are deleted; `normalise()` refuses `frame_results` with a message pointing at the pipeline, and
`pick_sources()` scans only `local_output/metadata`. Roster quality moved from
36 good / 58 weak / 2 missing to **68 / 26 / 2**; 67 (Sarah) and 77 (TABI) are still the two
with no references. Every reprocessed file validates with zero contract problems, and the
publish dry run stages all five reels.

---

## Workstream C — embeddings keyed by 編號

**Finding.** 94 embeddings, 96 contestants, **36 have no `{暱稱}_embedding.npy`**: 11 exist only
as `contestant_<編號>_embedding.npy` (2, 17, 18, 19, 21, 22, 23, 31, 33, 36, 40) and **25 have
neither** (4, 5, 8, 16, 50, 53, 55, 56, 59, 61, 62, 63, 65, 68, 69, 70, 71, 78, 79, 80, 82,
83, 85, 89, 92). `3 妹` and `3\xa0妹` are one person under two filenames.

Worse, `worker/src/index.ts:281-283` hardcodes `has_embedding: true, reference_count: 0` for
all 96 — so the API claims embeddings that do not exist for 25 contestants.

**Steps.** (1) Re-key by 編號 in `src/database/chroma_setup.py:72,79`,
`src/ui/database_status.py:55`, `inspect_npy.py:14,21`. (2) Write real `has_embedding` /
`reference_count` in the publish path. (3) Reconcile the `3 妹` duplicate.

**Gate.** Every contestant's `has_embedding` matches a file on disk; the cast sheet's quality
stamp stops lying.
**Risk.** Low, mechanical.

**Executed 2026-10-22 — C(1) + C(2) + C(3).** One resolver, `src/database/roster.py`, maps
embedding filenames to 編號 (nickname, 姓名, `contestant_<編號>`; whitespace normalised so the
`3 妹` / `3\xa0妹` pair is one person). `chroma_setup` keys its collection by id and keeps the
first file per contestant, logging the rest; `src/ui/database_status.py` labels by id; the
`inspect_npy.py` probe prints the mapping and the duplicate list. Two latent bugs surfaced
and were fixed: the loader read `paths.contestant_photos` while `config.json` says
`contestants_dir` (so it silently found zero files), and it globbed only the top level while
the files live under `embeddings/contestants/`.

Measured: 94 `.npy` files resolve to **71 contestants** (33 are `contestant_<編號>`
duplicates of a nickname file; 編號 96 had two spellings). The *live* store is
`reference_embeddings.npz` — 663 rows, 94 contestants, summing exactly to the manifest — so
`has_embedding`/`reference_count` from `scripts/publish` describe the real cache, and
contestants **67 (Sarah) and 77 (TABI)** are the only two with none. The worker's hardcoded
`has_embedding: true` block is the development fallback only; KV ships `contestants_structured`.

Verified: the real loader (chromadb stubbed) returns 71 numeric keys, all `(512,)`; every key
is a 編號 present in the cast sheet; mypy 202 → 196 (also gained a `streamlit.*` stub override
for the legacy UI).

---

## Workstream D — frontend consolidation

**Finding.** The redesign is complete but the shared vocabulary is only half adopted:

| Issue | Evidence |
| --- | --- |
| mm:ss formatter duplicated **5×** | `Ingestion:25`, `Dashboard:73`, `Processing:43`, `Player:27`, `PlayerControls:22` |
| Local band map diverges from `BAND_STAMP` | `Labelling.tsx:90-96` (`BAND_PILL`, medium and low share a colour) |
| Masthead chrome **7 files / 176 lines** | Home, Cast, Analytics, PlayerPage, Dashboard, Contestants, Flagging — only the right slot varies |
| Palette tokens duplicated per app | both `app.css:4-16` |
| Band→colour outside `BAND_STAMP` | `EmbeddingWorkbench:15-18` (#22c55e/#f59e0b/#ef4444), `ContestantTimeline:33-38,158` (#FF8400) — pre-redesign leaks |
| Unported pages | `Processing`, `EmbeddingWorkbench`, `Labelling` never got the masthead |
| Dead page | `Ingestion.tsx` (406 lines), not routed |
| Old-world Player components | **1,419 lines to port** (`Player` 907, `ContestantTimeline` 168, `FlagDialog` 146, `PlayerControls` 134, `DetectionBar` 64); keep `FaceOverlay`+`useAnnotations` (239) |

**Steps.** (1) Delete `Ingestion.tsx`; merge `BAND_PILL` into `BAND_STAMP`; route the 5 local
formatters through `formatMmSs`. (2) Extract `<Masthead>`. (3) Port the remaining Player
components. (4) Fix the worker's CORS methods (see E).

**Gate.** `grep -c "format.*MmSs\|BAND_STAMP"` shows no local duplicates; every page renders
the shared masthead.
**Risk.** Low.

**Executed 2026-10-22 — D(1)–(3).** One `formatMmSs` (`apps/shared/lib/format.ts`) and one
`BAND_STAMP` (`apps/shared/lib/bands.ts`) — the five local formatters and the local band map
are gone (`9a1ff14a`). `<Masthead>` is extracted and used by all seven routed pages
(`708da1bb`), verified in the browser smoke: viewer 圖庫/點唱單/名冊/紀錄 and admin
儀表/待核/標註/參賽者/播放/紀錄/處理/向量 all render the shared chrome with no console errors.
The Player components live in `apps/shared/components/Player/` (`Player`, `ContestantTimeline`,
`FlagDialog`, `PlayerControls`, `DetectionBar`, plus `VideoCanvas`, `FaceOverlay`,
`useAnnotations`, `pickInitialVideo`), with `apps/admin/src/pages/Player.tsx` now a five-line
re-export and `PlayerPage` consuming the shared component.
**Ingestion deleted 2026-10-22:** `apps/admin/src/pages/Ingestion.tsx` (404 lines, unrouted)
is gone with the Modal ingestion path; the orphaned route comment went too.

---

## Workstream E — the worker is not quite read-only

**Finding.** `worker/src/index.ts:108` advertises `Access-Control-Allow-Methods: 'GET, POST,
PUT, DELETE, OPTIONS'` on a worker whose own prose says read-only. No write handler exists, so
this is a lie in a header rather than a hole — but it is a one-line fix worth making today.
Separately, non-GET on `/faces/detect` falls through to 404 rather than 405.

**Steps.** `'GET, OPTIONS'`; return 405 for a known path with the wrong method.

**Gate.** The read-only test asserts the advertised methods too.
**Risk.** None.

**Executed 2026-10-22.** The header is `GET, OPTIONS` (`47a0f1f7`) and the read-only test
asserts it. Step 2 was deliberately answered the other way: unknown methods and paths return
**404, not 405**, because ADR 0003 removed the write routes and a 405 would advertise that they
exist (`worker/src/index.ts:549`, with the reasoning inline).

---

## Workstream F — make the tests meaningful (the real quality ratchet)

**Finding.** 829 mypy errors in 108 files, and neither suite has been green. But the debt is not
where it looks: **~480 of 829 errors (58 %) are in test files**, not product code.

| Class | Count | Where |
| --- | --- | --- |
| `no-untyped-def` | 366 (44 %) | whole test files — `test_output_modes.py` 31, `test_processing_api.py` 28 |
| `call-arg` | 114 (14 %) | stale test call sites: constructors that no longer take those kwargs |
| `attr-defined` | 55 | `face_matcher.py` (both copies), `routes/health.py`, `routes/videos.py` |
| `index` / `import-not-found` | 82 | `src/secure_logging.py`, `modal_batch_processor.py` (`Any` never imported) |
| `import-untyped` | 31 | benchmark/debug scripts |

Top 7 files hold 180 errors (22 %), and `backend/` + `src/core/` hold most of the product-code
share — both trees Workstream A deletes.

**Why the tests fail** (classified with `--tb=line`):

| Count | Cause |
| --- | --- |
| 32 × TypeError | stale API surface — `VideoProcessor.__init__(detector=…)`, `FaceDetector(device=…)` |
| 30 × AttributeError | stale API — `FaceMatcher.add_contestant`, `ProcessingResult.success`, patch targets that moved |
| 18 × UnboundLocalError + 17 failures | **one line**: `tests/contract/test_cli_interface.py:40` imports `shutil` *inside* a method, so teardown's use raises. 35 outcomes from a single misplaced import |
| 23 failed + 27 assertions | genuine outdated expectations |

`mvp-processor`'s 26 failures are **pure import path problems**, not logic: 15 ×
`No module named 'roi'` (`src/roi_cache.py:4` and `src/person_segmenter.py:7` use flat
`from roi import …` while the project sets `pythonpath = ["."]`, so it must be `from src.roi`),
and 8 × `cannot import name 'FaceParsingConfig' from 'config'` (it lives in `src/config.py:56`).
About 24 tests come back with a two-line change and zero behavioural risk.

**Steps, cheapest first.**
1. **One-liners that pay for themselves**: move `shutil` to module scope in
   `test_cli_interface.py` (35 outcomes); fix the `src.roi` / `src.config` imports in
   mvp-processor (~24 tests). Neither touches product code.
2. **Quarantine**: mypy `ignore_errors` overrides for `tests/**`, `scripts/debug/**`,
   `scripts/benchmarks/**`, `modal_*.py`, `backend/main.simple.py` — removes ~480 of 829 and
   makes the number mean something. (The test *annotation* override is already in place; this is
   the rest of the test debt.)
3. **Ratchet**: pin the remaining count as a baseline; a CI step fails when it rises. Enable
   `disallow_untyped_defs` per package, starting with the already-clean ones
   (`scripts/hf/`, `scripts/publish/`), and add `backend/app/` + `src/core/` only if Workstream A
   keeps them.
4. **Reprocess** reels 1–3 with the current pipeline: inputs verified present, ~20–40 min per
   reel because `convert_video_format` re-encodes 4K to 1080p *and* 720p (emptying
   `video.output_formats` skips that — metadata does not depend on it). This retires metadata
   generation A and the reel-5 cutoff contradiction at once.
5. **Re-enable CI** (`.github/workflows/test.yml` is `disabled_manually` since 2025-09-02 and is
   stale if re-enabled: it references the deleted `mvp-processor/package-lock.json` and
   `worker/index.js`, and its `frontend-tests` job targets the removed SvelteKit app).

**Gate.** CI on a clean tree reports the *number of new* failures, and that number is 0.
**Risk.** The reprocess is the only expensive step; everything above it is hours, not days.

**Executed 2026-10-22 — F(1), F(2), F(3), F(5).** F(1) landed first (`shutil` at module scope,
`src.roi` / `src.config` imports fixed: the mvp suite went from 26 failures to 100 passing).
F(5) was already re-enabled as `.github/workflows/test.yml`, now gating web typecheck, worker
tests, the mvp suite and the Python baselines.

F(2) + F(3): `[tool.mypy.overrides]` quarantines `tests/**`, `scripts/debug/**`,
`scripts/benchmarks/**` and the conftest moto/yaml shims via `ignore_errors` (both module-name
forms listed, since `tests/` has no `__init__.py`). Repo-wide `uvx mypy@1.16.1 .`:
**514 → 259 errors / 60 files**, and the remaining count is gated in
`scripts/ci/check_baselines.py` against `mypy_repo_wide`, measured with the same pinned
isolated invocation CI runs, so it no longer depends on which packages are installed.
`disallow_untyped_defs` remains on globally; the quarantined modules are the only relaxation.
Gate output at the time: mypy ratchet clean, ruff 66/66, pytest 140F/17E/123P → exit 0.
(The ratchets have since been lowered to ruff 27 / mypy 196 / root 0F·0E·3P by A and C.)

**F(4) executed 2026-10-22.** Reels 1–3 were reprocessed and generation A was deleted; the
numbers are recorded under Workstream B's B(4) note. Nothing in Workstream F remains open.

---

## Sequencing

**Do these first — measured pay-off, no interface risk** (hours, not days):

| Fix | Clears |
| --- | --- |
| Move `shutil` to module scope in `tests/contract/test_cli_interface.py:40` | 35 pytest outcomes |
| `from roi` → `from src.roi`, `from config` → `from src.config` in `mvp-processor/src` | ~24 pytest tests |
| Worker CORS `'GET, OPTIONS'` + 405 for wrong method | the read-only lie |

Then the workstreams:

1. **E + C + D(1)** — CORS, embedding keys, formatter/band/masthead consolidation. No
   interfaces change; ship in a day.
2. **B** — contract schema + validation + backfill. Depends on nothing, unblocks F.
3. **F(2–3)** — quarantine the test debt, pin the baseline, re-enable CI so regressions are
   visible again.
4. **A** — delete `backend/`, the shims and the dead scripts; move `src/` under
   `mvp-processor/`. Largest blast radius, so last among the deletions — and it removes the
   bulk of the remaining mypy errors rather than fixing them.
5. **D(3) + F(4)** — port the 1,419 lines of Player components and reprocess reels 1–3.
6. **A(4)** — retire metadata generation A once reels 1–3 are regenerated.

## Open product decisions (not engineering calls)

- ~~`scripts/modal_youtube_processor.py`~~: **retired 2026-10-22** with the rest of the Modal surface.
- ~~`apps/admin/src/pages/Ingestion.tsx`~~: **deleted 2026-10-22** (unrouted, and its backend never existed).
- ~~`backend/`~~: deleted (`58507562`); nothing called it.

## What must not break

- The viewer stays **provably read-only**; the admin is still the only writer.
- `CONTEXT.md`'s glossary: match score is a raw cosine, never a percentage; bboxes are frame
  fractions in `[x1,y1,x2,y2]`; a flag carries no score of its own.
- The published KV values stay compatible with `apps/shared/types` at every step — the viewer
  reads them directly.
