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
  3. **The repo-wide mypy total may not rise.** Measured with the pinned, isolated
     `uvx mypy` (no project install), which is exactly what CI runs — so the number is
     environment-independent. Tests, debug/benchmark scripts and conftest shims are
     quarantined in `[tool.mypy.overrides]` (refactor plan F(2)); the count is product
     code plus the still-untouched legacy scripts.

Run from the repo root. Exit 1 on any regression.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


PYTEST_TERMS = ("failed", "passed", "skipped", "error")


def count_pytest_log(path: Path) -> dict[str, int] | None:
    """Read pytest -q's summary line. None when the run produced no summary.

    A crashed or killed run prints no "in <time>" line; treating that as "0 failed"
    would turn a broken gate into a green one, so the caller must fail on None.
    """
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    except OSError:
        return None
    for line in reversed(lines[-5:]):  # the summary is within the last few lines
        if " in " not in line or "=" in line:
            continue
        counts = {term: 0 for term in PYTEST_TERMS}
        for number, term in re.findall(r"(\d+) (" + "|".join(PYTEST_TERMS) + r")s?", line):
            counts[term] = int(number)
        if any(counts.values()) or "passed" in line:
            return counts
    return None


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


def baseline_int(baseline: dict[str, object], key: str) -> int:
    """Read an integer baseline, refusing a malformed config instead of guessing."""
    value = baseline.get(key)
    if not isinstance(value, int):
        sys.exit(f"baseline {key!r} must be an integer, got {value!r}")
    return value


def check_pytest_log(baseline: dict[str, object], log_path: Path) -> bool:
    counts = count_pytest_log(log_path)
    if counts is None:
        print(f"pytest log {log_path}: no summary line — the run crashed or was killed")
        return False
    failed_limit = baseline_int(baseline, "pytest_root_failed")
    errors_limit = baseline_int(baseline, "pytest_root_errors")
    passed_min = baseline_int(baseline, "pytest_root_passed_min")
    ok = True
    print(
        f"pytest root: {counts['failed']} failed (baseline {failed_limit}), "
        f"{counts['error']} errors (baseline {errors_limit}), "
        f"{counts['passed']} passed (minimum {passed_min})"
    )
    if counts["failed"] > failed_limit:
        print("  more failures than the recorded baseline — this change makes it worse")
        ok = False
    if counts["error"] > errors_limit:
        print("  more errors than the recorded baseline — this change makes it worse")
        ok = False
    if counts["passed"] < passed_min:
        print("  fewer tests passed than the minimum — tests may have vanished")
        ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument(
        "--pytest-log",
        type=Path,
        help="path to a `pytest -q` log to gate against the recorded counts",
    )
    args = ap.parse_args()

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

    if args.pytest_log is not None and not check_pytest_log(baseline, args.pytest_log):
        failed = True

    # Gated with the pinned isolated invocation (see the module docstring), so it is
    # the same number in CI and on a developer machine.
    repo_wide = count_mypy((".",))
    repo_limit = baseline_int(baseline, "mypy_repo_wide")
    if repo_wide < 0:
        print("mypy failed to run repo-wide")
        failed = True
    elif repo_wide > repo_limit:
        print(f"mypy repo-wide: {repo_wide} > baseline {repo_limit} — this change adds debt")
        failed = True
    else:
        print(f"mypy repo-wide: {repo_wide} (baseline {repo_limit})")

    if failed:
        print(
            "\nLower the baseline in scripts/ci/baseline.json only when an improvement "
            "is intentional, so the number keeps ratcheting down."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
