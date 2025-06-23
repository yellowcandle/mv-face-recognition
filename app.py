"""
Streamlit application for MV Face Recognition.
Clean rewrite focusing on processing videos in /source/videos/ directory.
"""

import streamlit as st
import logging
import os
import time
from pathlib import Path
import pandas as pd
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our modules
try:
    from src.services.video_processor import VideoProcessor
    from src.database.chroma_setup import ChromaDBManager
    from src.core.face_detector import FaceDetector
    from src.core.face_matcher import FaceMatcher
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="MV Face Recognition",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "video_processor" not in st.session_state:
    with st.spinner("Initializing system..."):
        try:
            st.session_state.video_processor = VideoProcessor()
            st.session_state.db_manager = ChromaDBManager()
            st.session_state.system_ready = True
        except Exception as e:
            st.error(f"Failed to initialize system: {e}")
            st.session_state.system_ready = False


def main():
    """Main application function."""
    st.title("🎬 MV Face Recognition System")
    st.markdown("Process videos from `/source/videos/` directory for face recognition")

    if not st.session_state.get("system_ready", False):
        st.error("System not ready. Please check the error messages above.")
        return

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page", ["Video Processing", "Database Status", "Configuration"]
    )

    if page == "Video Processing":
        video_processing_page()
    elif page == "Database Status":
        database_status_page()
    elif page == "Configuration":
        configuration_page()


def video_processing_page():
    """Video processing interface."""
    st.header("Video Processing")

    # Get available videos
    videos = st.session_state.video_processor.get_available_videos()

    if not videos:
        st.warning("No videos found in `/source/videos/` directory")
        st.info("Please add video files to the `/source/videos/` directory")
        return

    st.success(f"Found {len(videos)} videos in `/source/videos/` directory")

    # Add helpful info about similarity threshold
    st.info(
        "💡 **Tip**: If no faces are recognized, try lowering the similarity threshold in Advanced Options below. Lower values (0.2-0.4) will find more matches."
    )

    # Video selection
    selected_video = st.selectbox("Select video to process:", videos)

    if selected_video:
        # Display video information
        with st.expander("Video Information", expanded=True):
            video_info = st.session_state.video_processor.get_video_info(selected_video)

            if "error" in video_info:
                st.error(f"Error loading video: {video_info['error']}")
                return

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Duration", video_info.get("duration_formatted", "Unknown"))
                st.metric("FPS", f"{video_info.get('fps', 0):.1f}")
            with col2:
                st.metric(
                    "Resolution",
                    f"{video_info.get('width', 0)}x{video_info.get('height', 0)}",
                )
                st.metric("Total Frames", f"{video_info.get('frame_count', 0):,}")
            with col3:
                st.metric("File Size", f"{video_info.get('file_size_mb', 0):.1f} MB")

        # Processing options
        st.subheader("Processing Options")

        col1, col2 = st.columns(2)
        with col1:
            start_time = st.number_input(
                "Start time (seconds)", min_value=0.0, value=0.0, step=1.0
            )
        with col2:
            max_duration = video_info.get("duration_seconds", 300)
            end_time = st.number_input(
                "End time (seconds)",
                min_value=start_time + 1,
                value=min(start_time + 60, max_duration),
                max_value=max_duration,
                step=1.0,
            )

        # Advanced options
        with st.expander("🔧 Advanced Options", expanded=True):
            st.markdown("**Face Recognition Settings**")

            similarity_threshold = st.slider(
                "Similarity threshold",
                min_value=0.1,
                max_value=0.9,
                value=0.4,
                step=0.05,
                help="Lower values = more matches but less accuracy. Higher values = fewer but more accurate matches.",
            )

            # Add threshold guidance
            if similarity_threshold <= 0.3:
                st.info(
                    "🔍 **Very Low** - Will match many faces but with lower confidence"
                )
            elif similarity_threshold <= 0.5:
                st.info(
                    "⚖️ **Balanced** - Good mix of matches and accuracy (Recommended)"
                )
            elif similarity_threshold <= 0.7:
                st.info("🎯 **Strict** - Fewer matches but higher confidence")
            else:
                st.info("🔒 **Very Strict** - Only very similar faces will match")

            # Add quick threshold recommendations
            st.markdown("**💡 Quick Settings:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(
                    "🔍 More Matches", help="Lower threshold for more results"
                ):
                    similarity_threshold = 0.3
                    st.rerun()
            with col2:
                if st.button("⚖️ Balanced", help="Recommended balanced setting"):
                    similarity_threshold = 0.4
                    st.rerun()
            with col3:
                if st.button("🎯 Strict", help="Higher accuracy, fewer matches"):
                    similarity_threshold = 0.6
                    st.rerun()

            st.markdown("**Processing Settings**")
            frame_skip = st.slider(
                "Frame skip (process every N frames)",
                min_value=1,
                max_value=30,
                value=5,
                help="Higher values = faster processing but may miss faces",
            )

        # Processing controls
        col1, col2, col3 = st.columns(3)

        with col1:
            process_button = st.button("🎯 Process Video", type="primary")

        with col2:
            create_annotated = st.checkbox("Create annotated video", value=True)

        with col3:
            export_csv = st.checkbox("Export CSV results", value=True)

        # Processing mode selection
        col1, col2 = st.columns(2)
        with col1:
            processing_mode = st.radio(
                "Processing Mode",
                ["Real-time Preview", "Batch Processing"],
                help="Real-time shows live preview, Batch is faster for final results",
            )

        # Process video
        if process_button:
            if processing_mode == "Real-time Preview":
                process_video_realtime(
                    selected_video,
                    start_time,
                    end_time,
                    similarity_threshold,
                    frame_skip,
                    create_annotated,
                    export_csv,
                )
            else:
                process_video_batch(
                    selected_video,
                    start_time,
                    end_time,
                    similarity_threshold,
                    frame_skip,
                    create_annotated,
                    export_csv,
                )


