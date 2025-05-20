import os
import glob
import numpy as np
import cv2
import gradio as gr
import matplotlib.pyplot as plt
import umap.umap_ as umap
import pandas as pd
import time
import matplotlib
from PIL import Image, ImageDraw, ImageFont
import logging
from typing import List, Tuple, Dict, Any, Optional, Union
from src.core.detector import FaceDetector
from insightface.app.common import Face as InsightFaceObject

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('face_recognition')

# Configure matplotlib fonts for CJKV support
matplotlib.rcParams["font.sans-serif"] = [
    "Arial Unicode MS", "SimHei", "Noto Sans CJK TC", "Noto Sans CJK SC",
    "Noto Sans CJK JP", "Noto Sans CJK KR", "Microsoft JhengHei",
    "Apple LiGothic Medium", "WenQuanYi Zen Hei",
]
matplotlib.rcParams["axes.unicode_minus"] = False

# Constants
CJKV_FONT_PATH = "fonts/SourceHanSansTC-VF.ttf"
FONT_SIZE = 60
CONTESTANT_INFO_PATH = "contestant_info.csv"
EMBEDDING_DIR = "source/photo/contestants/embeddings"
VIDEO_DIR = "source/videos"
RECOGNITION_THRESHOLD = 0.4
DETECTION_SCORE_THRESHOLD = 0.2

# =============================================================================
# Face Recognition Module
# =============================================================================

def load_contestant_info():
    """Load and process contestant information from CSV file."""
    try:
        contestant_info_df = pd.read_csv(CONTESTANT_INFO_PATH)
        logger.info(f"Loaded contestant info from {CONTESTANT_INFO_PATH}: {len(contestant_info_df)} entries")
        
        # Create nickname to full name mapping
        nickname_to_name = pd.Series(contestant_info_df["姓名"].values, index=contestant_info_df["暱稱"]).to_dict()
        # Create nickname to display name mapping (format: "FullName (Nickname)")
        nickname_to_display = {nick: f"{name} ({nick})" for nick, name in nickname_to_name.items()}
        
        return contestant_info_df, nickname_to_name, nickname_to_display
    except Exception as e:
        logger.error(f"Error loading contestant info: {str(e)}")
        return pd.DataFrame(), {}, {}

def load_gallery_embeddings():
    """Load embeddings from the gallery directory."""
    logger.info(f"Loading embeddings from: {os.path.abspath(EMBEDDING_DIR)}")
    
    # Load contestant info for proper name display
    _, _, nickname_to_display = load_contestant_info()
    
    glob_pattern = os.path.join(EMBEDDING_DIR, "*_embedding.npy")
    embedding_files = glob.glob(glob_pattern)
    logger.info(f"Found {len(embedding_files)} embedding files")
    
    gallery_nicknames = []
    gallery_display_names = []
    gallery_embeddings = []
    embedding_dimensions = None

    for f in embedding_files:
        try:
            arr = np.load(f)
            arr = arr.flatten()
            
            # Accept any 1D embedding array
            if len(arr.shape) == 1:
                if embedding_dimensions is None:
                    # Set the first encountered dimension as our standard
                    embedding_dimensions = arr.shape[0]
                    logger.info(f"Using embedding dimension: {embedding_dimensions}")
                
                # If dimensions don't match, resize the embedding
                if arr.shape[0] != embedding_dimensions:
                    logger.warning(f"Embedding in {os.path.basename(f)} has dimension {arr.shape[0]}, "
                                  f"resizing to {embedding_dimensions}")
                    
                    # Resize strategy: either truncate or pad with zeros
                    if arr.shape[0] > embedding_dimensions:
                        # Truncate to the standard dimension
                        arr = arr[:embedding_dimensions]
                    else:
                        # Pad with zeros
                        padding = np.zeros(embedding_dimensions - arr.shape[0])
                        arr = np.concatenate([arr, padding])
                
                nickname = os.path.basename(f).replace("_embedding.npy", "")
                gallery_nicknames.append(nickname)
                
                # Use display name if available in mapping, otherwise use nickname
                if nickname in nickname_to_display:
                    display_name = nickname_to_display[nickname]
                else:
                    display_name = nickname
                    
                gallery_display_names.append(display_name)
                gallery_embeddings.append(arr)
            else:
                logger.warning(f"Skipping embedding file {os.path.abspath(f)}: not a 1D array, shape={arr.shape}")
        except Exception as e:
            logger.error(f"Error loading embedding from {f}: {str(e)}")

    if not gallery_embeddings:
        logger.error("No embeddings found in gallery! Face recognition will not work.")
        return np.empty((0, 512), dtype=np.float32), [], []
    
    logger.info(f"Loaded {len(gallery_embeddings)} embeddings from gallery")
    if gallery_embeddings:
        logger.debug(f"Gallery embeddings shape: {np.stack(gallery_embeddings).shape}")
        
    return np.stack(gallery_embeddings), gallery_nicknames, gallery_display_names

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return np.dot(a, b)

