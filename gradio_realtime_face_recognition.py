import os
import glob
import numpy as np
import cv2
import gradio as gr
import matplotlib.pyplot as plt
import pandas as pd

# from insightface.app import FaceAnalysis # Will be replaced by core_detector
from src.core.detector import FaceDetector  # Import the centralized detector
from insightface.app.common import Face as InsightFaceObject  # For type hinting
from typing import List, Tuple  # Added Any for broader compatibility if needed
import time
import matplotlib
from PIL import Image, ImageDraw, ImageFont
import random

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

# Path to a CJKV-supporting font (adjust as needed)
CJKV_FONT_PATH = "fonts/SourceHanSansTC-VF.ttf"  # Update this path to a valid CJKV font on your system
FONT_SIZE = 60

# --- Load Contestant Info ---
CONTESTANT_INFO_PATH = "contestant_info.csv"
contestant_info_df = pd.read_csv(CONTESTANT_INFO_PATH)
# Create a mapping from nickname (used in embedding filenames) to actual name
nickname_to_name = pd.Series(contestant_info_df["姓名"].values, index=contestant_info_df["暱稱"]).to_dict()

# --- Load Gallery Embeddings ---
EMBEDDING_DIR = "source/photo/contestants"
# Look for embeddings in the generated directories
embedding_files = glob.glob(os.path.join(EMBEDDING_DIR, "*", "generated", "*_embedding.npy"), recursive=True)
gallery_nicknames = [] # Store nicknames corresponding to embeddings
gallery_display_names = [] # Store actual names for display
gallery_embeddings = []

for f in embedding_files:
    arr = np.load(f)
    arr = arr.flatten()
    if arr.shape == (512,):
        nickname = os.path.basename(f).replace("_embedding.npy", "")
        gallery_nicknames.append(nickname)
        # Use actual name if available, otherwise fallback to nickname
        display_name = nickname_to_name.get(nickname, nickname)
        gallery_display_names.append(display_name)
        gallery_embeddings.append(arr)
    else:
        # Print full path for problematic files
        full_path = os.path.abspath(f)
        print(
            f"[Warning] Skipping embedding file {full_path}: shape {arr.shape} != (512,)"
        )

if not gallery_embeddings:
    print("[ERROR] No embeddings found in gallery! Face recognition will not work.")
    # Initialize gallery_embeddings as an empty array with correct dimensions to avoid later errors
    gallery_embeddings = np.empty((0, 512), dtype=np.float32)
    # gallery_display_names remains an empty list
else:
    print(f"Loaded {len(gallery_embeddings)} embeddings from gallery. Display names: {gallery_display_names[:5]}...") # Print first 5 for brevity
    gallery_embeddings = np.stack(gallery_embeddings)
    print(f"[DEBUG] Gallery embeddings shape: {gallery_embeddings.shape}")
    if len(gallery_embeddings) > 0:
        print(f"[DEBUG] Sample gallery embedding (first one) shape: {gallery_embeddings[0].shape}, dtype: {gallery_embeddings[0].dtype}")
        print(f"[DEBUG] Sample gallery embedding (first one) norm: {np.linalg.norm(gallery_embeddings[0])}")


# --- Initialize Centralized FaceDetector ---
# Configure to use InsightFace backend, matching previous settings
core_detector = FaceDetector(
    backend=FaceDetector.BACKEND_INSIGHTFACE,
    model_size=(640, 640),  # Standard size for InsightFace
    device="auto",  # 'auto' will try CUDA first, then CPU
)
# Note: The FaceAnalysis object 'app' is no longer needed globally.
# The core_detector now manages its own instance of FaceAnalysis.

RECOGNITION_THRESHOLD = 0.02  # Changed from 0.02, consistent with FaceRecognizer

