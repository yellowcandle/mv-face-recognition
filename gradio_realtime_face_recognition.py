import glob
import logging
import os
import time
from typing import List, Optional, Tuple

import cv2
import gradio as gr
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap.umap_ as umap
from insightface.app.common import Face as InsightFaceObject
from PIL import Image, ImageDraw, ImageFont

from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("face_recognition")

# Configure matplotlib fonts for CJKV support
matplotlib.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "SimHei",
    "Noto Sans CJK TC",
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Noto Sans CJK KR",
    "Microsoft JhengHei",
    "Apple LiGothic Medium",
    "WenQuanYi Zen Hei",
]
matplotlib.rcParams["axes.unicode_minus"] = False

# Constants
CJKV_FONT_PATH = "fonts/SourceHanSansTC-VF.ttf"
FONT_SIZE = 60
CONTESTANT_INFO_PATH = "contestant_info.csv"
EMBEDDING_DIR = "source/photo/contestants/embeddings"
VIDEO_DIR = "source/videos"
RECOGNITION_THRESHOLD = 0.4 # Reverting to a general threshold for SFace
DETECTION_SCORE_THRESHOLD = 0.2 # Reverting to a general threshold

# =============================================================================
# Face Recognition Module
# =============================================================================


def load_contestant_info():
    """Load and process contestant information from CSV file."""
    try:
        contestant_info_df = pd.read_csv(CONTESTANT_INFO_PATH)
        logger.info(
            f"Loaded contestant info from {CONTESTANT_INFO_PATH}: {len(contestant_info_df)} entries"
        )

        # Create nickname to full name mapping
        nickname_to_name = pd.Series(
            contestant_info_df["姓名"].values, index=contestant_info_df["暱稱"]
        ).to_dict()
        # Create nickname to display name mapping (format: "FullName (Nickname)")
        nickname_to_display = {nick: f"{name} ({nick})" for nick, name in nickname_to_name.items()}

        return contestant_info_df, nickname_to_name, nickname_to_display
    except Exception as e:
        logger.error(f"Error loading contestant info: {str(e)}")
        return pd.DataFrame(), {}, {}


def load_gallery_embeddings(expected_embedding_size: int):
    """Load embeddings from the gallery directory and normalize them."""
    logger.info(f"Loading embeddings from: {os.path.abspath(EMBEDDING_DIR)}")
    logger.info(f"Expected embedding dimension: {expected_embedding_size}")

    # Load contestant info for proper name display
    _, _, nickname_to_display = load_contestant_info()

    glob_pattern = os.path.join(EMBEDDING_DIR, "*_embedding.npy")
    embedding_files = glob.glob(glob_pattern)
    logger.info(f"Found {len(embedding_files)} embedding files")

    gallery_nicknames = []
    gallery_display_names = []
    gallery_embeddings = []

    for f in embedding_files:
        try:
            arr = np.load(f)
            arr = arr.flatten()

            # Ensure embedding is 1D and resize if necessary to match expected size
            if len(arr.shape) == 1:
                if arr.shape[0] != expected_embedding_size:
                    logger.warning(
                        f"Embedding in {os.path.basename(f)} has dimension {arr.shape[0]}, "
                        f"resizing to expected {expected_embedding_size}"
                    )

                    # Resize strategy: either truncate or pad with zeros
                    if arr.shape[0] > expected_embedding_size:
                        # Truncate to the standard dimension
                        arr = arr[:expected_embedding_size]
                    else:
                        # Pad with zeros
                        padding = np.zeros(expected_embedding_size - arr.shape[0])
                        arr = np.concatenate([arr, padding])

                # L2 Normalize the embedding
                norm = np.linalg.norm(arr)
                if norm > 1e-9: # Avoid division by zero
                    arr = arr / norm
                else:
                    logger.warning(f"Embedding for {os.path.basename(f)} has zero norm. Skipping.")
                    continue # Skip this embedding if norm is zero

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
                logger.warning(
                    f"Skipping embedding file {os.path.abspath(f)}: not a 1D array, shape={arr.shape}"
                )
        except Exception as e:
            logger.error(f"Error loading embedding from {f}: {str(e)}")

    if not gallery_embeddings:
        logger.error("No embeddings found in gallery! Face recognition will not work.")
        return (
            np.empty((0, expected_embedding_size), dtype=np.float32),
            [],
            [],
        )

    logger.info(f"Loaded {len(gallery_embeddings)} embeddings from gallery")
    if gallery_embeddings:
        logger.debug(f"Gallery embeddings shape: {np.stack(gallery_embeddings).shape}")

    return np.stack(gallery_embeddings), gallery_nicknames, gallery_display_names


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:  # Avoid division by zero
        return 0.0
    a = a / a_norm
    b = b / b_norm
    return np.dot(a, b)


