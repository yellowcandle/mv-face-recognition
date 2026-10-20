"""Stage source videos and reference photos for the HF bucket.

Writes objects/ (paths are the bucket keys) and manifest/ (sha256 per object). Originals
are hardlinked, not copied. Upload with `hf sync`: objects first, manifest last, so a
manifest entry never points at an object that is not there yet.

A bad entry (unreadable file, unexpected name, path escaping its root) is logged and
skipped; only a failure that would leave the staging tree inconsistent exits non-zero.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_VIDEOS = os.path.join(REPO, 'source/videos')
SRC_PHOTOS = os.path.join(REPO, 'source/photo/contestants/ig_photos')
STAGE = os.path.expanduser('~/.cache/mv-hf-stage')
VIDEO_EXT = {'.mp4'}
PHOTO_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
LFS_MAGIC = b'version https://git-lfs'
NOW = datetime.now(timezone.utc).isoformat(timespec='seconds')
VIDEO_ID_RE = re.compile(r'[A-Za-z0-9_-]+')  # what video_id() may yield for a bucket key


def under(root: str, *parts: str) -> str | None:
    """realpath of root/parts, or None (logged) if it resolves outside root."""
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, *parts))
    if os.path.commonpath([base, target]) != base:
        logger.warning('rejecting %s: resolves outside %s', target, base)
        return None
    return target


def listdir(path: str) -> list[str]:
    try:
        return sorted(os.listdir(path))
    except OSError as exc:
        logger.error('cannot list %s: %s', path, exc)
        sys.exit(1)


def inspect(src: str) -> tuple[str, int] | None:
    """(sha256, bytes) of a real file, or None for an LFS pointer or (logged) a read error."""
    h = hashlib.sha256()
    try:
        with open(src, 'rb') as f:
            head = f.read(len(LFS_MAGIC))
            if head == LFS_MAGIC:
                return None
            h.update(head)
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        return h.hexdigest(), os.path.getsize(src)
    except OSError as exc:
        logger.warning('skipping unreadable %s: %s', src, exc)
        return None


def stage(src: str, key: str) -> bool:
    dest = under(os.path.join(STAGE, 'objects'), key)
    if dest is None:
        return False
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            os.unlink(dest)
        try:
            os.link(src, dest)  # same bytes, no second copy on disk
        except OSError:
            shutil.copy2(src, dest)  # different volume
    except OSError as exc:
        logger.warning('cannot stage %s -> %s: %s', src, key, exc)
        return False
    return True


def video_id(name: str) -> str:
    m = re.match(r'(\d+)-', name)  # the app keys metadata by the numeric prefix
    return m.group(1) if m else os.path.splitext(name)[0]


def main() -> None:
    videos: dict[str, dict[str, Any]] = {}
    photos: dict[str, list[dict[str, Any]]] = {}
    skipped: list[str] = []
    dups = 0

    for name in listdir(SRC_VIDEOS):
        src = under(SRC_VIDEOS, name)
        if src is None:
            skipped.append(name)
            continue
        if not os.path.isfile(src) or os.path.splitext(name)[1].lower() not in VIDEO_EXT:
            continue
        vid = video_id(name)
        if not VIDEO_ID_RE.fullmatch(vid):
            logger.warning('skipping %r: video id %r is not a safe key segment', name, vid)
            skipped.append(name)
            continue
        info = inspect(src)
        if info is None:
            skipped.append(name)
            continue
        if vid in videos:
            logger.error('duplicate video id %r: %r', vid, name)
            sys.exit(1)
        digest, size = info
        key = f'videos/source/{vid}/{digest}.mp4'
        if not stage(src, key):
            skipped.append(name)
            continue
        videos[vid] = {'key': key, 'sha256': digest, 'bytes': size,
                       'original_name': name, 'added_at': NOW}

    for cdir in listdir(SRC_PHOTOS):
        m = re.fullmatch(r'contestant_([0-9]+)', cdir)
        cdir_path = under(SRC_PHOTOS, cdir) if m else None
        if not m or cdir_path is None:
            skipped.append(cdir)
            continue
        try:
            cid = str(int(m.group(1)))
        except ValueError as exc:
            logger.warning('skipping %s: bad contestant id (%s)', cdir, exc)
            skipped.append(cdir)
            continue
        if not os.path.isdir(cdir_path):
            continue
        for name in listdir(cdir_path):
            src = under(cdir_path, name)
            ext = os.path.splitext(name)[1].lower()
            if src is None:
                skipped.append(f'{cdir}/{name}')
                continue
            if not os.path.isfile(src) or ext not in PHOTO_EXT:
                continue
            info = inspect(src)
            if info is None:
                skipped.append(f'{cdir}/{name}')
                continue
            digest, size = info
            key = f'photos/reference/{cid}/{digest}{ext}'
            if any(p['key'] == key for p in photos.get(cid, [])):
                dups += 1
                continue
            if not stage(src, key):
                skipped.append(f'{cdir}/{name}')
                continue
            photos.setdefault(cid, []).append({'key': key, 'sha256': digest,
                                               'bytes': size,
                                               'original_name': name})

    try:
        os.makedirs(os.path.join(STAGE, 'manifest'), exist_ok=True)
        for fname, data in (('videos.json', videos), ('photos.json', photos)):
            with open(os.path.join(STAGE, 'manifest', fname), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error('cannot write manifest: %s', exc)
        sys.exit(1)

    n_photos = sum(len(v) for v in photos.values())
    print(f'videos: {len(videos)} ({sum(v["bytes"] for v in videos.values()) / 1e9:.2f} GB)')
    print(f'photos: {n_photos} across {len(photos)} contestants '
          f'({sum(p["bytes"] for v in photos.values() for p in v) / 1e6:.0f} MB), '
          f'byte-identical duplicates skipped: {dups}')
    print(f'skipped (LFS pointers or non-matching entries): {skipped}')


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s %(name)s: %(message)s')
    main()
