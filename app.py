"""
Streamlit application for MV Face Recognition.
Clean rewrite focusing on processing videos in /source/videos/ directory.
"""

import streamlit as st
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our modules
try:
    from src.services.video_processor import VideoProcessor
    from src.database.chroma_setup import ChromaDBManager
    from src.ui.video_processing import video_processing_page
    from src.ui.database_status import database_status_page
    from src.ui.configuration import configuration_page
    from src.ui.shared_components import show_final_summary
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.stop()

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Page configuration
st.set_page_config(
    page_title="MV Face Recognition",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css("style.css")

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

def home_page():
    """The home page/dashboard for the application."""
    st.title("🏠 Welcome to the MV Face Recognition System")
    st.markdown("Navigate through the system using the sidebar.")

    st.header("System Status")
    if st.session_state.get("system_ready", False):
        st.success("✅ System is ready.")
    else:
        st.error("❌ System is not ready. Check logs for details.")

    # Display key stats
    col1, col2 = st.columns(2)
    with col1:
        videos = st.session_state.video_processor.get_available_videos()
        st.metric("📹 Available Videos", f"{len(videos)}")
    with col2:
        db_stats = st.session_state.db_manager.get_database_stats()
        st.metric("👥 Contestants in DB", db_stats.get("total_embeddings", 0))

    if "last_results" in st.session_state:
        st.header("Most Recent Run")
        show_final_summary(st.session_state.last_results)


def main():
    """Main application function."""
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Choose a page", ["Home", "Video Processing", "Database Status", "Configuration"]
    )

    if not st.session_state.get("system_ready", False):
        st.error("System not ready. Please check the error messages above.")
        return

    if page == "Home":
        home_page()
    elif page == "Video Processing":
        video_processing_page()
    elif page == "Database Status":
        database_status_page()
    elif page == "Configuration":
        configuration_page()


if __name__ == "__main__":
    main()
