#!/usr/bin/env python3
"""Fail CI when a quality signal regresses past its recorded baseline.

The repo carries 800+ mypy errors and two red pytest suites, and neither has been
green in living memory. Blocking CI on "clean" would leave CI permanently red and
unread. This gate does the honest version: pin what is true today and fail the moment
it gets worse.

Two signals are gated, both environment-independent:

  1. **New tooling must stay clean.** `scripts/hf/` and `scripts/publish/` typecheck
     with no project install (their heavy imports are in ignore_missing_imports), so
     this is exact anywhere. It is the ratchet: new code may not add debt.
  2. **Ruff total may not rise.** Ruff needs no imports to run, so the count is the
     same locally and in CI.

A repo-wide mypy count is *reported* but not gated: without the 39 project
dependencies installed, mypy cannot resolve imports that the project venv does, so
the number differs by environment (824 with deps, 971 without). Gating on it would
gate on which packages happen to be present.

Run from the repo root. Exit 1 on any regression.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "scripts/ci/baseline.json"
MYPY_PIN = "mypy@1.16.1"
RUFF_PIN = "ruff@0.7.3"
RATCHET_PATHS = ("scripts/hf", "scripts/publish")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


def count_mypy(paths: tuple[str, ...]) -> int:
    proc = run(["uvx", MYPY_PIN, *paths])
    for line in reversed(proc.stdout.splitlines()):
        if "Found " in line and " error" in line:
            return int(line.split("Found ")[1].split(" ")[0])
        if line.startswith("Success:"):
            return 0
    print(proc.stdout[-800:], file=sys.stderr)
    print(proc.stderr[-800:], file=sys.stderr)
    return -1


def count_ruff() -> int:
    proc = run(["uvx", RUFF_PIN, "check", "--output-format=json"])
    try:
        return len(json.loads(proc.stdout or "[]"))
    except json.JSONDecodeError:
        print(proc.stdout[-800:], file=sys.stderr)
        return -1


def main() -> int:
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {BASELINE}: {exc}", file=sys.stderr)
        return 1

    failed = False

    ratchet = count_mypy(RATCHET_PATHS)
    if ratchet < 0:
        print("mypy failed to run on the gated paths")
        failed = True
    elif ratchet > 0:
        print(f"mypy {RATCHET_PATHS}: {ratchet} errors — new tooling must stay clean")
        failed = True
    else:
        print(f"mypy {RATCHET_PATHS}: clean")

    ruff = count_ruff()
    limit = int(baseline["ruff_errors"])
    if ruff < 0:
        print("ruff failed to run")
        failed = True
    elif ruff > limit:
        print(f"ruff: {ruff} > baseline {limit} — this change makes it worse")
        failed = True
    else:
        print(f"ruff: {ruff} (baseline {limit})")

    # Reported, never gated: see the module docstring.
    repo_wide = count_mypy((".",))
    print(
        f"mypy repo-wide: {repo_wide} (informational; needs project deps to be exact)"
    )

    if failed:
        print(
            "\nLower the baseline in scripts/ci/baseline.json only when an improvement "
            "is intentional, so the number keeps ratcheting down."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
