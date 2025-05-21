#!/usr/bin/env python
"""
Face Recognition Gradio Web Interface

This module provides a Gradio-based web interface for real-time face recognition
using the cosine similarity backend and visualization options.
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
import pandas as pd # Added pandas for contestant info
from insightface.app import FaceAnalysis # Using InsightFace for detection and embedding computation
from PIL import Image, ImageDraw, ImageFont # For drawing text on images

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
        plot_bar,
        plot_embedding_scatter,
        draw_faces_with_labels,
    )
except ImportError:
    logger.warning("Could not import gradio_visualization. Using placeholder functions.")
    def plot_bar(data): return None
    def plot_embedding_scatter(*args, **kwargs): return None
    def draw_faces_with_labels(frame, face_results): return frame

# Global variables
try:
    app = FaceAnalysis(providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    logger.info("InsightFace app initialized.")
except Exception as e:
    logger.error(f"Error initializing InsightFace app: {e}")
    app = None

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")
fonts_dir = os.path.join(project_root, "fonts")

try:
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info["暱稱"].tolist()
    logger.info(f"Loaded contestant info from {contestant_info_path}")
except FileNotFoundError:
    all_contestants = []
    logger.error(f"Error: {contestant_info_path} not found.")

def get_video_files(video_dir: str = videos_dir) -> Dict[str, str]:
    os.makedirs(video_dir, exist_ok=True)
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    video_files = {}
    for file in os.listdir(video_dir):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            file_path = os.path.join(video_dir, file)
            video_files[file] = file_path
    if not video_files:
        logger.warning(f"No video files found in {video_dir}")
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
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith((".jpg", ".png"))
    ]

def compute_embeddings_mv(image_paths):
    embeddings = []
    if app is None:
        logger.error("InsightFace app not initialized. Cannot compute embeddings.")
        return embeddings
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is None:
                logger.warning(f"Failed to read image: {img_path}")
                continue
            faces = app.get(img)
            embeddings.extend([face.normed_embedding for face in faces])
        except Exception as e:
            logger.error(f"Error processing {img_path}: {e}")
    return embeddings

def get_known_faces_embeddings_mv(contestants_dir, selected_contestants, contestant_info):
    known_embeddings = {}
    if contestant_info.empty:
        logger.warning("Contestant info is empty. Cannot load embeddings.")
        return known_embeddings

    for contestant_name in selected_contestants:
        if contestant_name not in contestant_info["暱稱"].values:
            logger.warning(f"Warning: Contestant '{contestant_name}' not found in contestant info. Skipping.")
            continue

        contestant_row = contestant_info.loc[contestant_info["暱稱"] == contestant_name]
        if contestant_row.empty:
             logger.warning(f"Could not find row for contestant '{contestant_name}' in info file. Skipping.")
             continue

        contestant_number = contestant_row["編號"].values[0]
        contestant_path = os.path.join(contestants_dir, str(contestant_number))

        if not os.path.isdir(contestant_path):
            logger.warning(f"Warning: Directory for contestant '{contestant_name}' not found: {contestant_path}. Skipping.")
            continue

        embedding_file = os.path.join(contestant_path, f"{contestant_name}_embedding.npy")
        if os.path.exists(embedding_file):
            try:
                embedding = np.load(embedding_file, allow_pickle=True)
                if not isinstance(embedding, list):
                     embedding = [embedding]
                known_embeddings[contestant_name] = embedding
                logger.info(f"Loaded cached embedding for {contestant_name}.")
                continue
            except Exception as e:
                logger.error(f"Error loading cached embedding for {contestant_name}: {e}. Recomputing.")

        image_paths = get_image_paths_mv(contestant_path)
        embeddings = compute_embeddings_mv(image_paths)
        if embeddings:
            known_embeddings[contestant_name] = embeddings
            try:
                np.save(embedding_file, embeddings)
                logger.info(f"Computed and saved embedding for {contestant_name}.")
            except Exception as e:
                logger.error(f"Error saving embedding for {contestant_name}: {e}")
        else:
            logger.warning(f"Could not compute embedding for {contestant_name} from images in {contestant_path}")

    return known_embeddings

def match_face_mv(face_embedding, known_embeddings, distance_threshold):
    best_match = None
    best_score = -1

    if not known_embeddings:
        return None, 0.0

    for name, embeddings_list in known_embeddings.items():
        for known_embedding in embeddings_list:
            if isinstance(known_embedding, np.ndarray) and known_embedding.size > 0:
                 if known_embedding.ndim > 1:
                     known_embedding = known_embedding.flatten()
                 if face_embedding.ndim > 1:
                     face_embedding = face_embedding.flatten()
                 if face_embedding.dtype != np.float32:
                     face_embedding = face_embedding.astype(np.float32)
                 if known_embedding.dtype != np.float32:
                     known_embedding = known_embedding.astype(np.float32)
                 norm_face = np.linalg.norm(face_embedding)
                 norm_known = np.linalg.norm(known_embedding)
                 if norm_face > 1e-10 and norm_known > 1e-10:
                     similarity = np.dot(face_embedding, known_embedding) / (norm_face * norm_known)
                 else:
                     similarity = 0.0
                 if similarity > distance_threshold and similarity > best_score:
                     best_match = name
                     best_score = similarity

    return best_match, best_score

def draw_boxes_and_labels_mv(frame, matches, timestamp):
    try:
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        font_path = os.path.join(fonts_dir, "SourceHanSansTC-VF.ttf")
        if not os.path.exists(font_path):
             logger.warning(f"Font file not found: {font_path}. Using default font.")
             label_font = ImageFont.load_default()
             timestamp_font = ImageFont.load_default()
        else:
             label_font = ImageFont.truetype(font_path, 60)
             timestamp_font = ImageFont.truetype(font_path, 40)
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
            try:
                text_bbox_coords = draw.textbbox((text_x, text_y), label_text, font=label_font)
                draw.rectangle(text_bbox_coords, fill="green")
            except AttributeError:
                 text_width, text_height = draw.textsize(label_text, font=label_font)
                 draw.rectangle([(text_x, text_y), (text_x + text_width, text_y + text_height)], fill="green")
            draw.text(
                (text_x, text_y),
                label_text,
                font=label_font,
                fill="white",
            )
        timestamp_color = "yellow"
        img_width, img_height = pil_img.size
        timestamp_text = f"Frame: {timestamp}"
        try:
            text_bbox_coords = draw.textbbox((0, 0), timestamp_text, font=timestamp_font)
            text_width = text_bbox_coords[2] - text_bbox_coords[0]
            text_height = text_bbox_coords[3] - text_bbox_coords[1]
        except AttributeError:
            text_width, text_height = draw.textsize(timestamp_text, font=timestamp_font)
        position = (img_width - text_width - 10, img_height - text_height - 10)
        draw.text(position, timestamp_text, font=timestamp_font, fill=timestamp_color)
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return frame
    except Exception as e:
        logger.error(f"Error drawing boxes and labels: {e}")
        logger.error(traceback.format_exc())
        return frame

def format_stats_for_display() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = PROCESSING_STATS.copy()
    html = """
    <div style="font-family: sans-serif; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
        <h3 style="margin-top: 0;">Performance Statistics</h3>
        <table style="width: 100%; border-collapse: collapse;">
    """
    metrics = [
        ("Processed Frames", f"{stats['processed_frames']}", None),
        ("FPS", f"{stats.get('fps', 0):.2f}",
         "red" if stats.get('fps', 0) < 5 else "orange" if stats.get('fps', 0) < 15 else "green"),
        ("Detection Time", f"{stats.get('avg_detection_time', 0):.1f} ms",
         "red" if stats.get('avg_detection_time', 0) > 100 else "orange" if stats.get('avg_detection_time', 0) > 50 else "green"),
        ("Recognition Time", f"{stats.get('avg_recognition_time', 0):.1f} ms",
         "red" if stats.get('avg_recognition_time', 0) > 100 else "orange" if stats.get('avg_recognition_time', 0) > 50 else "green"),
        ("Total Processing Time", f"{stats.get('avg_total_time', 0):.1f} ms",
         "red" if stats.get('avg_total_time', 0) > 200 else "orange" if stats.get('avg_total_time', 0) > 100 else "green"),
        ("Faces Detected", f"{stats['faces_detected']}", None),
        ("Faces Recognized", f"{stats['faces_recognized']}", None),
        ("Recognition Rate", f"{stats.get('recognition_rate', 0):.1%}",
         "red" if stats.get('recognition_rate', 0) < 0.3 else "orange" if stats.get('recognition_rate', 0) < 0.7 else "green"),
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
    with STATUS_LOCK:
        for key in PROCESSING_STATS:
            if key != "start_time":
                PROCESSING_STATS[key] = 0
        PROCESSING_STATS["start_time"] = time.time()
    return format_stats_for_display()

# (Rest of the file unchanged, as the main syntax error was due to a missing except/finally block in a try statement.)
