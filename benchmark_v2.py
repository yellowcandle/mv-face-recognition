#!/usr/bin/env python3
"""
Benchmark script to compare standard face recognition with ChromaDB on v2.mp4 video.
"""

import os
import sys
import time

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

# Add the project root to PYTHONPATH for module imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

try:
    # Import face detection and recognition modules
    from src.detection.optimized_detector import OptimizedFaceDetector
    from src.recognition.optimized_recognizer import OptimizedFaceRecognizer

    # Try to import ChromaDB recognizer
    try:
        from src.recognition.chromadb_recognizer import ChromaDBFaceRecognizer

        HAS_CHROMADB = True
        print("ChromaDB is available.")
    except ImportError:
        HAS_CHROMADB = False
        print("ChromaDB is not available. Only standard matching will be tested.")

except ImportError as e:
    print(f"Error importing required modules: {e}")
    print(
        "Please check that all required modules are installed and you're running the script from the project root."
    )
    sys.exit(1)


def load_contestant_data():
    """Load contestant information and photos."""
    # Path to contestant info CSV
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")

    # Check if file exists
    if not os.path.isfile(contestant_info_path):
        print(f"Contestant info file not found: {contestant_info_path}")
        sys.exit(1)

    # Load contestant data
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info["編號"] = contestant_info["編號"].astype(str)

    # Get contestant nicknames
    all_contestants = contestant_info["暱稱"].tolist()

    # For benchmark purpose, just use a subset
    selected_contestants = all_contestants[:30]  # Use 30 contestants for benchmark
    print(f"Using {len(selected_contestants)} contestants for benchmark")

    return contestant_info, selected_contestants


def setup_components():
    """Set up face detection and recognition components."""
    # Initialize face detector
    detector = OptimizedFaceDetector(
        confidence_threshold=0.3,
        skip_frames=0,  # No frame skipping in detector for benchmark
        tracking_duration=0,  # No tracking for benchmark
    )

    # Initialize face recognizer
    recognizer = OptimizedFaceRecognizer(
        face_detector=detector,
        similarity_threshold=0.4,
        use_batch_processing=False,
        use_quantized_model=True,
    )

    # Initialize ChromaDB recognizer if available
    chroma_recognizer = None
    if HAS_CHROMADB:
        chroma_recognizer = ChromaDBFaceRecognizer(
            project_root=project_root,
            similarity_threshold=0.4,
            persistent=False,  # Use in-memory database for benchmark
        )

    return detector, recognizer, chroma_recognizer


