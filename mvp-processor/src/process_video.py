"""
Main Video Processing Script
Orchestrates the complete video processing pipeline
"""

import click
import yaml
import json
import logging
import os
import numpy as np
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm

from video_processor import VideoProcessor, FrameProcessor
from face_detector import FaceDetector, FaceRecognizer, ContestantDatabase
from unified_face_detector import UnifiedFaceDetector
from metadata_generator import MetadataGenerator

# Setup logging first
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    from supervision_face_tracker import SupervisionFaceTracker as FaceTracker
except ImportError:
    logger.warning("Supervision not available - using standard face tracker")
    from face_tracker import FaceTracker


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy data types"""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


class VideoProcessingPipeline:
    """Main video processing pipeline"""

    def __init__(self, config_path: str, enable_upload: bool = True):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Initialize components first (needed for _resolve_config_paths)
        self.video_processor = VideoProcessor(self.config)

        # Use unified face detection and recognition system
        use_unified_system = self.config.get("face_detection", {}).get(
            "use_unified_system", True
        )
        if use_unified_system:
            self.unified_face_detector = UnifiedFaceDetector(self.config)
            # Legacy components for compatibility
            self.face_detector = None
            self.contestant_db = self.unified_face_detector.contestant_db
            self.face_recognizer = None
            logger.info("Using unified face detection and recognition system")
        else:
            # Use legacy system
            self.face_detector = FaceDetector(self.config)
            self.contestant_db = ContestantDatabase(self.config)
            self.face_recognizer = FaceRecognizer(self.config, self.contestant_db)
            self.unified_face_detector = None
            logger.info("Using legacy face detection and recognition system")

        self.metadata_generator = MetadataGenerator(self.config)

        # Resolve relative paths in config based on project root
        self._resolve_config_paths(config_path)

        # Initialize face tracker if tracking is enabled (check both old and new config sections)
        self.face_tracker = None
        tracking_enabled = self.config.get("face_tracking", {}).get(
            "enable_tracking", False
        ) or self.config.get("processing", {}).get("enable_tracking", False)
        if tracking_enabled:
            self.face_tracker = FaceTracker(self.config)
            logger.info("Face tracking enabled")

        # Only initialize Cloudflare uploader if upload is enabled
        self.cloudflare_uploader = None
        if enable_upload:
            try:
                from cloudflare_uploader import CloudflareUploader

                self.cloudflare_uploader = CloudflareUploader(self.config)
                logger.info("Cloudflare uploader initialized")
            except ImportError as e:
                logger.warning("Cloudflare uploader not available: %s", e)
                logger.warning("Running in local-only mode")
            except Exception as e:
                logger.warning("Cloudflare uploader initialization failed: %s", e)
                logger.warning("Running in local-only mode")

        # Setup output directories
        self.setup_output_dirs()

    def _resolve_config_paths(self, config_path: str):
        """Resolve relative paths in config to absolute paths based on project root"""
        # Get project root directory (2 levels up from config file: config -> mvp-processor -> project root)
        config_dir = os.path.dirname(
            os.path.abspath(config_path)
        )  # mvp-processor/config
        mvp_processor_dir = os.path.dirname(config_dir)  # mvp-processor
        project_root = os.path.dirname(mvp_processor_dir)  # project root

        logger.debug(f"Config file: {config_path}")
        logger.debug(f"Project root: {project_root}")

        # Paths that need resolution
        path_mappings = {
            ("contestants", "photo_dir"): "../source/photo/contestants",
            ("contestants", "info_csv"): "../source/contestant_info.csv",
            ("contestants", "chroma_db_path"): "../database/chroma_db",
            ("face_recognition", "embeddings_path"): "../source/photo/contestants",
            ("output", "processed_dir"): "../processed_videos",
            ("output", "thumbnails_dir"): "../thumbnails",
            ("output", "metadata_dir"): "../metadata",
        }

        # Resolve each path
        for keys, default_path in path_mappings.items():
            config_section = self.config
            for key in keys[:-1]:
                if key in config_section:
                    config_section = config_section[key]
                else:
                    break
            else:
                if keys[-1] in config_section:
                    relative_path = config_section[keys[-1]]
                    if relative_path.startswith("../"):
                        # Convert relative path to absolute
                        absolute_path = os.path.join(project_root, relative_path[3:])
                        config_section[keys[-1]] = absolute_path

        # Database already initialized by unified system - no additional initialization needed

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

        # Use appropriate build method based on system type
        if self.unified_face_detector:
            # Use unified system method
            self.contestant_db.build_unified_face_encodings(force_rebuild=force_rebuild)
        else:
            # Use legacy system method
            self.contestant_db.build_face_encodings(force_rebuild=force_rebuild)

        logger.info(
            "Database ready with %d contestants", len(self.contestant_db.face_encodings)
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

        logger.info("Processing video: %s", video_path)

        # Get video info
        video_info = self.video_processor.get_video_info(str(video_path))
        logger.info(
            "Video info: %.1fs, %dx%d, %.1f fps",
            video_info["duration"],
            video_info["width"],
            video_info["height"],
            video_info["fps"],
        )

        # Create thumbnail
        thumbnail_path = (
            Path(self.config["output"]["thumbnails_dir"]) / f"{output_name}_thumb.jpg"
        )
        self.video_processor.create_thumbnail(str(video_path), str(thumbnail_path))

        # Process frames
        all_recognitions = []
        frame_data = []

        # Initialize face tracker for this video if enabled
        if self.face_tracker:
            self.face_tracker.reset()

        frames_generator = self.video_processor.extract_frames(str(video_path))
        frames_list = list(frames_generator)  # Convert to list for progress bar

        logger.info("Processing %d frames...", len(frames_list))

        for frame_idx, (frame, timestamp) in enumerate(
            tqdm(frames_list, desc="Processing frames")
        ):
            # Calculate actual video frame number based on timestamp and fps
            actual_frame_number = int(timestamp * video_info["fps"])

            # Preprocess frame
            rgb_frame = FrameProcessor.preprocess_frame(frame)

            # Detect faces
            if self.unified_face_detector:
                detections = self.unified_face_detector.detect_faces(
                    rgb_frame, timestamp, frame_idx
                )
            else:
                detections = self.face_detector.detect_faces(
                    rgb_frame, timestamp, frame_idx
                )

            # Update detections with correct frame number for tracking
            for detection in detections:
                detection.frame_number = actual_frame_number

            frame_recognitions = []
            if detections:
                if self.face_tracker:
                    # Use face tracking for temporal correlation
                    if self.unified_face_detector:
                        raw_recognitions = self.unified_face_detector.recognize_faces(
                            detections
                        )
                    else:
                        raw_recognitions = self.face_recognizer.recognize_faces(
                            detections
                        )

                    # Update trajectories with new detections and recognitions
                    active_trajectories = self.face_tracker.update_trajectories(
                        detections, raw_recognitions
                    )

                    # Get stable recognitions from tracking
                    frame_recognitions = self.face_tracker.get_stable_recognitions()

                    # Add raw recognitions for frames without stable tracking (fallback)
                    trajectory_locations = set()
                    for recognition in frame_recognitions:
                        trajectory_locations.add(recognition.detection.location)

                    # Add non-tracked detections
                    for raw_recognition in raw_recognitions:
                        if (
                            raw_recognition.detection.location
                            not in trajectory_locations
                        ):
                            frame_recognitions.append(raw_recognition)

                    logger.debug(
                        f"Frame {actual_frame_number}: {len(active_trajectories)} active trajectories, "
                        f"{len(frame_recognitions)} recognitions"
                    )
                else:
                    # Traditional frame-by-frame processing (no tracking)
                    if self.unified_face_detector:
                        frame_recognitions = self.unified_face_detector.recognize_faces(
                            detections
                        )
                    else:
                        frame_recognitions = self.face_recognizer.recognize_faces(
                            detections
                        )

                all_recognitions.extend(frame_recognitions)

                # Store frame data with actual video frame number and processing dimensions
                frame_data.append(
                    {
                        "frame_number": int(actual_frame_number),
                        "extraction_index": int(frame_idx),  # Keep for debugging
                        "timestamp": float(timestamp),
                        "detections_count": len(detections),
                        "recognitions_count": len(frame_recognitions),
                        "processing_width": rgb_frame.shape[
                            1
                        ],  # Processing frame width
                        "processing_height": rgb_frame.shape[
                            0
                        ],  # Processing frame height
                        "recognitions": [
                            {
                                "contestant_id": str(r.contestant_id),
                                "contestant_name": str(r.contestant_name),
                                "contestant_nickname": str(r.contestant_nickname),
                                "confidence": float(r.match_confidence),
                                "face_location": [int(x) for x in r.detection.location],
                            }
                            for r in frame_recognitions
                        ],
                    }
                )
            else:
                # No detections - update tracker with empty detections
                if self.face_tracker:
                    self.face_tracker.update_trajectories([], [])

        # Filter low-confidence recognitions using config similarity_threshold
        if self.unified_face_detector:
            # Apply filtering manually for unified system
            min_confidence = self.config["face_recognition"]["similarity_threshold"]
            filtered_recognitions = [
                r for r in all_recognitions if r.match_confidence >= min_confidence
            ]
            logger.info(
                f"Filtered {len(all_recognitions)} recognitions to {len(filtered_recognitions)} "
                f"(min_confidence: {min_confidence})"
            )
        else:
            filtered_recognitions = self.face_recognizer.filter_recognitions(
                all_recognitions
            )

        # Get tracking statistics if tracking was enabled
        tracking_stats = {}
        if self.face_tracker:
            tracking_stats = self.face_tracker.get_tracking_stats()
            logger.info(
                f"Tracking stats: {tracking_stats['active_trajectories']} active, "
                f"{tracking_stats['completed_trajectories']} completed, "
                f"{tracking_stats['stable_trajectories']} stable trajectories"
            )

        logger.info(
            "Processing complete: %d recognitions found", len(filtered_recognitions)
        )

        # Generate metadata
        metadata = self.metadata_generator.generate_metadata(
            video_info=video_info,
            recognitions=filtered_recognitions,
            frame_data=frame_data,
            output_name=output_name,
        )

        # Add tracking statistics to metadata
        if tracking_stats:
            metadata["tracking_stats"] = tracking_stats

        # Save metadata
        metadata_path = (
            Path(self.config["output"]["metadata_dir"]) / f"{output_name}_metadata.json"
        )
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        # Generate galleries
        gallery_data = self.metadata_generator.generate_face_galleries(
            recognitions=filtered_recognitions, output_name=output_name
        )

        # Convert video formats with face recognition overlays
        processed_videos = self.convert_video_formats_with_overlays(
            video_path, output_name, metadata
        )

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

    def convert_video_formats_with_overlays(
        self, input_path: Path, output_name: str, metadata: Dict
    ) -> List[str]:
        """Convert video to multiple formats with burned-in overlays."""
        output_dir = Path(self.config["output"]["processed_dir"])
        processed_videos = []

        for format_config in self.config["video"]["output_formats"]:
            format_name = format_config["format"]
            resolution = format_config["resolution"]

            output_filename = f"{output_name}_{resolution}.{format_name}"
            output_path = output_dir / output_filename

            logger.info(
                "Converting to %s with face recognition overlays...", output_filename
            )
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
@click.option(
    "--input", "-i", "input_path", required=True, help="Input video file path"
)
@click.option(
    "--config",
    "-c",
    default="config/processing_config.yaml",
    help="Configuration file",
)
@click.option(
    "--output-name", "-o", help="Custom output name (default: video filename)"
)
@click.option("--no-upload", is_flag=True, help="Skip Cloudflare upload")
@click.option("--rebuild-db", is_flag=True, help="Force rebuild contestant database")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main(
    input_path: str,
    config: str,
    output_name: str,
    no_upload: bool,
    rebuild_db: bool,
    debug: bool,
):
    """Process video through face recognition pipeline"""

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Set default config path if not provided
    if config is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config = os.path.join(script_dir, "../config/processing_config.yaml")
        logger.debug(f"Default config path resolved to: {config}")
        logger.debug(f"Config file exists: {os.path.exists(config)}")

    # Convert input path to absolute path if relative
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"Input video path: {input_path}")
    if not os.path.isabs(input_path):
        # If we're running from mvp-processor/src, adjust path resolution to project root
        cwd = os.getcwd()
        if cwd.endswith("mvp-processor/src"):
            # Go up 2 levels to project root
            project_root = os.path.dirname(os.path.dirname(cwd))
            input_path = os.path.join(project_root, input_path)
        else:
            # Resolve relative to current working directory
            input_path = os.path.abspath(input_path)
        logger.debug(f"Resolved video path: {input_path}")

    try:
        # Initialize pipeline (database is automatically initialized by unified system)
        pipeline = VideoProcessingPipeline(config, enable_upload=not no_upload)

        # Force rebuild database if requested
        if rebuild_db:
            if pipeline.unified_face_detector:
                pipeline.unified_face_detector.contestant_db.build_unified_face_encodings(
                    force_rebuild=True
                )
            else:
                pipeline.initialize_database(force_rebuild=True)

        # Process video
        upload_package = pipeline.process_video(input_path, output_name)

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
        logger.error("Processing failed: %s", e)
        raise


if __name__ == "__main__":
    main()
