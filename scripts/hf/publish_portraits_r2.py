"""Publish the gallery portraits to Cloudflare R2.

The cast sheet in the public viewer loads `/api/contestants/{id}/thumb/{size}`, which the
Worker serves from R2. This uploads the 512px face crops under `portraits/{id}.webp` and
writes `portraits/manifest.json` — the index the Worker reads to build `portrait_url`
responses and to answer the thumb route.

Reads the crops produced by `scripts/hf/make_portraits.py`; nothing is re-rendered here.

Integrity: every crop is hashed into the index first, then hashed again immediately before
its upload. A crop whose bytes changed in between (or whose size disagrees with the
make_portraits manifest) is never uploaded; it is logged and counted as a mismatch. The
index is published only when every upload succeeded, so it never names a missing object.

`--dry-run` does everything except the wrangler calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from typing import TypedDict

logger = logging.getLogger(__name__)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PORTRAITS = os.path.expanduser("~/.cache/mv-portraits")
BUCKET = "mv-face-recognition-videos"
PREFIX = "portraits"
CID_RE = re.compile(r"[0-9]+")  # ASCII only; str.isdigit() also accepts e.g. "²"


class Portrait(TypedDict):
    key: str
    bytes: int
    sha256: str
    source_file: str


def wrangler(*args: str) -> bool:
    try:
        proc = subprocess.run(
            ["npx", "wrangler", *args], cwd=REPO, capture_output=True, text=True
        )
    except OSError as exc:
        logger.error("cannot run wrangler %s: %s", " ".join(args), exc)
        return False
    if proc.returncode != 0:
        logger.error(
            "wrangler %s failed:\n%s\n%s",
            " ".join(args),
            proc.stdout[-600:],
            proc.stderr[-600:],
        )
        return False
    return True


def sha256(path: str) -> str | None:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        logger.error("cannot read %s: %s", path, exc)
        return None
    return digest.hexdigest()


def crop_path(cid: str) -> str | None:
    """The crop for one contestant, constrained to the portraits directory.

    The id comes from a JSON manifest, so it is untrusted input: it must be ASCII digits
    only, and the resolved path must still sit inside PORTRAITS. None (logged) otherwise.
    """
    if not CID_RE.fullmatch(cid):
        logger.error("refusing a non-numeric contestant id: %r", cid)
        return None
    root = os.path.realpath(PORTRAITS)
    path = os.path.realpath(os.path.join(root, f"{cid}.webp"))
    if os.path.commonpath([path, root]) != root:
        logger.error("refusing a path outside %s: %s", root, path)
        return None
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish the gallery portraits to Cloudflare R2."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="verify and index, upload nothing"
    )
    dry_run = parser.parse_args().dry_run

    manifest_path = os.path.join(PORTRAITS, "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        logger.error("cannot read %s: %s", manifest_path, exc)
        return 1
    if not isinstance(manifest, dict):
        logger.error("%s is not a JSON object", manifest_path)
        return 1

    # Pass 1: record what each crop is.
    pending: list[tuple[str, str]] = []
    index: dict[str, Portrait] = {}
    failed = mismatched = 0
    for cid, entry in sorted(
        manifest.items(),
        key=lambda kv: (len(kv[0]), kv[0]),  # numeric order for digit ids
    ):
        src = crop_path(cid)
        if src is None or not isinstance(entry, dict):
            if src is not None:
                logger.error("refusing manifest entry %s: not an object", cid)
            failed += 1
            continue
        if not os.path.isfile(src):
            logger.warning("skip %s: no crop at %s", cid, src)
            continue
        digest: str | None
        size: int
        try:
            digest = sha256(src)
            size = os.path.getsize(src)
        except OSError as exc:
            logger.error("cannot read %s: %s", src, exc)
            digest = None
            size = 0
        if digest is None:
            failed += 1
            continue
        if "size_bytes" in entry and entry["size_bytes"] != size:
            logger.error(
                "size mismatch for %s: manifest says %s, file is %d bytes; not uploading",
                src,
                entry["size_bytes"],
                size,
            )
            failed += 1
            mismatched += 1
            continue
        index[cid] = Portrait(
            key=f"{PREFIX}/{cid}.webp",
            bytes=size,
            sha256=digest,
            source_file=str(entry.get("source_file", "")),
        )
        pending.append((cid, src))

    # Pass 2: upload only bytes that still hash to what the index records.
    uploaded = 0
    for cid, src in pending:
        record = index.get(cid)
        if record is None:
            failed += 1
            continue
        # Copy the fields out before any `del index[cid]`: the deletion invalidates the
        # narrowing of `record`, and these are plain strings.
        key = record["key"]
        expected = record["sha256"]
        current = sha256(src)
        if current is None:
            failed += 1
            continue
        if current != expected:
            logger.error(
                "sha256 mismatch for %s: recorded %s, now %s; not uploading",
                src,
                expected,
                current,
            )
            del index[cid]
            failed += 1
            mismatched += 1
            continue
        if dry_run:
            print(f"  would put {BUCKET}/{key} ({current[:12]})")
        elif not wrangler(
            "r2", "object", "put", f"{BUCKET}/{key}", "--file", src, "--remote"
        ):
            del index[cid]
            failed += 1
            continue
        uploaded += 1

    index_path = os.path.join(
        PORTRAITS, "r2-index.dry-run.json" if dry_run else "r2-index.json"
    )
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error("cannot write %s: %s", index_path, exc)
        return 1

    total = sum(p["bytes"] for p in index.values())
    verb = "verified" if dry_run else "uploaded"
    print(f"{verb} {uploaded} portraits ({total / 1e6:.2f} MB) for {BUCKET}/{PREFIX}/")
    print(f"failed: {failed} (sha256/size mismatches: {mismatched})")
    if failed:
        logger.error(
            "not publishing %s/%s/manifest.json: %d failures", BUCKET, PREFIX, failed
        )
        return 1
    if dry_run:
        print(f"would put index: {BUCKET}/{PREFIX}/manifest.json")
        return 0
    if not wrangler(
        "r2",
        "object",
        "put",
        f"{BUCKET}/{PREFIX}/manifest.json",
        "--file",
        index_path,
        "--remote",
    ):
        return 1
    print(f"index: {BUCKET}/{PREFIX}/manifest.json")
    return 0


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
