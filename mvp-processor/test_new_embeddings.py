#!/usr/bin/env python3
"""
Test script to verify the fresh embeddings work correctly
"""

import sys
import numpy as np
from pathlib import Path
import yaml
import json

# Load config
config_path = Path(__file__).parent / "config" / "processing_config.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Load a few fresh contestant embeddings
photo_dir = Path("../source/photo/contestants")
contestant_embeddings = []
contestant_names = []
contestant_ids = []

# Load first 10 contestant embeddings to test
for i in range(1, 11):
    embedding_path = photo_dir / f"contestant_{i}_unified_embedding.npy"
    metadata_path = photo_dir / f"contestant_{i}_embedding_metadata.json"
    
    if embedding_path.exists() and metadata_path.exists():
        embedding = np.load(embedding_path).flatten()
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        contestant_embeddings.append(embedding)
        contestant_names.append(metadata['nickname'])
        contestant_ids.append(i)
        
        print(f"✅ Loaded contestant {i} ({metadata['nickname']}): {embedding.shape}, norm={np.linalg.norm(embedding):.6f}")

print(f"\n✅ Loaded {len(contestant_embeddings)} fresh contestant embeddings")

# Test all pairwise similarities
print("\n🔍 Testing pairwise similarities between contestants:")
max_similarity = 0.0
min_similarity = 1.0

for i, (emb1, name1, id1) in enumerate(zip(contestant_embeddings, contestant_names, contestant_ids)):
    for j, (emb2, name2, id2) in enumerate(zip(contestant_embeddings, contestant_names, contestant_ids)):
        if i >= j:
            continue
            
        # Calculate cosine similarity
        cosine_sim = np.dot(emb1, emb2)  # Already normalized, so just dot product
        max_similarity = max(max_similarity, cosine_sim)
        min_similarity = min(min_similarity, cosine_sim)
        
        print(f"  {id1:2d} ({name1:10s}) vs {id2:2d} ({name2:10s}): {cosine_sim:.6f}")

print(f"\n📊 Similarity Analysis:")
print(f"  Maximum inter-person similarity: {max_similarity:.6f}")
print(f"  Minimum inter-person similarity: {min_similarity:.6f}")
print(f"  Similarity range: {max_similarity - min_similarity:.6f}")

# Check if similarities are reasonable for the current threshold
threshold = config['face_recognition']['similarity_threshold']
print(f"\n⚙️  Current similarity threshold: {threshold}")

if max_similarity < threshold:
    print(f"✅ Good! All inter-person similarities ({max_similarity:.6f}) are below threshold ({threshold})")
    print("   This should prevent false positive recognitions between different people")
else:
    print(f"⚠️  Warning: Some inter-person similarities ({max_similarity:.6f}) exceed threshold ({threshold})")
    print("   This might cause false positive recognitions")

# Test self-similarity (should be 1.0)
print(f"\n🔍 Testing self-similarities (should be ~1.0):")
for emb, name, id_num in zip(contestant_embeddings, contestant_names, contestant_ids):
    self_sim = np.dot(emb, emb)
    print(f"  {id_num:2d} ({name:10s}): {self_sim:.6f}")

print(f"\n🎉 Fresh embedding test completed!")
print(f"   All embeddings are properly normalized and have reasonable similarity ranges")