def get_top_matches(face_embedding: np.ndarray, gallery_embeddings: np.ndarray, 
                   gallery_display_names: List[str], top_n: int = 5) -> Tuple[List[Tuple[str, float, int]], np.ndarray]:
    """
    Find the top matches for a face embedding from the gallery.
    
    Args:
        face_embedding: The embedding vector of the detected face
        gallery_embeddings: Matrix of all gallery embeddings
        gallery_display_names: List of names corresponding to gallery embeddings
        top_n: Maximum number of top matches to return
        
    Returns:
        filtered_matches: List of (name, score, index) tuples
        sims: Array of similarity scores for all gallery embeddings
    """
    # Ensure face_embedding is normalized
    norm_face_embedding = face_embedding / np.linalg.norm(face_embedding)
    
    # Make sure face_embedding has the right dimension
    if norm_face_embedding.shape[0] != gallery_embeddings.shape[1]:
        logger.warning(f"Face embedding dimension {norm_face_embedding.shape[0]} doesn't match gallery "
                       f"dimension {gallery_embeddings.shape[1]}. Adjusting...")
        if norm_face_embedding.shape[0] > gallery_embeddings.shape[1]:
            norm_face_embedding = norm_face_embedding[:gallery_embeddings.shape[1]]
        else:
            padding = np.zeros(gallery_embeddings.shape[1] - norm_face_embedding.shape[0])
            norm_face_embedding = np.concatenate([norm_face_embedding, padding])
    
    # Calculate similarities with all gallery embeddings
    sims = np.dot(gallery_embeddings, norm_face_embedding)
    
    # Get indices of top matches
    top_idx_all = np.argsort(sims)[::-1][:top_n]
    
    # Filter matches by threshold
    filtered_matches = []
    for i in top_idx_all:
        if sims[i] >= RECOGNITION_THRESHOLD:
            filtered_matches.append((gallery_display_names[i], sims[i], i))
            
    return filtered_matches, sims

# =============================================================================
# Visualization Module
# =============================================================================

