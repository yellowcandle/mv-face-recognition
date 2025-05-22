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
import umap.umap_ as umap
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.colors import hsv_to_rgb
from insightface.app import (
    FaceAnalysis,
)  # Using InsightFace for detection and embedding computation
from PIL import Image, ImageDraw, ImageFont  # For drawing text on images

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

# Import custom visualization modules (assuming these exist and are compatible)
try:
    from src.utils.gradio_visualization import (
        draw_faces_with_labels,
        plot_bar,
        plot_embedding_scatter,
    )
except ImportError:
    logger.warning("Could not import gradio_visualization. Using placeholder functions.")

    def plot_bar(matches: List[Tuple[str, float]], max_items: int = 10) -> Figure:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Placeholder - no gradio_visualization", ha='center', va='center')
        return fig

    def plot_embedding_scatter(
        detected_embeddings: List[np.ndarray],
        gallery_embeddings: Dict[str, List[np.ndarray]],
        gallery_names: Dict[str, str],
        matches: List[List[Tuple[str, float, int]]],
        dim_reduction: str = "pca"
    ) -> Figure:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Placeholder - no gradio_visualization", ha='center', va='center')
        return fig

    def draw_faces_with_labels(
        image: np.ndarray,
        faces: List[Dict[str, Any]],
        box_thickness: int = 2,
        font_scale: float = 0.7,
        include_score: bool = True
    ) -> np.ndarray:
        return image


# Global variables
try:
    _APP = FaceAnalysis(providers=["CPUExecutionProvider"])
    _APP.prepare(ctx_id=0, det_size=(640, 640))
    logger.info("InsightFace app initialized.")
except Exception as e:
    logger.error("Error initializing InsightFace app: %s", e)
    _APP = None

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")
fonts_dir = os.path.join(project_root, "fonts")

try:
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info["暱稱"].tolist()
    logger.info("Loaded contestant info from %s", contestant_info_path)
except FileNotFoundError:
    all_contestants = []
    logger.error("Error: %s not found.", contestant_info_path)


def get_video_files(video_dir: str = videos_dir) -> Dict[str, str]:
    """
    Retrieves a dictionary of video files from the specified directory.

    Args:
        video_dir (str): The directory to search for video files.

    Returns:
        Dict[str, str]: A dictionary where keys are video filenames and values are their
                        absolute paths. If no videos are found, a message is returned.
    """
    os.makedirs(video_dir, exist_ok=True)
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    video_files = {}
    for file in os.listdir(video_dir):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            file_path = os.path.join(video_dir, file)
            video_files[file] = file_path
    if not video_files:
        logger.warning("No video files found in %s", video_dir)
        video_files["No videos found - please add videos to source/videos/"] = ""
    return video_files


video_files = get_video_files()

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


def get_image_paths_mv(contestant_path):
    """
    Retrieves a list of image paths for a given contestant.

    Args:
        contestant_path (str): The path to the contestant's directory.

    Returns:
        List[str]: A list of absolute paths to image files.
    """
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith((".jpg", ".png"))
    ]


def compute_embeddings_mv(image_paths):
    """
    Computes face embeddings for a list of image paths using InsightFace.

    Args:
        image_paths (List[str]): A list of paths to image files.

    Returns:
        List[np.ndarray]: A list of computed face embeddings.
    """
    embeddings = []
    if _APP is None:
        logger.error("InsightFace app not initialized. Cannot compute embeddings.")
        return embeddings
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is None:
                logger.warning("Failed to read image: %s", img_path)
                continue
            faces = _APP.get(img)
            embeddings.extend([face.normed_embedding for face in faces])
        except Exception as e:
            logger.error("Error processing %s: %s", img_path, e)
    return embeddings