def load_embeddings(contestants_dir, contestant_info, selected_contestants, recognizer, detector):
    """Load face embeddings for standard dictionary approach."""
    known_embeddings = {}

    for contestant in tqdm(selected_contestants, desc="Loading standard embeddings"):
        # Try to get pre-computed embedding
        embedding = recognizer.get_embedding(contestant)

        if embedding is not None:
            known_embeddings[contestant] = [embedding]
            continue

        # If not available, compute from contestant photos
        try:
            contestant_number = contestant_info.loc[
                contestant_info["暱稱"] == contestant, "編號"
            ].values[0]

            contestant_path = os.path.join(contestants_dir, str(contestant_number))
            if not os.path.isdir(contestant_path):
                print(f"Directory not found for contestant {contestant}: {contestant_path}")
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

            # Process first image only
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
            preprocessed = recognizer.preprocess_face(face_img)
            embedding = recognizer.compute_embedding(preprocessed)

            # Save embedding
            known_embeddings[contestant] = [embedding]
            recognizer.save_embedding(contestant, embedding)

        except Exception as e:
            print(f"Error processing contestant {contestant}: {str(e)}")

    print(f"Loaded {len(known_embeddings)} contestant embeddings")
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

    # First load standard embeddings to dictionary for batch processing
    temp_embeddings = {}
    for contestant in tqdm(selected_contestants, desc="Loading ChromaDB embeddings"):
        embedding = std_recognizer.get_embedding(contestant)
        if embedding is not None:
            temp_embeddings[contestant] = [embedding]

    # Add all embeddings to ChromaDB in batch
    if temp_embeddings:
        print(f"Adding {len(temp_embeddings)} embeddings to ChromaDB...")
        chroma_recognizer.add_embeddings_batch(temp_embeddings)

    # Process missing embeddings
    missing_contestants = [c for c in selected_contestants if c not in temp_embeddings]
    if missing_contestants:
        print(f"Computing embeddings for {len(missing_contestants)} contestants...")

        for contestant in tqdm(missing_contestants, desc="Computing missing embeddings"):
            try:
                contestant_number = contestant_info.loc[
                    contestant_info["暱稱"] == contestant, "編號"
                ].values[0]

                contestant_path = os.path.join(contestants_dir, str(contestant_number))
                if not os.path.isdir(contestant_path):
                    print(f"Directory not found for contestant {contestant}: {contestant_path}")
                    continue

                # Get images
                image_paths = [
                    os.path.join(contestant_path, f)
                    for f in os.listdir(contestant_path)
                    if f.lower().endswith((".jpg", ".png"))
                ]

                if not image_paths:
                    print(f"No images found for contestant {contestant}")
                    continue

                # Process first image
                img = cv2.imread(image_paths[0])
                faces = detector.detect_faces(img)

                if not faces:
                    print(f"No face detected for contestant {contestant}")
                    continue

                # Extract face
                face_img = detector.extract_face(img, faces[0], padding=0.1)
                if face_img is None:
                    print(f"Failed to extract face for contestant {contestant}")
                    continue

                # Compute embedding
                preprocessed = std_recognizer.preprocess_face(face_img)
                embedding = std_recognizer.compute_embedding(preprocessed)

                # Add to ChromaDB
                chroma_recognizer.add_embedding(
                    face_id=contestant,
                    embedding=embedding,
                    metadata={"name": contestant},
                )

                # Also save for standard recognizer
                std_recognizer.save_embedding(contestant, embedding)

            except Exception as e:
                print(f"Error processing contestant {contestant}: {str(e)}")

    collection_count = chroma_recognizer.collection.count() if chroma_recognizer.collection else 0
    print(f"ChromaDB contains {collection_count} embeddings")
    return chroma_recognizer


def benchmark_video_processing(
    video_path,
    std_embeddings,
    chroma_recognizer,
    std_recognizer,
    detector,
    frame_limit=100,
):
    """Run benchmark comparing standard dictionary matching vs ChromaDB on a video."""
    # Make sure video exists
    if not os.path.isfile(video_path):
        print(f"Video file not found: {video_path}")
        return

    print(f"Benchmarking on video: {os.path.basename(video_path)}")
    print(f"Frame limit: {frame_limit}")

    # Check if ChromaDB recognizer is available
    has_chromadb = chroma_recognizer is not None

    # Results tracking
    std_times = []
    std_matches = []
    chroma_times = []
    chroma_matches = []

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return

    # Process frames
    frame_count = 0

    with tqdm(total=frame_limit, desc="Processing frames") as pbar:
        while frame_count < frame_limit:
            ret, frame = cap.read()
            if not ret:
                break

            # Process with standard matching
            start_time = time.time()
            std_results = std_recognizer.identify_faces(frame, std_embeddings)
            std_time = time.time() - start_time
            std_times.append(std_time)
            std_matches.append(len(std_results))

            # Process with ChromaDB if available
            if has_chromadb:
                start_time = time.time()
                chroma_results = chroma_recognizer.identify_faces(frame, detector, std_recognizer)
                chroma_time = time.time() - start_time
                chroma_times.append(chroma_time)
                chroma_matches.append(len(chroma_results))

            # Update progress
            frame_count += 1
            pbar.update(1)

            # Print some intermediate results every 10 frames
            if frame_count % 10 == 0:
                print(f"\nFrame {frame_count}:")
                print(f"  Standard: {std_time:.4f}s, {len(std_results)} matches")
                if has_chromadb:
                    print(f"  ChromaDB: {chroma_time:.4f}s, {len(chroma_results)} matches")

    # Clean up
    cap.release()

    # Calculate statistics
    avg_std_time = np.mean(std_times)
    avg_std_matches = np.mean(std_matches)

    # Print results
    print("\n===== BENCHMARK RESULTS =====")
    print("Standard Dictionary Matching:")
    print(f"  Average time per frame: {avg_std_time:.4f}s")
    print(f"  Total processing time: {sum(std_times):.4f}s")
    print(f"  Average matches per frame: {avg_std_matches:.2f}")
    print(f"  Total matches: {sum(std_matches)}")

    if has_chromadb:
        avg_chroma_time = np.mean(chroma_times)
        avg_chroma_matches = np.mean(chroma_matches)
        speedup = avg_std_time / avg_chroma_time if avg_chroma_time > 0 else 0

        print("\nChromaDB Matching:")
        print(f"  Average time per frame: {avg_chroma_time:.4f}s")
        print(f"  Total processing time: {sum(chroma_times):.4f}s")
        print(f"  Average matches per frame: {avg_chroma_matches:.2f}")
        print(f"  Total matches: {sum(chroma_matches)}")
        print(f"  Speedup factor: {speedup:.2f}x")

        # Compare match accuracy
        if sum(std_matches) > 0:
            match_accuracy = sum(chroma_matches) / sum(std_matches) * 100
            print(f"  Match accuracy: {match_accuracy:.1f}%")

    return {
        "standard": {
            "times": std_times,
            "matches": std_matches,
            "avg_time": avg_std_time,
            "total_time": sum(std_times),
            "total_matches": sum(std_matches),
        },
        "chromadb": {
            "times": chroma_times,
            "matches": chroma_matches,
            "avg_time": avg_chroma_time if has_chromadb else None,
            "total_time": sum(chroma_times) if has_chromadb else None,
            "total_matches": sum(chroma_matches) if has_chromadb else None,
            "speedup": speedup if has_chromadb else None,
        }
        if has_chromadb
        else None,
    }


