#!/usr/bin/env python
"""
Face Recognition Gradio Web Interface

This module provides a Gradio-based web interface for real-time face recognition
using the ChromaDB backend and advanced visualization options.
"""

import os
import sys
import time
import logging
from pathlib import Path
import threading
import numpy as np
import cv2
import gradio as gr
from typing import Dict, List, Tuple, Any, Optional, Union
import traceback
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("gradio_app.log"),
    ],
)
logger = logging.getLogger(__name__)

# Import custom modules
from src.utils.gradio_visualization import (
    plot_bar,
    plot_embedding_scatter,
    draw_faces_with_labels,
)

# Import core components
from src.core.detector import FaceDetector
from src.core.recognizer import StandardFaceRecognizer
from src.backends.chromadb_backend import ChromaDBFaceRecognizer

# Global variables
DETECTOR = None
RECOGNIZER = None
GALLERY_EMBEDDINGS = {}
GALLERY_NAMES = {}
PROCESSING_STATS = {
    "processed_frames": 0,
    "detection_time": 0,
    "recognition_time": 0,
    "total_time": 0,
    "faces_detected": 0,
    "faces_recognized": 0,
    "start_time": None,
}
STATUS_LOCK = threading.Lock()


# UI Component Creation Functions

def create_recognition_settings_group():
    """
    Creates a Gradio group for recognition settings.

    Returns:
        Tuple: (gr.Group, gr.Slider, gr.Checkbox, gr.Slider, gr.Radio)
               The group itself, similarity_threshold, use_tracking,
               max_matches, and visualization_type components.
    """
    with gr.Group():
        gr.Markdown("### Recognition Settings")
        similarity_threshold = gr.Slider(
            minimum=0.3,
            maximum=0.9,
            value=0.6,
            step=0.05,
            label="Similarity Threshold",
            info="Lower values match more faces but may have false positives",
        )
        use_tracking = gr.Checkbox(
            value=True,
            label="Use Face Tracking",
            info="Improves performance by tracking faces between frames",
        )
        max_matches = gr.Slider(
            minimum=1,
            maximum=10,
            value=3,
            step=1,
            label="Max Matches Per Face",
            info="Maximum number of matches to show for each face",
        )
        visualization_type = gr.Radio(
            choices=["bar", "scatter"],
            value="bar",
            label="Visualization Type",
            info="Bar chart or embedding scatter plot",
        )
    return similarity_threshold, use_tracking, max_matches, visualization_type


def create_status_group():
    """
    Creates a Gradio group for status display and controls.

    Returns:
        Tuple: (gr.Group, gr.HTML, gr.Button, gr.Button, gr.Markdown)
               The group itself, stats_html, reset_stats_btn,
               reload_gallery_btn, and gallery_status components.
    """
    with gr.Group():
        stats_html = gr.HTML(value=format_stats_for_display(), label="Performance Stats")
        reset_stats_btn = gr.Button("Reset Statistics")
        reload_gallery_btn = gr.Button("Reload Gallery")
        gallery_status = gr.Markdown("Gallery not loaded yet")
    return stats_html, reset_stats_btn, reload_gallery_btn, gallery_status


def initialize_models(
    detector_backend: str = "insightface",
    device: str = "auto",
    cache_dir: str = "cache/chromadb",
    similarity_threshold: float = 0.6,
    persistent_db: bool = True,
    use_tracking: bool = False,
) -> Tuple[FaceDetector, ChromaDBFaceRecognizer]:
    """
    Initialize face detection and recognition models.

    Args:
        detector_backend: Backend for face detection
        device: Compute device (cpu, cuda, or auto)
        cache_dir: Directory for caching
        similarity_threshold: Threshold for face matching
        persistent_db: Whether to use persistent ChromaDB storage
        use_tracking: Whether to use face tracking for optimization

    Returns:
        Tuple of (detector, recognizer)
    """
    try:
        logger.info(f"Initializing FaceDetector with backend={detector_backend}, device={device}")
        
        # Initialize face detector
        detector = FaceDetector(
            backend=detector_backend,
            confidence_threshold=0.5,
            device=device,
            tracking_method="kcf" if use_tracking else "none",
            tracking_duration=5 if use_tracking else 0,
            cache_enabled=True,
        )
        
        # Initialize standard recognizer (needed by ChromaDB recognizer)
        standard_recognizer = StandardFaceRecognizer(
            face_detector=detector,
            similarity_threshold=similarity_threshold,
        )
        
        # Initialize ChromaDB recognizer
        chromadb_recognizer = ChromaDBFaceRecognizer(
            face_detector=detector,
            standard_recognizer=standard_recognizer,
            similarity_threshold=similarity_threshold,
            persistent=persistent_db,
            collection_name="face_embeddings",
            cache_dir=cache_dir,
        )
        
        logger.info("Successfully initialized detector and recognizer models")
        return detector, chromadb_recognizer
        
    except Exception as e:
        logger.error(f"Error initializing models: {str(e)}")
        logger.error(traceback.format_exc())
        raise RuntimeError(f"Error during model setup: {str(e)}. Please check model files and configurations.")


