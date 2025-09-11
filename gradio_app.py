#!/usr/bin/env python3
"""
MV Face Recognition - Gradio Interface
A modern demo interface for face recognition in music videos with contestant identification.
Optimized for Hugging Face Spaces deployment.
"""

import gradio as gr
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator
from datetime import datetime
import queue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.append("src")

try:
    from src.services.enhanced_video_processor import EnhancedVideoProcessor
    from src.database.chroma_setup import ChromaDBManager
except ImportError as e:
    logger.error(f"Import error: {e}")
    # For HF Spaces, we'll work with pre-processed data only


class GradioMVFaceRecognition:
    """Main Gradio application for MV Face Recognition."""

    def __init__(self):
        """Initialize the Gradio application."""
        self.processed_videos_dir = Path("processed_videos")
        self.metadata_dir = Path("metadata")
        self.clips_dir = Path("clips")

        # Create directories if they don't exist
        self.processed_videos_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)
        self.clips_dir.mkdir(exist_ok=True)

        # Initialize data
        self.video_metadata = {}
        self.clips_data = {}
        self.contestant_stats = {}

        # Processing state
        self.is_processing = False
        self.current_progress = {
            "stage": "",
            "progress": 0,
            "status": "",
            "video_name": "",
            "stats": {},
        }
        self.progress_queue = queue.Queue()

        # Initialize video processor (if available)
        self.video_processor = None
        try:
            self.video_processor = EnhancedVideoProcessor()
        except Exception as e:
            logger.warning(f"Video processor not available: {e}")

        # Load processed data
        self._load_processed_data()

        logger.info("Gradio MV Face Recognition app initialized")

    def _load_processed_data(self):
        """Load pre-processed video data and metadata."""
        logger.info("Loading processed data...")

        # Load video metadata
        for metadata_file in self.metadata_dir.glob("*_metadata.json"):
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                video_name = metadata["video_info"]["filename"]
                self.video_metadata[video_name] = metadata
                logger.info(f"Loaded metadata for {video_name}")
            except Exception as e:
                logger.error(f"Error loading {metadata_file}: {e}")

        # Load clips data
        self._load_clips_data()

        # Calculate contestant statistics
        self._calculate_contestant_stats()

        logger.info(f"Loaded data for {len(self.video_metadata)} videos")

    def _load_clips_data(self):
        """Load information about generated clips."""
        self.clips_data = {}

        for clip_file in self.clips_dir.glob("*.mp4"):
            # Parse clip filename to extract information
            stem = clip_file.stem
            parts = stem.split("_")

            if len(parts) >= 3:
                video_base = parts[0]
                contestant = "_".join(parts[1:-2])  # Handle multi-word names
                clip_num = parts[-1]

                if contestant not in self.clips_data:
                    self.clips_data[contestant] = []

                self.clips_data[contestant].append(
                    {
                        "file_path": str(clip_file),
                        "video_source": video_base,
                        "clip_number": clip_num,
                        "contestant": contestant,
                    }
                )

    def _calculate_contestant_stats(self):
        """Calculate overall contestant statistics across all videos."""
        self.contestant_stats = {}

        for video_name, metadata in self.video_metadata.items():
            contestant_timeline = metadata.get("contestant_timeline", {})

            for contestant, data in contestant_timeline.items():
                if contestant not in self.contestant_stats:
                    self.contestant_stats[contestant] = {
                        "total_appearances": 0,
                        "videos_appeared": [],
                        "avg_confidence": 0,
                        "best_confidence": 0,
                        "total_clips": 0,
                    }

                stats = self.contestant_stats[contestant]
                stats["total_appearances"] += data["total_appearances"]
                stats["videos_appeared"].append(video_name)
                stats["avg_confidence"] = max(
                    stats["avg_confidence"], data["avg_confidence"]
                )
                stats["best_confidence"] = max(
                    stats["best_confidence"], data["max_confidence"]
                )

                # Count clips for this contestant
                stats["total_clips"] = len(self.clips_data.get(contestant, []))

    def get_available_videos(self) -> List[str]:
        """Get list of available processed videos."""
        videos = []
        for video_file in self.processed_videos_dir.glob("*_annotated.mp4"):
            # Find original video name
            base_name = video_file.stem.replace("_annotated", "")
            for original_name in self.video_metadata.keys():
                if Path(original_name).stem == base_name:
                    videos.append(original_name)
                    break
        return sorted(videos)

    def get_video_path(self, video_name: str) -> Optional[str]:
        """Get path to processed annotated video."""
        if not video_name:
            return None

        base_name = Path(video_name).stem
        annotated_path = self.processed_videos_dir / f"{base_name}_annotated.mp4"

        if annotated_path.exists():
            return str(annotated_path)
        return None

    def get_video_info(self, video_name: str) -> Tuple[str, str]:
        """Get video information and contestant timeline."""
        if not video_name or video_name not in self.video_metadata:
            return "No video selected", ""

        metadata = self.video_metadata[video_name]
        video_info = metadata["video_info"]

        # Format basic video info
        info_text = f"""
**Video Information:**
- **Duration:** {video_info.get('duration_seconds', 0):.1f} seconds
- **Resolution:** {video_info.get('width', 0)}x{video_info.get('height', 0)}
- **FPS:** {video_info.get('fps', 0):.1f}
- **File Size:** {video_info.get('file_size_mb', 0):.1f} MB

**Recognition Summary:**
- **Faces Detected:** {metadata['recognition_summary']['total_faces_detected']}
- **Faces Recognized:** {metadata['recognition_summary']['total_faces_recognized']}
- **Recognition Rate:** {metadata['recognition_summary']['recognition_rate']:.1%}
- **Unique Contestants:** {metadata['recognition_summary']['unique_contestants']}
"""

        # Format contestant timeline
        contestant_timeline = metadata.get("contestant_timeline", {})
        if contestant_timeline:
            timeline_text = "**Contestants Detected:**\\n\\n"

            # Sort by total appearances
            sorted_contestants = sorted(
                contestant_timeline.items(),
                key=lambda x: x[1]["total_appearances"],
                reverse=True,
            )

            for contestant, data in sorted_contestants[:10]:  # Top 10
                timeline_text += f"**{contestant}**\\n"
                timeline_text += f"- Appearances: {data['total_appearances']}\\n"
                timeline_text += f"- Avg Confidence: {data['avg_confidence']:.2f}\\n"
                timeline_text += (
                    f"- First seen: {data['first_appearance_time']:.1f}s\\n"
                )
                timeline_text += (
                    f"- Last seen: {data['last_appearance_time']:.1f}s\\n\\n"
                )
        else:
            timeline_text = "No contestants detected in this video."

        return info_text, timeline_text

    def get_contestant_clips(
        self, contestant_filter: str = "All"
    ) -> List[Tuple[str, str]]:
        """Get clips for a specific contestant or all clips."""
        clips_list = []

        if contestant_filter == "All":
            # Return all clips
            for contestant, clips in self.clips_data.items():
                for clip in clips:
                    label = f"{contestant} - {clip['video_source']} (Clip {clip['clip_number']})"
                    clips_list.append((clip["file_path"], label))
        else:
            # Return clips for specific contestant
            if contestant_filter in self.clips_data:
                for clip in self.clips_data[contestant_filter]:
                    label = f"{clip['video_source']} (Clip {clip['clip_number']})"
                    clips_list.append((clip["file_path"], label))

        return clips_list

    def get_contestant_list(self) -> List[str]:
        """Get list of all contestants with clips."""
        contestants = ["All"] + sorted(list(self.clips_data.keys()))
        return contestants

    def get_analytics_data(self) -> Tuple[str, str]:
        """Get analytics information."""

        # Overall statistics
        total_videos = len(self.video_metadata)
        total_contestants = len(self.contestant_stats)
        total_clips = sum(len(clips) for clips in self.clips_data.values())

        overall_stats = f"""
# 🎬 MV Face Recognition Analytics

## 📊 Overall Statistics
- **Total Videos Processed:** {total_videos}
- **Total Contestants Detected:** {total_contestants}  
- **Total Highlight Clips:** {total_clips}
- **Processing Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 🎭 Top Performing Contestants
"""

        # Top contestants by appearances
        if self.contestant_stats:
            sorted_contestants = sorted(
                self.contestant_stats.items(),
                key=lambda x: x[1]["total_appearances"],
                reverse=True,
            )

            for i, (contestant, stats) in enumerate(sorted_contestants[:15], 1):
                overall_stats += f"{i}. **{contestant}** - {stats['total_appearances']} appearances across {len(stats['videos_appeared'])} videos\\n"

        # Video-specific statistics
        video_stats = "## 🎥 Video Processing Details\\n\\n"

        for video_name, metadata in self.video_metadata.items():
            summary = metadata["recognition_summary"]
            video_stats += f"### {video_name}\\n"
            video_stats += f"- **Faces Detected:** {summary['total_faces_detected']}\\n"
            video_stats += (
                f"- **Faces Recognized:** {summary['total_faces_recognized']}\\n"
            )
            video_stats += (
                f"- **Recognition Rate:** {summary['recognition_rate']:.1%}\\n"
            )
            video_stats += (
                f"- **Unique Contestants:** {summary['unique_contestants']}\\n\\n"
            )

        return overall_stats, video_stats

    def get_available_source_videos(self) -> List[str]:
        """Get list of available source videos for processing."""
        if not self.video_processor:
            return []

        try:
            return self.video_processor.get_available_videos()
        except Exception as e:
            logger.error(f"Error getting source videos: {e}")
            return []

    def process_video_with_progress(
        self, video_name: str, similarity_threshold: float
    ) -> Generator[Dict, None, None]:
        """Process a video with real-time progress updates."""
        if not self.video_processor or not video_name:
            yield {
                "progress": 0,
                "status": "Error: Video processor not available or no video selected",
                "stage": "Error",
                "video_name": "",
                "stats": {},
            }
            return

        self.is_processing = True

        try:
            # Set similarity threshold
            self.video_processor.set_similarity_threshold(similarity_threshold)

            # Initialize progress tracking
            total_steps = 5
            current_step = 0

            # Progress callback for the video processor
            def progress_callback(step, total, step_desc):
                progress = int((step / total) * 100)
                self.current_progress = {
                    "stage": f"Step {current_step + 1}/{total_steps}",
                    "progress": progress,
                    "status": step_desc,
                    "video_name": video_name,
                    "stats": {},
                }

            # Step 1: Initialize
            current_step = 1
            yield {
                "progress": int((current_step / total_steps) * 100),
                "status": "Initializing video processing...",
                "stage": f"Step {current_step}/{total_steps}",
                "video_name": video_name,
                "stats": {},
            }
            time.sleep(0.5)

            # Step 2: Face recognition analysis
            current_step = 2
            yield {
                "progress": int((current_step / total_steps) * 100),
                "status": "Analyzing faces and recognition...",
                "stage": f"Step {current_step}/{total_steps}",
                "video_name": video_name,
                "stats": {},
            }

            recognition_results = self.video_processor.process_video_for_recognition(
                video_name, progress_callback=progress_callback
            )

            # Step 3: Generate annotated video
            current_step = 3
            yield {
                "progress": int((current_step / total_steps) * 100),
                "status": "Creating annotated video...",
                "stage": f"Step {current_step}/{total_steps}",
                "video_name": video_name,
                "stats": {
                    "faces_detected": recognition_results.get(
                        "total_faces_detected", 0
                    ),
                    "faces_recognized": recognition_results.get(
                        "total_faces_recognized", 0
                    ),
                    "frames_skipped": recognition_results.get(
                        "total_frames_skipped", 0
                    ),
                },
            }

            annotated_video_path = self.video_processor.create_enhanced_annotated_video(
                video_name, recognition_results
            )

            # Step 4: Extract highlight clips
            current_step = 4
            yield {
                "progress": int((current_step / total_steps) * 100),
                "status": "Extracting highlight clips...",
                "stage": f"Step {current_step}/{total_steps}",
                "video_name": video_name,
                "stats": {
                    "faces_detected": recognition_results.get(
                        "total_faces_detected", 0
                    ),
                    "faces_recognized": recognition_results.get(
                        "total_faces_recognized", 0
                    ),
                    "frames_skipped": recognition_results.get(
                        "total_frames_skipped", 0
                    ),
                    "unique_contestants": len(
                        recognition_results.get("contestant_appearances", {})
                    ),
                },
            }

            clips_info = self.video_processor.extract_highlight_clips(
                video_name, recognition_results
            )

            # Step 5: Save metadata and finalize
            current_step = 5
            yield {
                "progress": int((current_step / total_steps) * 100),
                "status": "Saving results and finalizing...",
                "stage": f"Step {current_step}/{total_steps}",
                "video_name": video_name,
                "stats": {
                    "faces_detected": recognition_results.get(
                        "total_faces_detected", 0
                    ),
                    "faces_recognized": recognition_results.get(
                        "total_faces_recognized", 0
                    ),
                    "frames_skipped": recognition_results.get(
                        "total_frames_skipped", 0
                    ),
                    "unique_contestants": len(
                        recognition_results.get("contestant_appearances", {})
                    ),
                    "clips_generated": len(clips_info),
                },
            }

            # Generate and save metadata
            metadata = self.video_processor.generate_video_metadata(
                video_name, recognition_results
            )
            metadata_file = (
                self.video_processor.metadata_dir
                / f"{Path(video_name).stem}_metadata.json"
            )
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, default=str)

            # Final completion
            yield {
                "progress": 100,
                "status": f"✅ Processing complete! Generated {len(clips_info)} clips.",
                "stage": "Complete",
                "video_name": video_name,
                "stats": {
                    "faces_detected": recognition_results.get(
                        "total_faces_detected", 0
                    ),
                    "faces_recognized": recognition_results.get(
                        "total_faces_recognized", 0
                    ),
                    "frames_skipped": recognition_results.get(
                        "total_frames_skipped", 0
                    ),
                    "unique_contestants": len(
                        recognition_results.get("contestant_appearances", {})
                    ),
                    "clips_generated": len(clips_info),
                    "annotated_video": str(annotated_video_path)
                    if annotated_video_path
                    else "",
                },
            }

            # Reload processed data to include new results
            self._load_processed_data()

        except Exception as e:
            logger.error(f"Error processing video {video_name}: {e}")
            yield {
                "progress": 0,
                "status": f"❌ Error: {str(e)}",
                "stage": "Error",
                "video_name": video_name,
                "stats": {},
            }

        finally:
            self.is_processing = False

    def format_processing_stats(self, stats: Dict) -> str:
        """Format processing statistics for display."""
        if not stats:
            return "No statistics available"

        formatted = "## 📊 Processing Statistics\n\n"

        if "faces_detected" in stats:
            formatted += f"- **Faces Detected:** {stats['faces_detected']}\n"
        if "faces_recognized" in stats:
            formatted += f"- **Faces Recognized:** {stats['faces_recognized']}\n"
        if "frames_skipped" in stats:
            formatted += f"- **Frames Skipped:** {stats['frames_skipped']} (no faces)\n"
        if "unique_contestants" in stats:
            formatted += f"- **Unique Contestants:** {stats['unique_contestants']}\n"
        if "clips_generated" in stats:
            formatted += f"- **Clips Generated:** {stats['clips_generated']}\n"

        if (
            "faces_detected" in stats
            and "faces_recognized" in stats
            and stats["faces_detected"] > 0
        ):
            recognition_rate = (
                stats["faces_recognized"] / stats["faces_detected"]
            ) * 100
            formatted += f"- **Recognition Rate:** {recognition_rate:.1f}%\n"

        return formatted

    def get_system_info(self) -> str:
        """Get system and hardware acceleration information."""
        info_text = "## 🖥️ System Information\\n\\n"

        if self.video_processor:
            try:
                hw_info = self.video_processor.get_hardware_info()
                info_text += f"**Processing Mode:** {hw_info['acceleration_type']}\\n"
                info_text += f"**Status:** {hw_info['status']}\\n\\n"

                detector_info = hw_info.get("face_detector", {})
                if detector_info:
                    providers = detector_info.get("providers", [])
                    if providers:
                        info_text += "**Execution Providers:**\\n"
                        for i, provider in enumerate(providers, 1):
                            icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                            info_text += f"{icon} {provider}\\n"
                        info_text += "\\n"

                    system_info = detector_info.get("system_info", {})
                    if system_info:
                        info_text += "**System Details:**\\n"
                        info_text += (
                            f"- Platform: {system_info.get('platform', 'Unknown')}\\n"
                        )
                        info_text += f"- Architecture: {system_info.get('machine', 'Unknown')}\\n"

                        if detector_info.get("apple_silicon"):
                            info_text += "- Apple Silicon: ✅ Detected\\n"
                        if detector_info.get("cuda_available"):
                            info_text += "- CUDA: ✅ Available\\n"

                        batch_size = detector_info.get("batch_size", 8)
                        info_text += f"- Optimal Batch Size: {batch_size}\\n"

            except Exception as e:
                info_text += f"**Error getting hardware info:** {e}\\n"
        else:
            info_text += "**Processing Mode:** Pre-processed data only\\n"
            info_text += "**Status:** Video processor not available\\n"

        return info_text

    def create_interface(self):
        """Create the main Gradio interface."""

        # Custom CSS for better styling
        css = """
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .video-container {
            border-radius: 10px;
            overflow: hidden;
        }
        .info-panel {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        .progress-container {
            background: #ffffff;
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            padding: 20px;
            margin: 10px 0;
        }
        .status-success {
            color: #28a745;
            font-weight: bold;
        }
        .status-error {
            color: #dc3545;
            font-weight: bold;
        }
        .status-processing {
            color: #007bff;
            font-weight: bold;
        }
        """

        with gr.Blocks(
            css=css, title="MV Face Recognition", theme=gr.themes.Soft()
        ) as demo:
            gr.Markdown("""
            # 🎬 MV Face Recognition System
            
            **Intelligent contestant recognition in music videos using AI face detection.**
            
            Explore annotated music videos with real-time contestant identification, browse highlight clips, 
            and analyze recognition statistics across multiple performances.
            """)

            with gr.Tabs():
                # Video Gallery Tab
                with gr.TabItem("🎥 Video Gallery", id="video_gallery"):
                    with gr.Row():
                        with gr.Column(scale=2):
                            video_selector = gr.Dropdown(
                                choices=self.get_available_videos(),
                                label="Select Video",
                                value=self.get_available_videos()[0]
                                if self.get_available_videos()
                                else None,
                                interactive=True,
                            )

                            video_player = gr.Video(
                                label="Annotated Video with Contestant Recognition",
                                elem_classes=["video-container"],
                            )

                        with gr.Column(scale=1):
                            video_info = gr.Markdown(
                                label="Video Information", elem_classes=["info-panel"]
                            )

                            contestant_timeline = gr.Markdown(
                                label="Contestant Timeline", elem_classes=["info-panel"]
                            )

                    # Update video when selection changes
                    video_selector.change(
                        fn=lambda video_name: [
                            self.get_video_path(video_name),
                            *self.get_video_info(video_name),
                        ],
                        inputs=[video_selector],
                        outputs=[video_player, video_info, contestant_timeline],
                    )

                    # Initialize with first video
                    if self.get_available_videos():
                        demo.load(
                            fn=lambda: [
                                self.get_video_path(self.get_available_videos()[0]),
                                *self.get_video_info(self.get_available_videos()[0]),
                            ],
                            outputs=[video_player, video_info, contestant_timeline],
                        )

                # Highlight Clips Tab
                with gr.TabItem("✨ Highlight Clips", id="clips_gallery"):
                    with gr.Row():
                        contestant_filter = gr.Dropdown(
                            choices=self.get_contestant_list(),
                            value="All",
                            label="Filter by Contestant",
                            interactive=True,
                        )

                    with gr.Row():
                        with gr.Column(scale=2):
                            clips_gallery = gr.Gallery(
                                label="Highlight Clips",
                                show_label=True,
                                elem_id="clips_gallery",
                                columns=3,
                                height="auto",
                            )

                        with gr.Column(scale=1):
                            gr.Video(
                                label="Selected Clip", elem_classes=["video-container"]
                            )

                            gr.Markdown(
                                "Select a clip to view details",
                                elem_classes=["info-panel"],
                            )

                    # Update clips when filter changes
                    contestant_filter.change(
                        fn=self.get_contestant_clips,
                        inputs=[contestant_filter],
                        outputs=[clips_gallery],
                    )

                    # Load initial clips
                    demo.load(
                        fn=lambda: self.get_contestant_clips("All"),
                        outputs=[clips_gallery],
                    )

                # Process Videos Tab
                with gr.TabItem("🎬 Process Videos", id="process_videos"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("## Video Processing")

                            with gr.Row():
                                source_video_selector = gr.Dropdown(
                                    choices=self.get_available_source_videos(),
                                    label="Select Video to Process",
                                    interactive=True,
                                    scale=4,
                                )

                                refresh_btn = gr.Button(
                                    "🔄 Refresh", size="sm", scale=1
                                )

                            similarity_threshold_processing = gr.Slider(
                                minimum=0.0,
                                maximum=1.0,
                                value=0.25,
                                step=0.05,
                                label="Face Similarity Threshold",
                                info="Lower values = more matches, Higher values = stricter matches",
                            )

                            process_btn = gr.Button(
                                "🎬 Start Processing", variant="primary", size="lg"
                            )

                            # Progress indicators
                            gr.Progress()

                            with gr.Group(elem_classes=["progress-container"]):
                                processing_stage = gr.Textbox(
                                    label="Current Stage",
                                    interactive=False,
                                    placeholder="Ready to process...",
                                )

                                processing_status = gr.Textbox(
                                    label="Status",
                                    interactive=False,
                                    placeholder="Select a video and click Start Processing",
                                )

                                processing_time = gr.Textbox(
                                    label="Processing Time",
                                    interactive=False,
                                    placeholder="--:--",
                                )

                        with gr.Column(scale=1):
                            processing_stats = gr.Markdown(
                                "## 📊 Processing Statistics\n\nNo processing started yet.",
                                elem_classes=["info-panel"],
                            )

                            result_video = gr.Video(
                                label="Processed Video Result",
                                visible=False,
                                elem_classes=["video-container"],
                            )

                    # Processing function with progress
                    def process_video_gradio(
                        video_name, threshold, progress=gr.Progress()
                    ):
                        if not video_name:
                            return (
                                "No video selected",
                                "Please select a video first",
                                "--:--",
                                "## 📊 Processing Statistics\n\nNo video selected.",
                                None,
                                gr.update(visible=False),
                            )

                        results = []
                        final_result = None
                        start_time = time.time()

                        # Process with real-time updates
                        for update in self.process_video_with_progress(
                            video_name, threshold
                        ):
                            progress(update["progress"] / 100, desc=update["status"])
                            results.append(update)
                            final_result = update

                            # Calculate elapsed time
                            elapsed = time.time() - start_time
                            elapsed_str = (
                                f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
                            )

                            # Update interface elements
                            yield (
                                update["stage"],
                                update["status"],
                                elapsed_str,
                                self.format_processing_stats(update["stats"]),
                                None,
                                gr.update(visible=False),
                            )

                        # Show final result
                        elapsed = time.time() - start_time
                        elapsed_str = (
                            f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
                        )

                        if final_result and "annotated_video" in final_result["stats"]:
                            video_path = final_result["stats"]["annotated_video"]
                            if video_path and Path(video_path).exists():
                                yield (
                                    final_result["stage"],
                                    final_result["status"],
                                    elapsed_str,
                                    self.format_processing_stats(final_result["stats"]),
                                    video_path,
                                    gr.update(visible=True),
                                )
                            else:
                                yield (
                                    final_result["stage"],
                                    final_result["status"],
                                    elapsed_str,
                                    self.format_processing_stats(final_result["stats"]),
                                    None,
                                    gr.update(visible=False),
                                )

                    # Connect the processing button
                    process_btn.click(
                        fn=process_video_gradio,
                        inputs=[source_video_selector, similarity_threshold_processing],
                        outputs=[
                            processing_stage,
                            processing_status,
                            processing_time,
                            processing_stats,
                            result_video,
                            result_video,
                        ],
                        show_progress=True,
                    )

                    # Refresh button functionality
                    def refresh_source_videos():
                        return gr.update(choices=self.get_available_source_videos())

                    refresh_btn.click(
                        fn=refresh_source_videos, outputs=[source_video_selector]
                    )

                # Analytics Tab
                with gr.TabItem("📊 Analytics", id="analytics"):
                    with gr.Row():
                        with gr.Column():
                            overall_stats = gr.Markdown()

                        with gr.Column():
                            video_stats = gr.Markdown()

                    # Processing Settings
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("## Processing Settings")

                            gr.Slider(
                                minimum=0.0,
                                maximum=1.0,
                                value=0.25,
                                step=0.05,
                                label="Face Similarity Threshold",
                                info="Lower values = more matches, Higher values = stricter matches",
                            )

                            gr.Markdown(
                                "**Tip:** Use the 'Process Videos' tab for real-time video processing with live progress tracking."
                            )

                    # Load analytics data
                    demo.load(
                        fn=self.get_analytics_data, outputs=[overall_stats, video_stats]
                    )

                # About Tab
                with gr.TabItem("ℹ️ About", id="about"):
                    with gr.Row():
                        with gr.Column(scale=2):
                            gr.Markdown("""
                            ## About MV Face Recognition
                            
                            This system uses advanced AI face recognition to identify contestants in music videos.
                            
                            ### Features:
                            - **Intelligent Face Detection**: Uses InsightFace models for accurate face detection
                            - **Contestant Database**: Recognizes 95+ contestants with high accuracy
                            - **Enhanced Annotations**: Color-coded bounding boxes with confidence scores
                            - **Automatic Highlights**: AI-generated clips featuring specific contestants
                            - **Comprehensive Analytics**: Detailed statistics and appearance timelines
                            - **Hardware Acceleration**: Optimized for Apple Silicon and CUDA GPUs
                            
                            ### Technology Stack:
                            - **Face Recognition**: InsightFace (buffalo_l model)
                            - **Vector Search**: ChromaDB for fast similarity matching
                            - **Video Processing**: OpenCV with enhanced annotation rendering
                            - **Hardware Acceleration**: ONNX Runtime with GPU support
                            - **Interface**: Gradio for interactive ML demos
                            - **Deployment**: Optimized for local and cloud deployment
                            
                            ### Dataset:
                            - **Videos**: 10+ music videos from talent competition shows
                            - **Contestants**: 95 pre-trained contestant embeddings
                            - **Processing**: Real-time and batch processing support
                            
                            ---
                            
                            **Note**: All videos and contestant data are used for demonstration purposes only.
                            This system showcases the capabilities of modern AI face recognition technology.
                            """)

                        with gr.Column(scale=1):
                            gr.Markdown(
                                self.get_system_info(), elem_classes=["info-panel"]
                            )

        return demo


def main():
    """Main function to launch the Gradio app."""
    try:
        # Initialize the application
        app = GradioMVFaceRecognition()

        # Create the interface
        demo = app.create_interface()

        # Launch configuration
        if os.getenv("SPACES_ZERO_GPU"):
            # Running on HF Spaces with Zero GPU
            demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
        else:
            # Local development
            demo.launch(
                server_name="127.0.0.1", server_port=7860, share=True, debug=True
            )

    except Exception as e:
        logger.error("Error launching Gradio app: %s", e)
        raise


if __name__ == "__main__":
    main()
