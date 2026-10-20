"""
Main Video Processing Script
Orchestrates the complete video processing pipeline
"""

import click
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from tqdm import tqdm

from video_processor import VideoProcessor
from face_detector import FaceDetector, FaceRecognizer, ContestantDatabase
from metadata_generator import MetadataGenerator
from cloudflare_uploader import CloudflareUploader
import numpy as np
import supervision as sv

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _json_default(obj):
    """Encode numpy scalars/arrays as native types so json.dump doesn't choke."""
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _create_tracker(frame_rate: int) -> sv.ByteTrack:
    """ByteTrack configured for faces tracked across sampled frames.

    Activation is on the detector score, which is what `detections.confidence` holds here.

    `minimum_matching_threshold` is a **cost ceiling on `1 - IoU`**, not a quality floor: the
    value is handed to `linear_assignment(1 - IoU, threshold)`, so 0.8 accepts pairs overlapping
    at IoU 0.2 while 0.3 would accept only IoU 0.7. This used to be 0.3 — reading as "require 30%
    of a match" and doing the opposite (the same inversion as the old `tolerance`/cosine mixup
    CONTEXT.md was written to end). Measured on `test-video-mv2` by replaying the stored
    detections, over 399 detections:

        threshold   IoU needed   tracks   1-frame   untracked   longest
        0.3         0.7          119      111       270         4
        0.5         0.5          81       48        221         16
        0.8         0.2          42       7         162         19     <- the library default
        0.9         0.1          36       3         144         20

    So the default it is: 0.9 buys a little more while merging far more aggressively (IoU 0.1
    across a camera cut can join two different people). The detections that stay untracked even
    at 0.9 are an artefact of `update_with_detections` re-associating at a fixed IoU 0.5, which
    this setting does not reach.
    """
    return sv.ByteTrack(
        track_activation_threshold=0.25,
        lost_track_buffer=30,
        minimum_matching_threshold=0.8,
        frame_rate=frame_rate,
    )


