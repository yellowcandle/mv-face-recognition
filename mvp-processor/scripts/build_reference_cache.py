"""Build the reference-embedding cache from contestant photos.

Reference embeddings are a derived cache, not source data: the photos in
`source/photo/contestants/ig_photos/contestant_{id}/` are the only source of truth, and this
script reproduces the cache from them. See docs/adr/0001-reference-embeddings-are-a-derived-cache.md.

Writes two files next to the photos:
  reference_embeddings.npz   gitignored, ~2 MB, regenerable (takes ~12 minutes)
  reference_manifest.json    committed, so a stale cache fails loudly instead of silently

Curation is applied here, at write time, per the matching-strategy decision: photos that are
byte-identical across different contestants are dropped (one face cannot be the reference for
four people), and so are photos containing more than one face (`faces[0]` picks by detection
score, not identity, so group shots contaminate).

    python scripts/build_reference_cache.py [--photos DIR] [--out DIR]
"""

import argparse
import hashlib
import os
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

EMBED_DIM = 512
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def iter_contestant_photos(photos_dir: Path):
    """Yield (contestant_id, path) for every photo, ordered by contestant number."""
    dirs = sorted(photos_dir.glob("contestant_*"), key=lambda p: int(p.name.split("_")[1]))
    for d in dirs:
        cid = d.name.split("_")[1]
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in IMAGE_SUFFIXES:
                yield cid, f


def photo_list_hash(entries: list[tuple[str, Path]], photos_dir: Path) -> str:
    """Hash of the photo inventory. Changes whenever a photo is added, removed, or edited."""
    h = hashlib.sha256()
    for cid, path in entries:
        h.update(cid.encode())
        h.update(str(path.relative_to(photos_dir)).encode())
        h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def curate_references(
    embeddings: np.ndarray, contestant_ids: np.ndarray, min_keep: int = 2
) -> np.ndarray:
    """Drop references that match another contestant better than their own.

    A single-face photo can still be the wrong person (a friend in the shot). Comparing every
    reference against the same matching rule the pipeline uses — max cosine over references —
    exposes it: such a reference scores higher against someone else's photos than against its
    own. Each contestant keeps every reference with a positive margin, but never fewer than
    ``min_keep`` (or all of them when they have fewer), so a thin roster entry is not erased.
    """
    sims = embeddings @ embeddings.T
    np.fill_diagonal(sims, -1.0)
    keep = np.zeros(len(embeddings), dtype=bool)

    for cid in np.unique(contestant_ids):
        idx = np.flatnonzero(contestant_ids == cid)
        if len(idx) <= min_keep:
            keep[idx] = True
            continue
        same = contestant_ids == cid
        margins = []
        for i in idx:
            genuine = sims[i][same].max()
            impostor = sims[i][~same].max()
            margins.append((genuine - impostor, i))
        chosen = [i for margin, i in margins if margin > 0]
        if len(chosen) < min_keep:
            chosen = [i for _, i in sorted(margins, reverse=True)[:min_keep]]
        keep[chosen] = True

    return keep


def build(photos_dir: Path, out_dir: Path) -> dict:
    from insightface.app import FaceAnalysis

    providers = os.environ.get(
        "INSIGHTFACE_PROVIDERS", "CoreMLExecutionProvider,CPUExecutionProvider"
    ).split(",")
    app = FaceAnalysis(name="buffalo_l", providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))

    entries = list(iter_contestant_photos(photos_dir))
    if not entries:
        raise SystemExit(f"No photos found under {photos_dir}")
    logger.info("Encoding %d photos from %s", len(entries), photos_dir)

    rows, cids, paths, nfaces, scores = [], [], [], [], []
    by_digest: dict[str, set[str]] = defaultdict(set)
    digests: list[str] = []
    dropped = {"unreadable": 0, "no_face": 0, "multi_face": 0, "duplicate": 0}

    for cid, path in entries:
        raw = path.read_bytes()
        digest = hashlib.md5(raw).hexdigest()
        by_digest[digest].add(cid)

        image = cv2.imread(str(path))
        if image is None:
            dropped["unreadable"] += 1
            logger.warning("Unreadable, skipping: %s", path)
            continue
        faces = app.get(image)
        if not faces:
            dropped["no_face"] += 1
            continue
        if len(faces) > 1:
            # faces[0] is the highest-scoring face, not necessarily this contestant
            dropped["multi_face"] += 1
            continue

        rows.append(np.asarray(faces[0].normed_embedding, dtype=np.float32))
        cids.append(cid)
        paths.append(str(path.relative_to(photos_dir)))
        nfaces.append(len(faces))
        scores.append(float(faces[0].det_score))
        digests.append(digest)

    # A photo filed under more than one contestant poisons every one of them.
    shared = {d for d, owners in by_digest.items() if len(owners) > 1}
    keep = [i for i, d in enumerate(digests) if d not in shared]
    dropped["duplicate"] = len(rows) - len(keep)

    embeddings = np.stack([rows[i] for i in keep]).astype(np.float32)
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
    contestant_ids = np.array([cids[i] for i in keep])
    photo_paths = np.array([paths[i] for i in keep])
    kept_faces = np.array([nfaces[i] for i in keep])
    kept_scores = np.array([scores[i] for i in keep])

    curated = curate_references(embeddings, contestant_ids)
    dropped["outlier"] = int((~curated).sum())
    logger.info(
        "Curation dropped %d references that matched another contestant better than their own",
        dropped["outlier"],
    )
    embeddings, contestant_ids, photo_paths = (
        embeddings[curated],
        contestant_ids[curated],
        photo_paths[curated],
    )
    kept_faces, kept_scores = kept_faces[curated], kept_scores[curated]

    if embeddings.shape[1] != EMBED_DIM:
        raise SystemExit(f"Expected {EMBED_DIM}-d embeddings, got {embeddings.shape[1]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_dir / "reference_embeddings.npz",
        embeddings=embeddings,
        contestant_ids=contestant_ids,
        photo_paths=photo_paths,
        n_faces=kept_faces,
        det_scores=kept_scores,
    )

    per_contestant = defaultdict(int)
    for c in contestant_ids.tolist():
        per_contestant[c] += 1
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "photo_count": len(entries),
        "reference_count": int(len(embeddings)),
        "contestant_count": len(per_contestant),
        "photo_list_sha256": photo_list_hash(entries, photos_dir),
        "dropped": dropped,
        "references_per_contestant": dict(sorted(per_contestant.items(), key=lambda kv: int(kv[0]))),
    }
    (out_dir / "reference_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photos", type=Path, default=repo / "source/photo/contestants/ig_photos")
    ap.add_argument("--out", type=Path, default=repo / "source/photo/contestants")
    args = ap.parse_args()

    m = build(args.photos, args.out)
    print(
        f"\n{m['reference_count']} references across {m['contestant_count']} contestants "
        f"from {m['photo_count']} photos"
    )
    print(f"dropped: {m['dropped']}")
    print(f"wrote {args.out}/reference_embeddings.npz and reference_manifest.json")


if __name__ == "__main__":
    main()
