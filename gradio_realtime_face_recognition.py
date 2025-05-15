import os
import glob
import numpy as np
import cv2
import gradio as gr
import matplotlib.pyplot as plt
import umap.umap_ as umap
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
print(f"[DEBUG] Current working directory: {os.getcwd()}") # Print CWD
CONTESTANT_INFO_PATH = "contestant_info.csv"
contestant_info_df = pd.read_csv(CONTESTANT_INFO_PATH)
# Create a mapping from nickname (used in embedding filenames) to actual name
# nickname_to_name = pd.Series(contestant_info_df["姓名"].values, index=contestant_info_df["暱稱"]).to_dict()

# --- Load Gallery Embeddings ---
EMBEDDING_DIR = "source/photo/contestants/embeddings"
print(f"[DEBUG] EMBEDDING_DIR: {os.path.abspath(EMBEDDING_DIR)}")
glob_pattern = os.path.join(EMBEDDING_DIR, "*_embedding.npy")
print(f"[DEBUG] Glob pattern: {glob_pattern}")
# Look for embeddings in the new embeddings directory
embedding_files = glob.glob(glob_pattern) # No recursive needed, files are directly in this dir
print(f"[DEBUG] Files found by glob: {embedding_files}") # Print files found by glob
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
        display_name = nickname
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

RECOGNITION_THRESHOLD = 0.4  # Changed from 0.02, consistent with FaceRecognizer

