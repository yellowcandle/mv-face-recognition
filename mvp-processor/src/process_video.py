"""
Main Video Processing Script
Orchestrates the complete video processing pipeline
"""

import click
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm

from video_processor import VideoProcessor, FrameProcessor
from face_detector import FaceDetector, FaceRecognizer, ContestantDatabase
from metadata_generator import MetadataGenerator
from cloudflare_uploader import CloudflareUploader

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VideoProcessingPipeline:
    """Main video processing pipeline"""

    def __init__(self, config_path: str, enable_upload: bool = True):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Initialize components
        self.video_processor = VideoProcessor(self.config)
        self.face_detector = FaceDetector(self.config)
        self.contestant_db = ContestantDatabase(self.config)
        self.face_recognizer = FaceRecognizer(self.config, self.contestant_db)
        self.metadata_generator = MetadataGenerator(self.config)

        # Only initialize Cloudflare uploader if upload is enabled
        self.cloudflare_uploader = None
        if enable_upload:
            self.cloudflare_uploader = CloudflareUploader(self.config)

        # Setup output directories
        self.setup_output_dirs()
        
        # Initialize contestant database with face encodings
        self.initialize_database()

    def setup_output_dirs(self):
        """Create output directories"""
        output_config = self.config["output"]
        for dir_key in [
            "processed_dir",
            "thumbnails_dir",
            "metadata_dir",
            "galleries_dir",
        ]:
            Path(output_config[dir_key]).mkdir(parents=True, exist_ok=True)

    def initialize_database(self, force_rebuild: bool = False):
        """Initialize contestant database"""
        logger.info("Initializing contestant database...")
        self.contestant_db.load_contestants_info()
        self.contestant_db.build_face_encodings(force_rebuild=force_rebuild)
        logger.info(
            f"Database ready with {len(self.contestant_db.face_encodings)} contestants"
        )

    def process_video(self, video_path: str, output_name: str = None) -> Dict:
        """
        Process a single video through the complete pipeline

        Args:
            video_path: Path to input video
            output_name: Optional custom output name

        Returns:
            Processing results dictionary
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        if output_name is None:
            output_name = video_path.stem

        logger.info(f"Processing video: {video_path}")

        # Get video info
        video_info = self.video_processor.get_video_info(str(video_path))
        logger.info(
            f"Video info: {video_info['duration']:.1f}s, "
            f"{video_info['width']}x{video_info['height']}, "
            f"{video_info['fps']:.1f} fps"
        )

        # Create thumbnail
        thumbnail_path = (
            Path(self.config["output"]["thumbnails_dir"]) / f"{output_name}_thumb.jpg"
        )
        self.video_processor.create_thumbnail(str(video_path), str(thumbnail_path))

        # Process frames
        all_recognitions = []
        frame_data = []

        frames_generator = self.video_processor.extract_frames(str(video_path))
        frames_list = list(frames_generator)  # Convert to list for progress bar

        logger.info(f"Processing {len(frames_list)} frames...")

        for frame_idx, (frame, timestamp) in enumerate(
            tqdm(frames_list, desc="Processing frames")
        ):
            # Preprocess frame
            rgb_frame = FrameProcessor.preprocess_frame(frame)

            # Detect faces
            detections = self.face_detector.detect_faces(
                rgb_frame, timestamp, frame_idx
            )

            if detections:
                # Recognize faces
                recognitions = self.face_recognizer.recognize_faces(detections)
                all_recognitions.extend(recognitions)

                # Store frame data
                frame_data.append(
                    {
                        "frame_number": int(frame_idx),
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

        # Filter low-confidence recognitions
        filtered_recognitions = self.face_recognizer.filter_recognitions(
            all_recognitions, min_confidence=0.5
        )

        logger.info(
            f"Processing complete: {len(filtered_recognitions)} recognitions found"
        )

        # Generate metadata
        metadata = self.metadata_generator.generate_metadata(
            video_info=video_info,
            recognitions=filtered_recognitions,
            frame_data=frame_data,
            output_name=output_name,
        )

        # Save metadata
        metadata_path = (
            Path(self.config["output"]["metadata_dir"]) / f"{output_name}_metadata.json"
        )
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Generate galleries
        gallery_data = self.metadata_generator.generate_face_galleries(
            recognitions=filtered_recognitions, output_name=output_name
        )

        # Convert video formats with face recognition overlays
        processed_videos = self.convert_video_formats_with_overlays(video_path, output_name, metadata)

        # Prepare upload package
        upload_package = {
            "video_info": video_info,
            "metadata": metadata,
            "gallery_data": gallery_data,
            "processed_videos": processed_videos,
            "thumbnail": str(thumbnail_path),
            "metadata_file": str(metadata_path),
        }

        return upload_package

    def convert_video_formats_with_overlays(self, input_path: Path, output_name: str, metadata: Dict) -> List[str]:
        """Convert video to multiple formats with burned-in face recognition overlays"""
        output_dir = Path(self.config["output"]["processed_dir"])
        processed_videos = []

        for format_config in self.config["video"]["output_formats"]:
            format_name = format_config["format"]
            resolution = format_config["resolution"]

            output_filename = f"{output_name}_{resolution}.{format_name}"
            output_path = output_dir / output_filename

            logger.info(f"Converting to {output_filename} with face recognition overlays...")
            self.video_processor.process_video_with_annotations(
                str(input_path), str(output_path), metadata, format_config
            )

            processed_videos.append(str(output_path))

        return processed_videos

    def upload_to_cloudflare(self, upload_package: Dict, upload_videos: bool = True):
        """Upload processed content to Cloudflare"""
        if upload_videos:
            logger.info("Uploading to Cloudflare R2...")
            self.cloudflare_uploader.upload_package(upload_package)
        else:
            logger.info("Skipping Cloudflare upload (upload_videos=False)")


@click.command()
@click.option("--input", "-i", required=True, help="Input video file path")
@click.option(
    "--config", "-c", default="config/processing_config.yaml", help="Configuration file"
)
@click.option(
    "--output-name", "-o", help="Custom output name (default: video filename)"
)
@click.option("--no-upload", is_flag=True, help="Skip Cloudflare upload")
@click.option("--rebuild-db", is_flag=True, help="Force rebuild contestant database")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main(
    input: str,
    config: str,
    output_name: str,
    no_upload: bool,
    rebuild_db: bool,
    debug: bool,
):
    """Process video through face recognition pipeline"""

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize pipeline
        pipeline = VideoProcessingPipeline(config, enable_upload=not no_upload)

        # Initialize contestant database
        pipeline.initialize_database(force_rebuild=rebuild_db)

        # Process video
        upload_package = pipeline.process_video(input, output_name)

        # Upload to Cloudflare (unless disabled)
        if not no_upload and pipeline.cloudflare_uploader:
            pipeline.upload_to_cloudflare(upload_package)

        logger.info("Processing complete!")

        # Print summary
        metadata = upload_package["metadata"]
        print("\n📊 Processing Summary:")
        print(f"   Video: {metadata['video_info']['filename']}")
        print(f"   Duration: {metadata['video_info']['duration']:.1f}s")
        print(
            f"   Frames processed: {metadata['processing_summary']['frames_processed']}"
        )
        print(
            f"   Faces detected: {metadata['processing_summary']['total_faces_detected']}"
        )
        print(
            f"   Recognitions: {metadata['processing_summary']['total_recognitions']}"
        )
        print(f"   Unique contestants: {len(metadata['contestant_timeline'])}")

        if not no_upload:
            print("   ☁️  Uploaded to Cloudflare R2")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()
