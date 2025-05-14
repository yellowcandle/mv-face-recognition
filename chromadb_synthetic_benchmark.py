#!/usr/bin/env python3
"""
Synthetic benchmark to compare standard face matching vs ChromaDB
without requiring the full face recognition pipeline.

This benchmark creates synthetic embeddings and tests the performance
of matching algorithms directly, which is where ChromaDB optimization applies.
"""

import time
import numpy as np
import argparse

# Check if ChromaDB is available
try:
    import chromadb

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Synthetic benchmark for ChromaDB vs standard matching"
    )

    parser.add_argument(
        "--embeddings",
        type=int,
        default=100,
        help="Number of reference embeddings (default: 100)",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=50,
        help="Number of query embeddings (default: 50)",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=512,
        help="Embedding dimensions (default: 512)",
    )
    parser.add_argument(
        "--iterations", type=int, default=5, help="Number of iterations (default: 5)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Similarity threshold (default: 0.6)",
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    return parser.parse_args()


def create_synthetic_embeddings(count, dimensions):
    """Create synthetic normalized embeddings."""
    # Create random vectors
    embeddings = np.random.randn(count, dimensions).astype(np.float32)

    # Normalize each vector to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized_embeddings = embeddings / norms

    return normalized_embeddings


def standard_matching(
    query_embeddings, reference_embeddings, threshold=0.6, verbose=False
):
    """Match using standard linear search approach."""
    start_time = time.time()

    matches = []

    for i, query in enumerate(query_embeddings):
        best_match = None
        best_score = 0

        # Linear search through all reference embeddings
        for j, ref in enumerate(reference_embeddings):
            # Cosine similarity (dot product of normalized vectors)
            similarity = np.dot(query, ref)

            if similarity > threshold and similarity > best_score:
                best_score = similarity
                best_match = j

        if best_match is not None:
            matches.append((i, best_match, best_score))

        if verbose and (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(query_embeddings)} queries")

    elapsed = time.time() - start_time

    return matches, elapsed


def chromadb_matching(
    query_embeddings, reference_embeddings, threshold=0.6, verbose=False, iteration=0
):
    """Match using ChromaDB."""
    if not HAS_CHROMADB:
        return [], 0

    # Initialize ChromaDB (in memory)
    start_setup = time.time()
    collection_name = f"synthetic_embeddings_{iteration}_{int(time.time())}"
    client = chromadb.Client()
    collection = client.create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"}
    )

    # Add reference embeddings to collection
    collection.add(
        embeddings=[emb.tolist() for emb in reference_embeddings],
        ids=[f"ref_{i}" for i in range(len(reference_embeddings))],
        metadatas=[{"index": i} for i in range(len(reference_embeddings))],
    )
    setup_time = time.time() - start_setup

    if verbose:
        print(f"ChromaDB setup time: {setup_time:.4f}s")

    # Perform queries
    start_time = time.time()

    matches = []

    for i, query in enumerate(query_embeddings):
        # Query ChromaDB
        results = collection.query(
            query_embeddings=[query.tolist()],
            n_results=1,
            include=["metadatas", "distances"],
        )

        # ChromaDB returns distance (0-2), convert to similarity (0-1)
        if results["distances"][0]:
            distance = results["distances"][0][0]
            similarity = 1.0 - (distance / 2.0)

            if similarity > threshold:
                ref_idx = results["metadatas"][0][0]["index"]
                matches.append((i, ref_idx, similarity))

        if verbose and (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(query_embeddings)} queries")

    elapsed = time.time() - start_time

    return matches, elapsed


