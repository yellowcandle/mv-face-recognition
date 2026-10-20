"""Prototype the gallery derivative: one face-cropped portrait per contestant.

Picks the detected face that best matches the contestant's stored embedding (cosine), so a
group photo or a selfie with friends yields *that* contestant, not the largest face. Falls back
to the largest face when no embedding exists. Output is a 512px square WebP plus a manifest
recording exactly which photo and box produced it — the provenance the publish step will copy
into R2 as `photos/thumb/{id}/{sha}-face.webp`.
"""

from __future__ import annotations

import csv
import glob
import json
import logging
import os
import sys
from collections import Counter
from typing import Sequence, TypedDict

import cv2

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - numpy is a hard dependency
    raise SystemExit(f"numpy is required: {exc}") from exc

from insightface.app import FaceAnalysis

logger = logging.getLogger(__name__)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PHOTOS = os.path.join(REPO, "source/photo/contestants/ig_photos")
PHOTOS_ALT = os.path.join(
    REPO, "source/photo/contestants/photos"
)  # curated set, some contestants only
# Curated per-contestant set recovered from old refs (all 96 present). Preferred source for the
# gallery: one directory per contestant, ~2 photos, chosen rather than scraped.
PHOTOS_HISTORICAL = os.path.join(REPO, "source/photo/historical/contestants")
# (root, dirname pattern) in priority order
PHOTO_SOURCES = (
    (PHOTOS_HISTORICAL, "{cid}"),
    (PHOTOS, "contestant_{cid}"),
    (PHOTOS_ALT, "contestant_{cid}"),
)
EMB_DIR = os.path.join(REPO, "source/photo/contestants/embeddings/contestants")
CSV = os.path.join(REPO, "metadata/contestant_info.csv")
OUT = os.path.expanduser("~/.cache/mv-portraits")
MAX_PHOTOS = 6  # per contestant; enough to find a good face
MIN_DET = 0.50  # detector confidence floor
MIN_FACE_PX = 96  # a face smaller than this upscales to mush at 512px
REF_MIN = 0.55  # cosine to the stored embedding below which we stop trusting it
CLUSTER_MIN = 0.35  # cross-photo agreement below which we fall back to largest face
SIDE = 512
PAD = 1.9  # square side as a multiple of the longer face edge
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def under(root: str, *parts: str) -> str | None:
    """realpath of root/parts, or None (logged) if it resolves outside root."""
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, *parts))
    if os.path.commonpath([base, target]) != base:
        logger.warning("rejecting %s: resolves outside %s", target, base)
        return None
    return target


class Portrait(TypedDict):
    portrait: str
    source_file: str
    bbox: list[float]
    det_score: float
    match_cosine: float
    method: str
    size_bytes: int