def get_known_faces_embeddings_mv(
    input_contestants_dir, selected_contestants, input_contestant_info
):
    """
    Loads or computes face embeddings for known contestants.
    Automatically regenerates cached embeddings if their shape does not match the current model.

    Args:
        input_contestants_dir (str): Directory containing contestant photos.
        selected_contestants (List[str]): List of contestant names to process.
        input_contestant_info (pd.DataFrame): DataFrame with contestant information.

    Returns:
        Dict[str, List[np.ndarray]]: A dictionary mapping contestant names to their embeddings.
    """
    known_embeddings = {}
    if input_contestant_info.empty:
        logger.warning("Contestant info is empty. Cannot load embeddings.")
        return known_embeddings

    # Determine the current model's embedding shape
    current_embedding_shape = None
    if _APP is not None:
        # Try to get a dummy embedding from a black image
        dummy_img = np.zeros((112, 112, 3), dtype=np.uint8)
        faces = _APP.get(dummy_img)
        if faces and hasattr(faces[0], "normed_embedding"):
            emb = faces[0].normed_embedding
            if hasattr(emb, "shape"):
                current_embedding_shape = emb.shape
    if current_embedding_shape is None:
        # Fallback: try to get from any existing embedding
        current_embedding_shape = (512,)

    for contestant_name in selected_contestants:
        if contestant_name not in input_contestant_info["暱稱"].values:
            logger.warning(
                "Warning: Contestant '%s' not found in contestant info. Skipping.",
                contestant_name,
            )
            continue

        contestant_row = input_contestant_info.loc[input_contestant_info["暱稱"] == contestant_name]
        if contestant_row.empty:
            logger.warning(
                "Could not find row for contestant '%s' in info file. Skipping.",
                contestant_name,
            )
            continue

        contestant_number = contestant_row["編號"].values[0]
        contestant_path = os.path.join(input_contestants_dir, str(contestant_number))

        if not os.path.isdir(contestant_path):
            logger.warning(
                "Warning: Directory for contestant '%s' not found: %s. Skipping.",
                contestant_name,
                contestant_path,
            )
            continue

        embedding_file = os.path.join(contestant_path, f"{contestant_name}_embedding.npy")
        need_regen = False
        if os.path.exists(embedding_file):
            try:
                embedding = np.load(embedding_file, allow_pickle=True)
                # If not a list, wrap in list for consistency
                if not isinstance(embedding, list):
                    embedding = [embedding]
                # Check shape of first embedding
                if embedding and hasattr(embedding[0], "shape"):
                    emb_shape = embedding[0].shape
                    if emb_shape != current_embedding_shape:
                        logger.warning(
                            f"Embedding shape mismatch for {contestant_name}: cached {emb_shape}, expected {current_embedding_shape}. Regenerating."
                        )
                        os.remove(embedding_file)
                        need_regen = True
                    else:
                        known_embeddings[contestant_name] = embedding
                        logger.info("Loaded cached embedding for %s.", contestant_name)
                        continue
                else:
                    logger.warning(
                        f"Embedding for {contestant_name} is empty or malformed. Regenerating."
                    )
                    os.remove(embedding_file)
                    need_regen = True
            except Exception as e:
                logger.error(
                    "Error loading cached embedding for %s: %s. Recomputing.", contestant_name, e
                )
                if os.path.exists(embedding_file):
                    os.remove(embedding_file)
                need_regen = True
        else:
            need_regen = True

        if need_regen:
            image_paths = get_image_paths_mv(contestant_path)
            embeddings = compute_embeddings_mv(image_paths)
            if embeddings:
                known_embeddings[contestant_name] = embeddings
                try:
                    np.save(embedding_file, embeddings)
                    logger.info("Computed and saved embedding for %s.", contestant_name)
                except Exception as e:
                    logger.error("Error saving embedding for %s: %s", contestant_name, e)
            else:
                logger.warning(
                    "Could not compute embedding for %s from images in %s",
                    contestant_name,
                    contestant_path,
                )

    return known_embeddings


def match_face_mv(face_embedding, known_embeddings, distance_threshold):
    """
    Matches a given face embedding against a dictionary of known embeddings.

    Args:
        face_embedding (np.ndarray): The embedding of the face to match.
        known_embeddings (Dict[str, List[np.ndarray]]): Dictionary of known embeddings.
        distance_threshold (float): The minimum similarity score for a match.

    Returns:
        Tuple[Optional[str], float]: The name of the best matching contestant and the
                                     similarity score, or (None, 0.0) if no match.
    """
    best_match = None
    best_score = -1

    if not known_embeddings:
        return None, 0.0

    for name, embeddings_list in known_embeddings.items():
        for known_embedding_item in embeddings_list:
            if not isinstance(known_embedding_item, np.ndarray) or known_embedding_item.size == 0:
                continue

            # Ensure face_embedding is 1D and float32
            current_face_embedding = face_embedding.flatten().astype(np.float32)
            
            # Ensure known_embedding_item is 1D and float32
            current_known_embedding = known_embedding_item.flatten().astype(np.float32)

            if current_known_embedding.shape != current_face_embedding.shape:
                logger.warning(f"Skipping comparison - embedding dimension mismatch after flatten: {current_known_embedding.shape} vs {current_face_embedding.shape} for {name}")
                continue
                
            norm_face = np.linalg.norm(current_face_embedding)
            norm_known = np.linalg.norm(current_known_embedding)
            if norm_face > 1e-10 and norm_known > 1e-10:
                similarity = np.dot(current_face_embedding, current_known_embedding) / (norm_face * norm_known)
            else:
                similarity = 0.0
            if similarity > distance_threshold and similarity > best_score:
                best_match = name
                best_score = similarity

    return best_match, best_score


