#!/usr/bin/env python3
"""
Simple Video Processing Test
Tests the face recognition pipeline with minimal dependencies
"""

import cv2
import numpy as np
from pathlib import Path
import json
import logging
from tqdm import tqdm

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_contestant_embeddings():
    """Load all contestant embeddings and metadata"""
    contestants_dir = Path('source/photo/contestants')
    embeddings = {}
    metadata = {}

    print("Loading contestant embeddings...")

    for i in range(1, 97):  # All 96 contestants
        try:
            # Load embedding
            embedding_file = contestants_dir / f'contestant_{i}_unified_embedding.npy'
            metadata_file = contestants_dir / f'contestant_{i}_embedding_metadata.json'

            if embedding_file.exists() and metadata_file.exists():
                embedding = np.load(embedding_file)

                with open(metadata_file, 'r', encoding='utf-8') as f:
                    contestant_metadata = json.load(f)

                embeddings[str(i)] = embedding
                metadata[str(i)] = contestant_metadata

        except Exception as e:
            logger.warning(f"Failed to load contestant {i}: {e}")

    print(f"Loaded {len(embeddings)} contestant embeddings")
    return embeddings, metadata

def calculate_similarity(embedding1, embedding2):
    """Calculate cosine similarity between two embeddings"""
    similarity = np.dot(embedding1, embedding2)
    return similarity

def recognize_face(face_embedding, contestant_embeddings, threshold=0.30):
    """Recognize a face by finding the best match"""
    best_match = None
    best_similarity = -1
    best_distance = float('inf')

    for contestant_id, contestant_embedding in contestant_embeddings.items():
        similarity = calculate_similarity(face_embedding, contestant_embedding)
        distance = 1.0 - similarity

        if distance < best_distance:
            best_distance = distance
            best_similarity = similarity
            best_match = contestant_id

    # Check if match is good enough
    if best_distance < threshold:
        return best_match, best_similarity, best_distance
    else:
        return None, best_similarity, best_distance

def process_video_simple(video_path, contestant_embeddings, metadata):
    """Process video with simple face detection and recognition"""
    print(f"Processing video: {video_path}")

    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"Video: {width}x{height}, {fps} FPS, {frame_count} frames")

    # Initialize face detector (OpenCV Haar cascades)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    # Processing stats
    recognition_results = {}
    frame_count_processed = 0
    faces_detected = 0
    faces_recognized = 0

    # Process every 12th frame (as per config)
    sample_rate = 12

    print("Processing frames...")
    with tqdm(total=frame_count // sample_rate) as pbar:
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Sample frames
            if frame_idx % sample_rate != 0:
                frame_idx += 1
                continue

            frame_count_processed += 1

            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

            for (x, y, w, h) in faces:
                faces_detected += 1

                # Extract face region
                face_roi = frame[y:y+h, x:x+w]

                # Simple preprocessing
                face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                face_resized = cv2.resize(face_gray, (64, 64))

                # Very basic embedding (just for testing)
                # In real system, this would use InsightFace or face_recognition
                face_flat = face_resized.flatten().astype(np.float32)
                face_norm = np.linalg.norm(face_flat)
                if face_norm > 0:
                    face_embedding = face_flat / face_norm
                else:
                    face_embedding = np.zeros_like(face_flat)

                # Pad to 512 dimensions
                if len(face_embedding) < 512:
                    padding = np.zeros(512 - len(face_embedding))
                    face_embedding = np.concatenate([face_embedding, padding])

                # Recognize face
                contestant_id, similarity, distance = recognize_face(
                    face_embedding, contestant_embeddings, threshold=0.30
                )

                if contestant_id:
                    faces_recognized += 1
                    contestant_name = metadata[contestant_id].get('name', f'Contestant {contestant_id}')

                    # Record recognition
                    if contestant_id not in recognition_results:
                        recognition_results[contestant_id] = {
                            'name': contestant_name,
                            'count': 0,
                            'similarities': [],
                            'distances': []
                        }

                    recognition_results[contestant_id]['count'] += 1
                    recognition_results[contestant_id]['similarities'].append(float(similarity))
                    recognition_results[contestant_id]['distances'].append(float(distance))

            frame_idx += 1
            if frame_count_processed % 10 == 0:
                pbar.update(10)

    cap.release()

    # Calculate statistics
    stats = {
        'frames_processed': frame_count_processed,
        'faces_detected': faces_detected,
        'faces_recognized': faces_recognized,
        'recognition_rate': faces_recognized / max(faces_detected, 1),
        'unique_contestants': len(recognition_results),
        'recognition_results': recognition_results
    }

    return stats

def main():
    """Main test function"""
    print("=== SIMPLE VIDEO PROCESSING TEST ===")

    # Load embeddings
    try:
        contestant_embeddings, metadata = load_contestant_embeddings()
        if not contestant_embeddings:
            print("❌ No embeddings loaded!")
            return
    except Exception as e:
        print(f"❌ Failed to load embeddings: {e}")
        return

    # Check for test video
    video_path = Path('source/videos/test_sample.mp4')
    if not video_path.exists():
        print(f"❌ Test video not found: {video_path}")
        return

    # Process video
    try:
        stats = process_video_simple(video_path, contestant_embeddings, metadata)

        print("\n=== PROCESSING RESULTS ===")
        print(f"Frames processed: {stats['frames_processed']}")
        print(f"Faces detected: {stats['faces_detected']}")
        print(f"Faces recognized: {stats['faces_recognized']}")
        print(".1f")
        print(f"Unique contestants recognized: {stats['unique_contestants']}")

        if stats['recognition_results']:
            print("\n=== RECOGNITION RESULTS ===")
            for contestant_id, data in sorted(
                stats['recognition_results'].items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:10]:  # Top 10
                avg_similarity = np.mean(data['similarities'])
                avg_distance = np.mean(data['distances'])
                print("2d"
                      "3.3f"
                      "3.3f")

        print("\n✅ Video processing test completed successfully!")

    except Exception as e:
        print(f"❌ Video processing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()