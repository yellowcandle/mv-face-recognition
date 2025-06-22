#!/usr/bin/env python
"""
Face Recognition Gradio Web Interface

This module provides a Gradio-based web interface for real-time face recognition
using the cosine similarity backend and visualization options.
"""

import logging
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import tempfile

import cv2
import numpy as np
import pandas as pd
import gradio as gr

# Set matplotlib backend before importing pyplot to avoid NSWindow threading issues on macOS
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

import umap.umap_ as umap
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.colors import hsv_to_rgb
from PIL import Image, ImageDraw, ImageFont # Re-add PIL imports for placeholder

# Import custom services
from src.config.config import Config, get_config
from src.services.face_recognition import FaceRecognitionService
from src.services.visualization import VisualizationService
from src.services.video_service import get_video_manager

logger = logging.getLogger(__name__)

# Global service instances
# These will be initialized in the main function
face_recognition_service: Optional[FaceRecognitionService] = None
visualization_service: Optional[VisualizationService] = None
app_config: Optional[Config] = None
video_manager = None

def get_video_files() -> Dict[str, str]:
    """
    Retrieves a dictionary of available videos using the video manager.
    Downloads videos from YouTube if needed.

    Returns:
        Dict[str, str]: A dictionary where keys are video names and values are their
                        local paths. Downloads missing videos automatically.
    """
    global video_manager
    
    if video_manager is None:
        logger.error("Video manager not initialized")
        return {"Video manager not initialized - please restart": ""}
    
    video_files = {}
    video_names = video_manager.get_video_list()
    
    if not video_names:
        logger.warning("No videos available in catalog")
        return {"No videos available in catalog": ""}
    
    # Get available videos (will download if missing and YouTube enabled)
    for video_name in video_names:
        video_path = video_manager.get_video_path(video_name, download_if_missing=True)
        if video_path:
            video_files[video_name] = video_path
        else:
            # Add as unavailable but still show in dropdown
            video_files[f"{video_name} (downloading...)"] = ""
    
    if not video_files:
        video_files["Videos are downloading - please wait and refresh"] = ""
    
    return video_files