def load_gallery_embeddings(
    recognizer: ChromaDBFaceRecognizer,
    gallery_dir: str = "source/photo/contestants",
) -> Tuple[Dict[str, List[np.ndarray]], Dict[str, str]]:
    """
    Load gallery embeddings for recognition.

    Args:
        recognizer: Face recognizer instance
        gallery_dir: Directory containing gallery images

    Returns:
        Tuple of (embeddings_dict, names_dict)
    """
    try:
        logger.info(f"Loading gallery embeddings from {gallery_dir}")
        
        if not os.path.exists(gallery_dir):
            logger.warning(f"Gallery directory {gallery_dir} does not exist")
            os.makedirs(gallery_dir, exist_ok=True)
            return {}, {}
        
        # Get all image files from the gallery directory
        image_extensions = [".jpg", ".jpeg", ".png", ".bmp"]
        image_files = []
        for root, _, files in os.walk(gallery_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(root, file))
        
        logger.info(f"Found {len(image_files)} gallery images")
        
        # Process each image
        embeddings_dict = {}
        names_dict = {}
        
        for img_path in image_files:
            try:
                # Extract person ID from filename or directory
                person_id = os.path.splitext(os.path.basename(img_path))[0]
                
                # Try to get display name from parent directory if in format "ID_Name"
                parent_dir = os.path.basename(os.path.dirname(img_path))
                if "_" in parent_dir:
                    parts = parent_dir.split("_", 1)
                    if len(parts) > 1:
                        dir_id, name = parts
                        if dir_id == person_id:
                            names_dict[person_id] = name
                
                # Load and process image
                img = cv2.imread(img_path)
                if img is None:
                    logger.warning(f"Failed to load image: {img_path}")
                    continue
                    
                # Convert to RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                
                # Detect faces
                faces = recognizer.face_detector.detect_faces(img_rgb)
                
                if not faces:
                    logger.warning(f"No faces detected in {img_path}")
                    continue
                
                # Use the largest face if multiple faces detected
                if len(faces) > 1:
                    # Sort by area (width * height)
                    face_areas = [(f, (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])) for f in faces]
                    face_areas.sort(key=lambda x: x[1], reverse=True)
                    largest_face = face_areas[0][0]
                    
                    logger.info(f"Multiple faces in {img_path}, using largest face")
                    faces = [largest_face]
                
                # Compute embedding for the face
                face_img = recognizer.face_detector.extract_face(img_rgb, faces[0].bbox)
                if face_img is None:
                    logger.warning(f"Failed to extract face from {img_path}")
                    continue
                
                face_embedding = recognizer.compute_embedding(face_img)
                
                # Add to dictionary
                if person_id not in embeddings_dict:
                    embeddings_dict[person_id] = []
                
                embeddings_dict[person_id].append(face_embedding)
                
                # If no name was set from directory, use ID as name
                if person_id not in names_dict:
                    names_dict[person_id] = person_id
                    
                logger.debug(f"Processed {person_id}: {img_path}")
                
            except Exception as e:
                logger.error(f"Error processing {img_path}: {str(e)}")
        
        # Load embeddings into ChromaDB
        if embeddings_dict:
            recognizer.load_embeddings_from_dict(embeddings_dict)
            logger.info(f"Loaded {sum(len(embs) for embs in embeddings_dict.values())} embeddings for {len(embeddings_dict)} people")
        else:
            logger.warning("No embeddings could be extracted from gallery images")
            
        return embeddings_dict, names_dict
        
    except Exception as e:
        user_friendly_error = f"Could not load gallery embeddings: {str(e)}. Check image files and directory structure in 'source/photo/contestants/'."
        logger.error(user_friendly_error)
        logger.error(traceback.format_exc())
        # This function is called by reload_gallery, which handles UI messages.
        # We should raise an exception here to be caught by the caller, allowing it to set a UI error.
        raise RuntimeError(user_friendly_error)


def process_frame(
    frame: np.ndarray,
    detector: FaceDetector,
    recognizer: ChromaDBFaceRecognizer,
    gallery_embeddings: Dict[str, List[np.ndarray]],
    gallery_names: Dict[str, str],
    similarity_threshold: float = 0.6,
    max_matches_per_face: int = 3,
    visualization_type: str = "bar",
) -> Tuple[np.ndarray, Any]:
    """
    Process a frame for face recognition and visualization.

    Args:
        frame: Input frame
        detector: Face detector instance
        recognizer: Face recognizer instance
        gallery_embeddings: Gallery embeddings dictionary
        gallery_names: Gallery names dictionary
        similarity_threshold: Threshold for face matching
        max_matches_per_face: Maximum matches to return per face
        visualization_type: Type of visualization ('bar' or 'scatter')

    Returns:
        Tuple of (frame with annotations, visualization figure)
    """
    try:
        with STATUS_LOCK:
            if PROCESSING_STATS["start_time"] is None:
                PROCESSING_STATS["start_time"] = time.time()
                
            PROCESSING_STATS["processed_frames"] += 1
        
        # Start timing
        start_time = time.time()
        
        # Ensure frame is RGB (Gradio sometimes gives BGR)
        if frame.shape[2] == 3 and np.mean(frame[:, :, 0]) > np.mean(frame[:, :, 2]):
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        detection_start = time.time()
        detected_faces = detector.detect_faces(frame)
        detection_time = time.time() - detection_start
        
        with STATUS_LOCK:
            PROCESSING_STATS["detection_time"] += detection_time
            PROCESSING_STATS["faces_detected"] += len(detected_faces) if detected_faces else 0
        
        # Prepare structures for visualization
        face_results = []
        matches = []
        
        # Process each detected face
        if detected_faces:
            recognition_start = time.time()
            
            for face in detected_faces:
                # Skip faces without valid bounding boxes
                if not hasattr(face, 'bbox') or face.bbox is None:
                    continue
                
                # Extract face region
                face_img = detector.extract_face(frame, face.bbox)
                if face_img is None:
                    continue
                
                # Match face using ChromaDB
                match_result = recognizer.match_face(face.normed_embedding, n_results=max_matches_per_face)
                
                # Process match result
                if match_result and match_result["similarity"] >= similarity_threshold:
                    # Add to results
                    face_results.append({
                        "bbox": face.bbox,
                        "name": match_result["name"],
                        "confidence": match_result["similarity"],
                        "match_id": match_result["id"],
                    })
                    
                    # Get similar faces for visualization
                    similar_faces = recognizer.get_similar_faces(face.normed_embedding, max_results=max_matches_per_face)
                    matches.append([(match[0], match[1], i) for i, match in enumerate(similar_faces)])
                    
                    with STATUS_LOCK:
                        PROCESSING_STATS["faces_recognized"] += 1
                else:
                    # Unknown face
                    face_results.append({
                        "bbox": face.bbox,
                        "name": "Unknown",
                        "confidence": match_result["similarity"] if match_result else 0.0,
                    })
                    matches.append([])
            
            recognition_time = time.time() - recognition_start
            with STATUS_LOCK:
                PROCESSING_STATS["recognition_time"] += recognition_time
        
        # Draw faces on the frame
        frame_with_faces = draw_faces_with_labels(frame, face_results)
        
        # Create visualization
        if visualization_type == "bar":
            # Prepare data for bar chart
            all_matches_for_plot = []
            for i, match_list in enumerate(matches):
                if match_list:
                    for name, score, _ in match_list:
                        display_name = gallery_names.get(name, name)
                        all_matches_for_plot.append((f"Face {i+1}: {display_name}", score))
            
            all_matches_for_plot.sort(key=lambda x: x[1], reverse=True)
            fig = plot_bar(all_matches_for_plot)
        else:
            # Scatter plot of embeddings
            detected_embeddings = [
                face.normed_embedding for face in detected_faces 
                if hasattr(face, 'normed_embedding') and face.normed_embedding is not None
            ]
            fig = plot_embedding_scatter(detected_embeddings, gallery_embeddings, gallery_names, matches)
        
        # Update timing stats
        total_time = time.time() - start_time
        with STATUS_LOCK:
            PROCESSING_STATS["total_time"] += total_time
        
        return frame_with_faces, fig
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Create error frame
        error_frame = frame.copy() if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            error_frame,
            f"Error: {str(e)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )
        
        # Create error figure
        fig = plot_bar([("Processing Error", 0.0)]) # Changed title
        
        return error_frame, fig