def get_top_matches(
    face_embedding: np.ndarray,
    gallery_embeddings: np.ndarray,
    gallery_display_names: List[str],
    top_n: int = 5,
) -> Tuple[List[Tuple[str, float, int]], np.ndarray]:
    """
    Find the top matches for a face embedding from the gallery.
    """
    face_emb_norm = np.linalg.norm(face_embedding)
    if face_emb_norm == 0:  # Avoid division by zero for detected embedding
        return [], np.zeros(gallery_embeddings.shape[0])

    norm_face_embedding = face_embedding / face_emb_norm

    if norm_face_embedding.shape[0] != gallery_embeddings.shape[1]:
        logger.warning(
            f"Face embedding dimension {norm_face_embedding.shape[0]} doesn't match gallery "
            f"dimension {gallery_embeddings.shape[1]}. Adjusting..."
        )
        if norm_face_embedding.shape[0] > gallery_embeddings.shape[1]:
            norm_face_embedding = norm_face_embedding[: gallery_embeddings.shape[1]]
        else:
            padding = np.zeros(gallery_embeddings.shape[1] - norm_face_embedding.shape[0])
            norm_face_embedding = np.concatenate([norm_face_embedding, padding])

    sims = np.dot(gallery_embeddings, norm_face_embedding)
    top_idx_all = np.argsort(sims)[::-1][:top_n]

    filtered_matches = []
    for i in top_idx_all:
        if sims[i] >= RECOGNITION_THRESHOLD:
            filtered_matches.append((gallery_display_names[i], sims[i], i))

    return filtered_matches, sims


# =============================================================================
# Visualization Module
# =============================================================================