class VideoProcessingPipeline:
    """Main video processing pipeline"""

    def __init__(
        self, config_path: str, enable_upload: bool = True, local_only: bool = False
    ):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Set local-only mode
        self.local_only = local_only
        if local_only:
            self.config["output"]["local_mode"]["enabled"] = True
            enable_upload = False  # Force disable upload in local-only mode

        # Initialize components
        self.video_processor = VideoProcessor(self.config)
        self.face_detector = FaceDetector(self.config)
        self.contestant_db = ContestantDatabase(self.config)
        self.face_recognizer = FaceRecognizer(self.config, self.contestant_db)
        self.metadata_generator = MetadataGenerator(self.config)

        # Only initialize Cloudflare uploader if upload is enabled
        self.cloudflare_uploader: Optional[CloudflareUploader] = None
        if enable_upload and not local_only:
            try:
                self.cloudflare_uploader = CloudflareUploader(self.config)
            except Exception as e:
                logger.warning(f"Failed to initialize Cloudflare uploader: {e}")
                if not local_only:
                    logger.warning("Continuing without cloud upload capability")

        # Setup output directories
        self.setup_output_dirs()

    def setup_output_dirs(self):
        """Create output directories"""
        output_config = self.config["output"]

        if self.local_only or output_config.get("local_mode", {}).get("enabled", False):
            # Use local-only directories
            local_config = output_config["local_mode"]

            # Create base output directory
            base_dir = Path(local_config["base_output_dir"])
            base_dir.mkdir(parents=True, exist_ok=True)

            # Create all local output directories
            local_dirs = [
                "processed_videos_dir",
                "thumbnails_dir",
                "metadata_dir",
                "galleries_dir",
                "clips_dir",
            ]

            for dir_key in local_dirs:
                if dir_key in local_config:
                    Path(local_config[dir_key]).mkdir(parents=True, exist_ok=True)

            # Update config to use local directories
            output_config["processed_dir"] = local_config["processed_videos_dir"]
            output_config["thumbnails_dir"] = local_config["thumbnails_dir"]
            output_config["metadata_dir"] = local_config["metadata_dir"]
            output_config["galleries_dir"] = local_config["galleries_dir"]

            logger.info(f"Local-only mode: Using output directory {base_dir}")
        else:
            # Use standard directories
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

    def process_video(
        self, video_path: Path, output_name: Optional[str] = None,
    ) -> Dict:
        """
        Process a single video through the complete pipeline

        Args:
            video_path: Path to input video
            output_name: Optional custom output name

        Returns:
            Processing results dictionary
        """
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

        # Generate multiple thumbnails
        thumbnails_dir = self.config["output"]["thumbnails_dir"]
        thumbnail_paths = self.video_processor.generate_thumbnails(
            str(video_path), thumbnails_dir, output_name
        )

        # Process frames
        all_recognitions = []
        frame_data = []

        frames_generator = self.video_processor.extract_frames(str(video_path))
        frames_list = list(frames_generator)  # Convert to list for progress bar

        logger.info(f"Processing {len(frames_list)} frames...")

        unmatched_faces = []

        # Initialize ByteTrack for persistent face tracking
        tracker = _create_tracker(self.config["video"]["fps_sample_rate"])

        for frame_idx, (frame, timestamp) in enumerate(
            tqdm(frames_list, desc="Processing frames")
        ):
            # Detect faces (InsightFace expects BGR frames as read by cv2;
            # gallery embeddings are built from BGR cv2.imread photos)
            detections = self.face_detector.detect_faces(
                frame, timestamp, frame_idx
            )

            if detections:
                # Recognize faces
                recognitions = self.face_recognizer.recognize_faces(detections)
                all_recognitions.extend(recognitions)

                recognition_by_detection = {id(r.detection): r for r in recognitions}
                unmatched_faces.extend(
                    det for det in detections if id(det) not in recognition_by_detection
                )

                # Every detection is stored, matched or not — a face the matcher got wrong is
                # exactly what a labeller needs to click. Unmatched entries carry no contestant
                # and no match_score; their det_score is the only score they have.
                entries = []
                for det in detections:
                    r = recognition_by_detection.get(id(det))
                    entries.append(
                        {
                            "contestant_id": str(r.contestant_id) if r else None,
                            "contestant_name": str(r.contestant_name) if r else None,
                            "contestant_nickname": str(r.contestant_nickname) if r else None,
                            "match_score": float(r.match_score) if r else None,
                            "det_score": float(det.det_score),
                            "bbox": [float(v) for v in det.bbox],
                            "tracker_id": None,
                        }
                    )

                frame_data.append(
                    {
                        "frame_number": int(frame_idx),
                        "timestamp": float(timestamp),
                        "detections_count": len(detections),
                        "recognitions_count": len(recognitions),
                        "detections": entries,
                    }
                )

                # ByteTrack needs pixels and runs in detection space, while the stored contract is
                # frame fractions — so project back with the detection frame's own dimensions.
                # Order is preserved end to end, so each tracker id lands on its own entry.
                frame_height, frame_width = frame.shape[:2]
                sv_detections = sv.Detections(
                    xyxy=np.array(
                        [
                            [
                                det.bbox[0] * frame_width,
                                det.bbox[1] * frame_height,
                                det.bbox[2] * frame_width,
                                det.bbox[3] * frame_height,
                            ]
                            for det in detections
                        ],
                        dtype=np.float32,
                    ),
                    confidence=np.array(
                        [det.det_score for det in detections], dtype=np.float32
                    ),
                )
                tracker.update_with_detections(sv_detections)
                # update_with_detections assigns tracker_id onto the *input* detections,
                # index-aligned with how sv_detections was built; -1 means no track.
                if sv_detections.tracker_id is not None:
                    for entry, track_id in zip(entries, sv_detections.tracker_id):
                        track_id = int(track_id)
                        entry["tracker_id"] = track_id if track_id >= 0 else None

        # Save unmatched face embeddings for clustering
        if unmatched_faces:
            self._save_unmatched_embeddings(unmatched_faces, output_name)

        # `acceptance_threshold` in processing_config.yaml is the single acceptance gate, and it is
        # a cosine, in the same direction as the match score. There is deliberately no second
        # filter here: a second gate on a different scale is what silently raised the real bar to
        # cosine 0.5325 while the config said 0.45 (see CONTEXT.md — "Acceptance threshold").
        logger.info(
            f"Processing complete: {len(all_recognitions)} recognitions found, "
            f"{len(unmatched_faces)} unmatched faces saved"
        )

        # Generate metadata
        metadata = self.metadata_generator.generate_metadata(
            video_info=video_info,
            recognitions=all_recognitions,
            frame_data=frame_data,
            output_name=output_name,
            thumbnail_paths=thumbnail_paths,
        )

        # Save metadata
        metadata_path = (
            Path(self.config["output"]["metadata_dir"]) / f"{output_name}_metadata.json"
        )
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=_json_default)

        # Generate galleries
        gallery_data = self.metadata_generator.generate_face_galleries(
            recognitions=all_recognitions, output_name=output_name
        )

        # Save gallery data locally
        self.save_gallery_data(gallery_data, output_name)

        # Convert video formats
        processed_videos = self.convert_video_formats(video_path, output_name)

        # No annotated rendition: overlays are drawn by the JS layer, which can toggle them.
        # `_annotated.mp4` burned boxes into pixels and was never published.
        upload_package = {
            "video_info": video_info,
            "metadata": metadata,
            "gallery_data": gallery_data,
            "processed_videos": processed_videos,
            "thumbnails": thumbnail_paths,
            "metadata_file": str(metadata_path),
        }

        return upload_package

    def _save_unmatched_embeddings(self, unmatched_faces, output_name: str):
        """Save unmatched face embeddings and index for later clustering."""
        import numpy as np

        unmatched_dir = Path("../data/unmatched_faces") / output_name
        unmatched_dir.mkdir(parents=True, exist_ok=True)

        index = []
        for i, det in enumerate(unmatched_faces):
            filename = f"face_{det.frame_number}_{i}.npy"
            np.save(str(unmatched_dir / filename), det.encoding)
            index.append({
                "file": filename,
                "frame_number": int(det.frame_number),
                "timestamp": float(det.timestamp),
                "bbox": [float(v) for v in det.bbox],
                "det_score": float(det.det_score),
            })

        index_path = unmatched_dir / "unmatched_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "video": output_name,
                "total_unmatched": len(index),
                "faces": index,
            }, f, indent=2, ensure_ascii=False, default=_json_default)

        logger.info(f"Saved {len(index)} unmatched face embeddings to {unmatched_dir}")

    def convert_video_formats(self, input_path: Path, output_name: str) -> List[str]:
        """Convert video to multiple formats"""
        output_dir = Path(self.config["output"]["processed_dir"])
        processed_videos = []

        for format_config in self.config["video"]["output_formats"]:
            format_name = format_config["format"]
            resolution = format_config["resolution"]

            output_filename = f"{output_name}_{resolution}.{format_name}"
            output_path = output_dir / output_filename

            logger.info(f"Converting to {output_filename}...")
            self.video_processor.convert_video_format(
                str(input_path), str(output_path), format_config
            )

            processed_videos.append(str(output_path))

        return processed_videos

    def save_gallery_data(self, gallery_data: Dict, output_name: str):
        """Save gallery data to local file"""
        galleries_dir = Path(self.config["output"]["galleries_dir"])
        gallery_path = galleries_dir / f"{output_name}_gallery.json"

        with open(gallery_path, "w", encoding="utf-8") as f:
            json.dump(gallery_data, f, indent=2, ensure_ascii=False, default=_json_default)

        logger.info(f"Gallery data saved to: {gallery_path}")

    def upload_to_cloudflare(self, upload_package: Dict, upload_videos: bool = True):
        """Upload processed content to Cloudflare"""
        if self.cloudflare_uploader and upload_videos:
            logger.info("Uploading to Cloudflare R2...")
            self.cloudflare_uploader.upload_package(upload_package)
        else:
            logger.info("Skipping Cloudflare upload")