def process_video_realtime(
    video_name,
    start_time,
    end_time,
    similarity_threshold,
    frame_skip,
    create_annotated,
    export_csv,
):
    """Process video with real-time preview."""

    # Update configuration
    with open("config.json", "r") as f:
        config = json.load(f)

    config["face_matching"]["similarity_threshold"] = similarity_threshold
    config["video_processing"]["frame_skip"] = frame_skip

    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

    # Reinitialize components with new config
    st.session_state.video_processor = VideoProcessor()

    st.subheader("🎬 Real-time Face Recognition")

    # Create layout for real-time preview
    preview_col, stats_col = st.columns([3, 2])

    with preview_col:
        st.markdown("**Live Preview**")
        frame_placeholder = st.empty()
        progress_placeholder = st.empty()

    with stats_col:
        st.markdown("**Live Statistics**")
        metrics_placeholder = st.empty()
        contestants_placeholder = st.empty()

    # Control buttons (for future pause/resume functionality)
    control_col1, control_col2, control_col3 = st.columns(3)

    # Add stop button in session state
    if "processing_stopped" not in st.session_state:
        st.session_state.processing_stopped = False

    # Initialize processing
    try:
        # Estimate total frames
        estimated_total = int((end_time - start_time) * 30 / frame_skip)

        # Storage for results
        all_results = {
            "video_name": video_name,
            "total_frames_processed": 0,
            "total_faces_detected": 0,
            "total_faces_recognized": 0,
            "contestant_appearances": {},
            "frame_results": [],
        }

        contestant_counts = {}

        # Real-time processing
        processor = st.session_state.video_processor.process_video_realtime(
            video_name, start_time, end_time
        )

        for frame_num, annotated_frame, face_results, frame_stats in processor:
            # Update frame display
            with frame_placeholder.container():
                st.image(annotated_frame, channels="BGR", use_container_width=True)

                # Progress info
                progress = frame_stats["total_faces_detected"] / max(
                    estimated_total * 2, 1
                )  # Rough estimate
                progress = min(progress, 1.0)

                st.progress(progress)
                timestamp = int(frame_stats["frame_timestamp"])
                minutes = timestamp // 60
                seconds = timestamp % 60
                st.caption(
                    f"Frame {all_results['total_frames_processed'] + 1} | {minutes}:{seconds:02d} | "
                    f"{frame_stats['processing_fps']:.1f} FPS"
                )

            # Update statistics
            with metrics_placeholder.container():
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("👥 Faces in Frame", frame_stats["current_frame_faces"])
                    st.metric("🎯 Recognized", frame_stats["current_frame_recognized"])
                with col2:
                    st.metric("📊 Total Detected", frame_stats["total_faces_detected"])
                    st.metric(
                        "✅ Total Recognized", frame_stats["total_faces_recognized"]
                    )

            # Update contestant counts
            for face_result in face_results:
                if face_result["matched"]:
                    name = face_result["contestant_name"]
                    if name not in contestant_counts:
                        contestant_counts[name] = 0
                    contestant_counts[name] += 1

            # Show top contestants
            if contestant_counts:
                with contestants_placeholder.container():
                    st.markdown("**Current Top Contestants:**")
                    sorted_contestants = sorted(
                        contestant_counts.items(), key=lambda x: x[1], reverse=True
                    )[:5]
                    for name, count in sorted_contestants:
                        st.text(f"• {name}: {count} appearances")

            # Store results
            all_results["total_frames_processed"] += 1
            all_results["total_faces_detected"] = frame_stats["total_faces_detected"]
            all_results["total_faces_recognized"] = frame_stats[
                "total_faces_recognized"
            ]

            # Add to contestant appearances
            for face_result in face_results:
                if face_result["matched"]:
                    name = face_result["contestant_name"]
                    if name not in all_results["contestant_appearances"]:
                        all_results["contestant_appearances"][name] = {
                            "total_appearances": 0,
                            "first_appearance": frame_num,
                            "last_appearance": frame_num,
                            "confidence_scores": [],
                        }

                    appearances = all_results["contestant_appearances"][name]
                    appearances["total_appearances"] += 1
                    appearances["last_appearance"] = frame_num
                    appearances["confidence_scores"].append(
                        face_result["recognition_confidence"]
                    )

            # Small delay to make preview visible
            time.sleep(0.1)

        # Final processing completion
        st.success("✅ Real-time processing completed!")

        # Calculate final statistics
        for name, appearances in all_results["contestant_appearances"].items():
            if appearances["confidence_scores"]:
                appearances["avg_confidence"] = sum(
                    appearances["confidence_scores"]
                ) / len(appearances["confidence_scores"])
                appearances["max_confidence"] = max(appearances["confidence_scores"])

        # Create outputs if requested
        if create_annotated or export_csv:
            with st.spinner("Creating final outputs..."):
                if create_annotated:
                    # Use batch processor for final annotated video
                    batch_results = (
                        st.session_state.video_processor.process_video_for_recognition(
                            video_name, start_time=start_time, end_time=end_time
                        )
                    )
                    annotated_path = (
                        st.session_state.video_processor.create_annotated_video(
                            video_name, batch_results
                        )
                    )
                    if annotated_path and os.path.exists(annotated_path):
                        st.success(f"✅ Annotated video created: `{annotated_path}`")

                if export_csv:
                    csv_path = st.session_state.video_processor.export_results_to_csv(
                        all_results
                    )
                    if csv_path and os.path.exists(csv_path):
                        st.success(f"✅ CSV results exported: `{csv_path}`")

        # Store results
        st.session_state.last_results = all_results

        # Show final summary
        show_final_summary(all_results)

    except Exception as e:
        st.error(f"Error in real-time processing: {e}")
        logger.error(f"Real-time processing error: {e}")


