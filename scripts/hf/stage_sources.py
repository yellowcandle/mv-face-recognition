"""Stage source videos and reference photos for the HF bucket.

Writes objects/ (paths are the bucket keys) and manifest/ (sha256 per object). Originals
are hardlinked, not copied. Upload with `hf sync`: objects first, manifest last, so a
manifest entry never points at an object that is not there yet.
"""
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_VIDEOS = os.path.join(REPO, 'source/videos')
SRC_PHOTOS = os.path.join(REPO, 'source/photo/contestants/ig_photos')
STAGE = os.path.expanduser('~/.cache/mv-hf-stage')
VIDEO_EXT = {'.mp4'}
PHOTO_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
LFS_MAGIC = b'version https://git-lfs'
NOW = datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def is_lfs_pointer(path):
    with open(path, 'rb') as f:
        return f.read(len(LFS_MAGIC)) == LFS_MAGIC


def stage(src, key):
    dest = os.path.join(STAGE, 'objects', key)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.lexists(dest):
        os.unlink(dest)
    try:
        os.link(src, dest)  # same bytes, no second copy on disk
    except OSError:
        shutil.copy2(src, dest)  # different volume


def video_id(name):
    m = re.match(r'(\d+)-', name)  # the app keys metadata by the numeric prefix
    return m.group(1) if m else os.path.splitext(name)[0]


def main():
    videos, photos, skipped, dups = {}, {}, [], 0

    for name in sorted(os.listdir(SRC_VIDEOS)):
        src = os.path.join(SRC_VIDEOS, name)
        if not os.path.isfile(src) or os.path.splitext(name)[1].lower() not in VIDEO_EXT:
            continue
        if is_lfs_pointer(src):
            skipped.append(name)
            continue
        vid = video_id(name)
        if vid in videos:
            sys.exit(f'duplicate video id {vid!r}: {name!r}')
        digest = sha256(src)
        key = f'videos/source/{vid}/{digest}.mp4'
        stage(src, key)
        videos[vid] = {'key': key, 'sha256': digest, 'bytes': os.path.getsize(src),
                       'original_name': name, 'added_at': NOW}

    for cdir in sorted(os.listdir(SRC_PHOTOS)):
        m = re.fullmatch(r'contestant_(\d+)', cdir)
        if not m:
            skipped.append(cdir)
            continue
        cid = str(int(m.group(1)))
        for name in sorted(os.listdir(os.path.join(SRC_PHOTOS, cdir))):
            src = os.path.join(SRC_PHOTOS, cdir, name)
            ext = os.path.splitext(name)[1].lower()
            if not os.path.isfile(src) or ext not in PHOTO_EXT:
                continue
            if is_lfs_pointer(src):
                skipped.append(f'{cdir}/{name}')
                continue
            digest = sha256(src)
            key = f'photos/reference/{cid}/{digest}{ext}'
            if any(p['key'] == key for p in photos.get(cid, [])):
                dups += 1
                continue
            stage(src, key)
            photos.setdefault(cid, []).append({'key': key, 'sha256': digest,
                                               'bytes': os.path.getsize(src),
                                               'original_name': name})

    os.makedirs(os.path.join(STAGE, 'manifest'), exist_ok=True)
    for fname, data in (('videos.json', videos), ('photos.json', photos)):
        with open(os.path.join(STAGE, 'manifest', fname), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    n_photos = sum(len(v) for v in photos.values())
    print(f'videos: {len(videos)} ({sum(v["bytes"] for v in videos.values()) / 1e9:.2f} GB)')
    print(f'photos: {n_photos} across {len(photos)} contestants '
          f'({sum(p["bytes"] for v in photos.values() for p in v) / 1e6:.0f} MB), '
          f'byte-identical duplicates skipped: {dups}')
    print(f'skipped (LFS pointers or non-matching entries): {skipped}')


if __name__ == '__main__':
    main()