def draw_boxes_and_labels_mv(frame, matches, timestamp):
    """
    Draws bounding boxes, labels, and a timestamp on the given frame.

    Args:
        frame (np.ndarray): The image frame to draw on.
        matches (List[Tuple[Any, str, float]]): A list of tuples, each containing
                                                 (face_object, name, confidence).
        timestamp (str): The timestamp to display on the frame.

    Returns:
        np.ndarray: The frame with drawn boxes, labels, and timestamp.
    """
    try:
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        font_path = os.path.join(fonts_dir, "SourceHanSansTC-VF.ttf")
        font_missing = False
        if not os.path.exists(font_path):
            logger.warning("Font file not found: %s. Using default font.", font_path)
            label_font = ImageFont.load_default()
            timestamp_font = ImageFont.load_default()
            font_missing = True
        else:
            try:
                label_font = ImageFont.truetype(font_path, 60)
                timestamp_font = ImageFont.truetype(font_path, 40)
            except Exception as e:
                logger.error("Error loading font: %s. Using default font.", e)
                label_font = ImageFont.load_default()
                timestamp_font = ImageFont.load_default()
                font_missing = True
        for face, name, confidence in matches:
            bbox = face.bbox.astype(int)
            padding = 10
            bbox_enlarged = [
                max(0, bbox[0] - padding),
                max(0, bbox[1] - padding),
                min(frame.shape[1], bbox[2] + padding),
                min(frame.shape[0], bbox[3] + padding),
            ]
            draw.rectangle(bbox_enlarged, outline="green", width=3)
            label_text = f"{name} ({confidence:.2f})"
            text_x = bbox_enlarged[0]
            text_y = max(0, bbox_enlarged[1] - 65)
            text_bbox = draw.textbbox((text_x, text_y), label_text, font=label_font)
            draw.rectangle(text_bbox, fill="green")
            draw.text(
                (text_x, text_y),
                label_text,
                font=label_font,
                fill="white",
            )

        # Overlay a visible warning if the font is missing (CJKV will not render)
        if font_missing:
            warning_text = "⚠️ CJKV font missing! CJKV chars will not render."
            w, h = draw.textsize(warning_text, font=ImageFont.load_default())
            draw.rectangle([(0, 0), (w + 20, h + 20)], fill="red")
            draw.text((10, 10), warning_text, fill="white", font=ImageFont.load_default())
        timestamp_color = "yellow"
        img_width, img_height = pil_img.size
        timestamp_text = f"Frame: {timestamp}"
        text_bbox = draw.textbbox((0, 0), timestamp_text, font=timestamp_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        position = (img_width - text_width - 10, img_height - text_height - 10)
        draw.text(position, timestamp_text, font=timestamp_font, fill=timestamp_color)
        # Return BGR image for Gradio (to test if Gradio expects BGR)
        frame = np.array(pil_img)
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame_bgr
    except Exception as e:
        logger.error("Error drawing boxes and labels: %s", e)
        logger.error(traceback.format_exc())
        return frame


def format_stats_for_display() -> str:
    """
    Formats the processing statistics into an HTML string for display.

    Returns:
        str: An HTML string containing the formatted statistics.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = PROCESSING_STATS.copy()
    html = """
    <div style="font-family: sans-serif; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
        <h3 style="margin-top: 0;">Performance Statistics</h3>
        <table style="width: 100%; border-collapse: collapse;">
    """
    metrics = [
        ("Processed Frames", f"{stats['processed_frames']}", None),
        (
            "FPS",
            f"{stats.get('fps', 0):.2f}",
            "red" if stats.get("fps", 0) < 5 else "orange" if stats.get("fps", 0) < 15 else "green",
        ),
        (
            "Detection Time",
            f"{stats.get('avg_detection_time', 0):.1f} ms",
            "red"
            if stats.get("avg_detection_time", 0) > 100
            else "orange"
            if stats.get("avg_detection_time", 0) > 50
            else "green",
        ),
        (
            "Recognition Time",
            f"{stats.get('avg_recognition_time', 0):.1f} ms",
            "red"
            if stats.get("avg_recognition_time", 0) > 100
            else "orange"
            if stats.get("avg_recognition_time", 0) > 50
            else "green",
        ),
        (
            "Total Processing Time",
            f"{stats.get('avg_total_time', 0):.1f} ms",
            "red"
            if stats.get("avg_total_time", 0) > 200
            else "orange"
            if stats.get("avg_total_time", 0) > 100
            else "green",
        ),
        ("Faces Detected", f"{stats['faces_detected']}", None),
        ("Faces Recognized", f"{stats['faces_recognized']}", None),
        (
            "Recognition Rate",
            f"{stats.get('recognition_rate', 0):.1%}",
            "red"
            if stats.get("recognition_rate", 0) < 0.3
            else "orange"
            if stats.get("recognition_rate", 0) < 0.7
            else "green",
        ),
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
    html += f"""
        </table>
        <p style="font-size: 0.9em; text-align: right; color: #555;">Last updated: {now}</p>
    </div>
    """
    return html


def reset_stats() -> str:
    """
    Resets the processing statistics.

    Returns:
        str: An HTML string with the reset and formatted statistics.
    """
    with STATUS_LOCK:
        for key in PROCESSING_STATS:
            if key != "start_time":
                PROCESSING_STATS[key] = 0
        PROCESSING_STATS["start_time"] = time.time()
    return format_stats_for_display()

# Video processing and UI functions
def get_video_frame(video_path: str, frame_num: int) -> np.ndarray:
    """Extract a specific frame from a video file."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Could not read frame {frame_num} from {video_path}")
    return frame

