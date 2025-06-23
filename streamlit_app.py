#!/usr/bin/env python3
"""
MV Face Recognition - Streamlit Edition
A simple, fast UI for face recognition in music videos.
"""

import os
import warnings
import logging

# Set environment variables before importing other modules
os.environ['STREAMLIT_LOGGER_LEVEL'] = 'ERROR'

# Comprehensive warning suppression
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*torch.*")
warnings.filterwarnings("ignore", message=".*classes.*")

# Suppress logging from specific modules
logging.getLogger('streamlit.watcher.local_sources_watcher').setLevel(logging.ERROR)
logging.getLogger('torch').setLevel(logging.ERROR)

import streamlit as st
import cv2
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import tempfile
import time
from typing import List, Dict, Any
from collections import defaultdict, Counter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import backend services
try:
    from src.services.video_processor import VideoProcessor
    from src.database.chroma_setup import ChromaDBManager
except ImportError as e:
    st.error(f"Error importing backend modules: {e}")
    st.stop()

# Configure Streamlit page
st.set_page_config(
    page_title="MV Face Recognition",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def initialize_services():
    """Initialize backend services with caching."""
    try:
        video_processor = VideoProcessor()
        db_manager = ChromaDBManager()
        return video_processor, db_manager, None
    except Exception as e:
        return None, None, str(e)

@st.cache_data
def get_available_videos() -> List[str]:
    """Get list of available video files (cached for performance)."""
    videos_dir = Path("source/videos")
    if not videos_dir.exists():
        return []
    
    # Get all MP4 files
    all_files = [f.name for f in videos_dir.iterdir() if f.is_file() and f.name.endswith('.mp4')]
    
    # Prefer simple symlinks over original files to avoid duplication
    simple_videos = [f for f in all_files if f.startswith('video')]
    original_videos = [f for f in all_files if not f.startswith('video')]
    
    if simple_videos:
        # Use symlinks only to avoid showing duplicates
        return sorted(simple_videos)
    else:
        # Fallback to original files if no symlinks exist
        return sorted(original_videos)

def main():
    """Main Streamlit application."""
    
    # Header
    st.title("🎬 MV Face Recognition")
    st.markdown("---")
    
    # Initialize services
    with st.spinner("Initializing face recognition system..."):
        video_processor, db_manager, error = initialize_services()
    
    if error:
        st.error(f"Failed to initialize system: {error}")
        st.stop()
    
    # Sidebar - System Status
    with st.sidebar:
        st.header("📊 System Status")
        
        # Video processor status
        if video_processor:
            videos = video_processor.get_available_videos()
            st.success(f"✅ VideoProcessor: {len(videos)} videos")
        else:
            st.error("❌ VideoProcessor: Not initialized")
        
        # Database status
        if db_manager:
            stats = db_manager.get_database_stats()
            embeddings_count = stats.get('total_embeddings', 0)
            st.success(f"✅ Database: {embeddings_count} embeddings")
            
            with st.expander("Database Details"):
                st.write(f"Similarity threshold: {stats.get('similarity_threshold', 'N/A')}")
                st.write(f"Collection: {stats.get('collection_name', 'N/A')}")
                st.write(f"Embedding dimension: {stats.get('embedding_dimension', 'N/A')}")
        else:
            st.error("❌ Database: Not initialized")
        
        st.markdown("---")
        
        # Configuration
        st.header("⚙️ Settings")
        similarity_threshold = st.slider(
            "Similarity Threshold", 
            min_value=0.1, 
            max_value=0.9, 
            value=0.4, 
            step=0.05,
            help="Higher values = more strict matching. Config file has 0.9 (very strict)!"
        )
        
        # Show current config vs selected
        config_threshold = 0.9  # From config.json
        if similarity_threshold != config_threshold:
            st.warning(f"⚠️ Config file uses {config_threshold}, but slider is {similarity_threshold}")
            st.info("💡 Try 0.4-0.6 for better results!")
        
        max_results = st.number_input(
            "Max Results", 
            min_value=1, 
            max_value=20, 
            value=5,
            help="Maximum number of face matches to show"
        )
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["🎥 Video Processing", "👥 Database Manager", "📊 Analytics"])
    
    with tab1:
        create_video_processing_tab(video_processor, db_manager, similarity_threshold, max_results)
    
    with tab2:
        create_database_tab(db_manager)
    
    with tab3:
        create_analytics_tab(video_processor, db_manager)