@click.command()
@click.option("--input", "-i", required=True, help="Input video file path")
@click.option(
    "--config", "-c", default="config/processing_config.yaml", help="Configuration file"
)
@click.option(
    "--output-name", "-o", help="Custom output name (default: video filename)"
)
@click.option("--no-upload", is_flag=True, help="Skip Cloudflare upload")
@click.option(
    "--local-only",
    is_flag=True,
    help="Run in local-only mode without any cloud dependencies",
)
@click.option("--output-dir", help="Custom base output directory for local-only mode")
@click.option("--rebuild-db", is_flag=True, help="Force rebuild contestant database")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main(
    input: str,
    config: str,
    output_name: str,
    no_upload: bool,
    local_only: bool,
    output_dir: str,
    rebuild_db: bool,
    debug: bool,
):
    """Process video through face recognition pipeline"""

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Input validation
        video_path = Path(input)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {input}")
        if video_path.suffix.lower() not in [".mp4", ".avi", ".mov", ".mkv"]:
            raise ValueError(f"Unsupported video format: {video_path.suffix}")

        # Load and modify configuration if custom output directory is specified
        temp_config_path = None

        if output_dir and local_only:
            with open(config, "r") as f:
                config_data = yaml.safe_load(f)

            # Update local mode configuration with custom output directory
            base_output_dir = Path(output_dir).resolve()
            config_data["output"]["local_mode"]["base_output_dir"] = str(
                base_output_dir
            )
            config_data["output"]["local_mode"]["processed_videos_dir"] = str(
                base_output_dir / "processed_videos"
            )
            config_data["output"]["local_mode"]["thumbnails_dir"] = str(
                base_output_dir / "thumbnails"
            )
            config_data["output"]["local_mode"]["metadata_dir"] = str(
                base_output_dir / "metadata"
            )
            config_data["output"]["local_mode"]["galleries_dir"] = str(
                base_output_dir / "galleries"
            )
            config_data["output"]["local_mode"]["clips_dir"] = str(
                base_output_dir / "clips"
            )

            # Write temporary config file
            temp_config_path = Path(config).parent / "temp_processing_config.yaml"
            with open(temp_config_path, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False)
            config = str(temp_config_path)

            logger.info(f"Using custom output directory: {base_output_dir}")

        try:
            # Initialize pipeline
            enable_upload = not (no_upload or local_only)
            pipeline = VideoProcessingPipeline(
                config, enable_upload=enable_upload, local_only=local_only
            )

            # Initialize contestant database
            pipeline.initialize_database(force_rebuild=rebuild_db)

            # Process video
            upload_package = pipeline.process_video(video_path, output_name)

            # Upload to Cloudflare (unless disabled or in local-only mode)
            if not (no_upload or local_only) and pipeline.cloudflare_uploader:
                pipeline.upload_to_cloudflare(upload_package)

            logger.info("Processing complete!")

            # Print summary
            metadata = upload_package["metadata"]
            logger.info("\n📊 Processing Summary:")
            logger.info(f"   Video: {metadata['video_info']['filename']}")
            logger.info(f"   Duration: {metadata['video_info']['duration']:.1f}s")
            logger.info(
                f"   Frames processed: {metadata['processing_summary']['frames_processed']}"
            )
            logger.info(
                f"   Faces detected: {metadata['processing_summary']['total_faces_detected']}"
            )
            logger.info(
                f"   Recognitions: {metadata['processing_summary']['total_recognitions']}"
            )
            logger.info(f"   Unique contestants: {len(metadata['contestant_timeline'])}")

            # Output location information
            if local_only:
                local_config = pipeline.config["output"]["local_mode"]
                logger.info(
                    f"   📁  Local output saved to: {local_config['base_output_dir']}"
                )
                logger.info(
                    f"   📹  Processed videos: {local_config['processed_videos_dir']}"
                )
                logger.info(f"   🖼️  Thumbnails: {local_config['thumbnails_dir']}")
                logger.info(f"   📄  Metadata: {local_config['metadata_dir']}")
                logger.info(f"   🎭  Galleries: {local_config['galleries_dir']}")
            elif not no_upload and pipeline.cloudflare_uploader:
                logger.info("   ☁️  Uploaded to Cloudflare R2")
            else:
                logger.info("   📁  Saved to local directories (cloud upload disabled)")

        finally:
            # Clean up temporary config file
            if temp_config_path and temp_config_path.exists():
                temp_config_path.unlink()
                logger.debug("Cleaned up temporary config file")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
