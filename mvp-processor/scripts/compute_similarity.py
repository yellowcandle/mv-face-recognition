#!/usr/bin/env python3
"""
Compute pairwise cosine similarity matrix between contestant embeddings.

Produces similarity_matrix.json (96x96 heatmap data) and top_pairs.json
(sorted confusion pairs) for the Embedding Workbench Confusion Matrix tab.

Usage:
    python scripts/compute_similarity.py
    python scripts/compute_similarity.py --top-n 20 --output ../data/similarity_matrix.json
"""

import argparse
import csv
import json
import logging
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = Path("../metadata/contestant_info.csv")
DEFAULT_EMBEDDINGS_DIR = Path("../source/photo/contestants")
DEFAULT_OUTPUT = Path("../data/similarity_matrix.json")
DEFAULT_PAIRS_OUTPUT = Path("../data/top_pairs.json")


def load_contestants(csv_path: Path) -> list[dict]:
    """Load contestant info from CSV."""
    contestants = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            contestants.append({
                "id": row["編號"].strip(),
                "name": row["姓名"].strip(),
                "nickname": row["暱稱"].strip(),
            })
    return contestants


def load_reference_sets(
    contestants: list[dict], embeddings_dir: Path
) -> tuple[list[dict], list[np.ndarray]]:
    """Load each contestant's reference set from the cache, keyed by contestant number.

    A contestant is a *set* of per-photo reference embeddings, not one averaged vector; see
    docs/adr/0001-reference-embeddings-are-a-derived-cache.md. Sets are ragged (1-16 photos),
    so this returns a list of (K,512) arrays rather than a stacked matrix.
    """
    path = embeddings_dir / "reference_embeddings.npz"
    if not path.exists():
        raise SystemExit(f"{path} not found. Run: python scripts/build_reference_cache.py")

    data = np.load(str(path), allow_pickle=False)
    embeddings = data["embeddings"].astype(np.float32)
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
    cids = data["contestant_ids"]

    valid, sets = [], []
    for c in contestants:
        rows = embeddings[cids == c["id"]]
        if len(rows) == 0:
            continue
        valid.append(c)
        sets.append(rows)

    if not sets:
        return [], []
    logger.info(
        "Loaded %d reference sets (%d references total)", len(sets), sum(len(s) for s in sets)
    )
    return valid, sets


def cosine_similarity_matrix(sets: list[np.ndarray]) -> np.ndarray:
    """Contestant-by-contestant similarity, as max cosine between their reference sets.

    Max, not mean, because that is how the matcher scores: a face is matched to the single
    closest reference. Cell (i,j) therefore reads as "the best case for confusing i with j",
    which is what the Workbench heatmap is for.
    """
    n = len(sets)
    matrix = np.ones((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            v = float((sets[i] @ sets[j].T).max())
            matrix[i, j] = matrix[j, i] = v
    return matrix


def extract_top_pairs(
    matrix: np.ndarray,
    contestants: list[dict],
    top_n: int = 20,
) -> list[dict]:
    """Extract top-N most similar non-self pairs."""
    n = matrix.shape[0]
    pairs = []

    for i in range(n):
        for j in range(i + 1, n):
            pairs.append({
                "contestant_a": {
                    "id": contestants[i]["id"],
                    "name": contestants[i]["name"],
                    "nickname": contestants[i]["nickname"],
                },
                "contestant_b": {
                    "id": contestants[j]["id"],
                    "name": contestants[j]["name"],
                    "nickname": contestants[j]["nickname"],
                },
                "similarity": round(float(matrix[i, j]), 6),
            })

    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    return pairs[:top_n]


def main():
    parser = argparse.ArgumentParser(description="Compute embedding similarity matrix")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to contestant_info.csv")
    parser.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS_DIR, help="Embeddings directory")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output similarity_matrix.json")
    parser.add_argument("--pairs-output", type=Path, default=DEFAULT_PAIRS_OUTPUT, help="Output top_pairs.json")
    parser.add_argument("--top-n", type=int, default=20, help="Number of top confusion pairs to extract")
    args = parser.parse_args()

    contestants = load_contestants(args.csv)
    logger.info(f"Loaded {len(contestants)} contestants from CSV")

    valid_contestants, reference_sets = load_reference_sets(contestants, args.embeddings)

    if len(valid_contestants) < 2:
        logger.error("Need at least 2 contestants with references to compute similarity")
        return

    matrix = cosine_similarity_matrix(reference_sets)
    logger.info(f"Computed {matrix.shape[0]}x{matrix.shape[1]} similarity matrix")

    # Labels for the heatmap
    labels = [
        {"id": c["id"], "name": c["name"], "nickname": c["nickname"]}
        for c in valid_contestants
    ]

    # Convert matrix to nested list for JSON
    matrix_data = {
        "labels": labels,
        "matrix": [[round(float(v), 6) for v in row] for row in matrix],
        "stats": {
            "min_off_diagonal": round(float(np.min(matrix[np.triu_indices_from(matrix, k=1)])), 6),
            "max_off_diagonal": round(float(np.max(matrix[np.triu_indices_from(matrix, k=1)])), 6),
            "mean_off_diagonal": round(float(np.mean(matrix[np.triu_indices_from(matrix, k=1)])), 6),
            "contestant_count": len(valid_contestants),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(matrix_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Matrix written to {args.output}")

    # Top confusion pairs
    top_pairs = extract_top_pairs(matrix, valid_contestants, args.top_n)

    with open(args.pairs_output, "w", encoding="utf-8") as f:
        json.dump({"pairs": top_pairs, "total_pairs": len(valid_contestants) * (len(valid_contestants) - 1) // 2}, f, indent=2, ensure_ascii=False)
    logger.info(f"Top {args.top_n} pairs written to {args.pairs_output}")

    # Preview top 5
    logger.info("Top confusion pairs:")
    for p in top_pairs[:5]:
        a = p["contestant_a"]["nickname"]
        b = p["contestant_b"]["nickname"]
        logger.info(f"  {a} <-> {b}: {p['similarity']:.4f}")


if __name__ == "__main__":
    main()
