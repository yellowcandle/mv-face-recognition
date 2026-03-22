#!/usr/bin/env python3
"""
Modal YouTube Video Processing Pipeline for MV Face Recognition

This pipeline processes YouTube videos in 3 stages:
1. Download YouTube video and extract metadata
2. Sample frames and run face detection/recognition
3. Bootstrap embeddings using validated faces + supplied photos

Usage:
    # Process a YouTube URL from the queue
    modal run scripts/modal_youtube_processor.py --queue-id yt_video123_1234567890

    # Download and sample only (no recognition)
    modal run scripts/modal_youtube_processor.py --url "https://youtube.com/watch?v=..." --sample-only
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import tempfile

from modal import App, Image, Volume, Secret, method

# --- Modal Configuration ---

app = App("mv-youtube-processor")

# Docker image with all dependencies
modal_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "sqlite3")
    .pip_install(
        "yt-dlp>=2024.8.6",  # YouTube downloader
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "pillow>=11.3.0",
        "insightface>=0.7.3",
        "onnxruntime-gpu",
        "chromadb>=0.4.0",
        "torch>=2.8.0",
        "supervision>=0.19.0",
    )
    .add_local_dir("src", "/src")
)

# Persistent volume for data storage
volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")


@dataclass
class VideoMetadata:
    """Metadata extracted from YouTube video"""
    video_id: str
    title: str
    duration: float
    width: int
    height: int
    fps: float
    upload_date: str
    uploader: str
    thumbnail_url: str


@dataclass
class FaceDetection:
    """Face detection result for a single frame"""
    frame_number: int
    timestamp: float
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float
    recognition_result: Optional[str] = None  # Contestant name if recognized
    recognition_confidence: Optional[float] = None
    embedding: Optional[List[float]] = None
    frame_path: str = ""  # Path to saved frame image


# --- Stage 1: YouTube Download ---

@app.cls(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=3600,  # 1 hour timeout
    gpu="T4",  # GPU for faster processing
)
class YouTubeProcessor:
    """Modal class for processing YouTube videos"""

    @method()
    def download_video(self, youtube_url: str, queue_id: str) -> Dict:
        """
        Stage 1: Download YouTube video and extract metadata

        Args:
            youtube_url: YouTube video URL
            queue_id: Queue ID for tracking

        Returns:
            Dictionary with video metadata and download path
        """
        import yt_dlp

        print(f"[Stage 1] Downloading YouTube video: {youtube_url}")

        # Create directories
        download_dir = VOL_MOUNT_PATH / "youtube_downloads" / queue_id
        download_dir.mkdir(parents=True, exist_ok=True)

        # yt-dlp options
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(download_dir / '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'writeinfojson': True,  # Save metadata
            'writethumbnail': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download and get info
                info = ydl.extract_info(youtube_url, download=True)
                video_id = info['id']

                # Extract metadata
                metadata = VideoMetadata(
                    video_id=video_id,
                    title=info.get('title', ''),
                    duration=info.get('duration', 0),
                    width=info.get('width', 1920),
                    height=info.get('height', 1080),
                    fps=info.get('fps', 30),
                    upload_date=info.get('upload_date', ''),
                    uploader=info.get('uploader', ''),
                    thumbnail_url=info.get('thumbnail', ''),
                )

                # Find downloaded video file
                video_files = list(download_dir.glob(f"{video_id}.mp4"))
                if not video_files:
                    video_files = list(download_dir.glob(f"{video_id}.*"))

                if not video_files:
                    raise FileNotFoundError(f"Downloaded video not found in {download_dir}")

                video_path = str(video_files[0])

                # Commit volume changes
                volume.commit()

                print(f"✓ Downloaded: {metadata.title} ({metadata.duration}s)")
                print(f"  Path: {video_path}")

                return {
                    'success': True,
                    'video_path': video_path,
                    'metadata': asdict(metadata),
                    'queue_id': queue_id,
                }

        except Exception as e:
            print(f"✗ Download failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'queue_id': queue_id,
            }


    @method()
    def sample_and_detect_faces(
        self,
        video_path: str,
        queue_id: str,
        sample_interval: float = 2.0,
        max_samples: int = 100,
    ) -> Dict:
        """
        Stage 2: Sample frames and detect faces

        Args:
            video_path: Path to downloaded video
            queue_id: Queue ID for tracking
            sample_interval: Seconds between samples (default: 2.0)
            max_samples: Maximum number of frames to sample

        Returns:
            Dictionary with face detections and sample paths
        """
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis

        print(f"[Stage 2] Sampling frames from: {video_path}")

        # Initialize face detector
        face_app = FaceAnalysis(
            name='buffalo_l',
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        face_app.prepare(ctx_id=0, det_size=(640, 640))

        # Create output directory
        samples_dir = VOL_MOUNT_PATH / "youtube_samples" / queue_id
        samples_dir.mkdir(parents=True, exist_ok=True)

        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {
                'success': False,
                'error': f'Failed to open video: {video_path}',
                'queue_id': queue_id,
            }

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # Calculate sampling
        frame_interval = int(sample_interval * fps)
        sample_frames = list(range(0, total_frames, frame_interval))[:max_samples]

        print(f"  Video: {total_frames} frames, {fps:.2f} FPS, {duration:.2f}s")
        print(f"  Sampling: {len(sample_frames)} frames (every {sample_interval}s)")

        detections: List[FaceDetection] = []
        frames_with_faces = 0

        for frame_num in sample_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()

            if not ret:
                continue

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            faces = face_app.get(frame_rgb)

            if faces:
                frames_with_faces += 1
                timestamp = frame_num / fps

                for idx, face in enumerate(faces):
                    bbox = face.bbox.tolist()

                    # Save cropped face image
                    x1, y1, x2, y2 = map(int, bbox)
                    face_crop = frame_rgb[y1:y2, x1:x2]

                    face_filename = f"frame_{frame_num:06d}_face_{idx}.jpg"
                    face_path = samples_dir / face_filename

                    # Save as JPEG
                    from PIL import Image
                    face_img = Image.fromarray(face_crop)
                    face_img.save(face_path, 'JPEG', quality=95)

                    # Create detection record
                    detection = FaceDetection(
                        frame_number=frame_num,
                        timestamp=timestamp,
                        bbox=bbox,
                        confidence=float(face.det_score),
                        embedding=face.embedding.tolist() if hasattr(face, 'embedding') else None,
                        frame_path=str(face_path),
                    )
                    detections.append(detection)

        cap.release()

        # Save detections metadata
        detections_file = samples_dir / "detections.json"
        with open(detections_file, 'w') as f:
            json.dump([asdict(d) for d in detections], f, indent=2)

        # Commit volume changes
        volume.commit()

        print(f"✓ Sampled {len(sample_frames)} frames, found {len(detections)} faces in {frames_with_faces} frames")
        print(f"  Saved to: {samples_dir}")

        return {
            'success': True,
            'detections': [asdict(d) for d in detections],
            'total_faces': len(detections),
            'frames_with_faces': frames_with_faces,
            'samples_dir': str(samples_dir),
            'queue_id': queue_id,
        }


    @method()
    def recognize_faces(
        self,
        queue_id: str,
        chroma_collection_name: str = "contestant_faces",
    ) -> Dict:
        """
        Stage 2b: Run face recognition on detected faces

        Args:
            queue_id: Queue ID for tracking
            chroma_collection_name: ChromaDB collection name

        Returns:
            Dictionary with recognition results
        """
        import chromadb
        import numpy as np

        print(f"[Stage 2b] Running face recognition for: {queue_id}")

        # Load detections
        samples_dir = VOL_MOUNT_PATH / "youtube_samples" / queue_id
        detections_file = samples_dir / "detections.json"

        if not detections_file.exists():
            return {
                'success': False,
                'error': 'Detections file not found',
                'queue_id': queue_id,
            }

        with open(detections_file, 'r') as f:
            detections = json.load(f)

        # Initialize ChromaDB
        chroma_path = VOL_MOUNT_PATH / "chroma_db"
        chroma_path.mkdir(parents=True, exist_ok=True)

        client = chromadb.PersistentClient(path=str(chroma_path))

        try:
            collection = client.get_collection(name=chroma_collection_name)
            print(f"  Using existing collection: {chroma_collection_name}")
        except:
            print(f"  No existing collection found, skipping recognition")
            return {
                'success': True,
                'recognized_faces': 0,
                'queue_id': queue_id,
                'message': 'No embeddings available for recognition',
            }

        # Run recognition on each face
        recognized_count = 0

        for detection in detections:
            if detection.get('embedding'):
                embedding = np.array(detection['embedding'])

                # Query ChromaDB
                results = collection.query(
                    query_embeddings=[embedding.tolist()],
                    n_results=1,
                )

                if results['ids'] and results['distances']:
                    distance = results['distances'][0][0]
                    # Convert distance to similarity (0-1 scale)
                    similarity = 1.0 / (1.0 + distance)

                    if similarity > 0.4:  # Threshold for recognition
                        contestant_id = results['ids'][0][0]
                        detection['recognition_result'] = contestant_id
                        detection['recognition_confidence'] = similarity
                        recognized_count += 1

        # Save updated detections
        with open(detections_file, 'w') as f:
            json.dump(detections, f, indent=2)

        volume.commit()

        print(f"✓ Recognized {recognized_count}/{len(detections)} faces")

        return {
            'success': True,
            'recognized_faces': recognized_count,
            'total_faces': len(detections),
            'queue_id': queue_id,
        }


    @method()
    def bootstrap_embeddings(
        self,
        queue_id: str,
        use_supplied_photos: bool = True,
        contestant_metadata_path: str = "/data/metadata/contestant_info.csv",
    ) -> Dict:
        """
        Stage 3: Bootstrap embeddings from validated faces + supplied photos

        Args:
            queue_id: Queue ID for tracking
            use_supplied_photos: Include supplied contestant photos
            contestant_metadata_path: Path to contestant metadata CSV

        Returns:
            Dictionary with bootstrap results
        """
        import cv2
        import numpy as np
        import pandas as pd
        from insightface.app import FaceAnalysis
        import chromadb
        from pathlib import Path

        print(f"[Stage 3] Bootstrapping embeddings for: {queue_id}")

        # Initialize face detector
        face_app = FaceAnalysis(
            name='buffalo_l',
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        face_app.prepare(ctx_id=0, det_size=(640, 640))

        # Load contestant metadata
        try:
            contestants_df = pd.read_csv(contestant_metadata_path)
            print(f"  Loaded {len(contestants_df)} contestants from metadata")
        except FileNotFoundError:
            print(f"  Warning: Contestant metadata not found at {contestant_metadata_path}")
            contestants_df = None

        # Load YouTube validations (this would come from KV in production)
        # For now, load from volume
        samples_dir = VOL_MOUNT_PATH / "youtube_samples" / queue_id
        detections_file = samples_dir / "detections.json"
        validations_file = samples_dir / "validations.json"

        if not detections_file.exists():
            return {
                'success': False,
                'error': 'Detections file not found',
                'queue_id': queue_id,
            }

        with open(detections_file, 'r') as f:
            detections = json.load(f)

        # Load validations if available
        validations = {}
        if validations_file.exists():
            with open(validations_file, 'r') as f:
                validations = json.load(f)

        # Collect validated faces
        validated_embeddings = {}  # contestant_id -> [embeddings]

        for idx, detection in enumerate(detections):
            validation = validations.get(str(idx))

            if validation and validation.get('is_correct'):
                # Face was correctly recognized
                contestant_id = detection.get('recognition_result')
                if contestant_id and detection.get('embedding'):
                    if contestant_id not in validated_embeddings:
                        validated_embeddings[contestant_id] = []
                    validated_embeddings[contestant_id].append(
                        np.array(detection['embedding'])
                    )

            elif validation and not validation.get('is_correct'):
                # Face was incorrectly recognized, use corrected ID
                contestant_id = validation.get('correct_contestant_id')
                if contestant_id and detection.get('embedding'):
                    if contestant_id not in validated_embeddings:
                        validated_embeddings[contestant_id] = []
                    validated_embeddings[contestant_id].append(
                        np.array(detection['embedding'])
                    )

        print(f"  Collected embeddings for {len(validated_embeddings)} contestants from YouTube samples")

        # Add supplied photos if requested
        if use_supplied_photos:
            supplied_photos_dir = VOL_MOUNT_PATH / "source" / "photo"
            if supplied_photos_dir.exists():
                print(f"  Processing supplied photos from {supplied_photos_dir}")

                for contestant_dir in supplied_photos_dir.iterdir():
                    if not contestant_dir.is_dir():
                        continue

                    contestant_id = contestant_dir.name

                    for img_path in contestant_dir.glob("*.jpg"):
                        try:
                            img = cv2.imread(str(img_path))
                            if img is None:
                                continue

                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            faces = face_app.get(img_rgb)

                            if faces:
                                # Use first face (assume one person per photo)
                                face = faces[0]
                                if contestant_id not in validated_embeddings:
                                    validated_embeddings[contestant_id] = []
                                validated_embeddings[contestant_id].append(face.embedding)

                        except Exception as e:
                            print(f"    Warning: Failed to process {img_path}: {e}")

                print(f"  Added embeddings from supplied photos")

        # Initialize ChromaDB
        chroma_path = VOL_MOUNT_PATH / "chroma_db"
        chroma_path.mkdir(parents=True, exist_ok=True)

        client = chromadb.PersistentClient(path=str(chroma_path))

        # Create or get collection
        collection_name = "contestant_faces"
        try:
            collection = client.get_collection(name=collection_name)
            print(f"  Using existing ChromaDB collection: {collection_name}")
            # Clear existing data (optional - could merge instead)
            # collection.delete(where={})  # Uncomment to clear
        except:
            collection = client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"  Created new ChromaDB collection: {collection_name}")

        # Add embeddings to ChromaDB
        total_embeddings = 0
        for contestant_id, embeddings in validated_embeddings.items():
            if not embeddings:
                continue

            # Average embeddings for better representation
            avg_embedding = np.mean(embeddings, axis=0).tolist()

            # Add to collection
            collection.add(
                ids=[contestant_id],
                embeddings=[avg_embedding],
                metadatas=[{
                    'contestant_id': contestant_id,
                    'source': 'youtube_bootstrap',
                    'queue_id': queue_id,
                    'num_samples': len(embeddings),
                    'bootstrapped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                }]
            )

            total_embeddings += len(embeddings)

        volume.commit()

        print(f"✓ Bootstrap complete: {len(validated_embeddings)} contestants, {total_embeddings} total embeddings")

        return {
            'success': True,
            'contestants_updated': len(validated_embeddings),
            'total_embeddings': total_embeddings,
            'queue_id': queue_id,
        }


# --- Main Entry Point ---

@app.local_entrypoint()
def main(
    queue_id: Optional[str] = None,
    url: Optional[str] = None,
    sample_only: bool = False,
):
    """
    Main entry point for YouTube processing pipeline

    Args:
        queue_id: Queue ID from admin panel submission
        url: Direct YouTube URL (for testing)
        sample_only: Only download and sample, skip recognition
    """

    if not queue_id and not url:
        print("Error: Must provide either --queue-id or --url")
        sys.exit(1)

    # Create processor instance
    processor = YouTubeProcessor()

    # Generate queue_id if using direct URL
    if url and not queue_id:
        import hashlib
        video_id = hashlib.md5(url.encode()).hexdigest()[:11]
        queue_id = f"yt_{video_id}_{int(time.time())}"
        youtube_url = url
    else:
        # TODO: Fetch queue entry from KV storage to get URL
        # For now, require URL parameter
        if not url:
            print("Error: --url required (KV integration pending)")
            sys.exit(1)
        youtube_url = url

    print(f"\n{'='*60}")
    print(f"YouTube Processing Pipeline")
    print(f"Queue ID: {queue_id}")
    print(f"URL: {youtube_url}")
    print(f"{'='*60}\n")

    # Stage 1: Download
    print("\n[1/3] Downloading YouTube video...")
    download_result = processor.download_video.remote(youtube_url, queue_id)

    if not download_result['success']:
        print(f"\n✗ Pipeline failed at Stage 1: {download_result.get('error')}")
        sys.exit(1)

    print(f"✓ Stage 1 complete")

    # Stage 2: Sample and detect
    print("\n[2/3] Sampling frames and detecting faces...")
    sample_result = processor.sample_and_detect_faces.remote(
        video_path=download_result['video_path'],
        queue_id=queue_id,
        sample_interval=2.0,
        max_samples=100,
    )

    if not sample_result['success']:
        print(f"\n✗ Pipeline failed at Stage 2: {sample_result.get('error')}")
        sys.exit(1)

    print(f"✓ Stage 2 complete: {sample_result['total_faces']} faces detected")

    # Stage 2b: Recognition (optional)
    if not sample_only:
        print("\n[2b/3] Running face recognition...")
        recognition_result = processor.recognize_faces.remote(queue_id=queue_id)

        if recognition_result['success']:
            print(f"✓ Stage 2b complete: {recognition_result['recognized_faces']} faces recognized")
        else:
            print(f"⚠ Stage 2b skipped: {recognition_result.get('message', recognition_result.get('error'))}")

    # Stage 3: User validation and embedding bootstrap
    print("\n[3/3] Ready for user validation")
    print(f"\nNext steps:")
    print(f"1. Review detected faces at: {sample_result['samples_dir']}")
    print(f"2. Use admin UI to validate/flag faces")
    print(f"3. Run embedding bootstrap with validated data")
    print(f"\n{'='*60}")
    print(f"Pipeline complete! Queue ID: {queue_id}")
    print(f"{'='*60}\n")