def create_video_processing_tab(video_processor, db_manager, similarity_threshold, max_results):
    """Create the video processing tab."""
    
    if not video_processor or not db_manager:
        st.error("Backend services not available. Please check system status.")
        return
    
    st.header("🎥 Video Processing")
    
    # Video selection
    videos = get_available_videos()
    
    if not videos:
        st.warning("No videos found in /source/videos/ directory")
        st.info("Add MP4 files to the source/videos directory to process them.")
        return
    
    # Two columns: video selection and processing controls
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📹 Video Selection")
        selected_video = st.selectbox(
            "Choose a video to process:",
            videos,
            help="Select from available video files"
        )
        
        if selected_video:
            # Show video file info
            video_path = Path("source/videos") / selected_video
            if video_path.exists():
                file_size = video_path.stat().st_size / (1024 * 1024)  # MB
                st.info(f"📁 File: {selected_video} ({file_size:.1f} MB)")
                
                # Display video
                try:
                    # For simple symlinks, use them directly; for original files, we might need encoding
                    if selected_video.startswith('video'):
                        video_url = f"source/videos/{selected_video}"
                    else:
                        # For original files with special characters, try direct path first
                        video_url = f"source/videos/{selected_video}"
                    
                    # Test if file exists before trying to display
                    if (Path("source/videos") / selected_video).exists():
                        st.video(video_url)
                        st.success("✅ Video loaded successfully")
                    else:
                        st.error(f"❌ Video file not found: {selected_video}")
                        
                except Exception as e:
                    st.error(f"❌ Could not display video: {e}")
                    
                    # Provide debugging info
                    with st.expander("🔧 Debugging Info"):
                        st.write(f"Selected: {selected_video}")
                        st.write(f"Video URL: {video_url}")
                        st.write(f"File exists: {video_path.exists()}")
                        st.write(f"File size: {video_path.stat().st_size if video_path.exists() else 'N/A'}")
                        
                        # Try alternative method
                        if st.button("🔄 Try Alternative Display Method"):
                            try:
                                with open(video_path, 'rb') as video_file:
                                    video_bytes = video_file.read()
                                    st.video(video_bytes)
                                    st.success("✅ Alternative method worked!")
                            except Exception as e2:
                                st.error(f"❌ Alternative method failed: {e2}")
    
    with col2:
        st.subheader("🎛️ Processing Controls")
        
        # Time range
        start_time = st.number_input("Start time (seconds)", min_value=0, value=0)
        end_time = st.number_input("End time (seconds)", min_value=1, value=60)
        
        if start_time >= end_time:
            st.warning("End time must be greater than start time")
        
        # Processing button
        process_button_disabled = not selected_video or start_time >= end_time
        
        if st.button(
            "🚀 Start Face Recognition", 
            type="primary", 
            disabled=process_button_disabled,
            help="Select a video and set valid time range to enable processing"
        ):
            if selected_video and start_time < end_time:
                with st.spinner("🔄 Initializing face recognition..."):
                    process_video_realtime(
                        video_processor, db_manager, selected_video, 
                        start_time, end_time, similarity_threshold, max_results
                    )
            else:
                st.error("❌ Please select a video and ensure end time > start time")