def get_video_files(video_dir: str = "source/videos") -> Dict[str, str]:
    """
    Get available video files in the specified directory.

    Args:
        video_dir: Directory containing video files

    Returns:
        Dictionary mapping video names to file paths
    """
    # Create directory if it doesn't exist
    os.makedirs(video_dir, exist_ok=True)
    
    # Find video files
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    video_files = {}
    
    for file in os.listdir(video_dir):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            file_path = os.path.join(video_dir, file)
            video_files[file] = file_path
    
    # Add a default None option
    if not video_files:
        logger.warning(f"No video files found in {video_dir}")
        # Add a placeholder if directory is empty
        sample_path = os.path.join(video_dir, "sample_video.mp4")
        with open(sample_path, "w") as f:
            f.write("placeholder")
        video_files["No videos found - please add videos to source/videos/"] = sample_path
    
    return video_files


def get_performance_stats() -> Dict[str, Any]:
    """
    Get current performance statistics.

    Returns:
        Dictionary with performance statistics
    """
    with STATUS_LOCK:
        stats = PROCESSING_STATS.copy()
        
        # Calculate derived metrics
        if stats["processed_frames"] > 0:
            stats["avg_detection_time"] = stats["detection_time"] / stats["processed_frames"] * 1000  # ms
            stats["avg_recognition_time"] = stats["recognition_time"] / stats["processed_frames"] * 1000  # ms
            stats["avg_total_time"] = stats["total_time"] / stats["processed_frames"] * 1000  # ms
            stats["faces_per_frame"] = stats["faces_detected"] / stats["processed_frames"]
            
            if stats["start_time"] is not None:
                elapsed_time = time.time() - stats["start_time"]
                stats["fps"] = stats["processed_frames"] / elapsed_time if elapsed_time > 0 else 0
            else:
                stats["fps"] = 0
                
            if stats["faces_detected"] > 0:
                stats["recognition_rate"] = stats["faces_recognized"] / stats["faces_detected"]
            else:
                stats["recognition_rate"] = 0
        else:
            stats.update({
                "avg_detection_time": 0,
                "avg_recognition_time": 0,
                "avg_total_time": 0,
                "faces_per_frame": 0,
                "fps": 0,
                "recognition_rate": 0,
            })
            
    return stats