def process_frame(frame: np.ndarray, **kwargs) -> Tuple[np.ndarray, List[np.ndarray], List[str]]:
    """Process a single frame for face recognition."""
    if _APP is None:
        raise RuntimeError("InsightFace app not initialized")

    det_threshold = kwargs.get("det_threshold", 0.5) 
    rec_threshold = kwargs.get("rec_threshold", 0.5)

    all_faces = _APP.get(frame)
    
    # Filter faces based on detection score (det_threshold)
    faces = [face for face in all_faces if face.det_score >= det_threshold]
    
    embeddings = []
    names = []
    
    # Make a copy of the frame to draw on, to avoid modifying the input frame directly
    # if it's passed around elsewhere, though Gradio usually handles copies.
    # The frame returned by draw_boxes_and_labels_mv is already RGB.
    output_frame = frame.copy()

    for face in faces:
        embedding = face.normed_embedding
        name, confidence = match_face_mv(embedding, GALLERY_EMBEDDINGS, rec_threshold)
        embeddings.append(embedding)
        names.append(f"{name} ({confidence:.2f})" if name else "Unknown")
        
        # Draw bounding boxes and labels on the output_frame
        output_frame = draw_boxes_and_labels_mv(output_frame, [(face, name or "Unknown", confidence)],
                                                datetime.now().strftime("%H:%M:%S"))
    
    return output_frame, embeddings, names

