#!/usr/bin/env python3
"""Process a single video with CJKV font and audio support"""

import sys
import json
import yaml
import logging
from pathlib import Path
from tqdm import tqdm

# Add processor source
sys.path.append("mvp-processor/src")

from video_processor import VideoProcessor
from face_detector import FaceDetector, FaceRecognizer, ContestantDatabase
from metadata_generator import MetadataGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_video_enhanced(video_path, output_name, config_path):
    """Process a single video with all enhancements"""

    # Load config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Initialize components
    video_processor = VideoProcessor(config)
    face_detector = FaceDetector(config)
    contestant_db = ContestantDatabase(config)
    face_recognizer = FaceRecognizer(config, contestant_db)
    metadata_generator = MetadataGenerator(config)

    # Setup output directories
    output_config = config["output"]
    for dir_key in ["processed_dir", "thumbnails_dir", "metadata_dir"]:
        Path(output_config[dir_key]).mkdir(parents=True, exist_ok=True)

    # Load database
    logger.info("Loading contestant database...")
    contestant_db.load_contestants_info()
    contestant_db.build_face_encodings(force_rebuild=False)
    logger.info(f"Database loaded with {len(contestant_db.face_encodings)} contestants")

    # Get video info
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Create video info
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()

    video_info = {
        "filename": video_path.name,
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration": duration,
        "processed_name": output_name,
        "processing_date": "2025-07-20T22:00:00.000000",
    }

    # Create thumbnail
    thumbnail_path = (
        Path(config["output"]["thumbnails_dir"]) / f"{output_name}_thumb.jpg"
    )
    video_processor.create_thumbnail(str(video_path), str(thumbnail_path))

    # Process frames
    all_recognitions = []
    frame_data = []

    frames_generator = video_processor.extract_frames(str(video_path))
    frames_list = list(frames_generator)

    logger.info(f"Processing {len(frames_list)} frames with face recognition...")

    for frame_idx, (frame, timestamp) in enumerate(
        tqdm(frames_list, desc="Processing frames")
    ):
        # Preprocess frame
        from video_processor import FrameProcessor

        rgb_frame = FrameProcessor.preprocess_frame(frame)

        # Detect faces
        detections = face_detector.detect_faces(rgb_frame, timestamp, frame_idx)

        if detections:
            # Recognize faces
            recognitions = face_recognizer.recognize_faces(detections)
            all_recognitions.extend(recognitions)

            # Store frame data with proper frame number calculation
            actual_frame_number = int(timestamp * video_info["fps"])
            frame_data.append(
                {
                    "frame_number": actual_frame_number,
                    "extraction_index": int(frame_idx),
                    "timestamp": float(timestamp),
                    "detections_count": len(detections),
                    "recognitions_count": len(recognitions),
                    "recognitions": [
                        {
                            "contestant_id": str(r.contestant_id),
                            "contestant_name": str(r.contestant_name),
                            "contestant_nickname": str(r.contestant_nickname),
                            "confidence": float(r.match_confidence),
                            "face_location": [int(x) for x in r.detection.location],
                        }
                        for r in recognitions
                    ],
                }
            )

    # Filter recognitions
    filtered_recognitions = face_recognizer.filter_recognitions(
        all_recognitions, min_confidence=0.5
    )
    logger.info(f"Processing complete: {len(filtered_recognitions)} recognitions found")

    # Generate metadata
    metadata = metadata_generator.generate_metadata(
        video_info=video_info,
        recognitions=filtered_recognitions,
        frame_data=frame_data,
        output_name=output_name,
    )

    # Save metadata
    metadata_path = (
        Path(config["output"]["metadata_dir"]) / f"{output_name}_metadata.json"
    )
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Convert video formats with enhanced annotations and audio
    processed_videos = []
    output_dir = Path(config["output"]["processed_dir"])

    for format_config in config["video"]["output_formats"]:
        format_name = format_config["format"]
        resolution = format_config["resolution"]

        output_filename = f"{output_name}_{resolution}.{format_name}"
        output_path = output_dir / output_filename

        logger.info(f"Converting to {output_filename} with CJKV fonts and audio...")
        video_processor.process_video_with_annotations(
            str(video_path), str(output_path), metadata, format_config
        )

        processed_videos.append(str(output_path))

    return {
        "video_info": video_info,
        "metadata": metadata,
        "processed_videos": processed_videos,
        "thumbnail": str(thumbnail_path),
        "metadata_file": str(metadata_path),
    }


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: python process_single_video_cjkv.py <video_path> <output_name> <config_path>"
        )
        sys.exit(1)

    video_path = sys.argv[1]
    output_name = sys.argv[2]
    config_path = sys.argv[3]

    import cv2  # Import here to avoid issues

    try:
        result = process_video_enhanced(video_path, output_name, config_path)
        print(f"✅ Video processing completed: {result['processed_videos']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
