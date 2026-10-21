# Test suites

Four gates run in CI (`.github/workflows/test.yml`); everything else on disk is not a gate.

| Suite | Command | What it proves |
| --- | --- | --- |
| `mvp-processor` | `cd mvp-processor && uv run python -m pytest tests/unit tests/contract -q` | the live pipeline's unit + contract behaviour (100 tests, no model weights needed) |
| Publisher contract | `uv run --no-project --with pytest --with numpy --with opencv-python-headless --with pandas python -m pytest tests/ -q` | every reel on disk normalises into the contract the apps read (`tests/contract/test_publish_contract.py`, 3 tests) |
| Worker | `cd worker && npm test` | API handlers + read-only guarantees (vitest) |
| Web | `pnpm --filter @mv/viewer check && pnpm --filter @mv/admin check` | `tsc --noEmit` for both apps |

The quality ratchets run alongside them:

```bash
uv run --no-project python scripts/ci/check_baselines.py --pytest-log <pytest -q log>
```

That script is the source of truth for what is gated: ruff total, the repo-wide mypy count
(measured with the pinned isolated `uvx mypy`, as CI does), the mypy ratchet on `scripts/hf`
and `scripts/publish` (always 0), and the root pytest counts in `scripts/ci/baseline.json`.
Lower the numbers when they improve; never raise one without recording why.

## History

The root `tests/` tree used to hold 29 modules written against the pre-refactor `src/` API.
They were 140 failures and 17 collection errors — stale constructors, moved patch targets, one
misplaced `shutil` import causing 35 outcomes — so they gated nothing. They were deleted on
2026-10-22 (see `docs/refactor-plan.md`, Workstream A). The live pipeline is covered by
`mvp-processor/tests`; the publisher by the contract test above.