def process_video_batch(
    video_name,
    start_time,
    end_time,
    similarity_threshold,
    frame_skip,
    create_annotated,
    export_csv,
):
    """Process the selected video."""

    # Update configuration
    with open("config.json", "r") as f:
        config = json.load(f)

    config["face_matching"]["similarity_threshold"] = similarity_threshold
    config["video_processing"]["frame_skip"] = frame_skip

    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

    # Reinitialize components with new config
    st.session_state.video_processor = VideoProcessor()

    st.subheader("Processing Progress")

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(frames_processed):
        estimated_total = int(
            (end_time - start_time) * 30 / frame_skip
        )  # Rough estimate
        progress = min(frames_processed / max(estimated_total, 1), 1.0)
        progress_bar.progress(progress)
        status_text.text(f"Processed {frames_processed} frames...")

    # Process video
    start_processing_time = time.time()

    try:
        with st.spinner("Processing video for face recognition..."):
            results = st.session_state.video_processor.process_video_for_recognition(
                video_name,
                start_time=start_time,
                end_time=end_time,
                progress_callback=progress_callback,
            )

        processing_time = time.time() - start_processing_time

        # Display results
        st.success(f"✅ Processing completed in {processing_time:.1f} seconds!")

        # Summary statistics
        st.subheader("Recognition Results")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Frames Processed", results["total_frames_processed"])
        with col2:
            st.metric("Faces Detected", results["total_faces_detected"])
        with col3:
            st.metric("Faces Recognized", results["total_faces_recognized"])

        # Contestant appearances
        if results["contestant_appearances"]:
            st.subheader("Contestant Appearances")

            appearances_data = []
            for name, data in results["contestant_appearances"].items():
                appearances_data.append(
                    {
                        "Contestant": name,
                        "Appearances": data["total_appearances"],
                        "Avg Confidence": f"{data.get('avg_confidence', 0):.3f}",
                        "Max Confidence": f"{data.get('max_confidence', 0):.3f}",
                        "First Frame": data["first_appearance"],
                        "Last Frame": data["last_appearance"],
                    }
                )

            df = pd.DataFrame(appearances_data)
            st.dataframe(df, use_container_width=True)

            # Visualization
            if len(appearances_data) > 0:
                st.subheader("Appearance Chart")
                chart_data = pd.DataFrame(
                    {
                        "Contestant": [item["Contestant"] for item in appearances_data],
                        "Appearances": [
                            item["Appearances"] for item in appearances_data
                        ],
                    }
                )
                st.bar_chart(chart_data.set_index("Contestant"))
        else:
            st.info("No contestants recognized in this video segment")

        # Create outputs
        if create_annotated:
            with st.spinner("Creating annotated video..."):
                annotated_path = (
                    st.session_state.video_processor.create_annotated_video(
                        video_name, results
                    )
                )
                if annotated_path and os.path.exists(annotated_path):
                    st.success(f"✅ Annotated video created: `{annotated_path}`")
                else:
                    st.warning("Failed to create annotated video")

        if export_csv:
            with st.spinner("Exporting CSV results..."):
                csv_path = st.session_state.video_processor.export_results_to_csv(
                    results
                )
                if csv_path and os.path.exists(csv_path):
                    st.success(f"✅ CSV results exported: `{csv_path}`")

                    # Offer download
                    with open(csv_path, "rb") as file:
                        st.download_button(
                            label="📥 Download CSV Results",
                            data=file,
                            file_name=os.path.basename(csv_path),
                            mime="text/csv",
                        )
                else:
                    st.warning("Failed to export CSV results")

        # Store results in session state for later use
        st.session_state.last_results = results

    except Exception as e:
        st.error(f"Error processing video: {e}")
        logger.error(f"Video processing error: {e}")