def plot_bar(all_top_matches_details: List[Tuple[str, float]]):
    if not all_top_matches_details:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.text(0.5, 0.5, "No recognized matches to display", ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    labels = [item[0] for item in all_top_matches_details]
    scores = [item[1] for item in all_top_matches_details]
    num_bars = len(labels)
    fig_height = max(3, num_bars * 0.4)

    fig, ax = plt.subplots(figsize=(5, fig_height))
    ax.barh(labels[::-1], scores[::-1], color="skyblue")
    ax.set_xlabel("Cosine Similarity")
    ax.set_title("Top Matches Across All Detected Faces")
    plt.subplots_adjust(left=0.4)
    plt.tight_layout(rect=[0, 0, 1, 1])
    return fig


def plot_embedding_scatter(
    detected_face_embeddings_list: List[np.ndarray],
    gallery_embeddings_global: np.ndarray,
    gallery_display_names_global: List[str],
    matches_per_detected_face: List[List[Tuple[str, float, int]]],
):
    num_detected = len(detected_face_embeddings_list)
    num_gallery = gallery_embeddings_global.shape[0]

    if num_detected == 0 and num_gallery == 0:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No embeddings to display", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    all_embeddings_list = []
    point_types = []
    point_labels = []
    nearest_gallery_indices_for_detected = [[] for _ in range(num_detected)]

    if num_gallery > 0:
        all_embeddings_list.extend(list(gallery_embeddings_global))
        point_types.extend(["gallery"] * num_gallery)
        point_labels.extend(gallery_display_names_global)

    if num_detected > 0:
        processed_detected_embeddings = []
        gallery_dim = (
            gallery_embeddings_global.shape[1]
            if num_gallery > 0
            else (
                detected_face_embeddings_list[0].shape[0] if detected_face_embeddings_list else 128
            )
        )

        for embed in detected_face_embeddings_list:
            if embed.shape[0] != gallery_dim:
                if embed.shape[0] > gallery_dim:
                    embed = embed[:gallery_dim]
                else:
                    padding = np.zeros(gallery_dim - embed.shape[0])
                    embed = np.concatenate([embed, padding])
            processed_detected_embeddings.append(embed)

        all_embeddings_list.extend(processed_detected_embeddings)
        for i, match_info_list_for_face in enumerate(matches_per_detected_face):
            if match_info_list_for_face:
                top_match_name = match_info_list_for_face[0][0]
                point_types.append("detected_recognized")
                point_labels.append(f"Face {i + 1}: {top_match_name}")
                nearest_gallery_indices_for_detected[i] = [
                    match[2] for match in match_info_list_for_face
                ]
            else:
                point_types.append("detected_unknown")
                point_labels.append(f"Face {i + 1}: Unknown")

    if not all_embeddings_list:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No embeddings for UMAP", ha="center", va="center")
        return fig
    all_embeddings_np = np.array(all_embeddings_list)
    if all_embeddings_np.shape[0] < 2:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "Need at least 2 points for UMAP", ha="center", va="center")
        return fig

    n_neighbors_val = min(15, all_embeddings_np.shape[0] - 1)
    if n_neighbors_val < 2:  # UMAP requires n_neighbors >= 2
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(
            0.5,
            0.5,
            f"Too few points ({all_embeddings_np.shape[0]}) for UMAP.",
            ha="center",
            va="center",
        )
        return fig

    try:
        reducer = umap.UMAP(
            n_neighbors=n_neighbors_val, n_components=2, random_state=42, min_dist=0.1
        )
        embedding_2d = reducer.fit_transform(all_embeddings_np)
    except Exception as e:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"UMAP error: {e}", ha="center", va="center", fontsize=8)
        return fig

    fig, ax = plt.subplots(figsize=(12, 10))
    color_map = {
        "gallery": "blue",
        "detected_recognized": "red",
        "detected_unknown": "orange",
        "nearest_gallery": "green",
    }
    size_map = {
        "gallery": 30,
        "detected_recognized": 100,
        "detected_unknown": 70,
        "nearest_gallery": 50,
    }

    if num_gallery > 0:
        gallery_2d = embedding_2d[:num_gallery]
        for i in range(num_gallery):
            if not any(i in nearest_list for nearest_list in nearest_gallery_indices_for_detected):
                ax.scatter(
                    gallery_2d[i, 0],
                    gallery_2d[i, 1],
                    c=color_map["gallery"],
                    s=size_map["gallery"],
                    alpha=0.5,
                    label="Gallery (Other)"
                    if "Gallery (Other)" not in plt.gca().get_legend_handles_labels()[1]
                    else "",
                )

    if num_detected > 0:
        detected_2d = embedding_2d[num_gallery:]
        for i in range(num_detected):
            detected_point = detected_2d[i]
            ptype = point_types[num_gallery + i]
            plabel = point_labels[num_gallery + i]
            ax.scatter(
                detected_point[0],
                detected_point[1],
                c=color_map[ptype],
                s=size_map[ptype],
                label=plabel.split(":")[0]
                if plabel.split(":")[0] not in plt.gca().get_legend_handles_labels()[1]
                else "",
                alpha=0.9,
                edgecolors="black" if ptype == "detected_recognized" else None,
                marker="o" if ptype == "detected_recognized" else "X",
            )
            ax.text(detected_point[0], detected_point[1] + 0.05, plabel, fontsize=9, ha="center")
            for gallery_idx in nearest_gallery_indices_for_detected[i]:
                if 0 <= gallery_idx < num_gallery:
                    gallery_match_point = embedding_2d[gallery_idx]
                    ax.scatter(
                        gallery_match_point[0],
                        gallery_match_point[1],
                        c=color_map["nearest_gallery"],
                        s=size_map["nearest_gallery"],
                        alpha=0.8,
                        edgecolors="black",
                        marker="s",
                        label="Nearest Gallery Match"
                        if "Nearest Gallery Match" not in plt.gca().get_legend_handles_labels()[1]
                        else "",
                    )
                    ax.plot(
                        [detected_point[0], gallery_match_point[0]],
                        [detected_point[1], gallery_match_point[1]],
                        c="gray",
                        linestyle="--",
                        linewidth=0.8,
                        alpha=0.7,
                    )

    ax.set_title("Embedding Space (UMAP) with Nearest Matches")
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2")
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles, strict=False))
    ax.legend(by_label.values(), by_label.keys(), loc="best")
    plt.tight_layout()
    return fig