def process_video_realtime(video_processor, db_manager, video_name, start_time, end_time, similarity_threshold, max_results):
    """Process video and show results in real-time."""
    
    # Resolve symlink to actual filename if needed
    actual_video_name = video_name
    if video_name.startswith('video') and video_name.endswith('.mp4'):
        video_path = Path("source/videos") / video_name
        if video_path.is_symlink():
            actual_video_name = video_path.readlink().name
    
    st.subheader(f"🔍 Processing: {actual_video_name}")
    
    # CRITICAL: Override the hardcoded similarity threshold
    # The face_matcher uses config.json (0.9) but we want to use the slider value
    original_threshold = db_manager.similarity_threshold
    db_manager.similarity_threshold = similarity_threshold
    
    # Also update the video processor's face matcher threshold
    original_video_threshold = None
    if hasattr(video_processor, 'face_matcher') and hasattr(video_processor.face_matcher, 'db_manager'):
        original_video_threshold = video_processor.face_matcher.db_manager.similarity_threshold
        video_processor.face_matcher.db_manager.similarity_threshold = similarity_threshold
        st.success(f"✅ Updated both DB and video processor thresholds to {similarity_threshold}")
    
    st.info(f"🎯 Similarity threshold: {similarity_threshold} (was {original_threshold} in config)")
    
    # Create containers for results
    progress_container = st.empty()
    results_container = st.container()
    
    try:
        # Progress bar and status
        progress_bar = progress_container.progress(0)
        status_text = progress_container.empty()
        
        # Processing info
        st.info(f"🎯 Processing {end_time - start_time} seconds of video (frames will be sampled)")
        
        # Results tracking
        detected_faces = []
        frame_count = 0
        max_frames = 100  # Limit for demo
        
        # Performance metrics
        start_processing_time = st.empty()
        processing_stats = st.empty()
        
        with results_container:
            # Enhanced layout with multiple visualization areas
            metrics_row = st.container()
            viz_row = st.container()
            details_row = st.container()
            
            with metrics_row:
                # Real-time metrics at the top
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    total_faces_metric = st.empty()
                with metric_col2:
                    matched_faces_metric = st.empty()
                with metric_col3:
                    unique_people_metric = st.empty()
                with metric_col4:
                    confidence_metric = st.empty()
            
            with viz_row:
                chart_col1, chart_col2 = st.columns([3, 2])
                
                with chart_col1:
                    st.write("### 📊 Recognition Timeline")
                    timeline_chart = st.empty()
                
                with chart_col2:
                    st.write("### 🏆 Top Detections")
                    leaderboard_chart = st.empty()
            
            with details_row:
                details_col1, details_col2 = st.columns([2, 1])
                
                with details_col1:
                    st.write("### 👥 Recent Detections")
                    faces_grid = st.empty()
                
                with details_col2:
                    st.write("### 🔍 Processing Stats")
                    debug_info = st.empty()
        
        # Track processing time and statistics
        processing_start = time.time()
        all_frame_detections = []  # For timeline chart
        face_counts = defaultdict(int)  # For leaderboard
        
        # Process video frames
        for frame_num, annotated_frame, face_results, frame_stats in video_processor.process_video_realtime(
            actual_video_name, start_time, end_time
        ):
            frame_count += 1
            progress = min(frame_count / max_frames, 1.0)
            progress_bar.progress(progress)
            
            timestamp = frame_stats.get('frame_timestamp', 0)
            elapsed_time = time.time() - processing_start
            fps_rate = frame_count / elapsed_time if elapsed_time > 0 else 0
            
            status_text.text(f"🎬 Frame {frame_num} at {timestamp:.1f}s | Processing: {fps_rate:.1f} FPS")
            
            # Debug: Show all face detection results
            total_faces_in_frame = len(face_results)
            matched_faces_in_frame = sum(1 for f in face_results if f.get('matched', False))
            
            # Process detected faces
            frame_detections = []
            for face_result in face_results:
                if face_result.get('matched', False):
                    face_data = {
                        'name': face_result['contestant_name'],
                        'confidence': face_result['recognition_confidence'],
                        'timestamp': f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}",
                        'frame_number': frame_num,
                        'video_timestamp': timestamp
                    }
                    detected_faces.append(face_data)
                    frame_detections.append(face_data)
                    face_counts[face_data['name']] += 1
            
            # Store frame data for timeline
            all_frame_detections.append({
                'frame': frame_num,
                'timestamp': timestamp,
                'total_faces': total_faces_in_frame,
                'matched_faces': matched_faces_in_frame,
                'detections': frame_detections
            })
            
            # Update visualizations every few frames for performance
            if frame_count % 3 == 0 or matched_faces_in_frame > 0:
                update_visualizations(
                    detected_faces, all_frame_detections, face_counts,
                    total_faces_metric, matched_faces_metric, unique_people_metric, confidence_metric,
                    timeline_chart, leaderboard_chart, faces_grid, debug_info,
                    elapsed_time, fps_rate, total_faces_in_frame, matched_faces_in_frame
                )
            
            # Break if we've processed enough frames
            if frame_count >= max_frames:
                status_text.text(f"✅ Processed {max_frames} frames in {elapsed_time:.1f}s")
                break
        
        # Final results summary
        progress_container.empty()
        
        if detected_faces:
            st.success(f"✅ Processing complete! Found {len(detected_faces)} face matches.")
            
            # Summary table
            import pandas as pd
            df = pd.DataFrame(detected_faces)
            
            st.subheader("📋 Detection Summary")
            
            # Group by contestant
            summary = df.groupby('name').agg({
                'confidence': ['count', 'mean', 'max'],
                'timestamp': 'first'
            }).round(3)
            
            summary.columns = ['Detections', 'Avg Confidence', 'Max Confidence', 'First Seen']
            st.dataframe(summary, use_container_width=True)
            
            # Full results
            with st.expander("📊 All Detections"):
                st.dataframe(df, use_container_width=True)
        else:
            st.warning("No faces detected in the processed frames.")
    
    except Exception as e:
        st.error(f"Error processing video: {e}")
        logger.error(f"Video processing error: {e}")
    finally:
        # Restore original thresholds
        db_manager.similarity_threshold = original_threshold
        if original_video_threshold is not None and hasattr(video_processor, 'face_matcher') and hasattr(video_processor.face_matcher, 'db_manager'):
            video_processor.face_matcher.db_manager.similarity_threshold = original_video_threshold

