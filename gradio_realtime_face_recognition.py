import os
import glob
import numpy as np
import cv2
import gradio as gr
import matplotlib.pyplot as plt
from insightface.app import FaceAnalysis
from typing import List, Tuple

# --- Load Gallery Embeddings ---
EMBEDDING_DIR = "source/photo/contestants"
embedding_files = glob.glob(os.path.join(EMBEDDING_DIR, "*_embedding.npy"))
gallery_names = []
gallery_embeddings = []
for f in embedding_files:
    arr = np.load(f)
    arr = arr.flatten()
    if arr.shape == (512,):
        gallery_names.append(os.path.basename(f).replace("_embedding.npy", ""))
        gallery_embeddings.append(arr)
    else:
        print(f"[Warning] Skipping {f}: shape {arr.shape} != (512,)")
if not gallery_embeddings:
    raise RuntimeError("No valid embeddings found in gallery!")
gallery_embeddings = np.stack(gallery_embeddings)

# --- Initialize FaceAnalysis ---
app = FaceAnalysis(providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))


# --- Helper Functions ---
def cosine_similarity(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return np.dot(a, b)


def get_top_matches(face_embedding, top_n=5):
    sims = np.dot(gallery_embeddings, face_embedding / np.linalg.norm(face_embedding))
    top_idx = np.argsort(sims)[::-1][:top_n]
    return [(gallery_names[i], sims[i]) for i in top_idx], sims


def plot_bar(names, sims):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.barh(names[::-1], sims[::-1], color="skyblue")
    ax.set_xlabel("Cosine Similarity")
    ax.set_title("Top Matches")
    plt.tight_layout()
    return fig


def plot_heatmap(sims):
    fig, ax = plt.subplots(figsize=(6, 2))
    im = ax.imshow(sims[np.newaxis, :], aspect="auto", cmap="viridis")
    ax.set_yticks([])
    ax.set_xticks(range(len(gallery_names)))
    ax.set_xticklabels(gallery_names, rotation=90, fontsize=6)
    plt.colorbar(im, ax=ax, orientation="vertical")
    plt.tight_layout()
    return fig


def overlay_faces(frame, faces: List, matches: List[List[Tuple[str, float]]]):
    for face, match in zip(faces, matches):
        box = face.bbox.astype(int)
        name, score = match[0]
        cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        label = f"{name} ({score:.2f})"
        cv2.putText(
            frame,
            label,
            (box[0], box[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
    return frame


def process_frame(frame, vis_type="bar"):
    faces = app.get(frame)
    if not faces:
        return frame, None
    matches = []
    all_sims = []
    for face in faces:
        top, sims = get_top_matches(face.normed_embedding)
        matches.append(top)
        all_sims.append(sims)
    frame = overlay_faces(frame, faces, matches)
    # Visualization: for now, only show for the first face
    if vis_type == "bar":
        fig = plot_bar([n for n, _ in matches[0]], [s for _, s in matches[0]])
    else:
        fig = plot_heatmap(all_sims[0])
    return frame, fig


def gradio_inference(video, vis_type):
    cap = cv2.VideoCapture(video)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        out_frame, fig = process_frame(frame_rgb, vis_type)
        # Convert frame back to BGR for display
        out_frame = cv2.cvtColor(out_frame, cv2.COLOR_RGB2BGR)
        yield out_frame, fig
    cap.release()


def gradio_webcam(frame, vis_type):
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    out_frame, fig = process_frame(frame_rgb, vis_type)
    out_frame = cv2.cvtColor(out_frame, cv2.COLOR_RGB2BGR)
    return out_frame, fig


# --- Gradio Interface ---
with gr.Blocks() as demo:
    gr.Markdown("# Real-Time Face Recognition & Embedding Visualization")
    with gr.Row():
        video_input = gr.Video(
            label="Video Input", sources=["upload"], interactive=True
        )
        webcam_input = gr.Image(sources=["webcam"], label="Webcam Input", interactive=True)
    vis_type = gr.Radio(["bar", "heatmap"], value="bar", label="Visualization Type")
    output_video = gr.Image(label="Output Frame")
    output_plot = gr.Plot(label="Embedding Visualization")

    video_input.change(
        fn=gradio_inference,
        inputs=[video_input, vis_type],
        outputs=[output_video, output_plot],
    )

demo.launch()
