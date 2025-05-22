import os
import sys
import time
from pathlib import Path

import cv2
import insightface
import mediapipe as mp
import numpy as np
import pandas as pd


class FaceDetectionComparison:
    def __init__(self):
        # Initialize MediaPipe
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_face_detector = self.mp_face_detection.FaceDetection(
            model_selection=1,  # 0 for short-range, 1 for full-range
            min_detection_confidence=0.5,
        )

        # Initialize InsightFace with recognition
        self.insightface_detector = insightface.app.FaceAnalysis(
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        self.insightface_detector.prepare(ctx_id=0, det_size=(640, 640))

        # Update paths for contestant data
        self.contestants_dir = Path("source/photo/contestants")
        self.contestant_info_path = Path("contestant_info.csv")
        self.contestant_db = self.load_contestant_database()

    def load_contestant_database(self):
        database = {}

        # Check if directories and files exist
        if not self.contestants_dir.exists():
            print(f"Warning: contestants directory not found at {self.contestants_dir}")
            return database

        if not self.contestant_info_path.exists():
            print(f"Warning: contestant info CSV not found at {self.contestant_info_path}")
            return database

        # Load contestant information
        try:
            contestant_info = pd.read_csv(self.contestant_info_path)
            # Convert 編號 to string to match folder names
            contestant_info["編號"] = contestant_info["編號"].astype(str)
        except Exception as e:
            print(f"Error reading contestant info CSV: {e}")
            return database

        # Process each contestant photo
        for folder in self.contestants_dir.iterdir():
            if not folder.is_dir():
                continue

            contestant_id = folder.name  # This should be the number

            # Get contestant info from CSV using the folder number
            contestant_row = contestant_info[contestant_info["編號"] == contestant_id]
            if contestant_row.empty:
                print(f"Warning: No info found for contestant folder {contestant_id}")
                continue

            # Use 暱稱 (nickname) instead of 姓名
            nickname = contestant_row["暱稱"].iloc[0]

            # Look for jpg files in the contestant folder
            photo_files = list(folder.glob("*.jpg"))
            if not photo_files:
                print(f"Warning: No jpg files found for contestant {nickname} ({contestant_id})")
                continue

            # Use the first jpg file found
            img = cv2.imread(str(photo_files[0]))
            if img is None:
                print(f"Warning: Could not load image for {nickname} ({contestant_id})")
                continue

            faces = self.insightface_detector.get(img)
            if not faces:
                print(f"Warning: No face found in reference image for {nickname} ({contestant_id})")
                continue

            # Store both embedding and contestant info
            database[contestant_id] = {
                "embedding": faces[0].embedding,
                "name": nickname,
                "info": contestant_row.to_dict("records")[0],
            }

        print(f"Loaded {len(database)} contestants into database")
        return database

    def identify_face(self, face_embedding):
        if not self.contestant_db:
            return "Unknown"

        # Find the closest matching face
        min_dist = float("inf")
        best_match = {"name": "Unknown"}

        for _contestant_id, data in self.contestant_db.items():
            dist = np.linalg.norm(face_embedding - data["embedding"])
            if dist < min_dist and dist < 0.6:  # Threshold for matching
                min_dist = dist
                best_match = data

        return best_match["name"]

    def detect_faces_mediapipe(self, image):
        start_time = time.time()

        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.mp_face_detector.process(image_rgb)

        processing_time = time.time() - start_time
        faces = []

        if results.detections:
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                h, w, _ = image.shape
                x, y = int(bbox.xmin * w), int(bbox.ymin * h)
                width, height = int(bbox.width * w), int(bbox.height * h)
                faces.append({"bbox": (x, y, width, height), "confidence": detection.score[0]})

        return faces, processing_time

    def detect_faces_insightface(self, image):
        start_time = time.time()

        faces = self.insightface_detector.get(image)
        processing_time = time.time() - start_time

        results = []
        for face in faces:
            bbox = face.bbox.astype(int)
            # Get identity if available
            identity = self.identify_face(face.embedding)
            results.append(
                {
                    "bbox": (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]),
                    "confidence": face.det_score,
                    "identity": identity,
                }
            )

        return results, processing_time

    def draw_faces(self, image, faces, color=(0, 255, 0)):
        img_copy = image.copy()
        for face in faces:
            x, y, w, h = face["bbox"]
            cv2.rectangle(img_copy, (x, y), (x + w, y + h), color, 2)
            # Add both confidence and identity
            label = f"{face['confidence']:.2f} {face.get('identity', 'Unknown')}"
            cv2.putText(img_copy, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return img_copy

    def compare_on_image(self, image):
        if image is None:
            print("Could not read image")
            return None

        # MediaPipe detection
        mp_faces, mp_time = self.detect_faces_mediapipe(image)
        mp_result = self.draw_faces(image, mp_faces, (0, 255, 0))  # Green for MediaPipe

        # InsightFace detection
        if_faces, if_time = self.detect_faces_insightface(image)
        if_result = self.draw_faces(image, if_faces, (0, 0, 255))  # Red for InsightFace

        # Combine results
        combined = np.hstack((mp_result, if_result))

        # Add labels
        cv2.putText(
            combined,
            f"MediaPipe ({len(mp_faces)} faces, {mp_time:.3f}s)",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            combined,
            f"InsightFace ({len(if_faces)} faces, {if_time:.3f}s)",
            (image.shape[1] + 10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )

        return {
            "combined_image": combined,
            "mediapipe": {"faces": len(mp_faces), "time": mp_time},
            "insightface": {"faces": len(if_faces), "time": if_time},
        }


def main():
    # Get video path from command line argument or use default
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        print("Usage: python face_detection_comparison.py <path_to_video>")
        print("Example: python face_detection_comparison.py videos/sample.mp4")
        sys.exit(1)

    # Validate video file exists
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        sys.exit(1)

    comparison = FaceDetectionComparison()

    # Open the video file
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        print("Make sure the video file is a valid video format (e.g., .mp4, .avi)")
        cap.release()
        sys.exit(1)

    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Create output directory with absolute path
    output_dir = Path.cwd() / "comparison_results"
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutput directory created at: {output_dir.absolute()}")

    # Initialize statistics
    total_mp_time = 0
    total_if_time = 0
    total_mp_faces = 0
    total_if_faces = 0
    frame_count = 0

    # Sample every 5 seconds (adjust fps * 5 for different intervals)
    sample_interval = fps * 5
    current_frame = 0

    while current_frame < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()

        if not ret:
            break

        print(f"\nProcessing frame {current_frame}/{total_frames} ({current_frame / fps:.1f}s)")

        results = comparison.compare_on_image(frame)
        if results is None:
            continue

        # Save the comparison image
        timestamp = current_frame / fps
        output_path = output_dir / f"comparison_{timestamp:.1f}s.jpg"
        success = cv2.imwrite(str(output_path), results["combined_image"])
        if success:
            print(f"Saved comparison image to: {output_path}")
        else:
            print(f"Failed to save image to: {output_path}")

        # Accumulate statistics
        total_mp_time += results["mediapipe"]["time"]
        total_if_time += results["insightface"]["time"]
        total_mp_faces += results["mediapipe"]["faces"]
        total_if_faces += results["insightface"]["faces"]
        frame_count += 1

        print(
            f"MediaPipe: {results['mediapipe']['faces']} faces in {results['mediapipe']['time']:.3f}s"
        )
        print(
            f"InsightFace: {results['insightface']['faces']} faces in {results['insightface']['time']:.3f}s"
        )

        current_frame += sample_interval

    cap.release()

    # Print summary
    if frame_count > 0:
        print("\nSummary:")
        print(f"Processed {frame_count} frames")
        print(
            f"MediaPipe - Avg time: {total_mp_time / frame_count:.3f}s, Total faces: {total_mp_faces}, Avg faces per frame: {total_mp_faces / frame_count:.1f}"
        )
        print(
            f"InsightFace - Avg time: {total_if_time / frame_count:.3f}s, Total faces: {total_if_faces}, Avg faces per frame: {total_if_faces / frame_count:.1f}"
        )


if __name__ == "__main__":
    main()
