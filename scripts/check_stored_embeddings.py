#!/usr/bin/env python3
"""
Check if stored embeddings are normalized.
"""

import numpy as np
from pathlib import Path


def check_embeddings():
    """Check normalization of stored embeddings."""
    contestants_dir = Path("source/photo/contestants")
    npy_files = list(contestants_dir.glob("*_embedding.npy"))[:5]  # Check first 5

    print("🔍 Checking stored embedding normalization:")

    for npy_file in npy_files:
        try:
            embedding = np.load(npy_file)

            # Handle different shapes
            if embedding.ndim == 2 and embedding.shape == (1, 512):
                embedding = embedding.flatten()

            norm = np.linalg.norm(embedding)
            print(
                f"   {npy_file.stem:20s}: norm = {norm:.6f}, shape = {embedding.shape}"
            )

        except Exception as e:
            print(f"   {npy_file.stem:20s}: ERROR - {e}")


if __name__ == "__main__":
    check_embeddings()