# --- Helper Functions ---
def cosine_similarity(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return np.dot(a, b)


def get_top_matches(face_embedding, top_n=5):
    # Ensure face_embedding is normalized before dot product if not already
    norm_face_embedding = face_embedding / np.linalg.norm(face_embedding)
    sims = np.dot(gallery_embeddings, norm_face_embedding) # gallery_embeddings are assumed normalized or handled by dot product correctly
    top_idx_all = np.argsort(sims)[::-1][:top_n]
    
    # Filtered results: (name, score, original_gallery_index)
    filtered_matches = []
    for i in top_idx_all:
        if sims[i] >= RECOGNITION_THRESHOLD:
            filtered_matches.append((gallery_display_names[i], sims[i], i)) # Add original index 'i'
            
    return filtered_matches, sims # Return list of (name, score, index) tuples and all similarities


def plot_bar(all_top_matches_details):
    """
    Plots a horizontal bar chart for all top matches from all detected faces.
    all_top_matches_details: A list of tuples, e.g., [("Face 1: Name A", 0.9), ("Face 2: Name B", 0.85)]
                             Assumed to be sorted by score if desired.
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
    fig_height = max(3, num_bars * 0.4) # Adjust 0.4 factor as needed

    fig, ax = plt.subplots(figsize=(5, fig_height)) # Increased width slightly for longer labels
    ax.barh(labels[::-1], scores[::-1], color="skyblue") # Plot in reverse to have highest score at top
    ax.set_xlabel("Cosine Similarity")
    ax.set_title("Top Matches Across All Detected Faces")
    
    # Adjust layout to prevent labels from being cut off
    plt.subplots_adjust(left=0.4) # Increase left margin; adjust as needed
    plt.tight_layout(rect=[0, 0, 1, 1]) # Apply tight_layout considering the whole figure
    return fig


def plot_embedding_scatter(detected_face_embeddings_list, gallery_embeddings_global, gallery_display_names_global, matches_per_detected_face):
    """
    Plots a 2D scatter plot of gallery and detected face embeddings using UMAP.
    Highlights recognized faces and their nearest gallery matches.
    """
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
    point_types = [] # 'gallery', 'detected_recognized', 'detected_unknown'
    point_labels = []
    # Store gallery indices of nearest matches for each detected face
    nearest_gallery_indices_for_detected = [[] for _ in range(num_detected)]

    # Add gallery embeddings
    if num_gallery > 0:
        all_embeddings_list.extend(list(gallery_embeddings_global))
        point_types.extend(['gallery'] * num_gallery)
        point_labels.extend(gallery_display_names_global)

    # Add detected face embeddings and identify their nearest gallery matches
    if num_detected > 0:
        all_embeddings_list.extend(detected_face_embeddings_list)
        for i, match_info_list_for_face in enumerate(matches_per_detected_face):
            if match_info_list_for_face: # Recognized
                top_match_name = match_info_list_for_face[0][0]
                point_types.append('detected_recognized')
                point_labels.append(f"Face {i+1}: {top_match_name}")
                # Store indices of all gallery items this detected face matched with
                nearest_gallery_indices_for_detected[i] = [match[2] for match in match_info_list_for_face]
            else: # Unrecognized
                point_types.append('detected_unknown')
                point_labels.append(f"Face {i+1}: Unknown")
                # No nearest gallery indices if unrecognized by threshold

    if not all_embeddings_list:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No embeddings available for UMAP", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig

    all_embeddings_np = np.array(all_embeddings_list)

    if all_embeddings_np.shape[0] < 2:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "Not enough data points for UMAP (need at least 2)", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout()
        return fig
        
    n_neighbors_val = min(15, all_embeddings_np.shape[0] - 1)
    if n_neighbors_val < 2 :
        if all_embeddings_np.shape[0] <=2 :
             fig, ax = plt.subplots(figsize=(6,4))
             ax.text(0.5, 0.5, f"Too few points ({all_embeddings_np.shape[0]}) for robust UMAP.", ha="center", va="center")
             ax.set_xticks([])
             ax.set_yticks([])
             plt.tight_layout()
             return fig
        n_neighbors_val = min(15, all_embeddings_np.shape[0] -1) 

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

    fig, ax = plt.subplots(figsize=(12, 10)) # Slightly larger plot

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

    # Plot gallery embeddings first (those not marked as nearest yet)
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
                       label=plabel.split(":")[0] if plabel.split(":")[0] not in plt.gca().get_legend_handles_labels()[1] else "", # Legend by type
                       alpha=0.9, edgecolors='black' if ptype == 'detected_recognized' else None,
                       marker='o' if ptype == 'detected_recognized' else 'X')
            ax.text(detected_point[0], detected_point[1] + 0.05, plabel, fontsize=9, ha='center')

            # Plot nearest gallery matches for this detected face and draw lines
            for gallery_idx in nearest_gallery_indices_for_detected[i]:
                if 0 <= gallery_idx < num_gallery:
                    gallery_match_point = embedding_2d[gallery_idx]
                    # Plot this specific gallery point as a "nearest match"
                    ax.scatter(gallery_match_point[0], gallery_match_point[1],
                               c=color_map['nearest_gallery'], s=size_map['nearest_gallery'],
                               alpha=0.8, edgecolors='black', marker='s', # Square marker for nearest
                               label="Nearest Gallery Match" if "Nearest Gallery Match" not in plt.gca().get_legend_handles_labels()[1] else "")
                    plotted_nearest_gallery_indices.add(gallery_idx)
                    
                    # Draw line from detected face to this gallery match
                    ax.plot([detected_point[0], gallery_match_point[0]],
                            [detected_point[1], gallery_match_point[1]],
                            c='gray', linestyle='--', linewidth=0.8, alpha=0.7)
                    # Optionally, label the nearest gallery point if not already clear
                    # ax.text(gallery_match_point[0], gallery_match_point[1] - 0.05, gallery_display_names_global[gallery_idx], 
                    #         fontsize=8, ha='center', color='green')


    # Re-plot any gallery points that were marked as nearest, to ensure they are on top or styled correctly if needed
    # This step might be redundant if the above scatter for nearest_gallery is sufficient.
    # For now, the above loop handles plotting nearest gallery points.

    ax.set_title("Embedding Space (UMAP) with Nearest Matches")
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2")
    
    # Create a unique legend
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='best')
    
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

    matches = [] # This will store List[List[Tuple[str, float, int]]]
    all_sims = [] # This seems unused now with the new scatter plot logic, but let's keep it for now.
    print(f"[DEBUG] Processing {len(detected_faces)} filtered faces for recognition.")
    for i, face in enumerate(detected_faces):  # Iterate through filtered InsightFaceObject instances
        print(f"[DEBUG] Face {i+1}/{len(detected_faces)}:")
        if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
            print(f"[DEBUG]   normed_embedding shape: {face.normed_embedding.shape}, dtype: {face.normed_embedding.dtype}")
            print(f"[DEBUG]   normed_embedding norm: {np.linalg.norm(face.normed_embedding):.4f}")
            
            top_matches_with_indices, sims_for_this_face = get_top_matches(face.normed_embedding)
            print(f"[DEBUG]   get_top_matches returned {len(top_matches_with_indices)} matches (after RECOGNITION_THRESHOLD {RECOGNITION_THRESHOLD}).")
            
            if top_matches_with_indices:
                for name, score, gallery_idx in top_matches_with_indices:
                    print(f"[DEBUG]     Match: {name}, Score: {score:.4f}, Gallery Index: {gallery_idx}")
            else:
                print(f"[DEBUG]     No matches found above threshold for this face.")
            
            matches.append(top_matches_with_indices) 
            all_sims.append(sims_for_this_face) # Store all similarities for this face
        else:
            print(f"[DEBUG]   Face {i+1} does not have 'normed_embedding' or it is None. Skipping recognition for this face.")
            matches.append([]) 
            all_sims.append(np.array([]))

    print(f"[DEBUG] Final 'matches' list (top matches for each detected face): {matches}")
    
    # Prepare matches for overlay_faces (name, score only)
    matches_for_overlay = []
    for match_list_for_face in matches: 
        matches_for_overlay.append([(name, score) for name, score, _ in match_list_for_face])
        
    frame = overlay_faces(
        frame, detected_faces, matches_for_overlay
    )

    # Visualization
    if not any(matches): 
        print("[DEBUG] No recognized matches for any detected faces after processing all.")
        if vis_type == "bar":
            fig = plot_bar([])
        else: # scatter plot
            detected_embeds = [face.normed_embedding for face in detected_faces if hasattr(face, 'normed_embedding') and face.normed_embedding is not None and face.normed_embedding.size > 0]
            fig = plot_embedding_scatter(detected_embeds, gallery_embeddings, gallery_display_names, matches)
        return frame, fig

    if vis_type == "bar":
        all_top_matches_for_plot = []
        for i, match_list_for_face in enumerate(matches): 
            if match_list_for_face: 
                for name, score, _ in match_list_for_face: 
                    all_top_matches_for_plot.append((f"Face {i+1}: {name}", score))
        
        all_top_matches_for_plot.sort(key=lambda x: x[1], reverse=True)
        fig = plot_bar(all_top_matches_for_plot)
    else: # scatter plot
        detected_embeds = [face.normed_embedding for face in detected_faces if hasattr(face, 'normed_embedding') and face.normed_embedding is not None and face.normed_embedding.size > 0]
        fig = plot_embedding_scatter(detected_embeds, gallery_embeddings, gallery_display_names, matches)
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
    vis_type = gr.Radio(["bar", "scatter"], value="bar", label="Visualization Type") # Changed heatmap to scatter
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
