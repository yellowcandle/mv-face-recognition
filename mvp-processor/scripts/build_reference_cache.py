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
import sys
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


def photo_list_hash(entries: list[tuple[str, Path]], photos_dirs: list[Path]) -> str:
    """Hash of the photo inventory. Changes whenever a photo is added, removed, or edited.

    Paths are hashed relative to the tree that supplied them, so the same photos produce the same
    hash from another checkout.
    """
    h = hashlib.sha256()
    for cid, path in entries:
        owner = next(tree for tree in photos_dirs if tree in path.parents)
        h.update(cid.encode())
        h.update(f"{owner.name}/{path.relative_to(owner)}".encode())
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


def load_promoted(promoted_dir: Path) -> tuple[list[np.ndarray], list[str], list[str], list[float]]:
    """Accepted-flag vectors: (vectors, contestant_ids, paths, det_scores).

    These are not photos. Each one is the embedding of a detection a human accepted as contestant
    N, so its identity is settled and curation must not delete it — but a conflicting vector is
    still worth logging, which is why the caller records the margin.
    """
    if not promoted_dir.is_dir():
        raise SystemExit(f"--promoted {promoted_dir} is not a directory")
    manifest_path = promoted_dir / "manifest.json"
    scores: dict[str, float] = {}
    if manifest_path.is_file():
        for entry in json.loads(manifest_path.read_text()).get("vectors", []):
            scores[entry["path"]] = float(entry.get("det_score", 0.0))

    vectors, contestant_ids, paths, det_scores = [], [], [], []
    for path in sorted(promoted_dir.glob("contestant_*/**/*.npy")):
        contestant = path.parent.name.split("_")[-1]
        vector = np.load(path).astype(np.float32).flatten()
        if vector.shape != (EMBED_DIM,):
            raise SystemExit(f"{path}: expected {EMBED_DIM}-d vector, got {vector.shape}")
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            raise SystemExit(f"{path}: zero vector")
        relative = str(path.relative_to(promoted_dir))
        vectors.append(vector / norm)
        contestant_ids.append(contestant)
        paths.append(f"{promoted_dir.name}/{relative}")
        det_scores.append(scores.get(relative, 0.0))
    return vectors, contestant_ids, paths, det_scores


def build(
    photos_dirs: list[Path],
    out_dir: Path,
    promoted_dirs: list[Path] | None = None,
    include_conflicting: bool = False,
) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from face_detector import create_face_app

    providers = os.environ.get(
        "INSIGHTFACE_PROVIDERS", "CoreMLExecutionProvider,CPUExecutionProvider"
    ).split(",")
    app = create_face_app(providers)

    entries = []
    for photos_dir in photos_dirs:
        found = list(iter_contestant_photos(photos_dir))
        if not found:
            raise SystemExit(f"No photos found under {photos_dir}")
        entries.extend(found)
    logger.info("Encoding %d photos from %s", len(entries), ", ".join(str(d) for d in photos_dirs))

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
        # Trees can both hold `contestant_<id>/`, so the stored path names its tree.
        owner = next(tree for tree in photos_dirs if tree in path.parents)
        paths.append(f"{owner.name}/{path.relative_to(owner)}")
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

    # Promoted vectors join after photo curation: a human has already ruled on whose they are.
    promoted_count = 0
    promoted_conflicts: list[dict] = []
    if promoted_dirs:
        vectors, promoted_ids, promoted_paths, promoted_scores = [], [], [], []
        for promoted_dir in promoted_dirs:
            part_vectors, part_ids, part_paths, part_scores = load_promoted(promoted_dir)
            vectors.extend(part_vectors)
            promoted_ids.extend(part_ids)
            promoted_paths.extend(part_paths)
            promoted_scores.extend(part_scores)
        if vectors:
            pending = np.stack(vectors).astype(np.float32)
            if embeddings.size:
                similarity = pending @ embeddings.T
                for row, contestant in enumerate(promoted_ids):
                    same = contestant_ids == contestant
                    genuine = float(similarity[row][same].max()) if same.any() else 0.0
                    impostor = (
                        float(similarity[row][~same].max()) if (~same).any() else 0.0
                    )
                    if genuine <= impostor:
                        promoted_conflicts.append(
                            {
                                "path": promoted_paths[row],
                                "contestant_id": contestant,
                                "own": round(genuine, 3),
                                "stranger": round(impostor, 3),
                            }
                        )
            if not include_conflicting and promoted_conflicts:
                refused = {conflict["path"].split("/", 1)[-1] for conflict in promoted_conflicts}
                keep_rows = [
                    row
                    for row, path in enumerate(promoted_paths)
                    if path.split("/", 1)[-1] not in refused
                ]
                logger.warning(
                    "Refused %d promoted vectors that match a stranger better than their own "
                    "contestant: %s",
                    len(refused),
                    ", ".join(sorted(refused)),
                )
                pending = pending[keep_rows]
                promoted_ids = [promoted_ids[row] for row in keep_rows]
                promoted_paths = [promoted_paths[row] for row in keep_rows]
                promoted_scores = [promoted_scores[row] for row in keep_rows]
                if not len(promoted_ids):
                    raise SystemExit("every promoted vector conflicts; nothing to add")

            embeddings = np.concatenate([embeddings, pending]) if embeddings.size else pending
            contestant_ids = np.concatenate([contestant_ids, np.array(promoted_ids)])
            photo_paths = np.concatenate([photo_paths, np.array(promoted_paths)])
            kept_faces = np.concatenate([kept_faces, np.ones(len(promoted_ids), dtype=int)])
            kept_scores = np.concatenate([kept_scores, np.array(promoted_scores, dtype=float)])
            promoted_count = len(promoted_ids)
            logger.info("Added %d promoted flag vectors", promoted_count)

    photo_rows = len(embeddings) - promoted_count
    curated = np.ones(len(embeddings), dtype=bool)
    if photo_rows:
        curated[:photo_rows] = curate_references(embeddings[:photo_rows], contestant_ids[:photo_rows])
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
        "photo_trees": [str(tree) for tree in photos_dirs],
        "photo_list_sha256": photo_list_hash(entries, photos_dirs),
        "dropped": dropped,
        "references_per_contestant": dict(sorted(per_contestant.items(), key=lambda kv: int(kv[0]))),
        "promoted": {"count": promoted_count, "conflicts": promoted_conflicts},
    }
    (out_dir / "reference_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--photos",
        type=Path,
        nargs="+",
        default=[repo / "source/photo/contestants/ig_photos"],
        help="one or more trees of contestant_<id>/ photos; all are curated in one pass",
    )
    ap.add_argument("--out", type=Path, default=repo / "source/photo/contestants")
    ap.add_argument(
        "--include-conflicting",
        action="store_true",
        help="also add promoted vectors that match a stranger better than their own contestant",
    )
    ap.add_argument(
        "--promoted",
        type=Path,
        nargs="+",
        default=None,
        help="human-verified vectors from scripts/promote_flags.py; omit to build from photos only",
    )
    args = ap.parse_args()

    m = build(args.photos, args.out, args.promoted, include_conflicting=args.include_conflicting)
    print(
        f"\n{m['reference_count']} references across {m['contestant_count']} contestants "
        f"from {m['photo_count']} photos"
    )
    print(f"dropped: {m['dropped']}")
    print(f"wrote {args.out}/reference_embeddings.npz and reference_manifest.json")


if __name__ == "__main__":
    main()
