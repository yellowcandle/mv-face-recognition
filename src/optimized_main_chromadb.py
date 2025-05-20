import argparse
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple, Union

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from src.detection.optimized_detector import OptimizedFaceDetector
from src.recognition.optimized_recognizer import OptimizedFaceRecognizer
from src.utils.performance import profile_execution
from src.utils.test_image_optimizer import TestImageOptimizer

# Import ChromaDBFaceRecognizer (with fallback for backward compatibility)
try:
    from src.recognition.chromadb_recognizer import ChromaDBFaceRecognizer

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Optimized Face Recognition for Videos")

    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.4,
        help="Distance threshold for face matching (default: 0.4)",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=5,
        help="Number of frames to skip between processing (default: 5)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Batch size for processing (default: 4)",
    )
    parser.add_argument(
        "--use-tracking", action="store_true", help="Use face tracking between frames"
    )
    parser.add_argument(
        "--parallel", action="store_true", help="Use parallel processing where possible"
    )
    parser.add_argument("--save-frames", action="store_true", help="Save annotated frames")
    parser.add_argument("--save-video", action="store_true", help="Save annotated video")
    parser.add_argument("--debug", action="store_true", help="Print debug information")

    parser.add_argument(
        "--test-images",
        action="store_true",
        help="Process test images in source/images/test",
    )
    parser.add_argument(
        "--optimize-cache",
        action="store_true",
        help="Preload and optimize cache for faster processing",
    )

    # Add ChromaDB option
    parser.add_argument(
        "--use-chromadb",
        action="store_true",
        help="Use ChromaDB for faster face matching",
    )
    parser.add_argument(
        "--in-memory-db",
        action="store_true",
        help="Use in-memory ChromaDB (faster but not persistent)",
    )

    return parser.parse_args()


def select_items(options, item_type):
    """Allow user to select items from a list."""
    print(f"\nAvailable {item_type}:")
    for idx, name in enumerate(options, 1):
        print(f"{idx}. {name}")
    print(f"{len(options) + 1}. Select all")

    indices = input(
        f"\nEnter the numbers of the {item_type} you want to select, separated by commas (e.g., 1,3,5), or '{len(options) + 1}' to select all: "
    )

    if indices.strip() == str(len(options) + 1):
        return options

    selected_indices = [int(i.strip()) - 1 for i in indices.split(",") if i.strip().isdigit()]
    selected_items = [options[i] for i in selected_indices if 0 <= i < len(options)]
    return selected_items