# --- Helper Functions ---
def cosine_similarity(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return np.dot(a, b)


def get_top_matches(face_embedding, top_n=5):
    # Ensure face_embedding is normalized before dot product if not already
    norm_face_embedding = face_embedding / np.linalg.norm(face_embedding)
    sims = np.dot(gallery_embeddings, norm_face_embedding) # gallery_embeddings are assumed normalized or handled by dot product correctly
    top_idx = np.argsort(sims)[::-1][:top_n]
    # Use gallery_display_names for the names
    filtered = [(gallery_display_names[i], sims[i]) for i in top_idx if sims[i] >= RECOGNITION_THRESHOLD]
    return filtered, sims


def plot_bar(names, sims):
    if not names or not sims:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.text(0.5, 0.5, "No data to display", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.barh(names[::-1], sims[::-1], color="skyblue")
    ax.set_xlabel("Cosine Similarity")
    ax.set_title("Top Matches")
    plt.tight_layout()
    return fig


def plot_heatmap(all_sims):
    if not all_sims or not gallery_display_names: # Use gallery_display_names
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, "No data to display", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

    sims_matrix = np.stack(all_sims)
    if sims_matrix.ndim < 2 or sims_matrix.shape[0] == 0 or sims_matrix.shape[1] == 0:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, "Insufficient data for heatmap", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

    fig, ax = plt.subplots(
        figsize=(max(6, len(gallery_display_names) * 0.3), 1 + len(all_sims) * 0.5) # Use gallery_display_names
    )
    im = ax.imshow(sims_matrix, aspect="auto", cmap="viridis")
    # Y-axis: Detected faces
    y_labels = [f"Face {i + 1}" for i in range(len(all_sims))]
    ax.set_yticks(range(len(all_sims)))
    ax.set_yticklabels(y_labels)
    # X-axis: Gallery names
    ax.set_xticks(range(len(gallery_display_names))) # Use gallery_display_names
    ax.set_xticklabels(gallery_display_names, rotation=90, fontsize=6) # Use gallery_display_names
    plt.colorbar(im, ax=ax, orientation="vertical", label="Cosine Similarity")
    ax.set_xlabel("Gallery Embeddings")
    ax.set_title("Similarity of Detected Faces to Gallery Embeddings")
    plt.tight_layout()
    return fig


def overlay_faces(
    frame, faces: List[InsightFaceObject], matches: List[List[Tuple[str, float]]]
):
    # Convert frame to PIL Image for CJKV text
    frame_pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(frame_pil)
    try:
        font = ImageFont.truetype(CJKV_FONT_PATH, FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()
    for face, match_list in zip(
        faces, matches
    ):  # Renamed match to match_list for clarity
        box = face.bbox.astype(int)

        if match_list:  # Check if match_list is not empty
            name, score = match_list[0]
            label = f"{name} ({score:.2f})"
        else:  # Handle empty match_list (no match found)
            name = "Unknown"
            score = 0.0
            label = f"{name} ({score:.2f})"

        # Draw rectangle with cv2
        # It's more efficient to convert to np.array once after all drawing if possible,
        # but current structure modifies frame_pil in loop. Let's keep it for now.
        current_frame_np = np.array(frame_pil)
        cv2.rectangle(current_frame_np, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2) # pylint: disable=no-member
        frame_pil = Image.fromarray(current_frame_np)  # Convert back to PIL Image
        draw = ImageDraw.Draw(
            frame_pil
        )  # Re-initialize draw object on the (potentially) new frame_pil

        # Draw CJKV label with PIL
        draw.text((box[0], box[1] - FONT_SIZE - 2), label, font=font, fill=(0, 255, 0))
    return np.array(frame_pil)


def process_frame(frame, vis_type="bar"):
    print(f"\n[DEBUG] --- process_frame called. Visualization type: {vis_type} ---")
    # Use the centralized detector. It returns a list of InsightFaceObject instances.
    print("[DEBUG] Calling core_detector.detect_faces()...")
    raw_detected_faces = core_detector.detect_faces(frame)
    print(f"[DEBUG] core_detector.detect_faces() returned {len(raw_detected_faces)} raw faces.")

    if not raw_detected_faces:
        print("[DEBUG] No raw faces detected by core_detector.")
        # No faces detected at all
        fig, ax = plt.subplots(figsize=(4, 3) if vis_type == "bar" else (6, 2))
        ax.text(0.5, 0.5, "No faces detected", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return frame, fig

    # Filter faces by detection score
    # InsightFaceObject has a 'det_score' attribute
    DETECTION_SCORE_THRESHOLD = 0.2  # This threshold might need tuning
    print(f"[DEBUG] Filtering raw faces with DETECTION_SCORE_THRESHOLD = {DETECTION_SCORE_THRESHOLD}")
    detected_faces = []
    for i, face in enumerate(raw_detected_faces):
        if hasattr(face, "det_score"):
            print(f"[DEBUG] Raw Face {i+1} det_score: {face.det_score:.4f}")
            if face.det_score >= DETECTION_SCORE_THRESHOLD:
                detected_faces.append(face)
            else:
                print(f"[DEBUG] Raw Face {i+1} REJECTED (score < threshold)")
        else:
            print(f"[DEBUG] Raw Face {i+1} has no det_score attribute, keeping it for now (check detector logic if this is unexpected).")
            detected_faces.append(face) # Keep if no score, might be from a different detector type or logic

    print(f"[DEBUG] Number of faces after detection score filtering: {len(detected_faces)}")

    if not detected_faces:  # If no faces meet the threshold
        print(f"[DEBUG] No faces met the detection score threshold of {DETECTION_SCORE_THRESHOLD}.")
        fig, ax = plt.subplots(figsize=(4, 3) if vis_type == "bar" else (6, 2))
        ax.text(0.5, 0.5, f"No faces above score threshold ({DETECTION_SCORE_THRESHOLD})", ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return frame, fig

    matches = []
    all_sims = []
    print(f"[DEBUG] Processing {len(detected_faces)} filtered faces for recognition.")
    for i, face in enumerate(detected_faces):  # Iterate through filtered InsightFaceObject instances
        print(f"[DEBUG] Face {i+1}/{len(detected_faces)}:")
        if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
            print(f"[DEBUG]   normed_embedding shape: {face.normed_embedding.shape}, dtype: {face.normed_embedding.dtype}")
            print(f"[DEBUG]   normed_embedding norm: {np.linalg.norm(face.normed_embedding):.4f}")
            # face.normed_embedding and face.bbox are available directly
            top, sims = get_top_matches(face.normed_embedding)
            print(f"[DEBUG]   get_top_matches returned {len(top)} matches (after RECOGNITION_THRESHOLD {RECOGNITION_THRESHOLD}).")
            if top:
                for name, score in top:
                    print(f"[DEBUG]     Match: {name}, Score: {score:.4f}")
            else:
                print(f"[DEBUG]     No matches found above threshold for this face.")
            print(f"[DEBUG]   Raw similarities for this face (all gallery items): {sims[:10]}... (len: {len(sims)})") # Print first 10 raw sims
            matches.append(top)
            all_sims.append(sims)
        else:
            print(f"[DEBUG]   Face {i+1} does not have 'normed_embedding' or it is None. Skipping recognition for this face.")
            matches.append([]) # Add empty list for this face if no embedding
            all_sims.append(np.array([])) # Add empty array for sims

    print(f"[DEBUG] Final 'matches' list (top matches for each detected face): {matches}")
    print(f"[DEBUG] Final 'all_sims' list length: {len(all_sims)}")

    frame = overlay_faces(
        frame, detected_faces, matches
    )  # Pass filtered detected_faces

    # Visualization
    # Check if any face had any matches. matches is a list of lists.
    # any_match_found = any(match_list for match_list in matches)
    # Simplified: if matches itself is not empty and its first element (matches for the first detected face) is not empty.

    if not any(matches): # If all sublists in 'matches' are empty (no face had any match)
        print("[DEBUG] No recognized matches for any detected faces after processing all.")
        fig, ax = plt.subplots(figsize=(4, 3) if vis_type == "bar" else (6, 2))
        ax.text(0.5, 0.5, "No recognized matches for detected faces", ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        # Still return the frame with bounding boxes for detected (but unrecognized) faces
        return frame, fig

    if vis_type == "bar":
        # Plot for the first detected face that has matches
        first_face_with_matches = next((m for m in matches if m), None)
        if first_face_with_matches:
            fig = plot_bar([n for n, _ in first_face_with_matches], [s for _, s in first_face_with_matches])
        else:
            # This case should ideally be caught by "any(matches)" check above,
            # but as a fallback:
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.text(0.5, 0.5, "No top matches for display", ha="center", va="center", fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
            plt.tight_layout()
    else: # heatmap
        # plot_heatmap can handle empty or insufficient all_sims internally
        fig = plot_heatmap(all_sims)
    return frame, fig


# --- Gradio Interface ---
# List available mp4 files in source/videos
VIDEO_DIR = "source/videos"
video_files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4")]
video_paths = {f: os.path.join(VIDEO_DIR, f) for f in video_files}


# Helper to get total frames for a video
def get_total_frames(video_path):
    cap = cv2.VideoCapture(video_path) # pylint: disable=no-member
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) # pylint: disable=no-member
    cap.release()
    return total


# Helper to get a specific frame by index
def get_frame_by_index(video_path, frame_idx, vis_type="bar"):  # Added vis_type
    cap = cv2.VideoCapture(video_path) # pylint: disable=no-member
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx) # pylint: disable=no-member
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # pylint: disable=no-member
    out_frame, fig = process_frame(frame_rgb, vis_type=vis_type)  # Pass vis_type
    return out_frame, fig


with gr.Blocks() as demo:
    gr.Markdown("# Real-Time Face Recognition & Embedding Visualization")
    with gr.Row():
        video_dropdown = gr.Dropdown(
            choices=video_files,
            label="Select Video File",
            value=video_files[0] if video_files else None,
            interactive=True,
        )
    vis_type = gr.Radio(["bar", "heatmap"], value="bar", label="Visualization Type")
    frame_slider = gr.Slider(
        minimum=0, maximum=1, value=0, step=1, label="Frame Timeline", interactive=True
    )
    play_btn = gr.Button("Play")
    pause_btn = gr.Button("Pause")
    output_video = gr.Image(label="Output Frame")
    output_plot = gr.Plot(label="Embedding Visualization")
    state = gr.State({"playing": False, "frame": 0, "total": 1})

    def update_slider_on_video(selected_video):
        video_path = video_paths[selected_video]
        total = get_total_frames(video_path)
        return gr.update(maximum=total - 1, value=0), {
            "playing": False,
            "frame": 0,
            "total": total,
        }

    def update_frame(selected_video, frame_idx, vis_type):
        video_path = video_paths[selected_video]
        result = get_frame_by_index(video_path, frame_idx, vis_type)  # Pass vis_type
        if result is None:
            return None, None
        out_frame, fig = result
        return out_frame, fig

    def play_loop(selected_video, vis_type, state):
        video_path = video_paths[selected_video]
        total = state["total"]
        frame = state["frame"]
        while state["playing"] and frame < total:
            result = get_frame_by_index(video_path, frame, vis_type)  # Pass vis_type
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

    video_dropdown.change(fn=update_slider_on_video, inputs=[video_dropdown], outputs=[frame_slider, state]) # pylint: disable=no-member
    frame_slider.change(fn=update_frame, inputs=[video_dropdown, frame_slider, vis_type], outputs=[output_video, output_plot]) # pylint: disable=no-member
    vis_type.change(fn=update_frame, inputs=[video_dropdown, frame_slider, vis_type], outputs=[output_video, output_plot]) # pylint: disable=no-member
    play_btn.click(fn=play_loop, inputs=[video_dropdown, vis_type, state], outputs=[output_video, output_plot, frame_slider, state], api_name=False) # pylint: disable=no-member
    pause_btn.click(fn=lambda s: {"playing": False, "frame": s["frame"], "total": s["total"]}, inputs=[state], outputs=[state], api_name=False) # pylint: disable=no-member

demo.launch()