def get_video_frame(video_path: str, frame_num: int) -> np.ndarray:
    """Extract a specific frame from a video file."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Could not read frame {frame_num} from {video_path}")
    return frame

def process_frame_for_gradio(video_name: str, frame_num: int, det_thresh: float, rec_thresh: float, embeddings: List[np.ndarray], labels: List[str], show_current_only: bool, auto_advance_enabled: bool) -> Tuple[np.ndarray, Figure, List[np.ndarray], List[str]]:
    """
    Processes a frame for Gradio display, using the FaceRecognitionService and VisualizationService.
    """
    global face_recognition_service, visualization_service, app_config
    
    # Initial checks for service and config initialization
    assert app_config is not None, "App configuration not initialized."
    assert app_config.paths is not None, "App configuration paths not initialized." # Added assert
    assert face_recognition_service is not None, "Face recognition service not initialized."
    assert visualization_service is not None, "Visualization service not initialized."

    # Handle cases where video is not selected or services are not initialized
    if face_recognition_service is None or visualization_service is None: # This check is redundant due to asserts above, but kept for clarity
        logger.error("Services not initialized.")
        empty_fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Services not initialized. Please restart the app.", ha='center', va='center')
        placeholder_img = np.zeros((480, 640, 3), dtype=np.uint8) # Black image
        draw = ImageDraw.Draw(Image.fromarray(placeholder_img))
        try:
            font = ImageFont.truetype(os.path.join(app_config.paths.font_path.parent, app_config.paths.font_path.name), 20)
        except (IOError, AttributeError): # Catch AttributeError if app_config.paths is None
            font = ImageFont.load_default()
        draw.text((50, 230), "Services not initialized", font=font, fill=(255,255,255))
        return np.array(placeholder_img), empty_fig, [], []

    video_files_map = get_video_files()

    # Check if a valid video is selected
    if not video_name or video_name not in video_files_map or not video_files_map[video_name]:
        empty_fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Please select a valid video.", ha='center', va='center')
        placeholder_img = np.zeros((480, 640, 3), dtype=np.uint8) # Black image
        draw = ImageDraw.Draw(Image.fromarray(placeholder_img))
        try:
            font = ImageFont.truetype(os.path.join(app_config.paths.font_path.parent, app_config.paths.font_path.name), 20)
        except (IOError, AttributeError):
            font = ImageFont.load_default()
        draw.text((50, 230), "Please select a video", font=font, fill=(255,255,255))
        return np.array(placeholder_img), empty_fig, [], []

    video_path = video_files_map[video_name]
    try:
        frame_cv = get_video_frame(video_path, frame_num)
    except ValueError as e:
        logger.error(f"Error getting video frame: {e}")
        empty_fig, ax = plt.subplots()
        ax.text(0.5, 0.5, f"Error: Could not load frame {frame_num}.", ha='center', va='center')
        return np.zeros((480, 640, 3), dtype=np.uint8), empty_fig, embeddings, labels # Return tuple

    # Process frame using the service
    matches_for_drawing, new_embeddings, new_labels = face_recognition_service.process_video_frame(
        frame_cv.copy(), det_threshold=det_thresh, rec_threshold=rec_thresh
    )

    # Draw annotations using the visualization service
    annotated_frame_rgb = visualization_service.draw_face_annotations(
        frame_cv.copy(), # Pass original frame for drawing
        matches_for_drawing, # This is now the correct list of matches
        timestamp=datetime.now().strftime("%H:%M:%S")
    )

    # Ensure correct format for Gradio (RGB, uint8, shape (H, W, 3))
    if annotated_frame_rgb is not None:
        annotated_frame_rgb = np.asarray(annotated_frame_rgb)
        if annotated_frame_rgb.dtype != np.uint8:
            annotated_frame_rgb = annotated_frame_rgb.astype(np.uint8)
        if len(annotated_frame_rgb.shape) == 2:  # grayscale, convert to RGB
            annotated_frame_rgb = np.stack([annotated_frame_rgb]*3, axis=-1)
        elif annotated_frame_rgb.shape[-1] != 3:
            # If alpha channel, drop it
            annotated_frame_rgb = annotated_frame_rgb[..., :3]

    # Update stored embeddings and labels
    embeddings.extend(new_embeddings)
    labels.extend(new_labels)

    # Get gallery data for UMAP
    gallery_embs, gallery_names = face_recognition_service.get_gallery_data_for_visualization()

    # Generate UMAP plot
    umap_plot = visualization_service.generate_umap_plot(
        detected_embeddings=embeddings, # Pass the accumulated embeddings
        gallery_embeddings=gallery_embs,
        gallery_names=gallery_names,
        detected_labels=labels, # Pass the accumulated labels
        show_current_only=show_current_only
    )

    return annotated_frame_rgb, umap_plot, embeddings, labels # Return tuple for multiple outputs

def create_gradio_interface():
    """Create the Gradio interface for video frame analysis."""
    global app_config, video_manager
    
    # Get initial video list
    video_files_map = get_video_files()
    video_names = list(video_files_map.keys())
    
    # Add cache status display
    cache_status = video_manager.get_cache_status() if video_manager else {}
    cache_info = f"Videos: {cache_status.get('cached_videos', 0)}/{cache_status.get('total_videos', 0)} cached" if cache_status else "Video manager not initialized"
    
    with gr.Blocks(title="Face Recognition Explorer") as demo:
        gr.Markdown("# Face Recognition Explorer")
        gr.Markdown("Select a video and navigate frames to analyze face recognition results")
        gr.Markdown(f"📊 **Status:** {cache_info}")
        
        with gr.Row():
            with gr.Column(scale=3):
                video_dropdown = gr.Dropdown(choices=video_names, label="Select Video")
                frame_slider = gr.Slider(minimum=0, maximum=100, value=0, step=1, label="Frame Number")
                with gr.Row():
                    prev_btn = gr.Button("Previous Frame")
                    next_btn = gr.Button("Next Frame")
            with gr.Column(scale=1):
                det_thresh_slider = gr.Slider(0.1, 1.0, value=0.5, step=0.05, label="Detection Threshold")
                rec_thresh_slider = gr.Slider(0.1, 1.0, value=0.5, step=0.05, label="Recognition Threshold")
                show_current_only = gr.Checkbox(label="Show Current Frame Only", value=False)
                auto_advance_checkbox = gr.Checkbox(label="Auto-advance Frame", value=False)

        with gr.Row():
            frame_output = gr.Image(label="Processed Frame")
            plot_output = gr.Plot(label="UMAP Embedding Visualization")
        
        # Store embeddings and labels across interactions
        all_embeddings = gr.State([])
        all_labels = gr.State([])
        auto_advance_state = gr.State(False)
        total_frames_state = gr.State(1)

        def load_video(video_name):
            """Initialize when video is selected."""
            # Get fresh video files map in case new videos were downloaded
            current_video_files = get_video_files()
            
            if video_name not in current_video_files or not current_video_files[video_name]:
                return {
                    frame_slider: gr.Slider(maximum=0, value=0),
                    all_embeddings: [],
                    all_labels: [],
                    total_frames_state: 1
                }
            
            video_path = current_video_files[video_name]
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            return {
                frame_slider: gr.Slider(maximum=total_frames-1),
                all_embeddings: [],
                all_labels: [],
                total_frames_state: total_frames
            }
        
        # Define inputs for process_frame_for_gradio
        process_inputs = [
            video_dropdown, 
            frame_slider, 
            det_thresh_slider, 
            rec_thresh_slider, 
            all_embeddings, 
            all_labels,
            show_current_only,
            auto_advance_state
        ]
        # Define outputs for process_frame_for_gradio
        common_process_outputs = [frame_output, plot_output, all_embeddings, all_labels]

        # Wire up the interface
        video_dropdown.change(
            load_video,
            inputs=[video_dropdown],
            outputs=[frame_slider, all_embeddings, all_labels, total_frames_state]
        )
        
        frame_slider.change(
            process_frame_for_gradio,
            inputs=process_inputs,
            outputs=common_process_outputs
        )
        
        det_thresh_slider.change(
            process_frame_for_gradio,
            inputs=process_inputs,
            outputs=common_process_outputs
        )

        rec_thresh_slider.change(
            process_frame_for_gradio,
            inputs=process_inputs,
            outputs=common_process_outputs
        )
        
        show_current_only.change(
            process_frame_for_gradio,
            inputs=process_inputs,
            outputs=common_process_outputs
        )

        auto_advance_checkbox.change(
            lambda x: x,
            inputs=[auto_advance_checkbox],
            outputs=[auto_advance_state]
        )

        prev_btn.click(
            lambda current_frame: max(0, current_frame - 1),
            inputs=[frame_slider],
            outputs=frame_slider
        ).then(
            process_frame_for_gradio,
            inputs=process_inputs,
            outputs=common_process_outputs
        )
        
        next_btn.click(
            lambda current_frame, total_frames: min(current_frame + 1, total_frames -1) if total_frames > 0 else 0,
            inputs=[frame_slider, total_frames_state],
            outputs=frame_slider
        ).then(
            process_frame_for_gradio,
            inputs=process_inputs,
            outputs=common_process_outputs
        )

        # Auto-advance logic: Triggered after processing a frame if auto_advance_state is True
        frame_output.change(
            lambda current_frame_num, total_frames, auto_advance_enabled: 
                min(current_frame_num + 1, total_frames - 1) if auto_advance_enabled and current_frame_num < total_frames - 1 else current_frame_num,
            inputs=[frame_slider, total_frames_state, auto_advance_state],
            outputs=frame_slider,
            queue=False
        )

    return demo

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("gradio_app.log"),
        ],
    )
    
    # Initialize configuration and services
    app_config = get_config()
    face_recognition_service = FaceRecognitionService(app_config)
    visualization_service = VisualizationService(str(app_config.paths.font_path.parent))
    
    # Initialize video manager with YouTube integration
    video_manager = get_video_manager(enable_youtube=True)
    
    # Download videos for better user experience
    logger.info("🎬 Initializing video downloads...")
    try:
        # Check if we're in HF Spaces or local environment
        is_hf_spaces = os.environ.get('SPACE_ID') or os.path.exists('/home/user')
        quality = "480p" if is_hf_spaces else "720p"  # Use lower quality for HF Spaces
        
        cache_status = video_manager.get_cache_status()
        if cache_status['cached_videos'] < cache_status['total_videos']:
            logger.info(f"📥 Downloading {cache_status['total_videos'] - cache_status['cached_videos']} missing videos...")
            downloaded = video_manager.download_all_videos(max_workers=1, quality=quality)
            logger.info(f"✅ Video initialization complete: {len(downloaded)} videos available")
        else:
            logger.info("✅ All videos already cached and ready")
    except Exception as e:
        logger.error(f"⚠️ Error during video initialization: {e}")
        logger.info("🔄 Videos will be downloaded on-demand during usage")

    # Create and launch Gradio interface
    demo = create_gradio_interface()
    demo.launch()
