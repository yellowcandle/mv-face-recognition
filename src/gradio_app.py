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
        raise RuntimeError(f"Failed to initialize models: {str(e)}")


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
        logger.error(f"Error loading gallery embeddings: {str(e)}")
        logger.error(traceback.format_exc())
        return {}, {}


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
        fig = plot_bar([("Error", 0.0)])
        
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
            DETECTOR, RECOGNIZER = initialize_models(
                similarity_threshold=similarity_threshold,
                use_tracking=use_tracking,
            )
            GALLERY_EMBEDDINGS, GALLERY_NAMES = load_gallery_embeddings(RECOGNIZER)
        
        # Check if video path exists
        if not os.path.exists(video_path):
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                error_frame,
                f"Video file not found: {os.path.basename(video_path)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2
            )
            fig = plot_bar([("Error", 0.0)])
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
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                error_frame,
                f"Could not read frame {frame_idx} from {os.path.basename(video_path)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2
            )
            fig = plot_bar([("Error", 0.0)])
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
        logger.error(f"Error processing video frame: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Create error frame
        error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
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
            error_msg = f"Video file not found: {video_name}"
            logger.error(error_msg)
            
            # Yield error message
            yield (
                None,  # frame
                None,  # plot
                start_frame,  # slider
                format_stats_for_display(),  # stats
                error_msg,  # status
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
                fig = plot_bar([("Error", 0.0)])
                
                # Yield error
                yield (
                    error_img,  # frame
                    fig,  # plot
                    frame_idx,  # slider
                    format_stats_for_display(),  # stats
                    f"Error processing frame {frame_idx}: {str(e)}",  # status
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
            f"Error: {str(e)}",  # status
            False,  # playing
            start_frame,  # current frame
            0,  # total frames
        )


def reload_gallery() -> Tuple[str, Dict[str, Any]]:
    """
    Reload gallery embeddings.
    
    Returns:
        Tuple of status message and updated state
    """
    global DETECTOR, RECOGNIZER, GALLERY_EMBEDDINGS, GALLERY_NAMES
    
    try:
        if RECOGNIZER:
            GALLERY_EMBEDDINGS, GALLERY_NAMES = load_gallery_embeddings(RECOGNIZER)
            
            # Count embeddings
            total_embeddings = sum(len(embs) for embs in GALLERY_EMBEDDINGS.values())
            total_people = len(GALLERY_EMBEDDINGS)
            
            if total_embeddings > 0:
                return f"Successfully loaded {total_embeddings} embeddings for {total_people} people", {}
            else:
                return "No gallery embeddings found. Please add faces to source/photo/contestants/", {}
        else:
            return "Models not initialized yet. Add a frame to initialize.", {}
            
    except Exception as e:
        logger.error(f"Error reloading gallery: {str(e)}")
        return f"Error reloading gallery: {str(e)}", {}


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
                        
                        with gr.Tab("Status"):
                            stats_html = gr.HTML(value=format_stats_for_display(), label="Performance Stats")
                            reset_stats_btn = gr.Button("Reset Statistics")
                            reload_gallery_btn = gr.Button("Reload Gallery")
                            gallery_status = gr.Markdown("Gallery not loaded yet")
            
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
                            with gr.Group():
                                gr.Markdown("### Recognition Settings")
                                webcam_threshold = gr.Slider(
                                    minimum=0.3,
                                    maximum=0.9,
                                    value=0.6,
                                    step=0.05,
                                    label="Similarity Threshold",
                                    info="Lower values match more faces but may have false positives",
                                )
                                webcam_tracking = gr.Checkbox(
                                    value=True,
                                    label="Use Face Tracking",
                                    info="Improves performance by tracking faces between frames",
                                )
                                webcam_max_matches = gr.Slider(
                                    minimum=1,
                                    maximum=10,
                                    value=3,
                                    step=1,
                                    label="Max Matches Per Face",
                                    info="Maximum number of matches to show for each face",
                                )
                                webcam_visualization = gr.Radio(
                                    choices=["bar", "scatter"],
                                    value="bar",
                                    label="Visualization Type",
                                    info="Bar chart or embedding scatter plot",
                                )
                        
                        with gr.Tab("Status"):
                            webcam_stats = gr.HTML(value=format_stats_for_display(), label="Performance Stats")
                            webcam_reset_btn = gr.Button("Reset Statistics")
                            webcam_reload_btn = gr.Button("Reload Gallery")
                            webcam_status = gr.Markdown("Ready to process webcam feed")
        
        # Help tab
        with gr.Row():
            gr.Markdown("""
            ### Instructions
            1. **Video Analysis:** Upload MP4 files to `source/videos/` directory
            2. **Add People:** Add face images to `source/photo/contestants/` directory
            3. **Recognition Settings:** Adjust threshold and tracking for optimal performance
            4. **Save Results:** Screenshots will be automatically saved in the `output` directory
            
            For technical support or issues, check the log file or repository documentation.
            """)
        
        # Event handlers for video tab
        def update_video_slider(video_name):
            """Update slider when video changes."""
            if not video_name or video_name not in video_files:
                return gr.update(maximum=100, value=0), "No video selected", {
                    "playing": False,
                    "current_frame": 0,
                    "total_frames": 0,
                    "input_mode": "video",
                }
            
            video_path = video_files[video_name]
            try:
                cap = cv2.VideoCapture(video_path)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                
                return gr.update(maximum=total_frames-1, value=0), f"Loaded {video_name} ({total_frames} frames)", {
                    "playing": False,
                    "current_frame": 0,
                    "total_frames": total_frames,
                    "input_mode": "video",
                }
            except Exception as e:
                logger.error(f"Error loading video: {str(e)}")
                return gr.update(maximum=100, value=0), f"Error loading video: {str(e)}", initial_state
        
        def update_video_frame(video_name, frame_idx, threshold, vis_type, tracking, max_match):
            """Update frame when slider changes."""
            if not video_name or video_name not in video_files:
                return None, None, "No video selected", {}
            
            video_path = video_files[video_name]
            try:
                # Process the video frame
                frame, plot, stats = process_video_frame(
                    video_path,
                    frame_idx,
                    threshold,
                    vis_type,
                    tracking,
                    max_match,
                )
                
                return frame, plot, f"Showing frame {frame_idx}", stats
            except Exception as e:
                logger.error(f"Error updating frame: {str(e)}")
                return None, None, f"Error: {str(e)}", format_stats_for_display()
        
        # Function to handle webcam input
        def process_webcam_

