#!/usr/bin/env python3
"""
Quick test to see actual cosine similarity values between embeddings
"""

import sys
import numpy as np
from pathlib import Path
import yaml

# Load config
config_path = Path(__file__).parent / "config" / "processing_config.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Load a few contestant embeddings
photo_dir = Path("../source/photo/contestants")
contestant_embeddings = []
contestant_names = []

# Load first 5 contestant embeddings
for i in range(1, 6):
    embedding_path = photo_dir / f"contestant_{i}_unified_embedding.npy"
    if embedding_path.exists():
        embedding = np.load(embedding_path).flatten()
        contestant_embeddings.append(embedding)
        contestant_names.append(f"contestant_{i}")

print(f"Loaded {len(contestant_embeddings)} contestant embeddings")

# Test all pairwise similarities
print("\nPairwise cosine similarities:")
for i, (emb1, name1) in enumerate(zip(contestant_embeddings, contestant_names)):
    for j, (emb2, name2) in enumerate(zip(contestant_embeddings, contestant_names)):
        if i >= j:
            continue
            
        # Calculate cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            cosine_sim = 0.0
        else:
            cosine_sim = dot_product / (norm1 * norm2)
        
        print(f"  {name1} vs {name2}: {cosine_sim:.6f}")

# Test self-similarity (should be 1.0)
print("\nSelf-similarities (should be ~1.0):")
for emb, name in zip(contestant_embeddings, contestant_names):
    dot_product = np.dot(emb, emb)
    norm = np.linalg.norm(emb)
    
    if norm == 0:
        cosine_sim = 0.0
    else:
        cosine_sim = dot_product / (norm * norm)
    
    print(f"  {name} vs self: {cosine_sim:.6f}")

# Test embedding properties
print("\nEmbedding properties:")
for emb, name in zip(contestant_embeddings, contestant_names):
    magnitude = np.linalg.norm(emb)
    is_normalized = abs(magnitude - 1.0) < 0.01
    mean_val = np.mean(emb)
    std_val = np.std(emb)
    
    print(f"  {name}:")
    print(f"    Magnitude: {magnitude:.6f} (normalized: {is_normalized})")
    print(f"    Mean: {mean_val:.6f}")
    print(f"    Std: {std_val:.6f}")
    print(f"    Range: [{emb.min():.6f}, {emb.max():.6f}]")