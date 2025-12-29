#!/usr/bin/env python3
"""
Benchmark script to compare standard face recognition performance with ChromaDB.
This script runs both approaches on the same videos and reports performance metrics.
"""

import argparse
import os
import sys
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

# Add src to path so we can import our modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import our modules
from src.detection.optimized_detector import OptimizedFaceDetector
from src.recognition.optimized_recognizer import OptimizedFaceRecognizer

# Try to import ChromaDB modules
try:
    from src.recognition.chromadb_recognizer import ChromaDBFaceRecognizer

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark ChromaDB vs Standard face recognition"
    )

    parser.add_argument(
        "--video", type=str, help="Video file to process (in source/videos/)"
    )
    parser.add_argument(
        "--iterations", type=int, default=3, help="Number of iterations to run"
    )
    parser.add_argument(
        "--frame-limit", type=int, default=100, help="Max frames to process"
    )
    parser.add_argument(
        "--contestants", type=int, default=5, help="Number of contestants to include"
    )
    parser.add_argument(
        "--plot", action="store_true", help="Generate performance plots"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    return parser.parse_args()


def load_contestants_data(num_contestants=None):
    """Load contestant information and return selected contestants."""
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info["編號"] = contestant_info["編號"].astype(str)

    all_contestants = contestant_info["暱稱"].tolist()

    if (
        num_contestants is not None
        and num_contestants > 0
        and num_contestants < len(all_contestants)
    ):
        # Take a sample of contestants
        selected_contestants = all_contestants[:num_contestants]
    else:
        selected_contestants = all_contestants

    return contestant_info, selected_contestants


def setup_recognizers(similarity_threshold=0.4):
    """Set up both standard and ChromaDB recognizers."""
    # Initialize face detector
    detector = OptimizedFaceDetector(
        confidence_threshold=0.3, skip_frames=0, tracking_duration=0
    )

    # Initialize standard recognizer
    std_recognizer = OptimizedFaceRecognizer(
        face_detector=detector,
        similarity_threshold=similarity_threshold,
        use_batch_processing=False,
        use_quantized_model=True,
    )

    # Initialize ChromaDB recognizer if available
    chroma_recognizer = None
    if HAS_CHROMADB:
        chroma_recognizer = ChromaDBFaceRecognizer(
            project_root=project_root,
            similarity_threshold=similarity_threshold,
            persistent=False,  # Use in-memory for benchmark
        )

    return detector, std_recognizer, chroma_recognizer


def load_embeddings(
    contestants_dir, contestant_info, selected_contestants, std_recognizer, detector
):
    """Load embeddings using the standard dictionary approach."""
    known_embeddings = {}

    for contestant in tqdm(selected_contestants, desc="Loading standard embeddings"):
        # Try to get pre-computed embedding
        embedding = std_recognizer.get_embedding(contestant)

        if embedding is not None:
            known_embeddings[contestant] = [embedding]
            continue

        # If not available, compute from contestant images
        try:
            contestant_number = contestant_info.loc[
                contestant_info["暱稱"] == contestant, "編號"
            ].values[0]

            contestant_path = os.path.join(contestants_dir, str(contestant_number))
            if not os.path.isdir(contestant_path):
                print(
                    f"Directory not found for contestant {contestant}: {contestant_path}"
                )
                continue

            # Get image paths
            image_paths = [
                os.path.join(contestant_path, f)
                for f in os.listdir(contestant_path)
                if f.lower().endswith((".jpg", ".png"))
            ]

            if not image_paths:
                print(f"No images found for contestant {contestant}")
                continue

            # Process first image only for now
            import cv2

            img = cv2.imread(image_paths[0])
            faces = detector.detect_faces(img)

            if not faces:
                print(f"No face detected for contestant {contestant}")
                continue

            # Extract and process face
            face_img = detector.extract_face(img, faces[0], padding=0.1)
            if face_img is None:
                print(f"Failed to extract face for contestant {contestant}")
                continue

            # Compute embedding
            preprocessed = std_recognizer.preprocess_face(face_img)
            embedding = std_recognizer.compute_embedding(preprocessed)

            # Save for future use
            known_embeddings[contestant] = [embedding]
            std_recognizer.save_embedding(contestant, embedding)

        except Exception as e:
            print(f"Error processing contestant {contestant}: {str(e)}")

    print(f"Loaded embeddings for {len(known_embeddings)} contestants")
    return known_embeddings


def load_chromadb_embeddings(
    contestants_dir,
    contestant_info,
    selected_contestants,
    std_recognizer,
    detector,
    chroma_recognizer,
):
    """Load embeddings into ChromaDB."""
    if not chroma_recognizer:
        print("ChromaDB recognizer not available.")
        return None

    # First load standard embeddings to dictionary
    temp_embeddings = {}
    for contestant in tqdm(selected_contestants, desc="Loading ChromaDB embeddings"):
        # Try to get pre-computed embedding
        embedding = std_recognizer.get_embedding(contestant)

        if embedding is not None:
            temp_embeddings[contestant] = [embedding]

    # Add all embeddings to ChromaDB in batch
    chroma_recognizer.add_embeddings_batch(temp_embeddings)

    print(f"Added {len(temp_embeddings)} embeddings to ChromaDB")
    return chroma_recognizer


def benchmark_matching(
    video_path,
    std_embeddings,
    chroma_embeddings,
    std_recognizer,
    detector,
    iterations=3,
    frame_limit=100,
    verbose=False,
):
    """Benchmark matching performance for both approaches."""
    import cv2

    # Ensure video file exists
    if not os.path.isfile(video_path):
        print(f"Video file not found: {video_path}")
        return

    # Check if we can use ChromaDB
    can_use_chromadb = chroma_embeddings is not None

    results = {
        "standard": {"times": [], "matches": []},
        "chromadb": {"times": [], "matches": []} if can_use_chromadb else None,
    }

    print(
        f"Benchmarking with {iterations} iterations, max {frame_limit} frames per iteration"
    )

    for iteration in range(iterations):
        print(f"\nIteration {iteration + 1}/{iterations}")

        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Failed to open video: {video_path}")
            return

        # Process frames
        frame_count = 0
        std_times = []
        std_matches = 0
        chroma_times = []
        chroma_matches = 0

        with tqdm(total=frame_limit, desc="Processing frames") as pbar:
            while frame_count < frame_limit:
                ret, frame = cap.read()
                if not ret:
                    break

                # Standard matching
                start_time = time.time()
                std_results = std_recognizer.identify_faces(frame, std_embeddings)
                std_time = time.time() - start_time
                std_times.append(std_time)
                std_matches += len(std_results)

                # ChromaDB matching if available
                if can_use_chromadb:
                    start_time = time.time()
                    chroma_results = chroma_embeddings.identify_faces(
                        frame, detector, std_recognizer
                    )
                    chroma_time = time.time() - start_time
                    chroma_times.append(chroma_time)
                    chroma_matches += len(chroma_results)

                frame_count += 1
                pbar.update(1)

                if verbose and frame_count % 10 == 0:
                    print(
                        f"Frame {frame_count}: Standard: {std_time:.4f}s, ChromaDB: {chroma_time:.4f}s"
                        if can_use_chromadb
                        else f"Frame {frame_count}: Standard: {std_time:.4f}s"
                    )

        # Close video
        cap.release()

        # Record results
        results["standard"]["times"].append(std_times)
        results["standard"]["matches"].append(std_matches)

        if can_use_chromadb:
            results["chromadb"]["times"].append(chroma_times)
            results["chromadb"]["matches"].append(chroma_matches)

    return results


def analyze_results(benchmark_results):
    """Analyze benchmark results and print statistics."""
    if not benchmark_results:
        print("No benchmark results to analyze.")
        return

    # Process standard results
    std_times = np.array(
        [item for sublist in benchmark_results["standard"]["times"] for item in sublist]
    )
    std_avg = np.mean(std_times) * 1000  # Convert to ms
    std_median = np.median(std_times) * 1000
    std_min = np.min(std_times) * 1000
    std_max = np.max(std_times) * 1000
    std_matches = sum(benchmark_results["standard"]["matches"])

    print("\nStandard Matching Performance:")
    print(f"  Average time per frame: {std_avg:.2f} ms")
    print(f"  Median time per frame: {std_median:.2f} ms")
    print(f"  Min/Max time per frame: {std_min:.2f}/{std_max:.2f} ms")
    print(f"  Total matches found: {std_matches}")

    # Process ChromaDB results if available
    if benchmark_results["chromadb"]:
        chroma_times = np.array(
            [
                item
                for sublist in benchmark_results["chromadb"]["times"]
                for item in sublist
            ]
        )
        chroma_avg = np.mean(chroma_times) * 1000  # Convert to ms
        chroma_median = np.median(chroma_times) * 1000
        chroma_min = np.min(chroma_times) * 1000
        chroma_max = np.max(chroma_times) * 1000
        chroma_matches = sum(benchmark_results["chromadb"]["matches"])

        speedup = std_avg / chroma_avg if chroma_avg > 0 else 0

        print("\nChromaDB Matching Performance:")
        print(f"  Average time per frame: {chroma_avg:.2f} ms")
        print(f"  Median time per frame: {chroma_median:.2f} ms")
        print(f"  Min/Max time per frame: {chroma_min:.2f}/{chroma_max:.2f} ms")
        print(f"  Total matches found: {chroma_matches}")

        print(f"\nSpeedup: {speedup:.2f}x faster with ChromaDB")

        # Compare match accuracy
        match_diff = abs(std_matches - chroma_matches)
        match_pct = 100 * (1 - match_diff / std_matches) if std_matches > 0 else 0

        print(f"Match accuracy: {match_pct:.1f}% agreement between methods")

        return {
            "standard": {
                "avg_ms": std_avg,
                "median_ms": std_median,
                "min_ms": std_min,
                "max_ms": std_max,
                "matches": std_matches,
            },
            "chromadb": {
                "avg_ms": chroma_avg,
                "median_ms": chroma_median,
                "min_ms": chroma_min,
                "max_ms": chroma_max,
                "matches": chroma_matches,
                "speedup": speedup,
            },
        }

    return {
        "standard": {
            "avg_ms": std_avg,
            "median_ms": std_median,
            "min_ms": std_min,
            "max_ms": std_max,
            "matches": std_matches,
        }
    }


def plot_results(benchmark_results, output_dir=None):
    """Generate performance comparison plots."""
    if not benchmark_results or not benchmark_results["chromadb"]:
        print("Cannot generate plots: ChromaDB results not available.")
        return

    if output_dir is None:
        output_dir = os.path.join(project_root, "benchmark_results")

    os.makedirs(output_dir, exist_ok=True)

    plt.figure(figsize=(10, 6))

    # Flatten times arrays
    std_times = (
        np.array(
            [
                item
                for sublist in benchmark_results["standard"]["times"]
                for item in sublist
            ]
        )
        * 1000
    )
    chroma_times = (
        np.array(
            [
                item
                for sublist in benchmark_results["chromadb"]["times"]
                for item in sublist
            ]
        )
        * 1000
    )

    # Plot histograms
    plt.hist(std_times, bins=30, alpha=0.7, label="Standard")
    plt.hist(chroma_times, bins=30, alpha=0.7, label="ChromaDB")

    plt.xlabel("Processing Time (ms)")
    plt.ylabel("Frequency")
    plt.title("Face Recognition Processing Time Distribution")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Save plot
    plt.savefig(os.path.join(output_dir, "time_distribution.png"))
    print(f"Plot saved to {os.path.join(output_dir, 'time_distribution.png')}")

    # Bar chart for average times
    plt.figure(figsize=(8, 5))

    avg_times = [np.mean(std_times), np.mean(chroma_times)]

    plt.bar(["Standard", "ChromaDB"], avg_times, color=["#3498db", "#2ecc71"])

    for i, v in enumerate(avg_times):
        plt.text(i, v + 1, f"{v:.1f} ms", ha="center")

    plt.ylabel("Average Time (ms)")
    plt.title("Average Face Recognition Processing Time")
    plt.grid(True, axis="y", alpha=0.3)

    # Save plot
    plt.savefig(os.path.join(output_dir, "average_time.png"))
    print(f"Plot saved to {os.path.join(output_dir, 'average_time.png')}")


def main():
    args = parse_args()

    if not HAS_CHROMADB:
        print(
            "WARNING: ChromaDB is not installed. Only standard matching will be benchmarked."
        )
        print("Install ChromaDB with: pip install chromadb>=0.4.18")

    # Setup paths
    contestants_dir = os.path.join(project_root, "source", "photo", "contestants")

    if args.video:
        videos_dir = os.path.join(project_root, "source", "videos")
        video_path = os.path.join(videos_dir, args.video)
    else:
        # Find first available video
        videos_dir = os.path.join(project_root, "source", "videos")
        video_files = [
            f
            for f in os.listdir(videos_dir)
            if os.path.isfile(os.path.join(videos_dir, f))
            and f.lower().endswith((".mp4", ".avi"))
        ]
        if not video_files:
            print(f"No video files found in {videos_dir}")
            return
        video_path = os.path.join(videos_dir, video_files[0])

    print(f"Using video: {os.path.basename(video_path)}")

    # Load contestant data
    contestant_info, selected_contestants = load_contestants_data(args.contestants)
    print(f"Using {len(selected_contestants)} contestants")

    # Setup recognizers
    detector, std_recognizer, chroma_recognizer = setup_recognizers()

    # Load standard embeddings
    std_embeddings = load_embeddings(
        contestants_dir, contestant_info, selected_contestants, std_recognizer, detector
    )

    # Load ChromaDB embeddings if available
    chroma_embeddings = None
    if HAS_CHROMADB:
        chroma_embeddings = load_chromadb_embeddings(
            contestants_dir,
            contestant_info,
            selected_contestants,
            std_recognizer,
            detector,
            chroma_recognizer,
        )

    # Run benchmark
    results = benchmark_matching(
        video_path,
        std_embeddings,
        chroma_embeddings,
        std_recognizer,
        detector,
        iterations=args.iterations,
        frame_limit=args.frame_limit,
        verbose=args.verbose,
    )

    # Analyze and report results
    analysis = analyze_results(results)

    # Generate plots if requested
    if args.plot and analysis and "chromadb" in analysis:
        plot_results(results)


if __name__ == "__main__":
    main()