def database_status_page():
    """Database status and management."""
    st.header("Database Status")

    # Get database statistics
    stats = st.session_state.db_manager.get_database_stats()

    st.subheader("ChromaDB Statistics")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Embeddings", stats["total_embeddings"])
    with col2:
        st.metric("Embedding Dimension", stats["embedding_dimension"])
    with col3:
        st.metric("Similarity Threshold", stats["similarity_threshold"])

    # Database management
    st.subheader("Database Management")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Refresh Database"):
            with st.spinner("Refreshing database..."):
                count = st.session_state.db_manager.populate_database(
                    force_refresh=True
                )
                st.success(f"Database refreshed with {count} embeddings")
                st.rerun()

    with col2:
        if st.button("🗑️ Reset Database"):
            if st.warning("This will delete all data. Are you sure?"):
                with st.spinner("Resetting database..."):
                    st.session_state.db_manager.reset_database()
                    st.success("Database reset successfully")
                    st.rerun()

    # Show available contestants
    if stats["total_embeddings"] > 0:
        st.subheader("Available Contestants")

        # Load contestant names from .npy files
        contestants_dir = Path("source/photo/contestants")
        npy_files = list(contestants_dir.glob("*.npy"))

        if npy_files:
            contestant_names = []
            for npy_file in npy_files:
                name = npy_file.stem.replace("_embedding", "")
                contestant_names.append(name)

            # Display in columns
            num_cols = 4
            cols = st.columns(num_cols)

            for i, name in enumerate(sorted(contestant_names)):
                with cols[i % num_cols]:
                    st.text(name)
        else:
            st.warning("No contestant embedding files found")


