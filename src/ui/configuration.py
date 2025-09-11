import streamlit as st
import json
from src.services.video_processor import VideoProcessor
from src.database.chroma_setup import ChromaDBManager


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
