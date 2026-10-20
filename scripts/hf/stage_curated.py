"""Stage the curated reference photos (source/photo/contestants/photos) for the bucket.

These files were recovered from GitHub's LFS object storage after their pointers were lost:
the folder is gitignored, untracked, and no ref points at the blobs. Archiving them under
`photos/curated/` is what stops a repeat loss. Originals are hardlinked into the staging tree.
"""

import hashlib
import json
import os
import re
import shutil
import sys
from typing import TypedDict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "source/photo/contestants/photos")
STAGE = os.path.expanduser("~/.cache/mv-hf-stage")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class Curated(TypedDict):
    key: str
    sha256: str
    bytes: int
    original_name: str


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        sys.exit(f"cannot read {path}: {exc}")
    return digest.hexdigest()


def stage(src: str, key: str) -> None:
    dest = os.path.join(STAGE, "objects", key)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            os.unlink(dest)
        try:
            os.link(src, dest)
        except OSError:
            shutil.copy2(src, dest)
    except OSError as exc:
        sys.exit(f"cannot stage {key}: {exc}")


def main() -> int:
    entries: dict[str, list[Curated]] = {}
    skipped: list[str] = []
    if not os.path.isdir(SRC):
        sys.exit(f"missing {SRC}")

    try:
        dirnames = sorted(os.listdir(SRC))
    except OSError as exc:
        sys.exit(f"cannot list {SRC}: {exc}")

    for dirname in dirnames:
        match = re.fullmatch(r"contestant_(\d+)", dirname)
        if not match:
            continue
        cid = str(int(match.group(1)))
        contestant_dir = os.path.join(SRC, dirname)
        try:
            names = sorted(os.listdir(contestant_dir))
        except OSError as exc:
            sys.exit(f"cannot list {contestant_dir}: {exc}")
        for name in names:
            path = os.path.join(contestant_dir, name)
            ext = os.path.splitext(name)[1].lower()
            if not os.path.isfile(path) or ext not in IMAGE_EXT:
                continue
            try:
                with open(path, "rb") as f:
                    head = f.read(40)
            except OSError as exc:
                sys.exit(f"cannot read {path}: {exc}")
            if head.startswith(b"version https://git-lfs"):
                skipped.append(path)
                continue
            digest = sha256(path)
            key = f"photos/curated/{cid}/{digest}{ext}"
            stage(path, key)
            entries.setdefault(cid, []).append(
                Curated(
                    key=key,
                    sha256=digest,
                    bytes=os.path.getsize(path),
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
        sys.exit(f"cannot write manifest: {exc}")

    files = sum(len(v) for v in entries.values())
    size = sum(entry["bytes"] for v in entries.values() for entry in v)
    print(
        f"curated: {files} photos across {len(entries)} contestants ({size / 1e6:.0f} MB)"
    )
    if skipped:
        print(f"skipped {len(skipped)} LFS pointers:", skipped[:3])
    return 0


if __name__ == "__main__":
    sys.exit(main())
