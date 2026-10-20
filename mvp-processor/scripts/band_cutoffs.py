#!/usr/bin/env python3
"""
Recompute the band cutoffs from the reference cache.

The display bands are set where the *measured false-match rate* crosses a threshold — not by
dividing up an observed video distribution, which only describes its own shape. This script
does the leave-one-out sweep that measures it:

  - for every reference embedding, take the maximum cosine against every reference belonging to
    a **different** contestant (the impostor score: what a stranger's face scores), and against
    the **same** contestant's other photos (the genuine score, leave-one-out);

then reports where the impostor tail crosses 1% and 0.1%.

Usage:
    python scripts/band_cutoffs.py
    python scripts/band_cutoffs.py --cache ../source/photo/contestants/reference_embeddings.npz

Provisional until ground-truth labels exist (ticket 006): these boundaries say how often a
*reference photo* would be mistaken for another contestant, which is not the same as how often a
video face would be. Copy the printed values into config/processing_config.yaml
`face_recognition.band_cutoffs`.
"""

import argparse
import logging
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CACHE = Path("../source/photo/contestants/reference_embeddings.npz")

# The tail rates the two cutoffs are placed at. The cache has to be big enough to resolve them:
# with N references there are ~N impostor pairs, so a 0.1% rate needs thousands of pairs before
# a zero count means anything.
TAIL_RATES = {"high": 0.001, "medium": 0.01}


def load_references(cache_path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(cache_path, allow_pickle=False) as cache:
        embeddings = cache["embeddings"]
        contestant_ids = cache["contestant_ids"].astype(str)
    if embeddings.ndim != 2:
        raise SystemExit(f"{cache_path} holds embeddings of shape {embeddings.shape}, expected (N, 512)")
    # Both detection and reference vectors are L2-normalized, so a dot product is the cosine.
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings, contestant_ids


def score_distributions(embeddings: np.ndarray, contestant_ids: np.ndarray):
    """Return (impostor_scores, genuine_scores), one entry per reference."""
    similarity = embeddings @ embeddings.T
    count = len(contestant_ids)
    diagonal = np.eye(count, dtype=bool)
    same = (contestant_ids[:, None] == contestant_ids[None, :]) & ~diagonal

    impostor = np.where(same | diagonal, -np.inf, similarity).max(axis=1)
    genuine = np.where(same, similarity, -np.inf).max(axis=1)
    # A contestant with one photo has no genuine pair; those entries are -inf and dropped.
    return impostor, genuine[np.isfinite(genuine)]


def cutoff_at(impostor: np.ndarray, rate: float) -> float:
    """Score at which the measured false-match rate is at most `rate`.

    Impostor scores sorted descending; the cutoff is the first one at which the count of pairs
    *at or above* it is the largest allowed for the target rate. `rate` is reported alongside,
    because with a finite sweep the realised rate lands on the nearest resolvable step.
    """
    ordered = np.sort(impostor)[::-1]
    allowed = min(int(np.floor(rate * len(ordered))), len(ordered) - 1)
    return float(ordered[allowed])


def main():
    parser = argparse.ArgumentParser(description="Recompute face-recognition band cutoffs")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Reference embedding cache (.npz)")
    args = parser.parse_args()

    embeddings, contestant_ids = load_references(args.cache)
    impostor, genuine = score_distributions(embeddings, contestant_ids)

    logger.info(
        f"{len(embeddings)} references for {len(set(contestant_ids))} contestants "
        f"({genuine.size} with a genuine pair, {impostor.size} impostor pairs each)"
    )
    logger.info(
        f"genuine  min {genuine.min():.3f}  mean {genuine.mean():.3f}  "
        f"p05 {np.percentile(genuine, 5):.3f}"
    )
    logger.info(
        f"impostor mean {impostor.mean():.3f}  p90 {np.percentile(impostor, 90):.3f}  "
        f"p99 {np.percentile(impostor, 99):.3f}  max {impostor.max():.3f}"
    )

    print()
    for band, rate in TAIL_RATES.items():
        cutoff = cutoff_at(impostor, rate)
        observed = float((impostor >= cutoff).mean())
        resolvable = rate >= 1 / len(impostor)
        note = "" if resolvable else "  NOTE: below this sweep's resolution"
        print(
            f"{band:>6}: {cutoff:.3f}  (impostors at or above: {observed:.4%} of {len(impostor)}){note}"
        )
    print()


if __name__ == "__main__":
    main()