def main():
    """Main benchmark script."""
    # Set paths
    contestants_dir = os.path.join(project_root, "source", "photo", "contestants")
    video_path = os.path.join(project_root, "source", "videos", "v2.mp4")

    # Check if files and directories exist
    if not os.path.isdir(contestants_dir):
        print(f"Contestants directory not found: {contestants_dir}")
        sys.exit(1)

    if not os.path.isfile(video_path):
        print(f"Video file not found: {video_path}")
        sys.exit(1)

    # Load contestant data
    contestant_info, selected_contestants = load_contestant_data()

    # Set up components
    detector, std_recognizer, chroma_recognizer = setup_components()

    # Load standard embeddings
    std_embeddings = load_embeddings(
        contestants_dir, contestant_info, selected_contestants, std_recognizer, detector
    )

    # Load ChromaDB embeddings if available
    if HAS_CHROMADB:
        chroma_recognizer = load_chromadb_embeddings(
            contestants_dir,
            contestant_info,
            selected_contestants,
            std_recognizer,
            detector,
            chroma_recognizer,
        )

    # Run benchmark (100 frames)
    results = benchmark_video_processing(
        video_path,
        std_embeddings,
        chroma_recognizer,
        std_recognizer,
        detector,
        frame_limit=100,
    )

    # Add additional scaling test for embedding counts
    if HAS_CHROMADB and chroma_recognizer is not None:
        print("\n\n===== SCALING TEST: EMBEDDING COUNT =====")
        print("Testing how performance scales with number of embeddings")

        # Create different sizes of embedding subsets
        embedding_counts = [10, 50, 100, 200, 500]
        for count in embedding_counts:
            if count <= len(selected_contestants):
                subset = selected_contestants[:count]

                print(f"\nTesting with {count} embeddings:")

                # Create subset of standard embeddings
                subset_std_embeddings = {
                    k: std_embeddings[k] for k in subset if k in std_embeddings
                }

                # Create new ChromaDB collection for this test
                test_chroma = ChromaDBFaceRecognizer(
                    project_root=project_root,
                    similarity_threshold=0.4,
                    persistent=False,
                    collection_name=f"test_{count}_embeddings_{int(time.time())}",  # Unique name
                )

                # Add subset of embeddings
                subset_dict = {k: std_embeddings[k] for k in subset if k in std_embeddings}
                test_chroma.add_embeddings_batch(subset_dict)

                # Test on 10 frames
                test_results = benchmark_video_processing(
                    video_path,
                    subset_std_embeddings,
                    test_chroma,
                    std_recognizer,
                    detector,
                    frame_limit=10,
                )

                if test_results and test_results["chromadb"]:
                    speedup = (
                        test_results["standard"]["avg_time"] / test_results["chromadb"]["avg_time"]
                    )
                    print(f"  {count} embeddings: Speedup = {speedup:.2f}x")


if __name__ == "__main__":
    main()
