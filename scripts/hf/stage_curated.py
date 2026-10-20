"""Stage the curated reference photos (source/photo/contestants/photos) for the bucket.

These files were recovered from GitHub's LFS object storage after their pointers were lost:
the folder is gitignored, untracked, and no ref points at the blobs. Archiving them under
`photos/curated/` is what stops a repeat loss. Originals are hardlinked into the staging tree.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import sys
from typing import TypedDict

logger = logging.getLogger(__name__)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "source/photo/contestants/photos")
STAGE = os.path.expanduser("~/.cache/mv-hf-stage")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class Curated(TypedDict):
    key: str
    sha256: str
    bytes: int
    original_name: str


def under(root: str, *parts: str) -> str | None:
    """realpath of root/parts, or None (logged) if it resolves outside root."""
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, *parts))
    if os.path.commonpath([base, target]) != base:
        logger.warning("rejecting %s: resolves outside %s", target, base)
        return None
    return target


def inspect(path: str) -> tuple[bool, str, int] | None:
    """(is_lfs_pointer, sha256, bytes), or None (logged) when the file cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            head = f.read(40)
            if head.startswith(b"version https://git-lfs"):
                return True, "", 0
            digest.update(head)
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        size = os.path.getsize(path)
    except OSError as exc:
        logger.warning("skipping unreadable %s: %s", path, exc)
        return None
    return False, digest.hexdigest(), size


def stage(src: str, key: str) -> bool:
    dest = under(os.path.join(STAGE, "objects"), key)
    if dest is None:
        return False
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            os.unlink(dest)
        try:
            os.link(src, dest)
        except OSError:
            shutil.copy2(src, dest)
    except OSError as exc:
        logger.warning("cannot stage %s -> %s: %s", src, key, exc)
        return False
    return True


def main() -> int:
    entries: dict[str, list[Curated]] = {}
    skipped: list[str] = []
    if not os.path.isdir(SRC):
        logger.error("missing %s", SRC)
        return 1

    try:
        dirnames = sorted(os.listdir(SRC))
    except OSError as exc:
        logger.error("cannot list %s: %s", SRC, exc)
        return 1

    for dirname in dirnames:
        match = re.fullmatch(r"contestant_([0-9]+)", dirname)
        if not match:
            continue
        try:
            cid = str(int(match.group(1)))
        except ValueError as exc:
            logger.warning("skipping %s: bad contestant id (%s)", dirname, exc)
            continue
        contestant_dir = under(SRC, dirname)
        if contestant_dir is None:
            continue
        try:
            names = sorted(os.listdir(contestant_dir))
        except OSError as exc:
            logger.warning("skipping %s: cannot list (%s)", contestant_dir, exc)
            continue
        for name in names:
            path = under(contestant_dir, name)
            ext = os.path.splitext(name)[1].lower()
            if path is None or not os.path.isfile(path) or ext not in IMAGE_EXT:
                continue
            info = inspect(path)
            if info is None:
                continue
            is_pointer, digest, size = info
            if is_pointer:
                skipped.append(path)
                continue
            key = f"photos/curated/{cid}/{digest}{ext}"
            if not stage(path, key):
                continue
            entries.setdefault(cid, []).append(
                Curated(
                    key=key,
                    sha256=digest,
                    bytes=size,
                    original_name=name,
                )
            )

    manifest_dir = os.path.join(STAGE, "manifest")
    try:
        os.makedirs(manifest_dir, exist_ok=True)
        with open(
            os.path.join(manifest_dir, "photos-curated.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(entries, f, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error("cannot write manifest: %s", exc)
        return 1

    files = sum(len(v) for v in entries.values())
    size = sum(entry["bytes"] for v in entries.values() for entry in v)
    print(
        f"curated: {files} photos across {len(entries)} contestants ({size / 1e6:.0f} MB)"
    )
    if skipped:
        print(f"skipped {len(skipped)} LFS pointers:", skipped[:3])
    return 0


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
