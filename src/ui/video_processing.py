import streamlit as st
import time
import os
import json
import pandas as pd
import logging
from src.services.video_processor import VideoProcessor
from src.ui.shared_components import show_final_summary

logger = logging.getLogger(__name__)


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
        video_info = st.session_state.video_processor.get_video_info(selected_video)
        if "error" in video_info:
            st.error(f"Error loading video: {video_info['error']}")
            return

        tab1, tab2, tab3 = st.tabs(["1. Setup", "2. Configuration", "3. Run & Results"])

        with tab1:
            st.subheader("Video Setup")
            # Display video information
            with st.expander("Video Information", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "Duration", video_info.get("duration_formatted", "Unknown")
                    )
                    st.metric("FPS", f"{video_info.get('fps', 0):.1f}")
                with col2:
                    st.metric(
                        "Resolution",
                        f"{video_info.get('width', 0)}x{video_info.get('height', 0)}",
                    )
                    st.metric("Total Frames", f"{video_info.get('frame_count', 0):,}")
                with col3:
                    st.metric(
                        "File Size", f"{video_info.get('file_size_mb', 0):.1f} MB"
                    )

            # Processing options
            st.subheader("Processing Range")
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

        with tab2:
            st.subheader("Advanced Configuration")
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

        with tab3:
            st.subheader("Run Processing")
            # Processing controls
            col1, col2, col3 = st.columns(3)

            with col2:
                create_annotated = st.checkbox("Create annotated video", value=True)

            with col3:
                export_csv = st.checkbox("Export CSV results", value=True)

            # Processing mode selection
            processing_mode = st.radio(
                "Processing Mode",
                ["Real-time Preview", "Batch Processing"],
                help="Real-time shows live preview, Batch is faster for final results",
            )

            process_button = st.button("🎯 Process Video", type="primary")

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
        st.empty()

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