def configuration_page():
    """Configuration management."""
    st.header("Configuration")

    # Load current configuration
    with open("config.json", "r") as f:
        config = json.load(f)

    st.subheader("Face Detection Settings")

    col1, col2 = st.columns(2)
    with col1:
        detection_threshold = st.slider(
            "Detection Threshold",
            min_value=0.1,
            max_value=0.9,
            value=config["face_detection"]["detection_threshold"],
            step=0.05,
            help="Minimum confidence for face detection",
        )

    with col2:
        input_size = st.selectbox(
            "Input Size",
            options=["320x320", "640x640", "800x800"],
            index=1 if config["face_detection"]["input_size"] == [640, 640] else 0,
        )

    st.subheader("Face Matching Settings")

    col1, col2 = st.columns(2)
    with col1:
        similarity_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.1,
            max_value=0.9,
            value=config["face_matching"]["similarity_threshold"],
            step=0.05,
            help="Lower values = more matches, higher values = more accurate matches",
        )

        # Add threshold guidance
        if similarity_threshold <= 0.3:
            st.caption("🔍 **Very Low** - Many matches, lower accuracy")
        elif similarity_threshold <= 0.5:
            st.caption("⚖️ **Balanced** - Recommended setting")
        elif similarity_threshold <= 0.7:
            st.caption("🎯 **Strict** - Fewer but more accurate matches")
        else:
            st.caption("🔒 **Very Strict** - Only very similar faces")

    with col2:
        max_results = st.number_input(
            "Max Results",
            min_value=1,
            max_value=20,
            value=config["face_matching"]["max_results"],
            help="Maximum number of similar faces to return",
        )

    st.subheader("Video Processing Settings")

    col1, col2 = st.columns(2)
    with col1:
        frame_skip = st.slider(
            "Frame Skip",
            min_value=1,
            max_value=30,
            value=config["video_processing"]["frame_skip"],
            help="Process every N frames",
        )

    with col2:
        output_fps = st.number_input(
            "Output FPS",
            min_value=10,
            max_value=60,
            value=config["video_processing"]["output_fps"],
            help="FPS for output videos",
        )

    # Save configuration
    if st.button("💾 Save Configuration"):
        # Update configuration
        size_map = {"320x320": [320, 320], "640x640": [640, 640], "800x800": [800, 800]}

        config["face_detection"]["detection_threshold"] = detection_threshold
        config["face_detection"]["input_size"] = size_map[input_size]
        config["face_matching"]["similarity_threshold"] = similarity_threshold
        config["face_matching"]["max_results"] = max_results
        config["video_processing"]["frame_skip"] = frame_skip
        config["video_processing"]["output_fps"] = output_fps

        # Save to file
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)

        st.success("✅ Configuration saved successfully!")

        # Reinitialize components
        with st.spinner("Reinitializing system..."):
            st.session_state.video_processor = VideoProcessor()
            st.session_state.db_manager = ChromaDBManager()

        st.info("System reinitialized with new configuration")


