"""Materialise the LFS-tracked source/photo set as plain files (no LFS dependency).

The set lives on 138 old refs (386 blobs, 112.8 MB) and is only fully reachable while those
branches exist. This copies the real bytes out of the LFS object cache into
`source/photo/historical/`, verifying every file against its sha256, so the photos survive a
branch cleanup or history rewrite.

Discovery uses `git lfs ls-files --all --long` (one call) rather than walking every ref with
ls-tree + cat-file (which would be tens of thousands of processes). Read-only with respect to
git: nothing is checked out, no branch is touched.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from typing import TypedDict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "source/photo/historical")
LFS = os.path.join(REPO, ".git/lfs/objects")
PREFIX = "source/photo"


class Copied(TypedDict):
    path: str
    oid: str
    bytes: int


def discover() -> dict[str, str]:
    """path -> lfs oid for every LFS-tracked file under source/photo, from the all-refs index."""
    proc = subprocess.run(
        ["git", "lfs", "ls-files", "--all", "--long"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if proc.returncode != 0:
        sys.exit(f"git lfs ls-files failed: {proc.stderr[:200]}")
    chosen: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        match = re.match(r"^([0-9a-f]{64}) [*-] (.+)$", line)
        if not match:
            continue
        oid, path = match.group(1), match.group(2).lstrip("./")
        if path.startswith(PREFIX) and path not in chosen:
            chosen[path] = oid
    return chosen


def main() -> int:
    chosen = discover()
    if not chosen:
        sys.exit("no LFS-tracked files found under source/photo")

    manifest: list[Copied] = []
    failed: list[str] = []
    for path, oid in sorted(chosen.items()):
        src = os.path.join(LFS, oid[:2], oid[2:4], oid)
        if not os.path.isfile(src):
            failed.append(f"{path} (missing object {oid[:10]})")
            continue
        try:
            with open(src, "rb") as src_f:
                data = src_f.read()
        except OSError as exc:
            failed.append(f"{path} (unreadable: {exc})")
            continue
        if hashlib.sha256(data).hexdigest() != oid:
            failed.append(f"{path} (hash mismatch)")
            continue
        rel = os.path.relpath(path, PREFIX)
        dest = os.path.join(OUT, rel)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as dest_f:
                dest_f.write(data)
        except OSError as exc:
            failed.append(f"{path} (cannot write: {exc})")
            continue
        manifest.append(Copied(path=path, oid=oid, bytes=len(data)))

    try:
        os.makedirs(OUT, exist_ok=True)
        with open(
            os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8"
        ) as manifest_f:
            json.dump(manifest, manifest_f, ensure_ascii=False, indent=2)
    except OSError as exc:
        sys.exit(f"cannot write manifest: {exc}")

    total = sum(m["bytes"] for m in manifest)
    print(
        f"copied {len(manifest)} files, {total / 1e6:.1f} MB -> {os.path.relpath(OUT, REPO)}"
    )
    if failed:
        print(f"FAILED {len(failed)}:")
        for label in failed[:10]:
            print("  ", label)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