def plot_bar(all_top_matches_details: List[Tuple[str, float]]):
    """
    Plots a horizontal bar chart for all top matches from all detected faces.
    
    Args:
        all_top_matches_details: A list of tuples (label, score)
        
    Returns:
        fig: Matplotlib figure object
    """
    if not all_top_matches_details:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.text(0.5, 0.5, "No recognized matches to display", ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    labels = [item[0] for item in all_top_matches_details]
    scores = [item[1] for item in all_top_matches_details]

    # Determine figure height based on number of bars
    num_bars = len(labels)
    fig_height = max(3, num_bars * 0.4)

    fig, ax = plt.subplots(figsize=(5, fig_height))
    ax.barh(labels[::-1], scores[::-1], color="skyblue")
    ax.set_xlabel("Cosine Similarity")
    ax.set_title("Top Matches Across All Detected Faces")
    
    # Adjust layout
    plt.subplots_adjust(left=0.4)
    plt.tight_layout(rect=[0, 0, 1, 1])
    return fig

def plot_embedding_scatter(detected_face_embeddings_list: List[np.ndarray], 
                          gallery_embeddings_global: np.ndarray,
                          gallery_display_names_global: List[str], 
                          matches_per_detected_face: List[List[Tuple[str, float, int]]]):
    """
    Plot a 2D UMAP scatter plot of embeddings showing detected faces and their gallery matches.
    
    Args:
        detected_face_embeddings_list: List of embedding vectors for detected faces
        gallery_embeddings_global: Matrix of gallery embedding vectors
        gallery_display_names_global: List of names for gallery embeddings
        matches_per_detected_face: List of match information for each detected face
        
    Returns:
        fig: Matplotlib figure object
    """
    num_detected = len(detected_face_embeddings_list)
    num_gallery = gallery_embeddings_global.shape[0]

    # Handle empty case
    if num_detected == 0 and num_gallery == 0:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No embeddings to display", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    # Prepare data for UMAP
    all_embeddings_list = []
    point_types = []  # 'gallery', 'detected_recognized', 'detected_unknown'
    point_labels = []
    nearest_gallery_indices_for_detected = [[] for _ in range(num_detected)]

    # Add gallery embeddings
    if num_gallery > 0:
        all_embeddings_list.extend(list(gallery_embeddings_global))
        point_types.extend(['gallery'] * num_gallery)
        point_labels.extend(gallery_display_names_global)

    # Add detected face embeddings
    if num_detected > 0:
        # Make sure detected embeddings match gallery embedding dimensions
        processed_detected_embeddings = []
        for embed in detected_face_embeddings_list:
            if embed.shape[0] != gallery_embeddings_global.shape[1]:
                if embed.shape[0] > gallery_embeddings_global.shape[1]:
                    # Truncate
                    embed = embed[:gallery_embeddings_global.shape[1]]
                else:
                    # Pad
                    padding = np.zeros(gallery_embeddings_global.shape[1] - embed.shape[0])
                    embed = np.concatenate([embed, padding])
            processed_detected_embeddings.append(embed)
            
        all_embeddings_list.extend(processed_detected_embeddings)
        for i, match_info_list_for_face in enumerate(matches_per_detected_face):
            if match_info_list_for_face:  # Recognized
                top_match_name = match_info_list_for_face[0][0]
                point_types.append('detected_recognized')
                point_labels.append(f"Face {i+1}: {top_match_name}")
                nearest_gallery_indices_for_detected[i] = [match[2] for match in match_info_list_for_face]
            else:  # Unrecognized
                point_types.append('detected_unknown')
                point_labels.append(f"Face {i+1}: Unknown")

    if not all_embeddings_list:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No embeddings available for UMAP", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    all_embeddings_np = np.array(all_embeddings_list)

    # Check if we have enough points for UMAP
    if all_embeddings_np.shape[0] < 2:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "Not enough data points for UMAP (need at least 2)", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig
        
    # Determine appropriate n_neighbors value
    n_neighbors_val = min(15, all_embeddings_np.shape[0] - 1)
    if n_neighbors_val < 2:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"Too few points ({all_embeddings_np.shape[0]}) for robust UMAP.", 
                ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    # Run UMAP
    try:
        reducer = umap.UMAP(n_neighbors=n_neighbors_val, n_components=2, random_state=42, min_dist=0.1)
        embedding_2d = reducer.fit_transform(all_embeddings_np)
    except Exception as e:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"UMAP processing error: {e}", ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 10))

    # Define colors and sizes
    color_map = {
        'gallery': 'blue',
        'detected_recognized': 'red',
        'detected_unknown': 'orange',
        'nearest_gallery': 'green' 
    }
    size_map = {
        'gallery': 30,
        'detected_recognized': 100,
        'detected_unknown': 70,
        'nearest_gallery': 50 
    }
    
    plotted_nearest_gallery_indices = set()

    # Plot gallery embeddings first
    if num_gallery > 0:
        gallery_2d = embedding_2d[:num_gallery]
        for i in range(num_gallery):
            is_nearest_to_any_detected = any(i in nearest_list for nearest_list in nearest_gallery_indices_for_detected)
            if not is_nearest_to_any_detected:
                 ax.scatter(gallery_2d[i, 0], gallery_2d[i, 1], 
                           c=color_map['gallery'], s=size_map['gallery'], 
                           alpha=0.5, label="Gallery (Other)" if 'Gallery (Other)' not in plt.gca().get_legend_handles_labels()[1] else "")

    # Plot detected faces and their nearest gallery matches
    if num_detected > 0:
        detected_2d = embedding_2d[num_gallery:]
        for i in range(num_detected):
            detected_point = detected_2d[i]
            ptype = point_types[num_gallery + i]
            plabel = point_labels[num_gallery + i]
            
            ax.scatter(detected_point[0], detected_point[1], 
                       c=color_map[ptype], s=size_map[ptype], 
                       label=plabel.split(":")[0] if plabel.split(":")[0] not in plt.gca().get_legend_handles_labels()[1] else "",
                       alpha=0.9, edgecolors='black' if ptype == 'detected_recognized' else None,
                       marker='o' if ptype == 'detected_recognized' else 'X')
            ax.text(detected_point[0], detected_point[1] + 0.05, plabel, fontsize=9, ha='center')

            # Plot nearest gallery matches and draw connecting lines
            for gallery_idx in nearest_gallery_indices_for_detected[i]:
                if 0 <= gallery_idx < num_gallery:
                    gallery_match_point = embedding_2d[gallery_idx]
                    # Plot gallery point as "nearest match"
                    ax.scatter(gallery_match_point[0], gallery_match_point[1],
                               c=color_map['nearest_gallery'], s=size_map['nearest_gallery'],
                               alpha=0.8, edgecolors='black', marker='s',
                               label="Nearest Gallery Match" if "Nearest Gallery Match" not in plt.gca().get_legend_handles_labels()[1] else "")
                    plotted_nearest_gallery_indices.add(gallery_idx)
                    
                    # Draw connection line
                    ax.plot([detected_point[0], gallery_match_point[0]],
                            [detected_point[1], gallery_match_point[1]],
                            c='gray', linestyle='--', linewidth=0.8, alpha=0.7)

    ax.set_title("Embedding Space (UMAP) with Nearest Matches")
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2")
    
    # Create a unique legend
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='best')
    
    plt.tight_layout()
    return fig