def load_contestants() -> list[tuple[int, str, str]]:
    """(編號, 暱稱, 姓名) for all 96 contestants."""
    try:
        with open(CSV, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        logger.error("cannot read %s: %s", CSV, exc)
        sys.exit(1)
    if not rows:
        logger.error("%s has no rows", CSV)
        sys.exit(1)
    people: list[tuple[int, str, str]] = []
    for row in rows:
        try:
            people.append(
                (int(row["編號"].strip()), row["暱稱"].strip(), row["姓名"].strip())
            )
        except (AttributeError, KeyError, ValueError) as exc:
            logger.warning("skipping malformed row in %s: %r (%s)", CSV, row, exc)
    return people


def read_image(path: str) -> np.ndarray | None:
    """cv2.imread is typed as always returning an array; normalise to array or None."""
    try:
        data = cv2.imread(path)
    except cv2.error as exc:
        logger.warning("cannot decode %s: %s", path, exc)
        return None
    if not isinstance(data, np.ndarray) or data.size == 0:
        logger.warning("cannot decode %s: not an image", path)
        return None
    return data


def load_embeddings() -> dict[str, np.ndarray]:
    """nickname (lower-cased) -> unit-norm 512-d vector, tolerating (512,) and (1,512)."""
    emb: dict[str, np.ndarray] = {}
    for found in glob.glob(os.path.join(EMB_DIR, "*.npy")):
        path = under(EMB_DIR, os.path.basename(found))
        if path is None:
            continue
        nick = (
            os.path.basename(found)[: -len("_embedding.npy")].replace("_", " ").strip()
        )
        try:
            # allow_pickle=False: a .npy that needs pickle can execute code on load, and
            # every embedding here is a plain float array (verified for all 94 files).
            vec = np.load(path, allow_pickle=False).astype(np.float32).reshape(-1)
        except (OSError, ValueError) as exc:
            logger.warning("skipping unreadable embedding %s: %s", path, exc)
            continue
        if vec.size != 512:
            logger.warning("skipping embedding %s: %d values, expected 512", path, vec.size)
            continue
        norm = float(np.linalg.norm(vec))
        emb[nick.lower()] = vec / norm if norm else vec
    return emb


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return float(a @ b / (na * nb)) if na and nb else 0.0


def crop_square(img: np.ndarray, box: Sequence[float]) -> np.ndarray | None:
    """Square crop around a face box, with headroom, clamped to the image."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box)
    side = max(x2 - x1, y2 - y1) * PAD
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    cy -= side * 0.04  # a portrait wants headroom, not chin room
    left, top = max(0, int(round(cx - side / 2))), max(0, int(round(cy - side / 2)))
    right, bottom = min(w, left + int(round(side))), min(h, top + int(round(side)))
    patch = img[top:bottom, left:right]
    if patch.size == 0:
        return None
    return cv2.resize(patch, (SIDE, SIDE), interpolation=cv2.INTER_AREA)


def pick_portrait(
    cid: int, files: list[str], ref: np.ndarray | None, app: FaceAnalysis
) -> tuple[float, str, Sequence[float], float, str] | None:
    """Choose this contestant's portrait across their photos.

    Two signals, in order of trust:

    1. **Reference embedding** — when the contestant has one, the highest-cosine face wins.
    2. **Repeated-person clustering** — 36 contestants have no embedding under their CSV
       nickname, and "largest face" is a coin flip in a group shot. Instead, score every face
       by how strongly it matches faces in *other* photos of the same contestant: the person
       who appears repeatedly is the contestant; a friend who appears once scores near zero.

    Returns (score, file, box, det, method) so the manifest records which signal decided it.
    """
    detected: list[tuple[str, Sequence[float], float, float, np.ndarray]] = []
    small: list[tuple[str, Sequence[float], float, float, np.ndarray]] = []
    for path in files:
        img = read_image(path)
        if img is None:
            continue
        frame_area = float(img.shape[0] * img.shape[1])
        for face in app.get(img):
            det = float(face.det_score)
            if det < MIN_DET:
                continue
            x1, y1, x2, y2 = (float(v) for v in face.bbox)
            entry = (
                path,
                face.bbox,
                det,
                (x2 - x1) * (y2 - y1) / frame_area,
                face.normed_embedding,
            )
            # Absolute pixels, not frame fraction: a 1%-of-frame face in a 4000px photo is
            # sharp, the same fraction in a 640px screenshot is not.
            if min(x2 - x1, y2 - y1) >= MIN_FACE_PX:
                detected.append(entry)
            else:
                small.append(entry)
    if not detected:
        detected = (
            small  # nothing sharp enough; take the best available rather than nothing
        )
    if not detected:
        return None

    if ref is not None:
        ranked_ref = sorted(
            ((cosine(ref, d[4]), d) for d in detected),
            key=lambda pair: (pair[0], pair[1][3]),
            reverse=True,
        )
        best_score, (path, box, det, _area, _emb) = ranked_ref[0]
        if best_score >= REF_MIN:
            return best_score, path, box, det, "embedding"

    # Clustering: mean of the best cross-photo match for each face. Photos are compared, never
    # a face with itself, so one photo's duplicate detections cannot inflate the score.
    clustered: list[tuple[float, float, str, Sequence[float], float]] = []
    for idx, (path, box, det, area, emb) in enumerate(detected):
        per_photo: dict[str, float] = {}
        for jdx, (other, *_rest) in enumerate(detected):
            if idx == jdx or other == path:
                continue
            sim = cosine(emb, detected[jdx][4])
            per_photo[other] = max(per_photo.get(other, 0.0), sim)
        cluster = sum(per_photo.values()) / len(per_photo) if per_photo else 0.0
        clustered.append((cluster, area, path, box, det))
    if not clustered:
        path, box, det, _area, _emb = detected[0]
        return 0.0, path, box, det, "largest-face"

    clustered.sort(key=lambda item: (item[0], item[1]), reverse=True)
    cluster, _area, path, box, det = clustered[0]
    method = "cluster" if cluster >= CLUSTER_MIN else "largest-face"
    return cluster, path, box, det, method


def main() -> int:
    try:
        os.makedirs(OUT, exist_ok=True)
    except OSError as exc:
        logger.error("cannot create %s: %s", OUT, exc)
        return 1

    embeddings = load_embeddings()
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    manifest: dict[str, Portrait] = {}
    no_portrait: list[int] = []
    try:
        only = {int(a) for a in sys.argv[1:]} if len(sys.argv) > 1 else None
    except ValueError as exc:
        logger.error("contestant ids must be integers: %s", exc)
        return 2

    manifest_path = os.path.join(OUT, "manifest.json")
    if only is not None:
        # A partial run must not drop the portraits it did not touch.
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest.update(json.load(f))
        except (OSError, ValueError) as exc:
            logger.warning("could not read existing manifest %s: %s", manifest_path, exc)

    for cid, nickname, _name in load_contestants():
        if only is not None and cid not in only:
            continue
        # ig_photos first (the pipeline's reference set), then the curated set to fill slots.
        files: list[str] = []
        for root, pattern in PHOTO_SOURCES:
            cdir = os.path.join(root, pattern.format(cid=cid))
            found = sorted(
                path
                for path in (
                    under(cdir, os.path.basename(p))
                    for p in glob.glob(os.path.join(cdir, "*"))
                )
                if path is not None and os.path.splitext(path)[1].lower() in IMAGE_EXT
            )
            if found:
                # Exclusive, not additive: the first source that has photos wins outright, so
                # the gallery shows the curated historical set rather than a scraped mixture.
                files = found[:MAX_PHOTOS]
                break
        if not files:
            no_portrait.append(cid)
            continue

        picked = pick_portrait(cid, files, embeddings.get(nickname.lower()), app)
        if picked is None:
            no_portrait.append(cid)
            continue
        score, path, box, det, method = picked

        img = read_image(path)
        patch = crop_square(img, box) if img is not None else None
        if patch is None:
            no_portrait.append(cid)
            continue

        out = os.path.join(OUT, f"{cid}.webp")
        try:
            if not cv2.imwrite(out, patch, [cv2.IMWRITE_WEBP_QUALITY, 88]):
                raise OSError("cv2.imwrite returned False")
            size = os.path.getsize(out)
        except (OSError, cv2.error) as exc:
            logger.warning("could not write portrait %s: %s", out, exc)
            no_portrait.append(cid)
            continue

        manifest[str(cid)] = {
            "portrait": f"photos/thumb/{cid}/proto-{os.path.basename(path)}.webp",
            "source_file": os.path.relpath(path, REPO),
            "bbox": [round(float(v), 1) for v in box],
            "det_score": round(det, 3),
            "match_cosine": round(score, 3),
            "method": method,
            "size_bytes": size,
        }
        if len(manifest) % 10 == 0:
            print(f"{len(manifest)} portraits…", flush=True)

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error("cannot write %s: %s", manifest_path, exc)
        return 1

    total = sum(p["size_bytes"] for p in manifest.values())
    print(
        f"portraits: {len(manifest)} | {total / 1e6:.1f} MB "
        f"(avg {total / max(1, len(manifest)) / 1024:.0f} KB)"
    )
    print("without a usable portrait:", no_portrait)

    # Scores are only comparable within a method: an embedding pick reports cosine to the
    # stored vector, a clustered pick reports cross-photo agreement.
    print("signal:", dict(Counter(p["method"] for p in manifest.values())))
    for method in ("embedding", "cluster"):
        scores = sorted(
            p["match_cosine"] for p in manifest.values() if p["method"] == method
        )
        if scores:
            print(
                f"  {method:<10} min {scores[0]:.2f} median {scores[len(scores) // 2]:.2f} "
                f"max {scores[-1]:.2f}"
            )
    weak = [cid for cid, p in manifest.items() if p["method"] == "largest-face"]
    if weak:
        print("no signal, needs review:", weak)
    return 0


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