def update_visualizations(detected_faces, all_frame_detections, face_counts,
                         total_faces_metric, matched_faces_metric, unique_people_metric, confidence_metric,
                         timeline_chart, leaderboard_chart, faces_grid, debug_info,
                         elapsed_time, fps_rate, total_faces_detected, matched_faces_detected):
    """Update all visualizations with current data."""
    
    # Update metrics
    total_faces_metric.metric(
        "👤 Total Faces", 
        len(detected_faces),
        delta=f"+{matched_faces_detected}" if matched_faces_detected > 0 else None
    )
    
    matched_faces_metric.metric(
        "✅ Matched", 
        len(detected_faces),
        delta=f"{len(detected_faces)/max(1, len(all_frame_detections)):.1f}/frame" if all_frame_detections else None
    )
    
    unique_people_metric.metric(
        "🏷️ Unique People", 
        len(face_counts),
        delta=f"{len(face_counts)/max(1, len(detected_faces))*100:.0f}% unique" if detected_faces else None
    )
    
    avg_confidence = np.mean([f['confidence'] for f in detected_faces]) if detected_faces else 0
    confidence_metric.metric(
        "📊 Avg Confidence", 
        f"{avg_confidence:.1%}",
        delta=f"Max: {max([f['confidence'] for f in detected_faces]):.1%}" if detected_faces else None
    )
    
    # Update timeline chart
    if all_frame_detections:
        timeline_df = pd.DataFrame([
            {
                'timestamp': frame['timestamp'],
                'total_faces': frame['total_faces'],
                'matched_faces': frame['matched_faces']
            }
            for frame in all_frame_detections
        ])
        
        if not timeline_df.empty:
            fig_timeline = go.Figure()
            
            fig_timeline.add_trace(go.Scatter(
                x=timeline_df['timestamp'],
                y=timeline_df['total_faces'],
                mode='lines+markers',
                name='Total Faces',
                line=dict(color='lightblue', width=2),
                marker=dict(size=4)
            ))
            
            fig_timeline.add_trace(go.Scatter(
                x=timeline_df['timestamp'],
                y=timeline_df['matched_faces'],
                mode='lines+markers',
                name='Matched Faces',
                line=dict(color='green', width=3),
                marker=dict(size=6),
                fill='tonexty'
            ))
            
            fig_timeline.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=20),
                xaxis_title="Time (seconds)",
                yaxis_title="Face Count",
                legend=dict(x=0, y=1),
                showlegend=True
            )
            
            timeline_chart.plotly_chart(fig_timeline, use_container_width=True)
    
    # Update leaderboard chart
    if face_counts:
        leaderboard_df = pd.DataFrame([
            {'name': name, 'count': count}
            for name, count in sorted(face_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ])
        
        fig_leaderboard = px.bar(
            leaderboard_df, 
            x='count', 
            y='name',
            orientation='h',
            title="Top Detected People",
            color='count',
            color_continuous_scale='viridis'
        )
        
        fig_leaderboard.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=30, b=20),
            showlegend=False,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        leaderboard_chart.plotly_chart(fig_leaderboard, use_container_width=True)
    
    # Update faces grid with enhanced layout
    if detected_faces:
        recent_faces = detected_faces[-12:]  # Show last 12 detections
        
        with faces_grid.container():
            # Create a grid layout
            cols_per_row = 4
            for i in range(0, len(recent_faces), cols_per_row):
                row_faces = recent_faces[i:i+cols_per_row]
                cols = st.columns(cols_per_row)
                
                for j, face in enumerate(row_faces):
                    if j < len(cols):
                        with cols[j]:
                            # Color coding
                            if face['confidence'] > 0.8:
                                color = "🟢"
                                border_color = "#28a745"
                            elif face['confidence'] > 0.6:
                                color = "🟡" 
                                border_color = "#ffc107"
                            else:
                                color = "🔴"
                                border_color = "#dc3545"
                            
                            # Create styled card
                            st.markdown(f"""
                            <div style="
                                border: 2px solid {border_color};
                                border-radius: 10px;
                                padding: 10px;
                                margin: 5px 0;
                                text-align: center;
                                background: linear-gradient(145deg, #f8f9fa, #e9ecef);
                            ">
                                <h4 style="margin: 0; color: #212529;">{color} {face['name']}</h4>
                                <p style="margin: 5px 0; font-size: 18px; font-weight: bold; color: {border_color};">
                                    {face['confidence']:.1%}
                                </p>
                                <p style="margin: 0; font-size: 12px; color: #6c757d;">
                                    {face['timestamp']}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
    else:
        faces_grid.info("🔍 Scanning for faces...")
    
    # Update debug info
    debug_info.markdown(f"""
    **Processing Statistics:**
    - ⏱️ Elapsed: {elapsed_time:.1f}s
    - 🚀 Processing FPS: {fps_rate:.1f}
    - 👤 Current Frame Faces: {total_faces_detected}
    - ✅ Current Frame Matches: {matched_faces_detected}
    - 📊 Total Detections: {len(detected_faces)}
    - 🎯 Unique People: {len(face_counts)}
    - 📈 Match Rate: {len(detected_faces)/max(1, len(all_frame_detections)*10)*100:.1f}%
    """)

def create_database_tab(db_manager):
    """Create the database manager tab."""
    
    st.header("👥 Database Manager")
    
    if not db_manager:
        st.error("Database manager not available.")
        return
    
    # Database stats
    stats = db_manager.get_database_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Embeddings", stats.get('total_embeddings', 0))
    with col2:
        st.metric("Similarity Threshold", stats.get('similarity_threshold', 'N/A'))
    with col3:
        st.metric("Collection", stats.get('collection_name', 'N/A'))
    
    st.markdown("---")
    
    # Contestant gallery
    st.subheader("🖼️ Contestant Gallery")
    
    contestants_dir = Path("source/photo/contestants")
    if not contestants_dir.exists():
        st.warning("Contestants directory not found")
        return
    
    # Get contestant folders
    contestant_folders = [f for f in contestants_dir.iterdir() if f.is_dir()]
    
    if not contestant_folders:
        st.info("No contestant folders found")
        return
    
    # Display in grid
    cols_per_row = 6
    for i in range(0, len(contestant_folders), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, contestant_folder in enumerate(contestant_folders[i:i+cols_per_row]):
            if j < len(cols):
                with cols[j]:
                    # Find first image
                    image_files = list(contestant_folder.glob('*.jpg')) + list(contestant_folder.glob('*.png'))
                    
                    if image_files:
                        try:
                            st.image(str(image_files[0]), caption=contestant_folder.name, width=100)
                        except:
                            st.write(f"📷 {contestant_folder.name}")
                    else:
                        st.write(f"📷 {contestant_folder.name}\n(No image)")

def create_analytics_tab(video_processor, db_manager):
    """Create the analytics tab."""
    
    st.header("📊 Analytics")
    
    if not video_processor or not db_manager:
        st.error("Backend services not available.")
        return
    
    # System overview
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎥 Video Library")
        videos = video_processor.get_available_videos()
        st.metric("Total Videos", len(videos))
        
        if videos:
            st.write("**Available Videos:**")
            for i, video in enumerate(videos, 1):
                st.write(f"{i}. {video}")
    
    with col2:
        st.subheader("👥 Face Database")
        stats = db_manager.get_database_stats()
        embeddings_count = stats.get('total_embeddings', 0)
        st.metric("Face Embeddings", embeddings_count)
        
        if embeddings_count > 0:
            st.success("✅ Database ready for recognition")
        else:
            st.warning("⚠️ No face embeddings available")
    
    st.markdown("---")
    
    # Configuration info
    st.subheader("⚙️ Configuration")
    
    try:
        import json
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        config_col1, config_col2 = st.columns(2)
        
        with config_col1:
            st.write("**Face Detection:**")
            st.write(f"- Model: {config['face_detection']['model_name']}")
            st.write(f"- Threshold: {config['face_detection']['detection_threshold']}")
            st.write(f"- Input size: {config['face_detection']['input_size']}")
        
        with config_col2:
            st.write("**Face Matching:**")
            st.write(f"- Similarity threshold: {config['face_matching']['similarity_threshold']}")
            st.write(f"- Max results: {config['face_matching']['max_results']}")
            
            st.write("**Video Processing:**")
            st.write(f"- Frame skip: {config['video_processing']['frame_skip']}")
            st.write(f"- Output FPS: {config['video_processing']['output_fps']}")
    
    except Exception as e:
        st.error(f"Could not load configuration: {e}")

if __name__ == "__main__":
    main()