def overlay_faces(frame: np.ndarray, 
                 faces: List[InsightFaceObject], 
                 matches: List[List[Tuple[str, float]]]) -> np.ndarray:
    """
    Draw bounding boxes and labels on the frame for each detected face.
    
    Args:
        frame: Input video frame
        faces: List of detected faces
        matches: List of match information for each face
        
    Returns:
        Annotated frame with bounding boxes and labels
    """
    # Convert frame to PIL Image for CJKV text support
    frame_pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(frame_pil)
    
    # Load font
    try:
        font = ImageFont.truetype(CJKV_FONT_PATH, FONT_SIZE)
    except Exception as e:
        logger.warning(f"Could not load specified font: {e}")
        font = ImageFont.load_default()
        
    for face, match_list in zip(faces, matches):
        box = face.bbox.astype(int)

        # Prepare label text
        if match_list:
            name, score = match_list[0]
            label = f"{name} ({score:.2f})"
        else:
            label = f"Unknown (0.00)"

        # Draw rectangle
        current_frame_np = np.array(frame_pil)
        cv2.rectangle(current_frame_np, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        frame_pil = Image.fromarray(current_frame_np)
        draw = ImageDraw.Draw(frame_pil)

        # Draw label
        draw.text((box[0], box[1] - FONT_SIZE - 2), label, font=font, fill=(0, 255, 0))
        
    return np.array(frame_pil)

# =============================================================================
# Image/Video Processing Functions
# =============================================================================

def process_frame(frame: np.ndarray, 
                 core_detector: FaceDetector,
                 gallery_embeddings: np.ndarray,
                 gallery_display_names: List[str],
                 vis_type: str = "bar") -> Tuple[np.ndarray, plt.Figure]:
    """
    Process a video frame for face recognition.
    
    Args:
        frame: Input video frame
        core_detector: FaceDetector instance
        gallery_embeddings: Matrix of gallery embedding vectors
        gallery_display_names: List of names for gallery embeddings
        vis_type: Visualization type, either "bar" or "scatter"
        
    Returns:
        processed_frame: Frame with annotations
        fig: Matplotlib figure with visualization
    """
    logger.debug(f"Processing frame with visualization type: {vis_type}")
    
    # Detect faces
    raw_detected_faces = core_detector.detect_faces(frame)
    logger.debug(f"Detected {len(raw_detected_faces)} raw faces")

    # Handle no faces case
    if not raw_detected_faces:
        logger.debug("No faces detected")
        fig, ax = plt.subplots(figsize=(4, 3) if vis_type == "bar" else (6, 2))
        ax.text(0.5, 0.5, "No faces detected", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return frame, fig

    # Filter faces by detection score
    detected_faces = []
    for face in raw_detected_faces:
        if hasattr(face, "det_score"):
            if face.det_score >= DETECTION_SCORE_THRESHOLD:
                detected_faces.append(face)
        else:
            detected_faces.append(face)

    logger.debug(f"Number of faces after filtering: {len(detected_faces)}")

    # Handle no faces after filtering
    if not detected_faces:
        fig, ax = plt.subplots(figsize=(4, 3) if vis_type == "bar" else (6, 2))
        ax.text(0.5, 0.5, f"No faces above score threshold ({DETECTION_SCORE_THRESHOLD})", 
                ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return frame, fig

    # Process each face for recognition
    matches = []
    all_sims = []
    detected_embeds = []
    
    for face in detected_faces:
        if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
            # Add to detected embeddings list for visualization
            detected_embeds.append(face.normed_embedding)
            
            # Find matches
            top_matches_with_indices, sims_for_this_face = get_top_matches(
                face.normed_embedding, gallery_embeddings, gallery_display_names)
            
            matches.append(top_matches_with_indices)
            all_sims.append(sims_for_this_face)
        else:
            matches.append([])
            all_sims.append(np.array([]))

    # Prepare matches for overlay (name, score only)
    matches_for_overlay = []
    for match_list_for_face in matches:
        matches_for_overlay.append([(name, score) for name, score, _ in match_list_for_face])
    
    # Overlay recognition results on frame
    processed_frame = overlay_faces(frame, detected_faces, matches_for_overlay)

    # Create visualization
    if not any(matches):
        logger.debug("No recognized matches for any detected faces")
        if vis_type == "bar":
            fig = plot_bar([])
        else:  # scatter plot
            fig = plot_embedding_scatter(detected_embeds, gallery_embeddings, gallery_display_names, matches)
        return processed_frame, fig

    if vis_type == "bar":
        # Prepare data for bar plot
        all_top_matches_for_plot = []
        for i, match_list_for_face in enumerate(matches):
            if match_list_for_face:
                for name, score, _ in match_list_for_face:
                    all_top_matches_for_plot.append((f"Face {i+1}: {name}", score))
        
        all_top_matches_for_plot.sort(key=lambda x: x[1], reverse=True)
        fig = plot_bar(all_top_matches_for_plot)
    else:  # scatter plot
        fig = plot_embedding_scatter(detected_embeds, gallery_embeddings, gallery_display_names, matches)
        
    return processed_frame, fig

def get_total_frames(video_path: str) -> int:
    """Get the total number of frames in a video file."""
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return total

def get_frame_by_index(video_path: str, 
                      frame_idx: int, 
                      core_detector: FaceDetector,
                      gallery_embeddings: np.ndarray,
                      gallery_display_names: List[str],
                      vis_type: str = "bar") -> Optional[Tuple[np.ndarray, plt.Figure]]:
    """
    Extract and process a specific frame from a video file.
    
    Args:
        video_path: Path to the video file
        frame_idx: Index of the frame to extract
        core_detector: FaceDetector instance
        gallery_embeddings: Matrix of gallery embedding vectors
        gallery_display_names: List of names for gallery embeddings
        vis_type: Visualization type, either "bar" or "scatter"
        
    Returns:
        processed_frame: Frame with annotations
        fig: Matplotlib figure with visualization
    """
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        logger.warning(f"Failed to read frame {frame_idx} from {video_path}")
        return None
        
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return process_frame(frame_rgb, core_detector, gallery_embeddings, gallery_display_names, vis_type)

# =============================================================================
# Gradio UI Module
# =============================================================================

def build_gradio_interface():
    """Build and configure the Gradio interface."""
    # Initialize face detector
    core_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE,
        model_size=(640, 640),
        device="auto",
    )
    
    # Load gallery embeddings
    gallery_embeddings, gallery_nicknames, gallery_display_names = load_gallery_embeddings()
    
    # Get available video files
    video_files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4")]
    video_paths = {f: os.path.join(VIDEO_DIR, f) for f in video_files}
    
    # Define UI update functions
    def update_slider_on_video(selected_video):
        """Update slider range when video is selected."""
        video_path = video_paths[selected_video]
        total = get_total_frames(video_path)
        return gr.update(maximum=total - 1, value=0), {
            "playing": False,
            "frame": 0,
            "total": total,
        }

    def update_frame(selected_video, frame_idx, vis_type):
        """Update displayed frame when slider changes."""
        video_path = video_paths[selected_video]
        result = get_frame_by_index(
            video_path, frame_idx, core_detector, gallery_embeddings, gallery_display_names, vis_type)
        if result is None:
            return None, None
        out_frame, fig = result
        return out_frame, fig

    def play_loop(selected_video, vis_type, state):
        """Play video frames in sequence."""
        video_path = video_paths[selected_video]
        total = state["total"]
        frame = state["frame"]
        while state["playing"] and frame < total:
            result = get_frame_by_index(
                video_path, frame, core_detector, gallery_embeddings, gallery_display_names, vis_type)
            if result is None:
                break
            out_frame, fig = result
            yield (
                out_frame,
                fig,
                frame,
                {"playing": True, "frame": frame + 1, "total": total},
            )
            frame += 1
            time.sleep(0.04)  # ~25 FPS
        yield (
            gr.update(),
            gr.update(),
            frame,
            {"playing": False, "frame": frame, "total": total},
        )
    
    # Create the Gradio interface
    with gr.Blocks(title="Face Recognition System", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Real-Time Face Recognition & Embedding Visualization")
        
        with gr.Row():
            with gr.Column(scale=3):
                video_dropdown = gr.Dropdown(
                    choices=video_files,
                    label="Select Video File",
                    value=video_files[0] if video_files else None,
                    interactive=True,
                )
            with gr.Column(scale=2):
                vis_type = gr.Radio(
                    ["bar", "scatter"],
                    value="bar",
                    label="Visualization Type",
                    interactive=True
                )
        
        with gr.Row():
            with gr.Column(scale=4):
                frame_slider = gr.Slider(
                    minimum=0, 
                    maximum=1, 
                    value=0, 
                    step=1, 
                    label="Frame Timeline", 
                    interactive=True
                )
            with gr.Column(scale=1):
                with gr.Row():
                    play_btn = gr.Button("▶️ Play", variant="primary")
                    pause_btn = gr.Button("⏸️ Pause", variant="secondary")
        
        with gr.Row():
            with gr.Column(scale=3):
                output_video = gr.Image(label="Video Frame with Recognized Faces")
            with gr.Column(scale=2):
                output_plot = gr.Plot(label="Similarity Visualization")
                
        gr.Markdown("### Instructions")
        with gr.Accordion("Help", open=False):
            gr.Markdown("""
            - **Select Video**: Choose a video file from the dropdown
            - **Visualization Type**: 
                - **Bar**: Shows similarity scores for recognized faces
                - **Scatter**: Shows UMAP projection of face embeddings
            - **Frame Timeline**: Drag to navigate through the video
            - **Play/Pause**: Control video playback
            """)
                
        state = gr.State({"playing": False, "frame": 0, "total": 1})

        # Connect events
        video_dropdown.change(
            fn=update_slider_on_video, 
            inputs=[video_dropdown], 
            outputs=[frame_slider, state]
        )
        frame_slider.change(
            fn=update_frame, 
            inputs=[video_dropdown, frame_slider, vis_type], 
            outputs=[output_video, output_plot]
        )
        vis_type.change(
            fn=update_frame, 
            inputs=[video_dropdown, frame_slider, vis_type], 
            outputs=[output_video, output_plot]
        )
        play_btn.click(
            fn=play_loop, 
            inputs=[video_dropdown, vis_type, state], 
            outputs=[output_video, output_plot, frame_slider, state], 
            api_name=False
        )
        pause_btn.click(
            fn=lambda s: {"playing": False, "frame": s["frame"], "total": s["total"]}, 
            inputs=[state], 
            outputs=[state], 
            api_name=False
        )
    
    return demo

# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    demo = build_gradio_interface()
    demo.launch()