def show_final_summary(results):
    """Show final processing summary with charts."""
    st.subheader("📊 Final Results Summary")

    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎬 Frames Processed", results["total_frames_processed"])
    with col2:
        st.metric("👥 Total Faces", results["total_faces_detected"])
    with col3:
        st.metric("✅ Recognized", results["total_faces_recognized"])
    with col4:
        recognition_rate = 0
        if results["total_faces_detected"] > 0:
            recognition_rate = (
                results["total_faces_recognized"] / results["total_faces_detected"]
            ) * 100
        st.metric("📈 Recognition Rate", f"{recognition_rate:.1f}%")

    # Add adaptive suggestions based on recognition rate
    if results["total_faces_detected"] > 0:
        if recognition_rate < 10:
            st.warning(
                "🔍 **Low recognition rate** - Consider lowering similarity threshold to 0.2-0.3 for more matches"
            )
        elif recognition_rate < 30:
            st.info(
                "⚖️ **Moderate recognition rate** - Try lowering similarity threshold to 0.3-0.4"
            )
        elif recognition_rate > 80:
            st.success(
                "🎯 **High recognition rate** - Great! Consider slightly raising threshold for better accuracy"
            )

    # Contestant appearances
    if results["contestant_appearances"]:
        st.subheader("🏆 Contestant Appearances")

        appearances_data = []
        for name, data in results["contestant_appearances"].items():
            appearances_data.append(
                {
                    "Contestant": name,
                    "Appearances": data["total_appearances"],
                    "Avg Confidence": f"{data.get('avg_confidence', 0):.3f}",
                    "Max Confidence": f"{data.get('max_confidence', 0):.3f}",
                    "First Frame": data["first_appearance"],
                    "Last Frame": data["last_appearance"],
                }
            )

        # Sort by appearances
        appearances_data = sorted(
            appearances_data, key=lambda x: x["Appearances"], reverse=True
        )

        # Show top 10 in a nice table
        df = pd.DataFrame(appearances_data[:10])
        st.dataframe(df, use_container_width=True)

        # Create visualization
        if len(appearances_data) > 0:
            st.subheader("📊 Top Contestants Chart")
            chart_data = pd.DataFrame(
                {
                    "Contestant": [item["Contestant"] for item in appearances_data[:8]],
                    "Appearances": [
                        item["Appearances"] for item in appearances_data[:8]
                    ],
                }
            )
            st.bar_chart(chart_data.set_index("Contestant"))

        # Show statistics
        st.subheader("📈 Recognition Statistics")
        total_contestants = len(appearances_data)
        avg_appearances = sum(item["Appearances"] for item in appearances_data) / max(
            total_contestants, 1
        )

        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.metric("🎭 Contestants Found", total_contestants)
        with stat_col2:
            st.metric("📊 Avg Appearances", f"{avg_appearances:.1f}")
        with stat_col3:
            most_appearances = max(appearances_data, key=lambda x: x["Appearances"])
            st.metric(
                "👑 Most Seen",
                f"{most_appearances['Contestant']} ({most_appearances['Appearances']})",
            )
    else:
        st.info("No contestants were recognized in this video segment.")

        # Provide helpful suggestions
        st.markdown("**💡 Suggestions to improve recognition:**")
        suggestions_col1, suggestions_col2 = st.columns(2)

        with suggestions_col1:
            st.markdown("""
            **Adjust Similarity Threshold:**
            - Current threshold might be too strict
            - Try lowering to 0.3 or 0.4
            - Lower values = more matches
            """)

        with suggestions_col2:
            st.markdown("""
            **Check Video Quality:**
            - Ensure faces are clearly visible
            - Good lighting conditions
            - Faces not too small or blurry
            """)


if __name__ == "__main__":
    main()
