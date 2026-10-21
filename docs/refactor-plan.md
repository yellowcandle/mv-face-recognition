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
  clears it. Anyone deleting a tree should do that first, and CI starts cold so it is
  unaffected.

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

---

## Workstream E — the worker is not quite read-only

**Finding.** `worker/src/index.ts:108` advertises `Access-Control-Allow-Methods: 'GET, POST,
PUT, DELETE, OPTIONS'` on a worker whose own prose says read-only. No write handler exists, so
this is a lie in a header rather than a hole — but it is a one-line fix worth making today.
Separately, non-GET on `/faces/detect` falls through to 404 rather than 405.

**Steps.** `'GET, OPTIONS'`; return 405 for a known path with the wrong method.

**Gate.** The read-only test asserts the advertised methods too.
**Risk.** None.

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

- `scripts/modal_youtube_processor.py`: TODO.md asks *"restore or consciously retire"*. It has
  10 mypy errors and belongs to the disabled ingestion feature; nothing imports it.
- `apps/admin/src/pages/Ingestion.tsx` (406 lines): unrouted because its backend does not exist.
  Keep as the placeholder for the feature, or delete with the Modal script.
- `backend/`: deleting it removes the only FastAPI surface — confirm nothing external calls it
  before Workstream A.

## What must not break

- The viewer stays **provably read-only**; the admin is still the only writer.
- `CONTEXT.md`'s glossary: match score is a raw cosine, never a percentage; bboxes are frame
  fractions in `[x1,y1,x2,y2]`; a flag carries no score of its own.
- The published KV values stay compatible with `apps/shared/types` at every step — the viewer
  reads them directly.