@profile_execution
def load_known_embeddings(
    contestants_dir: str,
    contestant_info: pd.DataFrame,
    selected_contestants: List[str],
    recognizer: OptimizedFaceRecognizer,
    detector: OptimizedFaceDetector,
    use_chromadb: bool = False,
    persistent: bool = True,
) -> Union[Dict[str, List[np.ndarray]], ChromaDBFaceRecognizer]:
    """
    Load or compute embeddings for selected contestants.

    Args:
        contestants_dir: Directory containing contestant photos
        contestant_info: DataFrame with contestant information
        selected_contestants: List of selected contestant names
        recognizer: Face recognizer instance
        detector: Face detector instance
        use_chromadb: Whether to use ChromaDB for storage/matching
        persistent: Whether to use persistent ChromaDB storage

    Returns:
        Either a dictionary of embeddings or a ChromaDBFaceRecognizer instance
    """
    # Check if ChromaDB should be used
    if use_chromadb:
        if not HAS_CHROMADB:
            print("ChromaDB not available. Install with: pip install chromadb")
            print("Falling back to standard dictionary matching.")
            use_chromadb = False
        else:
            print("Using ChromaDB for face matching (faster)")

    if use_chromadb and HAS_CHROMADB:
        # Initialize ChromaDB recognizer
        project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        chroma_recognizer = ChromaDBFaceRecognizer(
            project_root=project_root,
            similarity_threshold=recognizer.similarity_threshold,
            persistent=persistent,
        )

        # First load existing embeddings into a dictionary
        temp_embeddings = {}
        for contestant in tqdm(selected_contestants, desc="Loading embeddings"):
            # Try to get pre-computed embedding
            embedding = recognizer.get_embedding(contestant)

            if embedding is not None:
                temp_embeddings[contestant] = [embedding]

        # Add all embeddings to ChromaDB in a batch for better performance
        if temp_embeddings:
            print(f"Adding {len(temp_embeddings)} embeddings to ChromaDB...")
            chroma_recognizer.add_embeddings_batch(temp_embeddings)

        # Process contestants without pre-computed embeddings
        missing_contestants = [c for c in selected_contestants if c not in temp_embeddings]
        if missing_contestants:
            print(f"Computing embeddings for {len(missing_contestants)} contestants...")

            for contestant in tqdm(missing_contestants, desc="Computing missing embeddings"):
                try:
                    # Find contestant number
                    contestant_number = contestant_info.loc[
                        contestant_info["暱稱"] == contestant, "編號"
                    ].values[0]

                    # Get contestant directory
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

                    # Process first image only for now
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

                    # Add to ChromaDB
                    chroma_recognizer.add_embedding(
                        face_id=contestant,
                        embedding=embedding,
                        metadata={"name": contestant},
                    )

                    # Save for future use with standard recognizer too
                    recognizer.save_embedding(contestant, embedding)

                except Exception as e:
                    print(f"Error processing contestant {contestant}: {str(e)}")

        # Return the ChromaDB recognizer (which contains all embeddings)
        print(
            f"ChromaDB contains {chroma_recognizer.collection.count() if chroma_recognizer.collection else 0} embeddings"
        )
        return chroma_recognizer

    else:
        # Standard dictionary-based approach (original implementation)
        known_embeddings = {}

        for contestant in tqdm(selected_contestants, desc="Loading embeddings"):
            # Try to get pre-computed embedding
            embedding = recognizer.get_embedding(contestant)

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

                # Process first image only for now
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

                # Save for future use
                known_embeddings[contestant] = [embedding]
                recognizer.save_embedding(contestant, embedding)

            except Exception as e:
                print(f"Error processing contestant {contestant}: {str(e)}")

        print(f"Loaded embeddings for {len(known_embeddings)} contestants")
        return known_embeddings


@profile_execution
def process_test_images(
    recognizer: Union[OptimizedFaceRecognizer, ChromaDBFaceRecognizer],
    detector: OptimizedFaceDetector,
    args,
) -> List[Dict]:
    """
    Process test images from source/images/test directory.

    Args:
        recognizer: Face recognizer instance (either standard or ChromaDB)
        detector: Face detector instance
        args: Command line arguments

    Returns:
        list: Test image processing results
    """
    # For ChromaDB recognizer, we need to pass it to TestImageOptimizer differently
    if hasattr(recognizer, "match_face") and isinstance(recognizer, ChromaDBFaceRecognizer):
        # Using ChromaDB recognizer
        from src.recognition.optimized_recognizer import OptimizedFaceRecognizer

        std_recognizer = OptimizedFaceRecognizer(
            face_detector=detector, similarity_threshold=recognizer.similarity_threshold
        )
        optimizer = TestImageOptimizer(detector=detector, recognizer=std_recognizer)
        # TODO: Add ChromaDB support to TestImageOptimizer if needed
    else:
        optimizer = TestImageOptimizer(detector=detector, recognizer=recognizer)

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output",
        "test_images",
    )
    results = optimizer.process_test_images(output_dir=output_dir)
    return results


