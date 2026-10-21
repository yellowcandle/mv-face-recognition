# MV Face Recognition

Frame-accurate face recognition for 全民造星 IV: a read-only public viewer, a writable
back office, a Cloudflare Worker that serves the published read model, and a Python
pipeline that turns reels into per-detection metadata.

## What runs where

| Surface | Where | Port / host | Notes |
| --- | --- | --- | --- |
| Viewer (read-only) | `apps/viewer` | `localhost:5180` | 圖庫, 點唱單, 名冊, 紀錄 |
| Admin (writable) | `apps/admin` | `localhost:5173` | 儀表, 待核, 標註, 參賽者, 播放, 處理, 向量 |
| Local API | `mvp-processor/src/local_api.py` | `localhost:8000` | dense metadata, faces at a timestamp, labels, flag tray |
| Worker | `worker/` | Cloudflare | serves KV; advertises `GET, OPTIONS` only ([ADR 0003](docs/adr/0003-the-deployed-worker-is-read-only.md)) |
| Pipeline | `mvp-processor/src/process_video.py` | local | 6 fps sampling, InsightFace `buffalo_l`, per-detection metadata |
| Publisher | `scripts/publish/build_read_model.py` | local | normalises → validates → stages → KV |

## Quick start

```bash
# Terminal 1 — local API (real data from local_output/metadata)
cd mvp-processor && uv run python -m uvicorn src.local_api:app --port 8000

# Terminal 2 — viewer
pnpm --filter @mv/viewer dev

# Terminal 3 — admin
pnpm --filter @mv/admin dev
```

The Vite apps proxy `/api` to `localhost:8000`. Video ids are accepted as the numeric
編號 (`/player?video=4`) or the verbatim stem. Full detail: [START_APP.md](START_APP.md).

Toolchain: Node **≥22.22**, pnpm **12.14** (pinned in `package.json`), and **Vite+** —
`vp dev`, `vp build`, `vp check` (Oxfmt + Oxlint + type-aware checks) and `vp test`
(Vitest). The apps' `dev`/`build`/`preview` scripts run through `vp`.

## The data path

```
source/videos/*.mp4
  └─ process_video.py            → local_output/metadata/{reel}_metadata.json
        frame_data[].detections[]  (frame-fraction bboxes, raw cosine match scores)
  └─ build_read_model.py         → ~/.cache/mv-read-model/  (staged)
        normalise → backfill → validate → wrangler kv key put
  └─ Worker                      → apps/viewer, apps/admin
```

One metadata generation exists: generation A (`frame_results[].faces[]`, pixel boxes)
was retired on 2026-10-22 after reels 1–3 were reprocessed. The publisher refuses that
shape rather than converting it.

## Non-negotiable domain rules

See [CONTEXT.md](CONTEXT.md) and [DESIGN.md](DESIGN.md). In short:

- **Match score** is a raw cosine, never a percentage or rescaled value.
- **Bboxes** are frame fractions `[x1,y1,x2,y2]` in `0..1`, canonical order; they are
  multiplied by the rendered element's size and nothing else
  ([ADR 0002](docs/adr/0002-face-boxes-are-frame-fractions.md)).
- **The deployed Worker is read-only** ([ADR 0003](docs/adr/0003-the-deployed-worker-is-read-only.md));
  writes happen only through the local admin API.
- **Embeddings are keyed by 編號** ([ADR 0001](docs/adr/0001-reference-embeddings-are-a-derived-cache.md)).
  The record is `source/photo/contestants/reference_manifest.json`; the `.npy` files are
  a legacy artifact and nothing in the live pipeline reads them.
- **Bands are provisional**: high ≥ 0.585, medium ≥ 0.451, acceptance ≥ 0.45, measured
  from the 663-reference cache.

## Repository layout

```
apps/viewer, apps/admin      React + Vite; shared components in apps/shared
  apps/shared/components/Player   the single Player implementation
worker/                      Cloudflare Worker (TypeScript, KV + R2)
mvp-processor/               the live pipeline, local API and its pytest suite
scripts/publish/             read-model normaliser, validation, KV publish
scripts/hf/                  Hugging Face dataset/embedding upload helpers
scripts/ci/check_baselines.py  the quality ratchet (ruff, mypy, pytest counts)
docs/                        refactor plan, ADRs, pipeline and deployment notes
```

There is no `src/` package: the legacy CLI, Streamlit UI, Chroma helpers and the scripts that
used them are deleted. Retained utility scripts live under `scripts/` (portraits, Hugging Face
staging, embedding checks). The retired surfaces are recorded in
[docs/refactor-plan.md](docs/refactor-plan.md).

## Tests and gates

```bash
# the live pipeline (no model weights, no network)
cd mvp-processor && uv run python -m pytest tests/unit tests/contract -q

# the publisher contract, over every reel on disk
uv run --no-project --with pytest --with numpy --with opencv-python-headless --with pandas \
  python -m pytest tests/ -q

# web: formatting, type-aware lint, type check and Vitest
pnpm exec vp check
pnpm exec vp test

# worker
cd worker && npx tsc --noEmit && npm test

# every count is a ratchet: ruff, mypy, root pytest
uv run --no-project python scripts/ci/check_baselines.py
```

CI (`.github/workflows/test.yml`) runs all of the above. See [tests/README.md](tests/README.md).

## Publishing

```bash
# dry run — stages to ~/.cache/mv-read-model and validates every reel
uv run --no-project python scripts/publish/build_read_model.py

# write KV (needs wrangler auth)
uv run --no-project python scripts/publish/build_read_model.py --publish
```

## More documentation

- [START_APP.md](START_APP.md) — how to run each surface
- [DEPLOYMENT.md](DEPLOYMENT.md) — deploy the Worker and the apps
- [docs/refactor-plan.md](docs/refactor-plan.md) — the whole-codebase plan and what executed
- [docs/adr/](docs/adr) — the three decisions above

There is no LICENSE file in this repository; add one before distributing.