def generate_umap_plot(embeddings: List[np.ndarray], labels: List[str], gallery_embeddings: Dict[str, List[np.ndarray]], gallery_names: Dict[str, str]) -> Figure:
    """Generate UMAP plot of face embeddings, including all gallery embeddings."""
    # Combine gallery embeddings and current embeddings
    all_embeddings = []
    all_labels = []

    # Add gallery embeddings
    for name, emb_list in gallery_embeddings.items():
        for emb in emb_list:
            all_embeddings.append(emb)
            all_labels.append(gallery_names.get(name, name))

    # Add current detected embeddings
    all_embeddings.extend(embeddings)
    all_labels.extend(labels)

    if not all_embeddings:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No embeddings to visualize", ha='center', va='center')
        return fig

    # Check if we have enough embeddings for UMAP
    if len(all_embeddings) < 4:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, f"Not enough embeddings for UMAP visualization (found {len(all_embeddings)}, need at least 4)", 
                ha='center', va='center', wrap=True)
        return fig

    # n_neighbors must be less than the number of samples
    n_neighbors = min(15, len(all_embeddings) - 1)
    if len(all_embeddings) > 1 and n_neighbors < 2:
        n_neighbors = max(1, len(all_embeddings) - 1)
        if n_neighbors < 2 and len(all_embeddings) >= 2:
            n_neighbors = 1

    reducer = umap.UMAP(random_state=42, n_neighbors=n_neighbors, min_dist=0.1)
    raw_embeddings_2d = reducer.fit_transform(np.array(all_embeddings))

    # Ensure embeddings_2d is a dense numpy array for consistent indexing
    if hasattr(raw_embeddings_2d, "toarray"):
        embeddings_2d = raw_embeddings_2d.toarray()
    else:
        embeddings_2d = raw_embeddings_2d

    # Generate unique colors for each label
    unique_labels = list(set(all_labels))
    label_colors = {label: hsv_to_rgb([i/len(unique_labels), 0.9, 0.8]) 
                   for i, label in enumerate(unique_labels)}

    # Create scatter plot
    fig, ax = plt.subplots(figsize=(8, 6))
    for label in unique_labels:
        mask = np.array([l == label for l in all_labels])
        ax.scatter(embeddings_2d[mask, 0], embeddings_2d[mask, 1], 
                  color=label_colors[label], label=label, alpha=0.7)

    ax.set_title("Face Embedding Similarity (UMAP)")
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    return fig