@profile_execution
def process_video(
    video_path: str,
    embeddings: Union[Dict[str, List[np.ndarray]], ChromaDBFaceRecognizer],
    recognizer: OptimizedFaceRecognizer,
    detector: OptimizedFaceDetector,
    args,
) -> Tuple[str, List[Dict]]:
    """
    Process a video for face recognition.

    Args:
        video_path: Path to video file
        embeddings: Either a dictionary of embeddings or a ChromaDBFaceRecognizer
        recognizer: Standard face recognizer instance
        detector: Face detector instance
        args: Command line arguments

    Returns:
        tuple: (output_video_path, recognition_results)
    """
    video_name = os.path.basename(video_path)
    print(f"\nProcessing video: {video_name}")

    # Check if we're using ChromaDB or standard dictionary
    using_chromadb = hasattr(embeddings, "match_face") and isinstance(
        embeddings, ChromaDBFaceRecognizer
    )

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {video_path}")

    # Get video properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Setup output paths
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frames_dir = os.path.join(project_root, "output_frames", os.path.splitext(video_name)[0])
    output_video_path = os.path.join(project_root, "output_mp4s", f"{video_name}_labeled.mp4")

    if args.save_frames:
        os.makedirs(frames_dir, exist_ok=True)

    # Setup video writer if needed
    out = None
    if args.save_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))

    # Process video frames
    frame_count = 0
    processed_count = 0
    detection_results = []

    # Track processing time to adjust frame skip dynamically
    processing_times = []
    adaptive_frame_skip = args.frame_skip

    with tqdm(total=total_frames, desc="Processing frames") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            pbar.update(1)

            # Adaptive frame skipping
            if frame_count % adaptive_frame_skip != 0:
                # Write original frame to output if saving video
                if args.save_video:
                    out.write(frame)
                continue

            start_time = time.time()

            # Detect and identify faces (using either ChromaDB or standard method)
            if using_chromadb:
                face_results = embeddings.identify_faces(frame, detector, recognizer)
                # Convert ChromaDB results to standard format if needed
                std_results = []
                for result in face_results:
                    std_results.append(
                        {
                            "bbox": result["bbox"],
                            "person_id": result["name"],
                            "confidence": result["confidence"] if "confidence" in result else 0.0,
                        }
                    )
                face_results = std_results
            else:
                face_results = recognizer.identify_faces(frame, embeddings)

            # Create annotated frame
            annotated_frame = frame.copy()

            # Draw bounding boxes and labels
            for result in face_results:
                bbox = result["bbox"]
                person_id = result["person_id"]
                confidence = result["confidence"]

                if person_id:
                    x1, y1, x2, y2 = map(int, bbox)

                    # Draw rectangle
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                    # Prepare label text
                    label = f"{person_id} ({confidence:.2f})"

                    # Draw background rectangle for text
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

                    cv2.rectangle(
                        annotated_frame,
                        (x1, y1 - label_size[1] - 10),
                        (x1 + label_size[0], y1),
                        (0, 255, 0),
                        cv2.FILLED,
                    )

                    # Draw text
                    cv2.putText(
                        annotated_frame,
                        label,
                        (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )

                    # Add to results
                    timestamp = frame_count / fps
                    detection_results.append(
                        {
                            "video": video_name,
                            "frame": frame_count,
                            "timestamp": timestamp,
                            "nickname": person_id,
                            "confidence": confidence,
                        }
                    )

            # Add timestamp to frame
            timestamp_seconds = frame_count / fps
            timestamp_formatted = "{:02}:{:02}".format(
                int(timestamp_seconds // 60), int(timestamp_seconds % 60)
            )

            cv2.putText(
                annotated_frame,
                timestamp_formatted,
                (frame_width - 100, frame_height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

            # Save frame if requested
            if args.save_frames:
                output_frame_path = os.path.join(frames_dir, f"frame_{frame_count:04d}.jpg")
                cv2.imwrite(output_frame_path, annotated_frame)

            # Write to output video if requested
            if args.save_video:
                out.write(annotated_frame)

            # Track processing time for adaptive frame skipping
            processing_time = time.time() - start_time
            processing_times.append(processing_time)

            if len(processing_times) > 10:
                # Calculate average processing time for last 10 frames
                avg_time = sum(processing_times[-10:]) / 10

                # Target: process no more than 2 frames per second
                target_time = 0.5  # seconds

                if avg_time > target_time:
                    # Increase frame skip to reduce load
                    adaptive_frame_skip = min(30, adaptive_frame_skip + 1)
                elif avg_time < target_time * 0.5:
                    # Decrease frame skip if processing is fast
                    adaptive_frame_skip = max(1, adaptive_frame_skip - 1)

                if args.debug and processed_count % 10 == 0:
                    print(
                        f"\nAvg processing time: {avg_time:.3f}s, Frame skip: {adaptive_frame_skip}"
                    )

            processed_count += 1

    # Cleanup
    cap.release()
    if args.save_video and out is not None:
        out.release()

    if args.debug:
        print(f"Processed {processed_count} of {total_frames} frames")

        # Print ChromaDB stats if used
        if using_chromadb:
            stats = embeddings.get_stats()
            print("\nChromaDB Stats:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

    return output_video_path, detection_results


def main():
    """Main function"""
    # Parse command-line arguments
    args = parse_arguments()

    # Check if ChromaDB is requested but not available
    if args.use_chromadb and not HAS_CHROMADB:
        print("WARNING: ChromaDB was requested but is not installed.")
        print("Install ChromaDB with: pip install chromadb>=0.4.18")
        print("Continuing with standard face matching...")

    # Initialize paths
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    contestants_dir = os.path.join(project_root, "source", "photo", "contestants")
    videos_dir = os.path.join(project_root, "source", "videos")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")

    # Make sure output directories exist
    os.makedirs(os.path.join(project_root, "output_frames"), exist_ok=True)
    os.makedirs(os.path.join(project_root, "output_mp4s"), exist_ok=True)

    # Load contestant information
    try:
        contestant_info = pd.read_csv(contestant_info_path)
        # Ensure 編號 is string type for directory matching
        contestant_info["編號"] = contestant_info["編號"].astype(str)
    except Exception as e:
        print(f"Error reading contestant info CSV: {e}")
        return

    # Initialize components
    detector = OptimizedFaceDetector(
        confidence_threshold=0.3,
        skip_frames=args.frame_skip if args.use_tracking else 0,
        tracking_duration=30 if args.use_tracking else 0,
    )

    recognizer = OptimizedFaceRecognizer(
        face_detector=detector,
        similarity_threshold=args.distance_threshold,
        use_batch_processing=args.parallel,
        use_quantized_model=True,
    )

    # If optimize-cache option is enabled, preload and optimize cache
    if args.optimize_cache:
        print("Preloading and optimizing cache...")
        optimizer = TestImageOptimizer(detector=detector, recognizer=recognizer)
        optimizer.preprocess_all_test_images()

    # If test-images option is enabled, process test images instead of videos
    if args.test_images:
        print("\nProcessing test images...")
        test_results = process_test_images(recognizer, detector, args)
        print(f"Processed {len(test_results)} test images")
        return

    # Select contestants
    all_contestants = contestant_info["暱稱"].tolist()
    selected_contestants = select_items(all_contestants, "contestants")
    if not selected_contestants:
        print("No contestants selected, exiting.")
        return

    # Load contestant embeddings
    embeddings = load_known_embeddings(
        contestants_dir,
        contestant_info,
        selected_contestants,
        recognizer,
        detector,
        use_chromadb=args.use_chromadb,
        persistent=not args.in_memory_db,
    )

    # Select videos
    all_videos = sorted(
        [
            f
            for f in os.listdir(videos_dir)
            if os.path.isfile(os.path.join(videos_dir, f)) and f.lower().endswith((".mp4", ".avi"))
        ]
    )
    if not all_videos:
        print(f"No video files found in {videos_dir}")
        return

    selected_videos = select_items(all_videos, "videos")
    if not selected_videos:
        print("No videos selected, exiting.")
        return

    # Process each video
    all_results = []
    for video_file in selected_videos:
        video_path = os.path.join(videos_dir, video_file)
        try:
            print(
                f"\nProcessing video: {video_file} {'with ChromaDB' if args.use_chromadb and HAS_CHROMADB else ''}"
            )
            _, results = process_video(video_path, embeddings, recognizer, detector, args)
            all_results.extend(results)
        except Exception as e:
            print(f"Error processing video {video_file}: {str(e)}")
            continue

    # Save results
    if all_results:
        results_df = pd.DataFrame(all_results)
        output_csv = os.path.join(project_root, "video_recognition_results.csv")
        results_df.to_csv(output_csv, index=False)
        print(f"\nResults saved to {output_csv}")

        # Print summary
        print("\nRecognition Summary:")
        summary = results_df.groupby(["video", "nickname"]).size().unstack(fill_value=0)
        print(summary)
    else:
        print("No faces recognized in videos.")

    # Print performance comparison if using ChromaDB
    if args.use_chromadb and HAS_CHROMADB and hasattr(embeddings, "get_stats"):
        stats = embeddings.get_stats()
        print("\nChromaDB Performance:")
        print(f"  Total embeddings: {stats.get('total_embeddings', 0)}")
        print(f"  Total queries: {stats.get('queries', 0)}")
        print(f"  Average query time: {stats.get('avg_query_time_ms', 0):.3f} ms")


if __name__ == "__main__":
    main()