def run_benchmark(args):
    """Run the benchmark with given parameters."""
    print("Running synthetic benchmark with:")
    print(f"  Reference embeddings: {args.embeddings}")
    print(f"  Query embeddings: {args.queries}")
    print(f"  Dimensions: {args.dimensions}")
    print(f"  Iterations: {args.iterations}")
    print(f"  Threshold: {args.threshold}")

    # Results storage
    standard_times = []
    chromadb_times = []
    standard_match_counts = []
    chromadb_match_counts = []

    for iteration in range(args.iterations):
        print(f"\nIteration {iteration + 1}/{args.iterations}")

        # Create synthetic embeddings for this iteration
        reference_embeddings = create_synthetic_embeddings(
            args.embeddings, args.dimensions
        )
        query_embeddings = create_synthetic_embeddings(args.queries, args.dimensions)

        # Run standard matching
        print("Running standard matching...")
        std_matches, std_time = standard_matching(
            query_embeddings,
            reference_embeddings,
            threshold=args.threshold,
            verbose=args.verbose,
        )
        standard_times.append(std_time)
        standard_match_counts.append(len(std_matches))

        # Run ChromaDB matching if available
        if HAS_CHROMADB:
            print("Running ChromaDB matching...")
            chroma_matches, chroma_time = chromadb_matching(
                query_embeddings,
                reference_embeddings,
                threshold=args.threshold,
                iteration=iteration,
                verbose=args.verbose,
            )
            chromadb_times.append(chroma_time)
            chromadb_match_counts.append(len(chroma_matches))

        # Print iteration results
        print(f"Standard matching: {std_time:.4f}s, {len(std_matches)} matches")
        if HAS_CHROMADB:
            print(
                f"ChromaDB matching: {chroma_time:.4f}s, {len(chroma_matches)} matches"
            )

    # Compute and print overall results
    avg_std_time = np.mean(standard_times)
    avg_std_matches = np.mean(standard_match_counts)

    print("\n==== BENCHMARK RESULTS ====")
    print("Standard matching:")
    print(f"  Average time: {avg_std_time:.4f}s")
    print(f"  Average matches: {avg_std_matches:.1f}")

    if HAS_CHROMADB:
        avg_chroma_time = np.mean(chromadb_times)
        avg_chroma_matches = np.mean(chromadb_match_counts)

        speedup = avg_std_time / avg_chroma_time if avg_chroma_time > 0 else 0

        print("ChromaDB matching:")
        print(f"  Average time: {avg_chroma_time:.4f}s")
        print(f"  Average matches: {avg_chroma_matches:.1f}")
        print(f"  Speedup: {speedup:.2f}x")

        # Match consistency
        match_similarity = abs(avg_std_matches - avg_chroma_matches) / max(
            avg_std_matches, avg_chroma_matches
        )
        print(f"Match consistency: {(1 - match_similarity) * 100:.1f}%")

    # Scaling tests
    if args.embeddings <= 1000:
        print("\n==== SCALING TEST ====")
        print("Testing matching performance with increasing embedding counts:")

        embedding_counts = [100, 200, 500, 1000, 2000, 5000]
        std_scaling_times = []
        chroma_scaling_times = []

        for count in embedding_counts:
            if count > args.embeddings * 50:  # Limit the max size for performance
                break

            print(f"\nTesting with {count} reference embeddings...")

            # Create larger synthetic embeddings
            ref_embeddings = create_synthetic_embeddings(count, args.dimensions)
            query_embeddings = create_synthetic_embeddings(
                10, args.dimensions
            )  # Use fewer queries for scaling test

            # Standard matching
            _, std_time = standard_matching(
                query_embeddings, ref_embeddings, threshold=args.threshold
            )
            std_scaling_times.append(std_time)

            # ChromaDB matching
            if HAS_CHROMADB:
                _, chroma_time = chromadb_matching(
                    query_embeddings,
                    ref_embeddings,
                    threshold=args.threshold,
                    iteration=count,
                )
                chroma_scaling_times.append(chroma_time)

            print(
                f"Standard: {std_time:.4f}s, ChromaDB: {chroma_time:.4f}s"
                if HAS_CHROMADB
                else f"Standard: {std_time:.4f}s"
            )

        # Print scaling results
        print("\nScaling Results:")
        for i, count in enumerate(embedding_counts[: len(std_scaling_times)]):
            if HAS_CHROMADB and i < len(chroma_scaling_times):
                speedup = (
                    std_scaling_times[i] / chroma_scaling_times[i]
                    if chroma_scaling_times[i] > 0
                    else 0
                )
                print(
                    f"  {count} embeddings: Standard={std_scaling_times[i]:.4f}s, ChromaDB={chroma_scaling_times[i]:.4f}s, Speedup={speedup:.2f}x"
                )
            else:
                print(f"  {count} embeddings: Standard={std_scaling_times[i]:.4f}s")


def main():
    args = parse_args()

    if not HAS_CHROMADB:
        print(
            "WARNING: ChromaDB is not installed. Only standard matching will be benchmarked."
        )
        print("Install ChromaDB with: pip install chromadb>=0.4.18")

    run_benchmark(args)


if __name__ == "__main__":
    main()
