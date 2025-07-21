#!/usr/bin/env python3
"""
Quick analysis script to examine embedding distribution and identify potential issues
"""

import numpy as np
from pathlib import Path
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_contestant_info():
    """Load contestant information"""
    df = pd.read_csv("source/contestant_info.csv")
    contestants = {}
    for _, row in df.iterrows():
        contestant_id = str(row["編號"])
        contestants[contestant_id] = {
            "id": contestant_id,
            "name": row["姓名"],
            "nickname": row["暱稱"],
        }
    return contestants

def load_all_embeddings():
    """Load all contestant embeddings"""
    photo_dir = Path("source/photo/contestants")
    embeddings = {}
    contestants_info = load_contestant_info()
    
    for contestant_id, info in contestants_info.items():
        nickname = info['nickname']
        embedding_path = photo_dir / f"{nickname}_embedding.npy"
        
        try:
            if embedding_path.exists():
                embedding = np.load(embedding_path)
                embeddings[nickname] = embedding
                logger.debug(f"Loaded {nickname}: shape {embedding.shape}")
            else:
                logger.warning(f"No embedding found for {nickname}")
        except Exception as e:
            logger.error(f"Failed to load {nickname}: {e}")
    
    return embeddings

def calculate_pairwise_distances(embeddings):
    """Calculate all pairwise distances between embeddings"""
    names = list(embeddings.keys())
    n = len(names)
    distances = np.zeros((n, n))
    
    for i, name1 in enumerate(names):
        for j, name2 in enumerate(names):
            if i != j:
                emb1 = embeddings[name1].flatten()
                emb2 = embeddings[name2].flatten()
                
                # Use same distance calculation as face_detector.py
                euclidean_distance = np.linalg.norm(emb1 - emb2)
                
                # Calculate cosine similarity
                dot_product = np.dot(emb1, emb2)
                norm_product = np.linalg.norm(emb1) * np.linalg.norm(emb2)
                if norm_product > 0:
                    cosine_similarity = dot_product / norm_product
                    cosine_distance = 1.0 - cosine_similarity
                else:
                    cosine_distance = 1.0
                
                # Combined distance (same as face detector)
                combined_distance = 0.6 * euclidean_distance + 0.4 * cosine_distance
                distances[i, j] = combined_distance
    
    return names, distances

def main():
    print("Loading embeddings...")
    embeddings = load_all_embeddings()
    print(f"Loaded {len(embeddings)} embeddings")
    
    if len(embeddings) < 2:
        print("Need at least 2 embeddings for analysis")
        return
    
    print("\nCalculating pairwise distances...")
    names, distances = calculate_pairwise_distances(embeddings)
    
    # Find embedding shapes and check for consistency
    shapes = [embeddings[name].shape for name in names]
    unique_shapes = set(shapes)
    print(f"\nEmbedding shapes: {unique_shapes}")
    
    # Check if all embeddings are similar (potential corruption)
    mean_distance = np.mean(distances[np.nonzero(distances)])
    std_distance = np.std(distances[np.nonzero(distances)])
    min_distance = np.min(distances[np.nonzero(distances)])
    max_distance = np.max(distances[np.nonzero(distances)])
    
    print(f"\nDistance Statistics:")
    print(f"Mean distance: {mean_distance:.4f}")
    print(f"Std distance: {std_distance:.4f}")
    print(f"Min distance: {min_distance:.4f}")
    print(f"Max distance: {max_distance:.4f}")
    
    # Find closest pairs
    print(f"\n10 Closest Pairs:")
    flat_indices = np.argsort(distances.flatten())
    count = 0
    for idx in flat_indices:
        i, j = np.unravel_index(idx, distances.shape)
        if i != j and distances[i, j] > 0:  # Skip self-comparisons
            print(f"{names[i]} <-> {names[j]}: {distances[i, j]:.4f}")
            count += 1
            if count >= 10:
                break
    
    # Check for identical embeddings
    print(f"\nIdentical Embeddings Check:")
    identical_count = 0
    for idx in flat_indices:
        i, j = np.unravel_index(idx, distances.shape)
        if i != j and distances[i, j] < 0.001:  # Very small distance
            print(f"Very similar: {names[i]} <-> {names[j]}: {distances[i, j]:.8f}")
            identical_count += 1
    
    if identical_count == 0:
        print("No identical embeddings found")
    
    # Check the specific recognized contestants
    recognized = ['暐翹', 'Mei Mei']
    print(f"\nAnalyzing recognized contestants: {recognized}")
    
    for name in recognized:
        if name in embeddings:
            emb = embeddings[name].flatten()
            print(f"\n{name}:")
            print(f"  Shape: {embeddings[name].shape}")
            print(f"  Mean: {np.mean(emb):.4f}")
            print(f"  Std: {np.std(emb):.4f}")
            print(f"  Min: {np.min(emb):.4f}")
            print(f"  Max: {np.max(emb):.4f}")
            print(f"  Norm: {np.linalg.norm(emb):.4f}")
    
    # Check if these two are particularly close to each other or far from others
    if len(recognized) == 2 and all(name in names for name in recognized):
        idx1 = names.index(recognized[0])
        idx2 = names.index(recognized[1])
        between_distance = distances[idx1, idx2]
        
        # Average distance to all others
        avg_dist_1 = np.mean([distances[idx1, i] for i in range(len(names)) if i != idx1])
        avg_dist_2 = np.mean([distances[idx2, i] for i in range(len(names)) if i != idx2])
        
        print(f"\nRecognized pair analysis:")
        print(f"Distance between {recognized[0]} and {recognized[1]}: {between_distance:.4f}")
        print(f"Average distance {recognized[0]} to all others: {avg_dist_1:.4f}")
        print(f"Average distance {recognized[1]} to all others: {avg_dist_2:.4f}")
    
    print(f"\nConclusion:")
    if std_distance < 0.5:
        print("⚠️  Very low distance variation - embeddings may be too similar")
    if mean_distance > 8.0:
        print("⚠️  High mean distance - embeddings may have generation issues")
    if identical_count > 5:
        print("⚠️  Many identical embeddings detected")
    
    print(f"Recognition in video shows distances ~7.6-7.9, confidences ~0.2-0.24")
    print(f"Current threshold: 0.05 (very permissive)")

if __name__ == "__main__":
    main()