def create_gradio_interface():
    """Create the Gradio interface for video frame analysis."""
    video_files = get_video_files()
    video_names = list(video_files.keys())
    
    with gr.Blocks(title="Face Recognition Explorer") as demo:
        gr.Markdown("# Face Recognition Explorer")
        gr.Markdown("Select a video and navigate frames to analyze face recognition results")
        
        with gr.Row():
            with gr.Column(scale=3):
                video_dropdown = gr.Dropdown(choices=video_names, label="Select Video")
                frame_slider = gr.Slider(minimum=0, maximum=100, value=0, step=1, label="Frame Number") # Corrected Slider init
                with gr.Row():
                    prev_btn = gr.Button("Previous Frame")
                    next_btn = gr.Button("Next Frame")
            with gr.Column(scale=1):
                det_thresh_slider = gr.Slider(0.1, 1.0, value=0.5, step=0.05, label="Detection Threshold")
                rec_thresh_slider = gr.Slider(0.1, 1.0, value=0.5, step=0.05, label="Recognition Threshold")

        with gr.Row():
            frame_output = gr.Image(label="Processed Frame")
            plot_output = gr.Plot(label="UMAP Embedding Visualization")
        
        # Store embeddings and labels across interactions
        all_embeddings = gr.State([])
        all_labels = gr.State([])
        
        def load_video(video_name):
            """Initialize when video is selected."""
            video_path = video_files[video_name]
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            return {
                frame_slider: gr.Slider(maximum=total_frames-1),
                all_embeddings: [],
                all_labels: []
            }
        
        def process_video_frame(video_name, frame_num, det_thresh, rec_thresh, embeddings, labels):
            """Process a frame and update visualizations."""
            if not video_name or video_name not in video_files or not video_files[video_name]:
                empty_fig, ax = plt.subplots()
                ax.text(0.5, 0.5, "Please select a valid video.", ha='center', va='center')
                # Ensure frame_output is cleared or shows a placeholder
                placeholder_img = np.zeros((480, 640, 3), dtype=np.uint8) # Black image
                draw = ImageDraw.Draw(Image.fromarray(placeholder_img))
                try:
                    font = ImageFont.truetype(os.path.join(fonts_dir, "SourceHanSansTC-VF.ttf"), 20)
                except IOError:
                    font = ImageFont.load_default()
                draw.text((50, 230), "Please select a video", font=font, fill=(255,255,255))

                return {
                    frame_output: np.array(placeholder_img),
                    plot_output: empty_fig,
                    all_embeddings: [],
                    all_labels: []
                }

            video_path = video_files[video_name]
            try:
                frame_cv = get_video_frame(video_path, frame_num)
            except ValueError as e:
                logger.error(f"Error getting video frame: {e}")
                empty_fig, ax = plt.subplots()
                ax.text(0.5, 0.5, f"Error: Could not load frame {frame_num}.", ha='center', va='center')
                return {frame_output: None, plot_output: empty_fig, all_embeddings: embeddings, all_labels: labels}

            # Pass thresholds to process_frame
            processed_frame_rgb, new_embeddings, new_labels = process_frame(
                frame_cv.copy(), det_threshold=det_thresh, rec_threshold=rec_thresh
            )

            # Ensure correct format for Gradio (RGB, uint8, shape (H, W, 3))
            if processed_frame_rgb is not None:
                processed_frame_rgb = np.asarray(processed_frame_rgb)
                if processed_frame_rgb.dtype != np.uint8:
                    processed_frame_rgb = processed_frame_rgb.astype(np.uint8)
                if len(processed_frame_rgb.shape) == 2:  # grayscale, convert to RGB
                    processed_frame_rgb = np.stack([processed_frame_rgb]*3, axis=-1)
                elif processed_frame_rgb.shape[-1] != 3:
                    # If alpha channel, drop it
                    processed_frame_rgb = processed_frame_rgb[..., :3]

            # Update stored embeddings and labels
            embeddings.extend(new_embeddings)
            labels.extend(new_labels)

            # Generate UMAP plot (now includes all gallery embeddings)
            umap_plot = generate_umap_plot(
                embeddings, labels, GALLERY_EMBEDDINGS, GALLERY_NAMES
            )

            return {
                frame_output: processed_frame_rgb,
                plot_output: umap_plot,
                all_embeddings: embeddings,
                all_labels: labels
            }
        
        
        # Define inputs for process_video_frame
        process_inputs = [
            video_dropdown, 
            frame_slider, 
            det_thresh_slider, 
            rec_thresh_slider, 
            all_embeddings, 
            all_labels
        ]
        # Define outputs for process_video_frame
        process_outputs = {
            frame_output: "processed_frame_rgb", # Key in dict returned by process_video_frame
            plot_output: "umap_plot",
            all_embeddings: "all_embeddings",
            all_labels: "all_labels"
        } # This mapping is not directly used by Gradio outputs, it's for clarity.
          # Gradio expects a list of components for outputs.

        # Wire up the interface
        video_dropdown.change(
            load_video,
            inputs=[video_dropdown], # Corrected inputs
            outputs=[frame_slider, all_embeddings, all_labels]
        )
        
        # Common outputs for all controls that trigger processing
        common_process_outputs = [frame_output, plot_output, all_embeddings, all_labels]

        frame_slider.change(
            process_video_frame,
            inputs=process_inputs,
            outputs=common_process_outputs
        )
        
        det_thresh_slider.change(
            process_video_frame,
            inputs=process_inputs,
            outputs=common_process_outputs
        )

        rec_thresh_slider.change(
            process_video_frame,
            inputs=process_inputs,
            outputs=common_process_outputs
        )

        prev_btn.click(
            lambda current_frame: max(0, current_frame - 1), # Ensure lambda takes correct arg
            inputs=[frame_slider], # Corrected inputs
            outputs=frame_slider # Output to the slider itself
        ).then(
            process_video_frame,
            inputs=process_inputs, # Use the full list of inputs
            outputs=common_process_outputs
        )
        
        next_btn.click(
            lambda current_frame, total_frames: min(current_frame + 1, total_frames -1) if total_frames > 0 else 0, # Prevent going beyond max
            # Need total_frames for next_btn logic, which means load_video should also update a state for total_frames
            # For now, let's assume frame_slider.maximum is updated correctly by load_video and can be accessed
            # This lambda is getting complex. A helper might be better or simplify.
            # Simplified lambda for now, relies on slider max being set.
            inputs=[frame_slider, frame_slider], # Pass slider twice, once for current value, once to potentially get maximum (not ideal)
                                                # A better way is to store max_frames in a gr.State if needed by lambda
            outputs=frame_slider
        ).then(
            process_video_frame,
            inputs=process_inputs,
            outputs=common_process_outputs
        )

    return demo

if __name__ == "__main__":
    # Initialize gallery embeddings
    GALLERY_EMBEDDINGS = get_known_faces_embeddings_mv(contestants_dir, all_contestants, contestant_info)
    GALLERY_NAMES = {name: name for name in GALLERY_EMBEDDINGS.keys()}
    
    # Create and launch Gradio interface
    demo = create_gradio_interface()
    demo.launch()
