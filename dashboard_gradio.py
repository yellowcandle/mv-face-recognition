"""
Modern Face Recognition Dashboard for MV Face Recognition System.
Implements the UI specification from DESIGN.md with real-time capabilities.
"""

import warnings
import gradio as gr
import pandas as pd
import logging
import json
import base64
import time
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from pathlib import Path
import os
import threading
import queue
import cv2
import numpy as np

# Import our modular components
from src.config.settings import get_config, save_config
from src.core.face_detector import FaceDetector
from src.services.embedding_service import EmbeddingService
from src.services.recognition_service import RecognitionService
from src.services.video_processing_service import VideoProcessingService
from src.services.visualization import VisualizationService

# Suppress warnings
warnings.filterwarnings("ignore", message=".*rcond.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="insightface")
warnings.filterwarnings("ignore", message=".*Albumentations.*")
warnings.filterwarnings("ignore", category=UserWarning, module="albumentations")

# Hugging Face Spaces GPU support
try:
    import spaces
    HF_SPACES_GPU = True
    print("✅ ZeroGPU support detected")
except ImportError:
    def spaces_gpu_decorator(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
    
    spaces = type('spaces', (), {'GPU': spaces_gpu_decorator})()
    HF_SPACES_GPU = False
    print("💻 Running without ZeroGPU support")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceRecognitionDashboard:
    """Modern Face Recognition Dashboard implementing DESIGN.md specifications."""

    def __init__(self):
        """Initialize the dashboard."""
        self.config = get_config()
        
        # Core services
        self.face_detector: Optional[FaceDetector] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self.recognition_service: Optional[RecognitionService] = None
        self.video_processing_service: Optional[VideoProcessingService] = None
        self.visualization_service: Optional[VisualizationService] = None
        
        # Real-time state
        self.is_processing = False
        self.current_video_path = None
        self.detection_results = []
        self.face_tiles_data = []
        self.similarity_scores = []
        
        # UI state
        self.selected_face_id = None
        self.video_metadata = {}
        
        # Initialize services
        self._initialize_system()

    def _initialize_system(self, force_cpu=False):
        """Initialize all services required for the dashboard."""
        logger.info(f"Initializing dashboard system (force_cpu={force_cpu})...")
        try:
            if not HF_SPACES_GPU or force_cpu:
                # Non-GPU environment - initialize immediately
                config = get_config()
                if force_cpu:
                    config.recognition.use_gpu = False
                self.face_detector = FaceDetector(config, force_cpu_only=force_cpu)
                
            # Initialize other services
            self.recognition_service = RecognitionService(use_chroma=self.config.recognition.enable_chromadb)
            self.visualization_service = VisualizationService()
            
            # Initialize embedding service if possible
            contestants_dir = self._get_contestants_directory()
            if contestants_dir:
                contestant_info_path = self.config.project_root / "contestant_info.csv"
                try:
                    self.embedding_service = EmbeddingService(self.face_detector, str(contestants_dir), str(contestant_info_path))
                    self._load_all_embeddings()
                except Exception as e:
                    logger.error(f"Failed to initialize embedding service: {e}")
                    
            if self.face_detector and not self.video_processing_service:
                self.video_processing_service = VideoProcessingService(self.face_detector, self.recognition_service)
                
        except Exception as e:
            logger.error(f"System initialization failed: {e}", exc_info=True)

    def _get_contestants_directory(self):
        """Get the contestants directory with fallback logic."""
        contestants_dir = self.config.project_root / "source/photo/contestants"
        if contestants_dir.exists():
            return contestants_dir
        
        # Try alternative paths
        alt_paths = [
            Path.cwd() / "source" / "photo" / "contestants",
            Path("/home/user/app") / "source" / "photo" / "contestants",
            Path("/app") / "source" / "photo" / "contestants",
        ]
        
        for alt_path in alt_paths:
            if alt_path.exists():
                return alt_path
                
        return None

    def _load_all_embeddings(self):
        """Load all known face embeddings."""
        if not self.embedding_service:
            return
        try:
            all_names = self.embedding_service.contestant_info["暱稱"].tolist()
            self.embedding_service.load_embeddings_for_contestants(all_names)
            logger.info(f"✅ Loaded {len(self.embedding_service.known_embeddings)} contestant embeddings")
        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")

    def get_available_videos(self):
        """Get list of available videos."""
        try:
            from src.config.video_titles import VIDEO_TITLE_MAPPING
        except ImportError:
            VIDEO_TITLE_MAPPING = {}
        
        videos_dir = self.config.project_root / "source/videos"
        
        # Check alternative paths if primary doesn't exist
        if not videos_dir.exists():
            alt_paths = [
                Path.cwd() / "source" / "videos",
                Path("/home/user/app") / "source" / "videos",
                Path("/app") / "source" / "videos",
            ]
            
            for alt_path in alt_paths:
                if alt_path.exists():
                    videos_dir = alt_path
                    break
        
        video_files = []
        title_to_path_mapping = {}
        
        if videos_dir.exists():
            for ext in ["*.mp4", "*.mov", "*.avi"]:
                for video_file in videos_dir.glob(ext):
                    display_title = VIDEO_TITLE_MAPPING.get(video_file.name, video_file.stem)
                    video_files.append(display_title)
                    title_to_path_mapping[display_title] = str(video_file)
        
        return sorted(video_files), title_to_path_mapping

    def create_header_component(self):
        """Create the header bar component according to DESIGN.md."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        header_html = f"""
        <div style="
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            background: #2a2a2a; 
            color: white; 
            padding: 15px 30px; 
            height: 60px; 
            border-radius: 8px;
            margin-bottom: 10px;
        ">
            <div style="font-size: 20px; font-weight: bold;">
                🎬 Face Recognition Dashboard
            </div>
            <div style="display: flex; align-items: center; gap: 20px;">
                <div id="live-indicator" style="
                    display: flex; 
                    align-items: center; 
                    gap: 8px;
                    background: #dc2626;
                    padding: 6px 12px;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: bold;
                    {'' if self.is_processing else 'opacity: 0.5;'}
                ">
                    <div style="
                        width: 8px; 
                        height: 8px; 
                        background: white; 
                        border-radius: 50%;
                        animation: pulse 1.5s infinite;
                    "></div>
                    LIVE
                </div>
                <div style="font-size: 16px; color: #e5e7eb;">
                    {current_time}
                </div>
            </div>
        </div>
        
        <style>
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        </style>
        """
        
        return gr.HTML(header_html)

    def create_video_player_panel(self):
        """Create the video player panel (60% width) with detection overlays."""
        # Video selection
        video_titles, self.title_to_path_mapping = self.get_available_videos()
        video_dropdown = gr.Dropdown(
            choices=video_titles,
            label="Select Video",
            interactive=True
        )
        
        # Video display with 16:9 aspect ratio (following DESIGN.md)
        video_display = gr.Video(
            label="",
            show_label=False,
            height=480,  # 16:9 aspect ratio for 854x480
            interactive=False
        )
        
        # Video controls
        with gr.Row():
            play_btn = gr.Button("▶️ Play", size="sm")
            pause_btn = gr.Button("⏸️ Pause", size="sm")
            stop_btn = gr.Button("⏹️ Stop", size="sm")
            process_btn = gr.Button("🔍 Process Video", variant="primary")
        
        # Video info overlay (frame rate and resolution as per DESIGN.md)
        video_info = gr.HTML("""
        <div style="
            display: flex; 
            justify-content: space-between; 
            background: rgba(0,0,0,0.7); 
            color: white; 
            padding: 8px 16px; 
            border-radius: 4px; 
            margin-top: 5px;
        ">
            <span id="fps-display">-- FPS</span>
            <span id="resolution-display">--x--</span>
        </div>
        """)
        
        return {
            'video_dropdown': video_dropdown,
            'video_display': video_display,
            'play_btn': play_btn,
            'pause_btn': pause_btn,
            'stop_btn': stop_btn,
            'process_btn': process_btn,
            'video_info': video_info
        }

    def create_face_recognition_panel(self):
        """Create the face recognition panel (40% width) with face tiles grid."""
        # Panel header matching DESIGN.md (Dark blue-gray #1e293b background)
        face_count_html = gr.HTML("""
        <div style="
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            background: #1e293b; 
            color: white; 
            padding: 15px; 
            border-radius: 8px 8px 0 0;
        ">
            <h3 style="margin: 0; color: white;">Detected Faces</h3>
            <div style="
                background: #3b82f6; 
                color: white; 
                padding: 4px 12px; 
                border-radius: 20px; 
                font-weight: bold;
            ">
                0
            </div>
        </div>
        """)
        
        # Face tiles grid following DESIGN.md specifications:
        # - 120x120px per tile 
        # - 3 columns layout with 10px gap
        # - Color-coded borders (green/yellow/red by confidence)
        face_tiles_html = gr.HTML("""
        <div id="face-tiles-container" style="
            background: #1e293b; 
            padding: 20px; 
            max-height: 600px; 
            overflow-y: auto;
            border-radius: 0 0 8px 8px;
        ">
            <div style="
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: center; 
                height: 200px; 
                color: #64748b; 
                text-align: center;
            ">
                <div style="font-size: 48px; margin-bottom: 16px;">👤</div>
                <p style="margin: 0; font-size: 16px;">No faces detected</p>
                <p style="margin: 4px 0 0 0; font-size: 14px;">Start processing to see faces</p>
            </div>
        </div>
        """)
        
        return {
            'face_count_html': face_count_html,
            'face_tiles_html': face_tiles_html
        }

    def create_similarity_scores_panel(self):
        """Create the similarity scores panel (bottom) with confidence chart."""
        # Horizontal bar chart as specified in DESIGN.md
        # Background: Dark gray (#374151), Height: 200px
        similarity_chart = gr.HTML("""
        <div style="
            background: #374151; 
            padding: 20px; 
            border-radius: 8px; 
            height: 200px;
            position: relative;
            margin-top: 10px;
        ">
            <h3 style="margin: 0 0 15px 0; color: white; font-size: 18px;">Recognition Confidence Scores</h3>
            
            <div style="
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: center; 
                height: 120px; 
                color: #9ca3af; 
                text-align: center;
            ">
                <div style="font-size: 32px; margin-bottom: 12px;">📊</div>
                <p style="margin: 0; font-size: 14px; font-weight: 500;">No recognition data</p>
                <p style="margin: 4px 0 0 0; font-size: 12px;">Confidence scores will appear here when faces are recognized</p>
            </div>
            
            <!-- Chart legend -->
            <div style="
                position: absolute; 
                bottom: 10px; 
                left: 10px; 
                background: rgba(0,0,0,0.8); 
                padding: 8px 12px; 
                border-radius: 6px; 
                font-size: 12px; 
                color: white;
                display: none;
            " id="chart-legend">
                <div style="display: flex; gap: 16px;">
                    <span><span style="color: #22c55e;">●</span> High (90%+)</span>
                    <span><span style="color: #eab308;">●</span> Med (70-90%)</span>
                    <span><span style="color: #ef4444;">●</span> Low (&lt;70%)</span>
                </div>
            </div>
            
            <!-- Real-time indicator -->
            <div style="
                position: absolute; 
                top: 10px; 
                right: 10px; 
                display: flex; 
                align-items: center; 
                gap: 6px; 
                font-size: 12px; 
                color: #9ca3af;
                display: none;
            " id="realtime-indicator">
                <div style="
                    width: 6px; 
                    height: 6px; 
                    background: #22c55e; 
                    border-radius: 50%; 
                    animation: pulse 1.5s infinite;
                "></div>
                Real-time updates
            </div>
        </div>
        """)
        
        return similarity_chart

    @spaces.GPU(duration=300)
    def process_video_real_time(self, video_title, progress=gr.Progress()):
        """Process video with real-time updates (GPU-accelerated)."""
        if not video_title:
            return None, "Please select a video", "", ""
        
        self.is_processing = True
        video_path = self.title_to_path_mapping.get(video_title, video_title)
        self.current_video_path = video_path
        
        # Initialize GPU context if needed
        if HF_SPACES_GPU and self.face_detector is None:
            logger.info("🚀 Initializing FaceDetector within GPU context...")
            try:
                config = get_config()
                config.recognition.use_gpu = True
                self.face_detector = FaceDetector(config, force_cpu_only=False)
                self._initialize_detector_dependent_services()
            except Exception as e:
                logger.error(f"GPU initialization failed: {e}")
                self.is_processing = False
                return None, f"GPU initialization failed: {e}", "", ""
        
        try:
            # Process video and get results
            known_embeddings = self.embedding_service.get_known_embeddings() if self.embedding_service else {}
            
            output_video_path, results = self.video_processing_service.process_video(
                video_path,
                known_embeddings,
                self.config.recognition.similarity_threshold,
                self.config.recognition.frame_skip,
                self.config.ui.enhanced_ui,
                lambda x, desc=None: progress(x, desc=desc) if progress else None
            )
            
            if output_video_path and results:
                # Update dashboard state
                self.detection_results = results
                self._update_face_tiles()
                self._update_similarity_scores()
                
                # Generate updated components
                face_tiles_html = self._generate_face_tiles_html()
                similarity_chart_html = self._generate_similarity_chart_html()
                
                summary = f"✅ Processing complete! Found {len(results)} recognition events with {len(set(r.get('Name', 'Unknown') for r in results if r.get('Name') != 'Unknown'))} unique contestants."
                
                self.is_processing = False
                return output_video_path, summary, face_tiles_html, similarity_chart_html
            else:
                self.is_processing = False
                return None, "Video processing failed", "", ""
                
        except Exception as e:
            logger.error(f"Video processing error: {e}", exc_info=True)
            self.is_processing = False
            return None, f"Processing error: {e}", "", ""

    def _initialize_detector_dependent_services(self):
        """Initialize services that require a FaceDetector."""
        contestants_dir = self._get_contestants_directory()
        if contestants_dir and self.face_detector:
            contestant_info_path = self.config.project_root / "contestant_info.csv"
            try:
                self.embedding_service = EmbeddingService(self.face_detector, str(contestants_dir), str(contestant_info_path))
                self._load_all_embeddings()
            except Exception as e:
                logger.error(f"Failed to initialize embedding service: {e}")
        
        if self.face_detector and not self.video_processing_service:
            self.video_processing_service = VideoProcessingService(self.face_detector, self.recognition_service)

    def _update_face_tiles(self):
        """Update face tiles data from detection results."""
        self.face_tiles_data = []
        for i, result in enumerate(self.detection_results[-50:]):  # Show last 50 detections
            confidence = result.get('Confidence', 0)
            name = result.get('Name', 'Unknown')
            timestamp = result.get('Time', '00:00')
            
            # Determine confidence color
            if confidence >= 0.9:
                border_color = "#22c55e"  # Green
            elif confidence >= 0.7:
                border_color = "#eab308"  # Yellow
            else:
                border_color = "#ef4444"  # Red
            
            self.face_tiles_data.append({
                'id': f"face_{i}",
                'name': name,
                'confidence': confidence,
                'timestamp': timestamp,
                'border_color': border_color
            })

    def _update_similarity_scores(self):
        """Update similarity scores from detection results."""
        # Get last 10 recognized faces
        recognized_faces = [r for r in self.detection_results if r.get('Name', 'Unknown') != 'Unknown']
        self.similarity_scores = recognized_faces[-10:]

    def _generate_face_tiles_html(self):
        """Generate HTML for face tiles grid following DESIGN.md specifications."""
        if not self.face_tiles_data:
            return """
            <div style="
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                background: #1e293b; 
                color: white; 
                padding: 15px; 
                border-radius: 8px 8px 0 0;
            ">
                <h3 style="margin: 0; color: white;">Detected Faces</h3>
                <div style="
                    background: #3b82f6; 
                    color: white; 
                    padding: 4px 12px; 
                    border-radius: 20px; 
                    font-weight: bold;
                ">
                    0
                </div>
            </div>
            <div style="
                background: #1e293b; 
                padding: 20px; 
                max-height: 600px; 
                overflow-y: auto;
                border-radius: 0 0 8px 8px;
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: center; 
                height: 200px; 
                color: #64748b; 
                text-align: center;
            ">
                <div style="font-size: 48px; margin-bottom: 16px;">👤</div>
                <p style="margin: 0; font-size: 16px;">No faces detected</p>
                <p style="margin: 4px 0 0 0; font-size: 14px;">Start processing to see faces</p>
            </div>
            """
        
        # Update face count
        face_count = len(self.face_tiles_data)
        
        # DESIGN.md specifications: 3 columns, 120x120px tiles, 10px gap
        tiles_html = f'''
        <div style="
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            background: #1e293b; 
            color: white; 
            padding: 15px; 
            border-radius: 8px 8px 0 0;
        ">
            <h3 style="margin: 0; color: white;">Detected Faces</h3>
            <div style="
                background: #3b82f6; 
                color: white; 
                padding: 4px 12px; 
                border-radius: 20px; 
                font-weight: bold;
            ">
                {face_count}
            </div>
        </div>
        <div style="
            background: #1e293b; 
            padding: 20px; 
            max-height: 600px; 
            overflow-y: auto;
            border-radius: 0 0 8px 8px;
        ">
            <div style="
                display: grid; 
                grid-template-columns: repeat(3, 120px); 
                gap: 10px; 
                justify-content: start;
            ">
        '''
        
        for tile in self.face_tiles_data:
            confidence_pct = int(tile['confidence'] * 100)
            is_selected = tile['id'] == self.selected_face_id
            
            # DESIGN.md Face Tile Specifications:
            # - Size: 120x120px per tile
            # - Border: 2px solid, color-coded by confidence
            # - Content: Cropped face image (100x100px), Name/ID, Confidence %, Timestamp
            tiles_html += f"""
            <div class="face-tile" style="
                width: 120px; 
                height: 120px; 
                border: 2px solid {tile['border_color']}; 
                border-radius: 8px; 
                background: #2d3748; 
                cursor: pointer; 
                transition: transform 0.2s;
                position: relative;
                overflow: hidden;
                {'transform: scale(1.05); box-shadow: 0 0 0 2px #3b82f6;' if is_selected else ''}
            " onclick="selectFace('{tile['id']}')">
                <!-- Face crop area (100x100px as per DESIGN.md) -->
                <div style="
                    width: 100px; 
                    height: 80px; 
                    background: #4a5568; 
                    margin: 8px auto 4px; 
                    border-radius: 4px; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    color: #a0aec0; 
                    font-size: 24px;
                    position: relative;
                    overflow: hidden;
                ">
                    <!-- TODO: Replace with actual face crop image -->
                    👤
                    {f'<div style="position: absolute; top: 2px; right: 2px; width: 8px; height: 8px; background: #3b82f6; border-radius: 50%; animation: pulse 1.5s infinite;"></div>' if is_selected else ''}
                </div>
                
                <!-- Name/ID label and metadata -->
                <div style="
                    text-align: center; 
                    color: white; 
                    font-size: 10px; 
                    padding: 0 4px;
                    position: absolute;
                    bottom: 4px;
                    left: 0;
                    right: 0;
                ">
                    <div style="
                        font-weight: bold; 
                        margin-bottom: 2px; 
                        white-space: nowrap; 
                        overflow: hidden; 
                        text-overflow: ellipsis;
                        font-size: 11px;
                    ">
                        {tile['name']}
                    </div>
                    <div style="color: #a0aec0; font-size: 9px;">
                        {confidence_pct}% • {tile['timestamp']}
                    </div>
                </div>
            </div>
            """
        
        tiles_html += '</div></div>'
        return tiles_html

    def _generate_similarity_chart_html(self):
        """Generate HTML for similarity scores chart."""
        if not self.similarity_scores:
            return """
            <div style="
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: center; 
                height: 160px; 
                color: #9ca3af; 
                text-align: center;
            ">
                <div style="font-size: 32px; margin-bottom: 12px;">📊</div>
                <p style="margin: 0; font-size: 14px; font-weight: 500;">No recognition data</p>
                <p style="margin: 4px 0 0 0; font-size: 12px;">Confidence scores will appear here when faces are recognized</p>
            </div>
            """
        
        chart_html = '<div style="padding: 10px;">'
        max_confidence = max(score.get('Confidence', 0) for score in self.similarity_scores)
        
        for score in self.similarity_scores:
            name = score.get('Name', 'Unknown')
            confidence = score.get('Confidence', 0)
            confidence_pct = int(confidence * 100)
            
            # Determine bar color
            if confidence >= 0.9:
                bar_color = "#22c55e"  # Green
            elif confidence >= 0.7:
                bar_color = "#eab308"  # Yellow
            else:
                bar_color = "#ef4444"  # Red
            
            bar_width = (confidence / max_confidence * 100) if max_confidence > 0 else 0
            
            chart_html += f"""
            <div style="margin-bottom: 8px;">
                <div style="
                    display: flex; 
                    justify-content: space-between; 
                    color: white; 
                    font-size: 12px; 
                    margin-bottom: 2px;
                ">
                    <span>{name}</span>
                    <span>{confidence_pct}%</span>
                </div>
                <div style="
                    width: 100%; 
                    height: 16px; 
                    background: #4b5563; 
                    border-radius: 8px; 
                    overflow: hidden;
                ">
                    <div style="
                        width: {bar_width}%; 
                        height: 100%; 
                        background: {bar_color}; 
                        transition: width 0.3s ease;
                    "></div>
                </div>
            </div>
            """
        
        chart_html += '</div>'
        
        # Add indicators
        chart_html += '''
        <div style="
            position: absolute; 
            bottom: 10px; 
            left: 10px; 
            background: rgba(0,0,0,0.8); 
            padding: 8px 12px; 
            border-radius: 6px; 
            font-size: 12px; 
            color: white;
        ">
            <div style="display: flex; gap: 16px;">
                <span><span style="color: #22c55e;">●</span> High (90%+)</span>
                <span><span style="color: #eab308;">●</span> Med (70-90%)</span>
                <span><span style="color: #ef4444;">●</span> Low (&lt;70%)</span>
            </div>
        </div>
        
        <div style="
            position: absolute; 
            top: 10px; 
            right: 10px; 
            display: flex; 
            align-items: center; 
            gap: 6px; 
            font-size: 12px; 
            color: #9ca3af;
        ">
            <div style="
                width: 6px; 
                height: 6px; 
                background: #22c55e; 
                border-radius: 50%; 
                animation: pulse 1.5s infinite;
            "></div>
            Real-time updates
        </div>
        '''
        
        return chart_html

def create_dashboard_interface():
    """Create the main dashboard interface according to DESIGN.md specifications."""
    dashboard = FaceRecognitionDashboard()
    
    # Custom CSS following DESIGN.md specifications
    css = """
    .gradio-container {
        max-width: none !important;
        background: #000000 !important;
    }
    
    /* DESIGN.md Layout Specifications */
    .main-container {
        height: 100vh;
        display: flex;
        flex-direction: column;
    }
    
    .header-bar {
        height: 60px;
        background: #2a2a2a;
        color: white;
    }
    
    .content-area {
        flex: 1;
        display: flex;
    }
    
    .video-panel {
        width: 60%;
        background: #000000;
        padding: 10px;
    }
    
    .face-panel {
        width: 40%;
        background: #1e293b;
        padding: 10px;
    }
    
    .similarity-panel {
        height: 200px;
        background: #374151;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* Face tile grid specifications from DESIGN.md */
    .face-grid {
        display: grid;
        grid-template-columns: repeat(3, 120px);
        gap: 10px;
        max-height: 500px;
        overflow-y: auto;
        padding: 10px;
    }
    
    .face-tile {
        width: 120px;
        height: 120px;
        border: 2px solid;
        border-radius: 8px;
        cursor: pointer;
        transition: transform 0.2s;
    }
    
    .face-tile:hover {
        transform: scale(1.05);
    }
    
    /* Confidence color coding from DESIGN.md */
    .confidence-high { border-color: #22c55e; }    /* Green: >90% */
    .confidence-medium { border-color: #eab308; }  /* Yellow: 70-90% */
    .confidence-low { border-color: #ef4444; }     /* Red: <70% */
    """
    
    with gr.Blocks(
        title="🎬 Face Recognition Dashboard",
        css=css,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="gray")
    ) as demo:
        # Header Bar (60px height) - DESIGN.md specification
        header = dashboard.create_header_component()
        
        # Main Content Area - Two-column layout as per DESIGN.md
        with gr.Row(elem_classes=["content-area"]):
            # Video Player Panel (60% width) - DESIGN.md specification
            with gr.Column(scale=3, elem_classes=["video-panel"]):
                video_components = dashboard.create_video_player_panel()
            
            # Face Recognition Panel (40% width) - DESIGN.md specification  
            with gr.Column(scale=2, elem_classes=["face-panel"]):
                face_components = dashboard.create_face_recognition_panel()
        
        # Similarity Scores Panel (200px height) - DESIGN.md specification
        similarity_chart = dashboard.create_similarity_scores_panel()
        
        # Add JavaScript for face interaction as specified in DESIGN.md
        js_code = """
        <script>
        function selectFace(faceId) {
            console.log('Face selected:', faceId);
            // Update selected face UI state
            const tiles = document.querySelectorAll('[onclick*="selectFace"]');
            tiles.forEach(tile => {
                tile.style.transform = '';
                tile.style.boxShadow = '';
            });
            
            // Highlight selected tile
            event.target.closest('[onclick*="selectFace"]').style.transform = 'scale(1.05)';
            event.target.closest('[onclick*="selectFace"]').style.boxShadow = '0 0 0 2px #3b82f6';
            
            // Highlight corresponding detection in video (DESIGN.md requirement)
            highlightVideoDetection(faceId);
        }
        
        function highlightVideoDetection(faceId) {
            // Highlight the corresponding detection in video panel
            console.log('Highlighting video detection for:', faceId);
            // Implementation would depend on video overlay system
        }
        
        // Update timestamps every second for real-time display
        setInterval(() => {
            const timestampElements = document.querySelectorAll('[id*="timestamp"]');
            const now = new Date().toLocaleString();
            timestampElements.forEach(el => {
                if (el.textContent.includes(':')) {
                    el.textContent = now;
                }
            });
        }, 1000);
        </script>
        """
        
        gr.HTML(js_code)
        
        # Event handlers
        video_components['process_btn'].click(
            dashboard.process_video_real_time,
            inputs=[video_components['video_dropdown']],
            outputs=[
                video_components['video_display'],
                gr.Textbox(label="Status", visible=False),  # Hidden status textbox
                face_components['face_tiles_html'],
                similarity_chart
            ]
        )
        
        # Refresh video list functionality
        refresh_btn = gr.Button("🔄 Refresh Videos", size="sm")
        refresh_btn.click(
            lambda: gr.Dropdown(choices=dashboard.get_available_videos()[0]),
            outputs=[video_components['video_dropdown']]
        )
    
    return demo

def launch_dashboard():
    """Launch the face recognition dashboard."""
    try:
        demo = create_dashboard_interface()
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=True
        )
    except Exception as e:
        logger.error(f"Failed to launch dashboard: {e}", exc_info=True)

if __name__ == "__main__":
    launch_dashboard()