# How to Start the MV Face Recognition App

> **Retired surface (2026-10-22).** The FastAPI `backend/` tree, its `Dockerfile` and the
> Heroku `Procfile` were deleted. Nothing imported the backend, nothing deployed it
> (`fly.toml` builds from buildpacks, and the `Procfile` pointed at a deleted `app.py`),
> and it held 30 files of a second implementation of the same pipeline. The Cloudflare
> Worker (`worker/`) plus `apps/viewer` and `apps/admin` are the product; the local API
> lives in `mvp-processor/src/local_api.py`. See `docs/refactor-plan.md`.

## Quick summary

```bash
# Terminal 1 — local API (real data from local_output/metadata)
cd mvp-processor && uv run python -m uvicorn src.local_api:app --port 8000

# Terminal 2 — viewer  (read-only public UI, http://localhost:5180)
pnpm --filter @mv/viewer dev

# Terminal 3 — admin   (back office, writes locally; http://localhost:5173)
pnpm --filter @mv/admin dev
```

Both Vite apps proxy `/api` to `localhost:8000` (`apps/*/vite.config.ts`). Video ids are
accepted as the bare numeric 編號 (`/player?video=4`) or the verbatim stem
(`4-《全民造星IV》極限拍MV`) — `local_api._metadata_path` resolves both.

## What each process serves

| Process | Port | Notes |
| --- | --- | --- |
| `local_api` (uvicorn) | 8000 | dense metadata, faces at a timestamp, ground-truth labels, flag tray, processing trigger |
| `@mv/viewer` (Vite) | 5180 | read-only public surface: 圖庫, 點唱單, 名冊, 紀錄 |
| `@mv/admin` (Vite) | 5173 | 可寫 back office: 儀表, 待核, 標註, 參賽者, 處理, 向量 |

Writes only ever happen through the admin app against this local API; the viewer stays
provably read-only.

## Publishing to the Cloudflare Worker

The Worker serves the *published* read model from KV, not your local files. Rebuild and
stage it any time the metadata or roster changes:

```bash
uv run --no-project python scripts/publish/build_read_model.py          # dry run, stages to ~/.cache/mv-read-model
uv run --no-project python scripts/publish/build_read_model.py --publish # picks up wrangler auth and writes KV
```

`--dry-run` is the default; the run validates every reel against the metadata contract
(`tests/contract/test_publish_contract.py`) and fails loudly on a mismatch.

## Tests and gates

```bash
cd mvp-processor && uv run python -m pytest tests/unit tests/contract -q   # the green suite, no weights needed
uv run --no-project python scripts/ci/check_baselines.py                   # ruff/mypy/pytest-count ratchets
```