def overlay_faces(
    frame: np.ndarray, faces: List[InsightFaceObject], matches: List[List[Tuple[str, float]]]
) -> np.ndarray:
    frame_pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(frame_pil)
    try:
        font = ImageFont.truetype(CJKV_FONT_PATH, FONT_SIZE)
    except Exception as e:
        logger.warning(f"Could not load font: {e}")
        font = ImageFont.load_default()

    for face, match_list in zip(faces, matches, strict=False):
        box = face.bbox.astype(int)
        label = f"{match_list[0][0]} ({match_list[0][1]:.2f})" if match_list else "Unknown (0.00)"
        current_frame_np = np.array(frame_pil)
        cv2.rectangle(current_frame_np, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        frame_pil = Image.fromarray(current_frame_np)
        draw = ImageDraw.Draw(frame_pil)  # Re-initialize draw object
        draw.text((box[0], box[1] - FONT_SIZE - 2), label, font=font, fill=(0, 255, 0))
    return np.array(frame_pil)


# =============================================================================
# Image/Video Processing Functions
# =============================================================================


# MODIFIED: Added face_recognizer_instance parameter
def process_frame(
    frame: np.ndarray,
    core_detector: FaceDetector,
    face_recognizer_instance: FaceRecognizer,
    gallery_embeddings: np.ndarray,
    gallery_display_names: List[str],
    vis_type: str = "bar",
) -> Tuple[np.ndarray, plt.Figure]:
    logger.debug(f"Processing frame with visualization type: {vis_type}")
    raw_detected_faces = core_detector.detect_faces(frame)
    logger.debug(f"Detected {len(raw_detected_faces)} raw faces")

    empty_fig, ax = plt.subplots(figsize=(4, 3) if vis_type == "bar" else (6, 2))
    ax.set_xticks([])
    ax.set_yticks([])
    if not raw_detected_faces:
        logger.debug("No faces detected")
        ax.text(0.5, 0.5, "No faces detected", ha="center", va="center")
        plt.tight_layout()
        return frame, empty_fig

    detected_faces = [
        f
        for f in raw_detected_faces
        if not hasattr(f, "det_score") or f.det_score >= DETECTION_SCORE_THRESHOLD
    ]
    logger.debug(f"Number of faces after filtering: {len(detected_faces)}")
    if not detected_faces:
        ax.text(
            0.5,
            0.5,
            f"No faces above score threshold ({DETECTION_SCORE_THRESHOLD})",
            ha="center",
            va="center",
            fontsize=8,
        )
        plt.tight_layout()
        return frame, empty_fig
    plt.close(empty_fig)  # Close if not used

    matches = []
    all_sims = []
    detected_embeds = []
    for face in detected_faces:
        face_img = core_detector.extract_face(frame, face.bbox.astype(int), padding=0.1)
        current_embedding = None
        sims_for_this_face = np.array([])
        if face_img is not None and face_img.size > 0:
            current_embedding = face_recognizer_instance._get_embedding(
                face_img
            )  # MODIFIED: Use FaceRecognizer
            if current_embedding is not None and current_embedding.size > 0:
                detected_embeds.append(current_embedding)
                top_matches_with_indices, sims_for_this_face = get_top_matches(
                    current_embedding, gallery_embeddings, gallery_display_names
                )
                matches.append(top_matches_with_indices)
            else:
                logger.debug("Failed to get embedding")
                matches.append([])
        else:
            logger.debug("Failed to extract face image")
            matches.append([])
        all_sims.append(sims_for_this_face)

    matches_for_overlay = [[(name, score) for name, score, _ in mlist] for mlist in matches]
    processed_frame = overlay_faces(frame, detected_faces, matches_for_overlay)

    if not any(matches):
        logger.debug("No recognized matches for any detected faces")
        fig = (
            plot_bar([])
            if vis_type == "bar"
            else plot_embedding_scatter(
                detected_embeds, gallery_embeddings, gallery_display_names, matches
            )
        )
        return processed_frame, fig

    if vis_type == "bar":
        all_top_matches_for_plot = sorted(
            [
                (f"Face {i + 1}: {name}", score)
                for i, mlist in enumerate(matches)
                if mlist
                for name, score, _ in mlist
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        fig = plot_bar(all_top_matches_for_plot)
    else:
        fig = plot_embedding_scatter(
            detected_embeds, gallery_embeddings, gallery_display_names, matches
        )
    return processed_frame, fig


def get_total_frames(video_path: str) -> int:
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return total


# MODIFIED: Added face_recognizer_instance parameter
def get_frame_by_index(
    video_path: str,
    frame_idx: int,
    core_detector: FaceDetector,
    face_recognizer_instance: FaceRecognizer,
    gallery_embeddings: np.ndarray,
    gallery_display_names: List[str],
    vis_type: str = "bar",
) -> Optional[Tuple[np.ndarray, plt.Figure]]:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        logger.warning(f"Failed to read frame {frame_idx} from {video_path}")
        return None
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    # MODIFIED: Pass face_recognizer_instance
    return process_frame(
        frame_rgb,
        core_detector,
        face_recognizer_instance,
        gallery_embeddings,
        gallery_display_names,
        vis_type,
    )


# =============================================================================
# Gradio UI Module
# =============================================================================

def process_static_image(image: np.ndarray, vis_type: str = "bar") -> Tuple[np.ndarray, plt.Figure]:
    logger.debug(f"Processing static image with visualization type: {vis_type}")
    
    # Re-initialize detector and recognizer for this function call to ensure latest settings
    # This is a simplified approach; in a real app, these might be global or passed
    core_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto"
    )
    sface_model_path = os.path.join("models", "face_recognition_sface.onnx")
    face_recognizer_instance = FaceRecognizer(
        face_detector=core_detector,
        similarity_threshold=RECOGNITION_THRESHOLD,
        model_path=sface_model_path
    )
    
    gallery_embeddings, gallery_nicknames, gallery_display_names = load_gallery_embeddings(face_recognizer_instance.embedding_size)

    # Use the existing process_frame logic
    return process_frame(
        image,
        core_detector,
        face_recognizer_instance,
        gallery_embeddings,
        gallery_display_names,
        vis_type,
    )


def build_gradio_interface():
    # Create detector with proper access to providers attribute
    core_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto"
    )
    # No longer trying to access non-existent 'providers' attribute

    # MODIFIED: Initialize FaceRecognizer instance with optimized model path and threshold
    sface_model_path = os.path.join("models", "face_recognition_sface.onnx")
    face_recognizer_instance = FaceRecognizer(
        face_detector=core_detector,
        similarity_threshold=RECOGNITION_THRESHOLD, # Use the updated constant
        model_path=sface_model_path # Explicitly use the sface model path
    )
    logger.info(
        f"Initialized FaceRecognizer for Gradio with model: {face_recognizer_instance.model_path}, embedding size: {face_recognizer_instance.embedding_size}"
    )
    # SFace model is expected to be 128-dim.

    gallery_embeddings, gallery_nicknames, gallery_display_names = load_gallery_embeddings(face_recognizer_instance.embedding_size)
    video_files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4")]
    video_paths = {f: os.path.join(VIDEO_DIR, f) for f in video_files}

    def update_slider_on_video(selected_video):
        video_path = video_paths[selected_video]
        total = get_total_frames(video_path)
        return gr.update(maximum=total - 1, value=0), {"playing": False, "frame": 0, "total": total}

    def update_frame(selected_video, frame_idx, vis_type):
        video_path = video_paths[selected_video]
        # MODIFIED: Pass face_recognizer_instance
        result = get_frame_by_index(
            video_path,
            frame_idx,
            core_detector,
            face_recognizer_instance,
            gallery_embeddings,
            gallery_display_names,
            vis_type,
        )
        if result is None:
            return None, None
        out_frame, fig = result
        return out_frame, fig

    def play_loop(selected_video, vis_type, state_in):  # Renamed state to state_in for clarity
        video_path = video_paths[selected_video]
        current_frame_idx = state_in["frame"]
        total_frames = state_in["total"]

        # This function is a generator. Gradio calls it iteratively if it yields.
        # The pause button will set state_in["playing"] to False externally.

        # Case 1: Play button just clicked (state_in['playing'] is False)
        if not state_in["playing"]:
            if current_frame_idx < total_frames:  # If not at the end
                # Process and yield the current frame to start
                result = get_frame_by_index(
                    video_path,
                    current_frame_idx,
                    core_detector,
                    face_recognizer_instance,
                    gallery_embeddings,
                    gallery_display_names,
                    vis_type,
                )
                if result:
                    out_frame, fig = result
                    time.sleep(0.04)  # FPS control
                    # Yield current frame, update slider to current_frame_idx, set playing to True, and prepare for *next* frame
                    yield (
                        out_frame,
                        fig,
                        current_frame_idx,
                        {"playing": True, "frame": current_frame_idx + 1, "total": total_frames},
                    )
                    return  # End this iteration, Gradio calls again with new state if playing is True
                else:  # Failed to get the first frame
                    yield (
                        gr.update(),
                        gr.update(),
                        current_frame_idx,
                        {"playing": False, "frame": current_frame_idx, "total": total_frames},
                    )
                    return
            else:  # Already at the end when play was clicked
                yield (
                    gr.update(),
                    gr.update(),
                    current_frame_idx,
                    {"playing": False, "frame": current_frame_idx, "total": total_frames},
                )
                return

        # Case 2: Already playing (state_in['playing'] is True from previous yield)
        elif state_in["playing"]:  # Explicitly check if playing is true
            if current_frame_idx < total_frames:
                # Process and yield the current_frame_idx (which was set to frame + 1 in previous yield)
                result = get_frame_by_index(
                    video_path,
                    current_frame_idx,
                    core_detector,
                    face_recognizer_instance,
                    gallery_embeddings,
                    gallery_display_names,
                    vis_type,
                )
                if result:
                    out_frame, fig = result
                    time.sleep(0.04)  # FPS control
                    # Yield current frame, update slider, set playing True, prepare for next frame
                    yield (
                        out_frame,
                        fig,
                        current_frame_idx,
                        {"playing": True, "frame": current_frame_idx + 1, "total": total_frames},
                    )
                    return
                else:  # Failed to get a subsequent frame
                    yield (
                        gr.update(),
                        gr.update(),
                        current_frame_idx,
                        {"playing": False, "frame": current_frame_idx, "total": total_frames},
                    )
                    return
            else:  # Reached end of video while playing
                yield (
                    gr.update(),
                    gr.update(),
                    current_frame_idx,
                    {"playing": False, "frame": current_frame_idx, "total": total_frames},
                )
                return

        # Fallback: If neither condition met (e.g., paused externally and then called again), ensure playing is false.
        # This part might not be strictly necessary if pause_btn correctly sets playing to False.
        yield (
            gr.update(),
            gr.update(),
            current_frame_idx,
            {"playing": False, "frame": current_frame_idx, "total": total_frames},
        )

    with gr.Blocks(title="Face Recognition System", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Real-Time Face Recognition & Embedding Visualization")
        
        with gr.Tab("Video Processing"):
            with gr.Row():
                with gr.Column(scale=3):
                    video_dropdown = gr.Dropdown(
                        choices=video_files,
                        label="Select Video File",
                        value=video_files[0] if video_files else None,
                        interactive=True,
                    )
                with gr.Column(scale=2):
                    vis_type_video = gr.Radio(
                        ["bar", "scatter"], value="bar", label="Visualization Type", interactive=True
                    )
            with gr.Row():
                with gr.Column(scale=4):
                    frame_slider = gr.Slider(
                        minimum=0, maximum=1, value=0, step=1, label="Frame Timeline", interactive=True
                    )
                with gr.Column(scale=1):
                    with gr.Row():
                        play_btn = gr.Button("▶️ Play", variant="primary")
                        pause_btn = gr.Button("⏸️ Pause", variant="secondary")
            with gr.Row():
                with gr.Column(scale=3):
                    output_video = gr.Image(label="Video Frame with Recognized Faces")
                with gr.Column(scale=2):
                    output_plot_video = gr.Plot(label="Similarity Visualization")
            
            state = gr.State({"playing": False, "frame": 0, "total": 1})
            video_dropdown.change(
                fn=update_slider_on_video, inputs=[video_dropdown], outputs=[frame_slider, state]
            )
            frame_slider.change(
                fn=update_frame,
                inputs=[video_dropdown, frame_slider, vis_type_video],
                outputs=[output_video, output_plot_video],
            )
            vis_type_video.change(
                fn=update_frame,
                inputs=[video_dropdown, frame_slider, vis_type_video],
                outputs=[output_video, output_plot_video],
            )
            play_btn.click(
                fn=play_loop,
                inputs=[video_dropdown, vis_type_video, state],
                outputs=[output_video, output_plot_video, frame_slider, state],
                api_name=False,
            )
            pause_btn.click(
                fn=lambda s: {"playing": False, "frame": s["frame"], "total": s["total"]},
                inputs=[state],
                outputs=[state],
                api_name=False,
            )

        with gr.Tab("Static Image Processing"):
            with gr.Row():
                with gr.Column(scale=3):
                    static_image_input = gr.Image(type="numpy", label="Upload Image for Recognition")
                with gr.Column(scale=2):
                    vis_type_static = gr.Radio(
                        ["bar", "scatter"], value="bar", label="Visualization Type", interactive=True
                    )
            with gr.Row():
                process_image_btn = gr.Button("Process Image", variant="primary")
            with gr.Row():
                with gr.Column(scale=3):
                    output_static_image = gr.Image(label="Processed Image with Recognized Faces")
                with gr.Column(scale=2):
                    output_plot_static = gr.Plot(label="Similarity Visualization")
            
            process_image_btn.click(
                fn=process_static_image,
                inputs=[static_image_input, vis_type_static],
                outputs=[output_static_image, output_plot_static],
            )

        gr.Markdown("### Instructions")
        with gr.Accordion("Help", open=False):
            gr.Markdown(
                "- **Select Video**: Choose a video file from the dropdown\n- **Visualization Type**: \n    - **Bar**: Shows similarity scores for recognized faces\n    - **Scatter**: Shows UMAP projection of face embeddings\n- **Frame Timeline**: Drag to navigate through the video\n- **Play/Pause**: Control video playback\n\n"
                "- **Upload Image**: Upload a static image for face recognition\n- **Process Image**: Click to process the uploaded image"
            )
    return demo


if __name__ == "__main__":
    demo = build_gradio_interface()
    demo.launch()