def format_stats_for_display() -> str:
    """
    Format performance statistics for display.

    Returns:
        Formatted statistics as HTML
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = get_performance_stats()
    
    html = """
    <div style="font-family: sans-serif; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
        <h3 style="margin-top: 0;">Performance Statistics</h3>
        <table style="width: 100%; border-collapse: collapse;">
    """
    
    # Add rows for each stat with colored indicators for performance
    metrics = [
        ("Processed Frames", f"{stats['processed_frames']}", None),
        ("FPS", f"{stats['fps']:.2f}", 
         "red" if stats['fps'] < 5 else "orange" if stats['fps'] < 15 else "green"),
        ("Detection Time", f"{stats['avg_detection_time']:.1f} ms", 
         "red" if stats['avg_detection_time'] > 100 else "orange" if stats['avg_detection_time'] > 50 else "green"),
        ("Recognition Time", f"{stats['avg_recognition_time']:.1f} ms",
         "red" if stats['avg_recognition_time'] > 100 else "orange" if stats['avg_recognition_time'] > 50 else "green"),
        ("Total Processing Time", f"{stats['avg_total_time']:.1f} ms",
         "red" if stats['avg_total_time'] > 200 else "orange" if stats['avg_total_time'] > 100 else "green"),
        ("Faces Detected", f"{stats['faces_detected']}", None),
        ("Faces Recognized", f"{stats['faces_recognized']}", None),
        ("Recognition Rate", f"{stats['recognition_rate']:.1%}",
         "red" if stats['recognition_rate'] < 0.3 else "orange" if stats['recognition_rate'] < 0.7 else "green"),
    ]
    
    for label, value, color in metrics:
        if color:
            html += f"""
            <tr>
                <td style="padding: 4px; border-bottom: 1px solid #ddd;">{label}</td>
                <td style="padding: 4px; border-bottom: 1px solid #ddd; text-align: right; color: {color}; font-weight: bold;">{value}</td>
            </tr>
            """
        else:
            html += f"""
            <tr>
                <td style="padding: 4px; border-bottom: 1px solid #ddd;">{label}</td>
                <td style="padding: 4px; border-bottom: 1px solid #ddd; text-align: right;">{value}</td>
            </tr>
            """
    
    html += """
        </table>
        <p style="font-size: 0.9em; text-align: right; color: #555;">Last updated: {now}</p>
    </div>
    """
    
    return html


def reset_stats() -> str:
    """
    Reset performance statistics.

    Returns:
        HTML status message
    """
    with STATUS_LOCK:
        for key in PROCESSING_STATS:
            if key != "start_time":
                PROCESSING_STATS[key] = 0
        PROCESSING_STATS["start_time"] = time.time()
    
    return format_stats_for_display()


def process_webcam_frame(
    frame: np.ndarray,
    similarity_threshold: float,
    visualization_type: str,
    use_tracking: bool,
    max_matches: int,
) -> Tuple[np.ndarray, Any, str]:
    """
    Process a webcam frame for face recognition.

    Args:
        frame: Input frame from webcam
        similarity_threshold: Threshold for face matching
        visualization_type: Type of visualization
        use_tracking: Whether to use face tracking
        max_matches: Maximum matches per face

    Returns:
        Tuple of (frame with annotations, visualization figure, status HTML)
    """
    global DETECTOR, RECOGNIZER, GALLERY_EMBEDDINGS, GALLERY_NAMES
    
    try:
        # Create models if they don't exist
        if DETECTOR is None or RECOGNIZER is None:
            gr.Info("Initializing models, please wait...")
            DETECTOR, RECOGNIZER = initialize_models(
                similarity_threshold=similarity_threshold,
                use_tracking=use_tracking,
            )
            GALLERY_EMBEDDINGS, GALLERY_NAMES = load_gallery_embeddings(RECOGNIZER)
        
        # Handle empty frame
        if frame is None:
            # Return an error frame and figure
            empty_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                empty_frame,
                "No webcam frame received",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2
            )
            fig = plot_bar([("Error", 0.0)])
            return empty_frame, fig, format_stats_for_display()
        
        # Update detector settings if tracking setting has changed
        if DETECTOR.tracking_method == "none" and use_tracking:
            DETECTOR.tracking_method = "kcf"
            DETECTOR.tracking_duration = 5
        elif DETECTOR.tracking_method != "none" and not use_tracking:
            DETECTOR.tracking_method = "none"
            DETECTOR.tracking_duration = 0
        
        # Update recognizer threshold if changed
        if RECOGNIZER.similarity_threshold != similarity_threshold:
            RECOGNIZER.similarity_threshold = similarity_threshold
        
        # Process the frame
        frame_with_faces, fig = process_frame(
            frame,
            DETECTOR,
            RECOGNIZER,
            GALLERY_EMBEDDINGS,
            GALLERY_NAMES,
            similarity_threshold=similarity_threshold,
            max_matches_per_face=max_matches,
            visualization_type=visualization_type,
        )
        
        # Return the results with updated stats
        return frame_with_faces, fig, format_stats_for_display()
        
    except Exception as e:
        logger.error(f"Error processing webcam frame: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Create error frame
        error_frame = frame.copy() if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            error_frame,
            f"Error: {str(e)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )
        
        # Create error figure
        fig = plot_bar([("Error", 0.0)])
        
        return error_frame, fig, format_stats_for_display()


def process_video_frame(
    video_path: str,
    frame_idx: int,
    similarity_threshold: float,
    visualization_type: str,
    use_tracking: bool,
    max_matches: int,
) -> Tuple[np.ndarray, Any, str]:
    """
    Process a video frame for face recognition.

    Args:
        video_path: Path to video file
        frame_idx: Frame index to process
        similarity_threshold: Threshold for face matching
        visualization_type: Type of visualization
        use_tracking: Whether to use face tracking
        max_matches: Maximum matches per face

    Returns:
        Tuple of (frame with annotations, visualization figure, status HTML)
    """
    global DETECTOR, RECOGNIZER, GALLERY_EMBEDDINGS, GALLERY_NAMES
    
    try:
        # Create models if they don't exist
        if DETECTOR is None or RECOGNIZER is None:
            gr.Info("Initializing models, please wait...")
            DETECTOR, RECOGNIZER = initialize_models(
                similarity_threshold=similarity_threshold,
                use_tracking=use_tracking,
            )
            GALLERY_EMBEDDINGS, GALLERY_NAMES = load_gallery_embeddings(RECOGNIZER)
        
        # Check if video path exists
        if not os.path.exists(video_path):
            # Raise gr.Error for Gradio UI
            gr.Error(f"Video file not found: {os.path.basename(video_path)}. Please check the 'source/videos' directory.")
            # Return an error frame and figure as per existing logic
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                error_frame,
                f"Video Not Found: {os.path.basename(video_path)}", # Updated message
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255), # Red color for error text
                2
            )
            fig = plot_bar([("Video Not Found", 0.0)])
            return error_frame, fig, format_stats_for_display()
            
        # Update detector settings if tracking setting has changed
        if DETECTOR.tracking_method == "none" and use_tracking:
            DETECTOR.tracking_method = "kcf"
            DETECTOR.tracking_duration = 5
        elif DETECTOR.tracking_method != "none" and not use_tracking:
            DETECTOR.tracking_method = "none"
            DETECTOR.tracking_duration = 0
        
        # Update recognizer threshold if changed
        if RECOGNIZER.similarity_threshold != similarity_threshold:
            RECOGNIZER.similarity_threshold = similarity_threshold
        
        # Open video and get frame
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Check if frame index is valid
        if frame_idx >= total_frames:
            frame_idx = total_frames - 1
        
        # Seek to frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            gr.Warning(f"Could not read frame {frame_idx} from {os.path.basename(video_path)}. The video file might be corrupted or incomplete.")
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                error_frame,
                f"Frame Read Error: {os.path.basename(video_path)} Frame {frame_idx}", # Updated message
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255), # Red color for error text
                2
            )
            fig = plot_bar([("Frame Read Error", 0.0)])
            return error_frame, fig, format_stats_for_display()
        
        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the frame
        frame_with_faces, fig = process_frame(
            frame_rgb,
            DETECTOR,
            RECOGNIZER,
            GALLERY_EMBEDDINGS,
            GALLERY_NAMES,
            similarity_threshold=similarity_threshold,
            max_matches_per_face=max_matches,
            visualization_type=visualization_type,
        )
        
        # Return the results with updated stats
        return frame_with_faces, fig, format_stats_for_display()
        
    except Exception as e:
            user_friendly_message = f"Error processing video frame: {str(e)}. Please check the video file and system logs."
            logger.error(user_friendly_message)
        logger.error(traceback.format_exc())
            gr.Error(user_friendly_message) # Display error in Gradio UI
        
        # Create error frame
        error_frame = np.zeros((480, 640, 3), dtype=np.uint8) # Default error frame
        # Try to use the original frame if available, otherwise use the blank one
        if 'frame' in locals() and frame is not None:
            error_frame = frame.copy()

        cv2.putText(
            error_frame,
            f"Processing Error: {str(e)}", # More specific message
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255), # Red color
            2
        )
        
        # Create error figure
        fig = plot_bar([("Video Processing Error", 0.0)]) # More specific title
        
        return error_frame, fig, format_stats_for_display()


def video_play_loop(
    video_name: str,
    video_paths: Dict[str, str],
    start_frame: int,
    similarity_threshold: float,
    visualization_type: str,
    use_tracking: bool,
    max_matches: int,
    state: Dict[str, Any]
):
    """
    Generator function for video playback loop.
    
    Args:
        video_name: Name of the video file
        video_paths: Dictionary of video paths
        start_frame: Starting frame index
        similarity_threshold: Threshold for face matching
        visualization_type: Visualization type
        use_tracking: Whether to use face tracking
        max_matches: Maximum number of matches per face
        state: Current state dictionary
    
    Yields:
        Sequence of outputs for Gradio interface
    """
    global DETECTOR, RECOGNIZER
    
    try:
        # Get video path
        video_path = video_paths.get(video_name)
        if not video_path or not os.path.exists(video_path):
            error_msg = f"Video file not found: {video_name}. Please check 'source/videos/' directory."
            logger.error(error_msg)
            gr.Error(error_msg) # Show Gradio error notification
            
            # Yield error message
            yield (
                None,  # frame
                None,  # plot
                start_frame,  # slider
                format_stats_for_display(),  # stats
                error_msg,  # status (Markdown)
                False,  # playing
                start_frame,  # current frame
                0,  # total frames
            )
            return
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        # Set starting frame
        frame_idx = start_frame
        
        # Set playing state
        playing = True
        
        # Main playback loop
        while playing and frame_idx < total_frames:
            # Update state from input
            playing = state.get("playing", True)
            if not playing:
                break
                
            # Seek to the current frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                logger.warning(f"Could not read frame {frame_idx}")
                frame_idx += 1
                continue
                
            # Convert to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the frame
            try:
                processed_frame, visualization = process_frame(
                    frame_rgb,
                    DETECTOR,
                    RECOGNIZER,
                    GALLERY_EMBEDDINGS,
                    GALLERY_NAMES,
                    similarity_threshold=similarity_threshold,
                    max_matches_per_face=max_matches,
                    visualization_type=visualization_type,
                )
                
                # Yield results
                yield (
                    processed_frame,  # frame
                    visualization,  # plot
                    frame_idx,  # slider
                    format_stats_for_display(),  # stats
                    f"Processing frame {frame_idx}/{total_frames}",  # status
                    playing,  # playing
                    frame_idx,  # current frame
                    total_frames,  # total frames
                )
                
            except Exception as e:
                logger.error(f"Error processing frame {frame_idx}: {str(e)}")
                error_img = frame_rgb.copy()
                cv2.putText(
                    error_img,
                    f"Error: {str(e)}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 0, 0),
                    2
                )
                
                # Create error figure
                fig = plot_bar([("Frame Processing Error", 0.0)]) # More specific title
                
                # Yield error
                yield (
                    error_img,  # frame
                    fig,  # plot
                    frame_idx,  # slider
                    format_stats_for_display(),  # stats
                    f"Error processing frame {frame_idx} in {video_name}: {str(e)}",  # More specific status
                    playing,  # playing
                    frame_idx,  # current frame
                    total_frames,  # total frames
                )
            
            # Increment frame counter
            frame_idx += 1
            
            # Add delay to control playback speed
            time.sleep(1.0 / (fps * 1.5))  # Slightly faster than original
            
        # Playback finished
        cap.release()
        
        # Yield final state update
        yield (
            gr.update(),  # frame
            gr.update(),  # plot
            frame_idx,  # slider
            format_stats_for_display(),  # stats
            "Playback finished" if frame_idx >= total_frames else "Playback paused",  # status
            False,  # playing
            frame_idx,  # current frame
            total_frames,  # total frames
        )
        
    except Exception as e:
        logger.error(f"Error in video playback: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Yield error state
        yield (
            None,  # frame
            None,  # plot
            start_frame,  # slider
            format_stats_for_display(),  # stats
            f"Video Playback Error: {str(e)}. Check logs.",  # status
            False,  # playing
            start_frame,  # current frame
            0,  # total frames
        )


def reload_gallery() -> str:
    """
    Reload gallery embeddings.
    
    Returns:
        Status message
    """
    global DETECTOR, RECOGNIZER, GALLERY_EMBEDDINGS, GALLERY_NAMES
    
    try:
        if RECOGNIZER:
            logger.info("Recognizer found, proceeding with gallery reload.")
            # This call might raise RuntimeError if load_gallery_embeddings fails
            GALLERY_EMBEDDINGS, GALLERY_NAMES = load_gallery_embeddings(RECOGNIZER)
            
            # Count embeddings
            total_embeddings = sum(len(embs) for embs in GALLERY_EMBEDDINGS.values())
            total_people = len(GALLERY_EMBEDDINGS)
            
            if total_embeddings > 0:
                msg = f"Successfully loaded {total_embeddings} embeddings for {total_people} people."
                logger.info(msg)
                return msg
            else:
                msg = "No gallery embeddings found or loaded. Please check 'source/photo/contestants/' and logs."
                logger.warning(msg)
                return msg
        else:
            msg = "Models not initialized. Cannot reload gallery. Process a frame or webcam feed first."
            logger.warning(msg)
            return msg
            
    except RuntimeError as e: # Catch specific error from load_gallery_embeddings
        error_msg = f"Failed to reload gallery: {str(e)}"
        logger.error(error_msg)
        return error_msg # Return the user-friendly message from the caught exception
    except Exception as e:
        error_msg = f"Unexpected error reloading gallery: {str(e)}. Check logs for details."
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return error_msg

# Action functions for reload_gallery buttons
def reload_gallery_action():
    """
    Action for the reload gallery button.
    Updates UI to show loading state, reloads gallery, then updates UI with result.
    This function is a generator.
    """
    yield "Reloading gallery, please wait...", gr.update(interactive=False)
    try:
        # reload_gallery now returns a message, or raises an exception that is caught here
        result_message = reload_gallery() 
        if "Error" in result_message or "Failed" in result_message or "Could not" in result_message:
            gr.Warning(result_message) # Show warning for non-critical load issues
        else:
            gr.Info(result_message) # Show info for success
        yield result_message, gr.update(interactive=True)
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"Critical exception in reload_gallery_action: {str(e)}")
        logger.error(traceback.format_exc())
        gr.Error(f"A critical error occurred during gallery reload: {str(e)}")
        yield f"Critical error: {str(e)}", gr.update(interactive=True)


# Create the Gradio interface
def create_interface():
    """Create the Gradio web interface."""
    
    # Get available videos
    video_files = get_video_files()
    
    # Create initial state
    initial_state = {
        "playing": False,
        "current_frame": 0,
        "total_frames": 0,
        "input_mode": "webcam",  # Initial input mode
    }
    
    # Create the interface
    with gr.Blocks(title="Face Recognition System") as app:
        gr.Markdown("# Face Recognition System with ChromaDB")
        
        # Create state
        state = gr.State(initial_state)
        
        with gr.Tabs() as tabs:
            # Video input tab
            with gr.TabItem("Video Analysis") as video_tab:
                with gr.Row():
                    with gr.Column(scale=3):
                        # Video selection and controls
                        video_dropdown = gr.Dropdown(
                            choices=list(video_files.keys()),
                            value=list(video_files.keys())[0] if video_files else None,
                            label="Select Video",
                            interactive=True,
                        )
                        
                        with gr.Row():
                            video_player_image = gr.Image(type="numpy", label="Video Output")
                        
                        with gr.Row():
                            frame_slider = gr.Slider(
                                minimum=0,
                                maximum=100,
                                value=0,
                                step=1,
                                label="Frame",
                                interactive=True,
                            )
                            
                        with gr.Row():
                            play_btn = gr.Button("Play", variant="primary")
                            pause_btn = gr.Button("Pause")
                            prev_frame_btn = gr.Button("Previous Frame")
                            next_frame_btn = gr.Button("Next Frame")
                            video_status = gr.Markdown("Ready to play")
                    
                    with gr.Column(scale=2):
                        # Visualization
                        with gr.Tab("Visualization"):
                            plot_output = gr.Plot(label="Recognition Results")
                            
                        with gr.Tab("Settings"):
                            (similarity_threshold_video, 
                             use_tracking_video, 
                             max_matches_video, 
                             visualization_type_video) = create_recognition_settings_group()
                        
                        with gr.Tab("Status"):
                            (stats_html_video, 
                             reset_stats_btn_video, 
                             reload_gallery_btn_video, 
                             gallery_status_video) = create_status_group()
            
            # Webcam input tab
            with gr.TabItem("Webcam Mode") as webcam_tab:
                with gr.Row():
                    with gr.Column(scale=3):
                        # Webcam input
                        webcam_input = gr.Image(source="webcam", streaming=True, type="numpy", label="Webcam Input")
                        webcam_output = gr.Image(type="numpy", label="Webcam Output")
                    
                    with gr.Column(scale=2):
                        # Visualization
                        with gr.Tab("Visualization"):
                            webcam_plot = gr.Plot(label="Recognition Results")
                            
                        with gr.Tab("Settings"):
                            (similarity_threshold_webcam, 
                             use_tracking_webcam, 
                             max_matches_webcam, 
                             visualization_type_webcam) = create_recognition_settings_group()
                        
                        with gr.Tab("Status"):
                            (stats_html_webcam, 
                             reset_stats_btn_webcam, 
                             reload_gallery_btn_webcam, 
                             gallery_status_webcam) = create_status_group()
        
        # Help tab
        with gr.Row():
            gr.Markdown("""
            ### Instructions

            1.  **Video Analysis:**
                *   Upload your MP4, AVI, MOV, MKV, or WEBM video files into the `source/videos/` directory in the project.
                *   Select the video from the dropdown in the "Video Analysis" tab.
                *   Use the player controls and frame slider to navigate or analyze specific frames.

            2.  **Gallery Management (Known Faces):**
                The system identifies faces by comparing them against a gallery of known individuals. Here's how to manage it:
                *   **Main Gallery Folder:** All known faces should be organized within the `source/photo/contestants/` directory in your project.
                *   **Adding a New Person:**
                    1.  Inside `source/photo/contestants/`, create a new sub-folder for the person.
                    2.  **Folder Naming:** For best results, name this folder using the format `ID_DisplayName` (e.g., `001_AliceSmith`, `002_BobJohnson`).
                        *   The `DisplayName` (e.g., AliceSmith) will be used in the recognition results.
                        *   If the `_DisplayName` part is omitted (e.g., folder named just `001`), the `ID` (e.g., 001) will be used as the name.
                    3.  Place one or more clear photos of this person into their newly created sub-folder. More photos, especially with varied angles and expressions, can improve recognition accuracy.
                    4.  Supported image types are `.jpg`, `.jpeg`, and `.png`.
                *   **Removing a Person:**
                    1.  Delete the person's entire sub-folder (e.g., `001_AliceSmith`) from the `source/photo/contestants/` directory.
                *   **Applying Changes:**
                    *   After making any changes to the gallery (adding new people, adding/removing photos, deleting person folders), you **must** click the **"Reload Gallery"** button.
                    *   This button is located in the "Status" tab within both the "Video Analysis" and "Webcam Mode" sections. This action rescans the gallery and updates the face recognition database.

            3.  **Recognition Settings:**
                *   Adjust the "Similarity Threshold", "Face Tracking", and other settings in the "Settings" tab for optimal performance based on your input.
                *   Experiment with these settings to find the best balance between detection accuracy and speed.

            4.  **Webcam Mode:**
                *   Ensure your webcam is connected and permissions are granted if prompted by your browser.
                *   The processed feed will appear in the "Webcam Output" panel.

            5.  **Viewing Results:**
                *   Detected faces will be highlighted in the output images/video.
                *   Recognition results (name, confidence) and visualizations (bar chart or scatter plot) are shown in the "Visualization" tab.
                *   Performance statistics (FPS, processing times) are available in the "Status" tab.

            6.  **Saving Results (Screenshots):**
                *   Screenshots of processed frames with detected faces are automatically saved in the `output/screenshots/` directory. These are timestamped for easy reference.

            For technical support, to report issues, or for more advanced configurations, please check the application's log file (`gradio_app.log`) or consult the project's repository documentation.
            """)
        
        # Event handlers for video tab
            
            # Connect reset statistics button for video tab
            reset_stats_btn_video.click(
                reset_stats,
                outputs=[stats_html_video],
                queue=False
            )
            
            # Connect reload gallery button for video tab
            reload_gallery_btn_video.click(
                reload_gallery_action,
                outputs=[gallery_status_video, reload_gallery_btn_video],
                queue=True # Use queue for generator
            )

        def update_video_slider(video_name, current_state):
            """Update slider when video changes. Also clears outputs if video is invalid."""
            logger.info(f"update_video_slider called with video_name: {video_name}")
            
            # Default state to reset to on failure
            reset_s = {
                "playing": False,
                "current_frame": 0,
                "total_frames": 0,
                "input_mode": "video",
            }

            if not video_name or video_name not in video_files or not os.path.exists(video_files.get(video_name, "")):
                status_message = "No video selected or video file not found."
                if video_name and (video_name not in video_files or not os.path.exists(video_files.get(video_name, ""))):
                    status_message = f"Video file '{video_name}' not found. Please check file path or select a valid video."
                    gr.Warning(status_message)
                
                logger.info(f"Invalid video selection: {video_name}. Resetting UI.")
                # Outputs: frame_slider, video_status, state, video_player_image, plot_output
                return (
                    gr.update(maximum=0, value=0, interactive=False), 
                    status_message, 
                    reset_s,
                    None, # Clear video_player_image
                    None  # Clear plot_output
                )
            
            video_path = video_files[video_name]
            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    cap.release()
                    error_msg = f"Failed to open video: {video_name}. It might be corrupted or an unsupported format."
                    gr.Error(error_msg)
                    logger.error(error_msg)
                    return (
                        gr.update(maximum=0, value=0, interactive=False), 
                        error_msg, 
                        reset_s,
                        None, 
                        None
                    )

                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                
                if total_frames == 0:
                    error_msg = f"Video '{video_name}' has 0 frames or could not be read properly."
                    gr.Warning(error_msg)
                    logger.warning(error_msg)
                    return (
                        gr.update(maximum=0, value=0, interactive=False),
                        error_msg,
                        reset_s,
                        None,
                        None
                    )

                logger.info(f"Successfully loaded video '{video_name}' with {total_frames} frames.")
                success_s = {
                    "playing": False,
                    "current_frame": 0, # Will be processed by initial_video_load
                    "total_frames": total_frames,
                    "input_mode": "video",
                }
                return (
                    gr.update(maximum=total_frames - 1, value=0, interactive=True), 
                    f"Video '{video_name}' loaded ({total_frames} frames). Processing initial frame...",
                    success_s,
                    None, # video_player_image will be updated by initial_video_load
                    None  # plot_output will be updated by initial_video_load
                )

            except Exception as e:
                error_msg = f"Critical error loading video '{video_name}': {str(e)}"
                logger.error(error_msg, exc_info=True)
                gr.Error(error_msg)
                return (
                    gr.update(maximum=0, value=0, interactive=False), 
                    error_msg, 
                    reset_s,
                    None, 
                    None
                )

        def initial_video_load(video_name, current_state, threshold, vis_type, tracking, max_match):
            """Loads the initial frame (frame 0) of the selected video AFTER update_video_slider."""
            logger.info(f"initial_video_load called for video: {video_name}, current_state total_frames: {current_state.get('total_frames')}")

            if not video_name or video_name not in video_files or current_state.get("total_frames", 0) == 0:
                logger.warning(f"initial_video_load: Skipping frame processing for '{video_name}' due to invalid state or zero total frames.")
                # Outputs: video_player_image, plot_output, video_status, stats_html_video, frame_slider (no change needed), state (no change needed)
                return None, None, "No valid video loaded to process initial frame.", format_stats_for_display(), gr.update(), current_state

            video_path = video_files[video_name]
            logger.info(f"initial_video_load: Processing frame 0 for {video_path}")
            
            try:
                processed_frame, plot, stats_text = process_video_frame(
                    video_path, 0, threshold, vis_type, tracking, max_match
                )
                # Update state's current_frame, though it should be 0 from update_video_slider's success path
                updated_s = {**current_state, "current_frame": 0} 
                logger.info(f"initial_video_load: Successfully processed frame 0 for {video_name}")
                return processed_frame, plot, f"Displaying frame 0 of {video_name}.", stats_text, gr.update(value=0), updated_s
            except Exception as e:
                error_message = f"Error processing initial frame of '{video_name}': {str(e)}"
                logger.error(error_message, exc_info=True)
                gr.Error(error_message)
                return None, plot_bar([("Load Error", 0.0)]), error_message, format_stats_for_display(), gr.update(value=0, interactive=False), current_state

        def update_video_frame_on_slider_release(video_name, frame_idx, threshold, vis_type, tracking, max_match, current_state):
            """Update frame when slider is released."""
            logger.info(f"update_video_frame_on_slider_release for video: {video_name}, frame: {frame_idx}")
            if not video_name or video_name not in video_files or current_state.get("total_frames", 0) == 0:
                logger.warning("Slider released but no valid video loaded or video is empty.")
                # Outputs: video_player_image, plot_output, video_status, stats_html_video, state
                return None, None, "Cannot process frame: No valid video selected or video is empty.", format_stats_for_display(), current_state
            
            video_path = video_files[video_name]
            try:
                processed_frame, plot, stats_text = process_video_frame(
                    video_path, frame_idx, threshold, vis_type, tracking, max_match
                )
                updated_s = {**current_state, "current_frame": frame_idx}
                return processed_frame, plot, f"Displaying frame {frame_idx} of {video_name}.", stats_text, updated_s
            except Exception as e:
                error_message = f"Failed to update video frame (slider release): {str(e)}"
                logger.error(error_message, exc_info=True)
                gr.Error(error_message)
                # Outputs: video_player_image, plot_output, video_status, stats_html_video, state
                return None, plot_bar([("Frame Error", 0.0)]), error_message, format_stats_for_display(), current_state
        
        def _update_video_frame_on_setting_change(video_name, frame_idx, threshold, vis_type, tracking, max_match, current_state):
            """Dedicated handler for settings changes, re-processes current frame."""
            logger.info(f"Settings changed. Re-processing frame {frame_idx} for video {video_name}.")
            if not video_name or video_name not in video_files or current_state.get("total_frames", 0) == 0:
                logger.warning("Setting changed but no valid video loaded. Cannot re-process.")
                # Outputs: video_player_image, plot_output, video_status, stats_html_video
                return None, None, "Cannot re-process: No valid video loaded.", format_stats_for_display()

            video_path = video_files[video_name]
            try:
                # Re-use the core processing logic
                processed_frame, plot, stats_text = process_video_frame(
                    video_path, frame_idx, threshold, vis_type, tracking, max_match
                )
                # Note: We don't update state's current_frame here as it's already the correct one.
                return processed_frame, plot, f"Re-processed frame {frame_idx} of {video_name} with new settings.", stats_text
            except Exception as e:
                error_message = f"Failed to re-process frame on setting change: {str(e)}"
                logger.error(error_message, exc_info=True)
                gr.Error(error_message)
                # Outputs: video_player_image, plot_output, video_status, stats_html_video
                return None, plot_bar([("Settings Error", 0.0)]), error_message, format_stats_for_display()

        # Event handlers for frame slider and video settings
        frame_slider.release(  # Changed from .change to .release
            update_video_frame_on_slider_release,
            inputs=[
                video_dropdown,
                frame_slider,
                similarity_threshold_video,
                visualization_type_video,
                use_tracking_video,
                max_matches_video,
                state # Pass current state
            ],
            outputs=[video_player_image, plot_output, video_status, stats_html_video, state], # state is an output
            queue=True
        )
        
        settings_inputs_video = [
            video_dropdown,
            frame_slider, # Current frame index
            similarity_threshold_video,
            visualization_type_video,
            use_tracking_video,
            max_matches_video,
            state # Pass current state
        ]
        
        for setting_component in [similarity_threshold_video, use_tracking_video, max_matches_video, visualization_type_video]:
            setting_component.change(
                _update_video_frame_on_setting_change,
                inputs=settings_inputs_video,
                outputs=[video_player_image, plot_output, video_status, stats_html_video], # No state output here
                queue=True 
            )

        # Function to handle webcam input
        def process_webcam_input_stream(frame, threshold, vis_type, tracking, max_match):
            """Process webcam stream."""
            global DETECTOR, RECOGNIZER # Added to check model status
            if frame is None:
                return None, None, format_stats_for_display()

            # Feedback for model initialization
            if DETECTOR is None or RECOGNIZER is None:
                gr.Info("Initializing models for webcam, please wait...")
            
            try:
                processed_frame, plot, stats_text = process_webcam_frame(
                    frame,
                    threshold,
                    vis_type,
                    tracking,
                    max_match,
                )
                return processed_frame, plot, stats_text
            except Exception as e:
                error_message = f"Error processing webcam stream: {str(e)}"
                logger.error(error_message)
                logger.error(traceback.format_exc())
                gr.Error(error_message) # Show error in Gradio UI

                # Create error frame
                current_frame_for_error = frame.copy() if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    current_frame_for_error,
                    f"Stream Error: {str(e)}", # More specific message
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255), # Red color
                    2
                )
                # Create error plot
                fig = plot_bar([("Webcam Stream Error", 0.0)]) # More specific title
                return current_frame_for_error, fig, format_stats_for_display()

        # Event handlers for webcam tab
        webcam_input.stream(
            process_webcam_input_stream,
            inputs=[
                webcam_input,
                similarity_threshold_webcam,
                visualization_type_webcam,
                use_tracking_webcam,
                max_matches_webcam,
            ],
            outputs=[webcam_output, webcam_plot, stats_html_webcam],
            show_progress="hidden",
        )

        # Connect reset statistics button for webcam tab
        reset_stats_btn_webcam.click(
            reset_stats,
            outputs=[stats_html_webcam],
            queue=False
        )
            
        # Connect reload gallery button for webcam tab
        reload_gallery_btn_webcam.click(
                reload_gallery_action, # Use the same action function
                outputs=[gallery_status_webcam, reload_gallery_btn_webcam],
                queue=True # Use queue for generator
        )
        
        # Video playback logic (play, pause, next, prev)
        # ... (This part needs to be carefully reviewed and updated if necessary)
        
        # Update video dropdown:
        # 1. Calls update_video_slider to set up slider, state, and clear outputs if invalid.
        # 2. Then calls initial_video_load to process and display the first frame if valid.
        video_dropdown.change(
            update_video_slider,
            inputs=[video_dropdown, state], # Pass state
            outputs=[frame_slider, video_status, state, video_player_image, plot_output], # Ensure all outputs are covered
            queue=True
        ).then(
            initial_video_load, # This is called after update_video_slider completes
            inputs=[
                video_dropdown, 
                state, # Pass the updated state from update_video_slider
                similarity_threshold_video, 
                visualization_type_video, 
                use_tracking_video, 
                max_matches_video
            ],
            outputs=[ # Outputs for initial_video_load
                video_player_image, 
                plot_output, 
                video_status, 
                stats_html_video,
                frame_slider, # initial_video_load can update slider (e.g. value, interactive)
                state         # initial_video_load can update state
            ],
            queue=True
        )
        
        # REMOVE app.load as per instructions, initial load handled by video_dropdown.change().then()
        # app.load(
        # initial_video_load,
        # inputs=[
        # video_dropdown, # Uses the default selected video
        # similarity_threshold_video,
        # visualization_type_video,
        # use_tracking_video,
        # max_matches_video,
        # ],
        # outputs=[
        # video_player_image, 
        # plot_output, 
        # video_status, 
        # stats_html_video,
        # frame_slider, # Update slider value
        # frame_slider, # Update slider maximum (this is a bit of a hack, ideally one output for max)
        # ]
        # )

        # Video Playback Control Logic
        # Play button
        play_btn.click(
            lambda current_state: {"playing": True, "input_mode": "video", **current_state},
            inputs=[state],
            outputs=[state],
            queue=False
        ).then(
            video_play_loop,
            inputs=[
                video_dropdown,
                gr.State(video_files), # Pass video_files as a state
                frame_slider,
                similarity_threshold_video,
                visualization_type_video,
                use_tracking_video,
                max_matches_video,
                state
            ],
            outputs=[
                video_player_image,
                plot_output,
                frame_slider,
                stats_html_video,
                video_status,
                state, # Update playing status
                gr.Number(label="Current Frame", interactive=False), # For display
                gr.Number(label="Total Frames", interactive=False)  # For display
            ],
            show_progress="hidden"
        )

        # Pause button
        pause_btn.click(
            lambda current_state: {"playing": False, **current_state},
            inputs=[state],
            outputs=[state],
            queue=False
        )

        # Previous Frame button
        def go_to_prev_frame(current_frame_idx, video_name, threshold, vis_type, tracking, max_match):
            new_frame_idx = max(0, current_frame_idx - 1)
            frame, plot, status, stats = update_video_frame(video_name, new_frame_idx, threshold, vis_type, tracking, max_match)
            return frame, plot, new_frame_idx, status, stats

        prev_frame_btn.click(
            go_to_prev_frame,
            inputs=[
                frame_slider,
                video_dropdown,
                similarity_threshold_video,
                visualization_type_video,
                use_tracking_video,
                max_matches_video,
            ],
            outputs=[video_player_image, plot_output, frame_slider, video_status, stats_html_video],
            queue=True
        )

        # Next Frame button
        def go_to_next_frame(current_frame_idx, total_frames, video_name, threshold, vis_type, tracking, max_match):
            # total_frames comes from state.total_frames, need to ensure it's up-to-date
            new_frame_idx = min(total_frames - 1 if total_frames > 0 else 0, current_frame_idx + 1)
            frame, plot, status, stats = update_video_frame(video_name, new_frame_idx, threshold, vis_type, tracking, max_match)
            return frame, plot, new_frame_idx, status, stats

        next_frame_btn.click(
            lambda current_frame_idx, current_state, video_name, threshold, vis_type, tracking, max_match: \
                go_to_next_frame(current_frame_idx, current_state.get("total_frames", 0), video_name, threshold, vis_type, tracking, max_match),
            inputs=[
                frame_slider,
                state, # Pass the whole state to get total_frames
                video_dropdown,
                similarity_threshold_video,
                visualization_type_video,
                use_tracking_video,
                max_matches_video,
            ],
            outputs=[video_player_image, plot_output, frame_slider, video_status, stats_html_video],
            queue=True
        )

        # Handle tab changes to set input mode in state
        def on_tab_select(selected_tab: gr.SelectData, current_state: dict):
            if selected_tab.index == 0: # Video tab
                current_state["input_mode"] = "video"
            elif selected_tab.index == 1: # Webcam tab
                current_state["input_mode"] = "webcam"
                # Reset stats when switching to webcam tab for a fresh view
                reset_stats() 
                return current_state, format_stats_for_display() # Also update webcam stats display
            return current_state, gr.update() # No change to stats display for video tab

        tabs.select(
            on_tab_select,
            inputs=[state],
            outputs=[state, stats_html_webcam], # Update webcam stats on tab change
            queue=False
        )
        
        # Load initial frame for the default video when the app loads
        # This uses the `load` event of the Blocks object
        app.load(
            initial_video_load,
            inputs=[
                video_dropdown, # Uses the default selected video
                similarity_threshold_video,
                visualization_type_video,
                use_tracking_video,
                max_matches_video,
            ],
            outputs=[
                video_player_image, 
                plot_output, 
                video_status, 
                stats_html_video,
                frame_slider, # Update slider value
                frame_slider, # Update slider maximum (this is a bit of a hack, ideally one output for max)
            ]
        )

    return app


if __name__ == "__main__":
    # Initialize models globally (optional, can be done on first frame too)
    # DETECTOR, RECOGNIZER = initialize_models()
    # GALLERY_EMBEDDINGS, GALLERY_NAMES = load_gallery_embeddings(RECOGNIZER)
    
    app_instance = create_interface()
    app_instance.queue(max_size=20).launch(share=True, debug=True)
    logger.info("Gradio app launched.")

