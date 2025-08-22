#!/usr/bin/env python3
"""Test embedding distance calculations to validate unified system"""

import numpy as np
from pathlib import Path
import sys

# Add the src directory to the path
sys.path.append("mvp-processor/src")

from unified_embedding_system import UnifiedEmbeddingSystem


def test_embedding_distances():
    """Test distance calculations between different contestants"""

    # Load config
    import yaml

    with open("mvp-processor/config/processing_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    embedding_system = UnifiedEmbeddingSystem(config)

    # Load some unified embeddings
    contestants_dir = Path("source/photo/contestants")

    unified_files = list(contestants_dir.glob("*_unified_embedding.npy"))

    if len(unified_files) < 2:
        print("Not enough unified embeddings found")
        return

    print(f"Found {len(unified_files)} unified embeddings")
    print("Testing distance calculations...")

    # Load first 5 embeddings for testing
    embeddings = {}
    for file in unified_files[:5]:
        name = file.stem.replace("_unified_embedding", "")
        try:
            embedding = np.load(file)
            embeddings[name] = embedding
            print(
                f"  - Loaded {name}: shape={embedding.shape}, norm={np.linalg.norm(embedding):.3f}"
            )
        except Exception as e:
            print(f"  - Failed to load {name}: {e}")

    if len(embeddings) < 2:
        print("Not enough valid embeddings loaded")
        return

    # Test distance calculations between pairs
    print("\nDistance calculations:")
    names = list(embeddings.keys())

    for i, name1 in enumerate(names[:3]):  # Test first 3
        for name2 in names[i + 1 : 4]:  # Against next ones
            emb1 = embeddings[name1]
            emb2 = embeddings[name2]

            # Calculate distances using the system
            distance = embedding_system.calculate_distance(emb1, emb2, method="cosine")
            confidence = embedding_system.distance_to_confidence(
                distance, method="cosine"
            )

            print(f"  {name1} vs {name2}:")
            print(f"    Distance: {distance:.3f}")
            print(f"    Confidence: {confidence:.3f}")
            print(f"    Threshold met: {confidence > 0.5}")
            print()


if __name__ == "__main__":
    test_embedding_distances()
