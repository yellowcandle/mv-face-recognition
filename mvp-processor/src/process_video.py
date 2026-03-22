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

from video_processor import VideoProcessor, FrameProcessor
from face_detector import FaceDetector, FaceRecognizer, ContestantDatabase
from metadata_generator import MetadataGenerator
from cloudflare_uploader import CloudflareUploader
from src.supervision_annotator import (
    insightface_to_sv_detections,
    create_tracker,
    create_annotator_pipeline,
    annotate_frame,
    build_contestant_id_map,
    get_color_for_contestant,
)
import shutil
import numpy as np
import supervision as sv

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
        no_annotate: bool = False,
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
        tracker = create_tracker(frame_rate=self.config["video"]["fps_sample_rate"])
        contestant_id_map = build_contestant_id_map(self.contestant_db.contestants_info)
        screen_time = {}  # nickname → cumulative seconds
        frame_interval = 1.0 / self.config["video"]["fps_sample_rate"]

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

                # Collect unmatched detections (detected but not recognized)
                matched_detections = {id(r.detection) for r in recognitions}
                for det in detections:
                    if id(det) not in matched_detections:
                        unmatched_faces.append(det)

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

                # Run ByteTrack for persistent tracking
                sv_detections = insightface_to_sv_detections(
                    recognitions,
                    [det for det in detections if id(det) not in matched_detections],
                    contestant_id_map,
                )
                if len(sv_detections) > 0:
                    tracked = tracker.update_with_detections(sv_detections)
                    # Store tracker IDs in frame_data
                    if frame_data:
                        frame_data[-1]["tracker_ids"] = tracked.tracker_id.tolist() if tracked.tracker_id is not None else []

                    # Accumulate screen time for recognized contestants
                    labels = tracked.data.get("labels", [])
                    for label in labels:
                        if label != "Unknown":
                            screen_time[label] = screen_time.get(label, 0) + frame_interval

        # Save unmatched face embeddings for clustering
        if unmatched_faces:
            self._save_unmatched_embeddings(unmatched_faces, output_name)

        # Filter low-confidence recognitions
        filtered_recognitions = self.face_recognizer.filter_recognitions(
            all_recognitions, min_confidence=0.5
        )

        logger.info(
            f"Processing complete: {len(filtered_recognitions)} recognitions found, "
            f"{len(unmatched_faces)} unmatched faces saved"
        )

        # Generate metadata
        metadata = self.metadata_generator.generate_metadata(
            video_info=video_info,
            recognitions=filtered_recognitions,
            frame_data=frame_data,
            output_name=output_name,
            thumbnail_paths=thumbnail_paths,
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

        # Save gallery data locally
        self.save_gallery_data(gallery_data, output_name)

        # Convert video formats
        processed_videos = self.convert_video_formats(video_path, output_name)

        # Generate annotated video with Supervision
        annotated_video_path = None
        if not no_annotate and frame_data:
            output_dir = Path(self.config["output"]["processed_dir"])
            annotated_filename = f"{output_name}_annotated.mp4"
            annotated_output = output_dir / annotated_filename

            try:
                annotators = create_annotator_pipeline()

                # Build color map for timeline bar
                color_map = {}
                for nickname, cid in contestant_id_map.items():
                    color_map[nickname] = get_color_for_contestant(cid)

                # Re-read video and annotate each frame
                cap = cv2.VideoCapture(str(video_path))
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                video_info_sv = sv.VideoInfo(
                    width=width, height=height, fps=fps,
                )

                # Create a frame_number → frame_data lookup
                frame_lookup = {fd["frame_number"]: fd for fd in frame_data}

                with sv.VideoSink(str(annotated_output), video_info_sv) as sink:
                    sample_rate = self.config["video"]["fps_sample_rate"]
                    frame_idx = 0

                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break

                        # Check if this frame was processed (sampled)
                        sampled_frame_num = int(frame_idx * sample_rate / fps) if fps > 0 else frame_idx
                        fd = frame_lookup.get(sampled_frame_num)

                        if fd and fd.get("recognitions"):
                            # Reconstruct detections from stored frame_data
                            xyxy_list = []
                            labels = []
                            confidences = []
                            class_ids = []

                            for r in fd["recognitions"]:
                                top, right, bottom, left = r["face_location"]
                                xyxy_list.append([left, top, right, bottom])
                                labels.append(r["contestant_nickname"])
                                confidences.append(r["confidence"])
                                class_ids.append(contestant_id_map.get(r["contestant_nickname"], -1))

                            detections = sv.Detections(
                                xyxy=np.array(xyxy_list, dtype=np.float32),
                                confidence=np.array(confidences, dtype=np.float32),
                                class_id=np.array(class_ids, dtype=int),
                                data={"labels": labels},
                            )

                            # Set tracker IDs if available
                            tracker_ids = fd.get("tracker_ids", [])
                            if tracker_ids and len(tracker_ids) == len(detections):
                                detections.tracker_id = np.array(tracker_ids, dtype=int)
                        else:
                            detections = sv.Detections.empty()

                        frame = annotate_frame(frame, detections, annotators, screen_time, color_map)
                        sink.write_frame(frame)
                        frame_idx += 1

                cap.release()

                # Merge audio from original video
                if shutil.which("ffmpeg"):
                    final_output = output_dir / f"{output_name}_annotated_audio.mp4"
                    import subprocess
                    result = subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(annotated_output),
                        "-i", str(video_path),
                        "-c", "copy",
                        "-map", "0:v:0", "-map", "1:a:0",
                        str(final_output),
                    ], capture_output=True)
                    if result.returncode == 0:
                        annotated_output.unlink()  # Remove video-only version
                        final_output.rename(annotated_output)  # Rename to expected name
                        logger.info(f"Audio merged into annotated video")
                    else:
                        logger.warning(f"FFmpeg audio merge failed: {result.stderr.decode()[:200]}")
                else:
                    logger.warning("FFmpeg not found — annotated video has no audio")

                annotated_video_path = str(annotated_output)
                processed_videos.append(annotated_video_path)
                logger.info(f"Annotated video created: {annotated_video_path}")
            except Exception as e:
                logger.warning(f"Failed to create annotated video: {e}")

        # Prepare upload package
        upload_package = {
            "video_info": video_info,
            "metadata": metadata,
            "gallery_data": gallery_data,
            "processed_videos": processed_videos,
            "thumbnails": thumbnail_paths,
            "metadata_file": str(metadata_path),
            "annotated_video": annotated_video_path,
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
                "location": [int(x) for x in det.location],
                "confidence": float(det.confidence),
            })

        index_path = unmatched_dir / "unmatched_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "video": output_name,
                "total_unmatched": len(index),
                "faces": index,
            }, f, indent=2, ensure_ascii=False)

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
            json.dump(gallery_data, f, indent=2, ensure_ascii=False)

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
@click.option("--no-annotate", is_flag=True, help="Skip annotated video generation")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main(
    input: str,
    config: str,
    output_name: str,
    no_upload: bool,
    local_only: bool,
    output_dir: str,
    rebuild_db: bool,
    no_annotate: bool,
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
            upload_package = pipeline.process_video(video_path, output_name, no_annotate=no_annotate)

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
