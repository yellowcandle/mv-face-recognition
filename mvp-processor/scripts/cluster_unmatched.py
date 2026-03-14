#!/usr/bin/env python3
"""
Cluster unmatched face embeddings using HDBSCAN.

Reads unmatched face embeddings saved during video processing and groups
them into clusters of similar faces. Produces clusters.json for the
Embedding Workbench Unmatched Faces tab.

Usage:
    python scripts/cluster_unmatched.py
    python scripts/cluster_unmatched.py --min-cluster-size 3 --output ../data/clusters.json
"""

import argparse
import json
import logging
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_UNMATCHED_DIR = Path("../data/unmatched_faces")
DEFAULT_OUTPUT = Path("../data/clusters.json")


def load_unmatched_embeddings(unmatched_dir: Path) -> tuple[list[dict], np.ndarray]:
    """
    Load all unmatched face embeddings from all video subdirectories.

    Returns:
        Tuple of (face metadata list, embedding matrix NxD)
    """
    faces = []
    vectors = []

    if not unmatched_dir.exists():
        return [], np.array([])

    for video_dir in sorted(unmatched_dir.iterdir()):
        if not video_dir.is_dir():
            continue

        index_path = video_dir / "unmatched_index.json"
        if not index_path.exists():
            continue

        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)

        video_name = index["video"]

        for face_info in index["faces"]:
            npy_path = video_dir / face_info["file"]
            if not npy_path.exists():
                continue

            try:
                vec = np.load(str(npy_path)).flatten().astype(np.float32)
                faces.append({
                    "video": video_name,
                    "file": face_info["file"],
                    "frame_number": face_info["frame_number"],
                    "timestamp": face_info["timestamp"],
                    "location": face_info["location"],
                    "confidence": face_info["confidence"],
                })
                vectors.append(vec)
            except Exception as e:
                logger.warning(f"Failed to load {npy_path}: {e}")

    if not vectors:
        return [], np.array([])

    return faces, np.stack(vectors)


def cluster_embeddings(
    embeddings: np.ndarray,
    min_cluster_size: int = 3,
    min_samples: int = 2,
) -> np.ndarray:
    """
    Cluster embeddings using HDBSCAN.

    Falls back to simple cosine similarity clustering if hdbscan is not installed.

    Returns:
        Array of cluster labels (-1 = noise/unclustered)
    """
    try:
        from sklearn.cluster import HDBSCAN as SklearnHDBSCAN

        # Normalize for cosine distance
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = embeddings / norms

        clusterer = SklearnHDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",  # on normalized vectors ≈ cosine
        )
        labels = clusterer.fit_predict(normalized)
        logger.info(f"HDBSCAN: {len(set(labels) - {-1})} clusters, {(labels == -1).sum()} noise points")
        return labels

    except ImportError:
        logger.warning("scikit-learn HDBSCAN not available, falling back to agglomerative clustering")
        return _fallback_clustering(embeddings, min_cluster_size)


def _fallback_clustering(embeddings: np.ndarray, min_cluster_size: int) -> np.ndarray:
    """Simple agglomerative clustering fallback."""
    from sklearn.cluster import AgglomerativeClustering

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normalized = embeddings / norms

    # Use cosine-like distance threshold
    clusterer = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.8,
        metric="euclidean",
        linkage="average",
    )
    labels = clusterer.fit_predict(normalized)

    # Filter out clusters smaller than min_cluster_size
    from collections import Counter
    counts = Counter(labels)
    for label, count in counts.items():
        if count < min_cluster_size:
            labels[labels == label] = -1

    # Re-number clusters
    unique_labels = sorted(set(labels) - {-1})
    remap = {old: new for new, old in enumerate(unique_labels)}
    labels = np.array([remap.get(l, -1) for l in labels])

    logger.info(f"Agglomerative: {len(unique_labels)} clusters, {(labels == -1).sum()} noise points")
    return labels


def build_clusters_json(
    faces: list[dict],
    labels: np.ndarray,
    embeddings: np.ndarray,
) -> dict:
    """Build the clusters.json output structure."""
    clusters = {}

    for i, (face, label) in enumerate(zip(faces, labels)):
        if label == -1:
            continue  # skip noise
        label = int(label)
        if label not in clusters:
            clusters[label] = {
                "id": label,
                "faces": [],
                "embeddings": [],
            }
        clusters[label]["faces"].append(face)
        clusters[label]["embeddings"].append(embeddings[i])

    result = []
    for cluster_id in sorted(clusters.keys()):
        c = clusters[cluster_id]
        # Compute centroid
        centroid = np.mean(c["embeddings"], axis=0)

        result.append({
            "id": cluster_id,
            "face_count": len(c["faces"]),
            "faces": c["faces"],
            "centroid_norm": float(np.linalg.norm(centroid)),
            "videos": list(set(f["video"] for f in c["faces"])),
        })

    noise_count = int((labels == -1).sum())

    return {
        "clusters": result,
        "total_unmatched": len(faces),
        "total_clustered": len(faces) - noise_count,
        "total_noise": noise_count,
        "cluster_count": len(result),
    }


def main():
    parser = argparse.ArgumentParser(description="Cluster unmatched face embeddings")
    parser.add_argument("--unmatched-dir", type=Path, default=DEFAULT_UNMATCHED_DIR, help="Unmatched faces directory")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output clusters.json path")
    parser.add_argument("--min-cluster-size", type=int, default=3, help="Minimum faces per cluster")
    parser.add_argument("--min-samples", type=int, default=2, help="HDBSCAN min_samples parameter")
    args = parser.parse_args()

    faces, embeddings = load_unmatched_embeddings(args.unmatched_dir)
    logger.info(f"Loaded {len(faces)} unmatched faces from {args.unmatched_dir}")

    if len(faces) < args.min_cluster_size:
        logger.info("Not enough faces to cluster. Run video processing first to generate unmatched embeddings.")
        # Write empty result
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"clusters": [], "total_unmatched": len(faces), "total_clustered": 0, "total_noise": len(faces), "cluster_count": 0}, f, indent=2)
        return

    labels = cluster_embeddings(embeddings, args.min_cluster_size, args.min_samples)
    result = build_clusters_json(faces, labels, embeddings)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote {result['cluster_count']} clusters ({result['total_clustered']} faces) to {args.output}")
    logger.info(f"Noise: {result['total_noise']} faces not in any cluster")

    # Preview top clusters
    for c in result["clusters"][:5]:
        logger.info(f"  Cluster {c['id']}: {c['face_count']} faces from {c['videos']}")


if __name__ == "__main__":
    main()
