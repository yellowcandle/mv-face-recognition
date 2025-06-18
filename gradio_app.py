"""
Modern Gradio Web Interface for MV Face Recognition System.
Provides real-time camera processing, image/video analysis, and configuration management.
"""

import warnings

# Suppress warnings BEFORE any other imports
warnings.filterwarnings("ignore", message=".*rcond.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="insightface")
warnings.filterwarnings("ignore", message=".*Albumentations.*")
warnings.filterwarnings("ignore", category=UserWarning, module="albumentations")
warnings.filterwarnings("ignore", message=".*browser-compatible.*")
warnings.filterwarnings("ignore", message=".*does not have browser-compatible.*")
warnings.filterwarnings(
    "ignore", category=UserWarning, module="gradio.components.video"
)
warnings.filterwarnings("ignore", category=UserWarning, module="gradio")

import gradio as gr
import cv2
import numpy as np
import pandas as pd
import os
import logging
from typing import Optional, Any
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import tempfile
from PIL import Image, ImageDraw, ImageFont

# Hugging Face Spaces GPU support
try:
    import spaces
    HF_SPACES_GPU = True
except ImportError:
    # Fallback decorator for local development
    def spaces_gpu_decorator(func):
        return func
    spaces = type('spaces', (), {'GPU': spaces_gpu_decorator})()
    HF_SPACES_GPU = False

# GPU error handling decorator
def gpu_safe_decorator(func):
    """Decorator to handle GPU errors and fallback to CPU."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "GPU" in str(e) or "CUDA" in str(e) or "ZeroGPU" in str(e):
                print(f"GPU error in {func.__name__}: {e}")
                print("Falling back to CPU processing...")
                # Clear GPU memory if possible
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except:
                    pass
                # Re-run without GPU acceleration
                return func(*args, **kwargs)
            else:
                raise e
    return wrapper

# Import our modular components
try:
    from src.config.settings import get_config, save_config
    from src.core.face_detector import FaceDetector
    from src.services.visualization import VisualizationService
    from chroma_db import get_contestant_collection
except ImportError as e:
    print(f"Import warning: {e}")
    # Fallback imports for development
    pass

# Global instances to avoid re-initialization
_global_detector = None
_global_cjkv_font = None
_font_cache_info = ""


def get_face_detector():
    """Get or create the global face detector instance."""
    global _global_detector
    if _global_detector is None:
        try:
            config = get_config()
            _global_detector = FaceDetector(config)
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            _global_detector = None
    return _global_detector


@spaces.GPU
@gpu_safe_decorator
def process_frame(
    frame, known_embeddings, similarity_threshold=0.5, return_similarities=False
):
    """Process a video frame and detect/recognize faces with adaptive scaling."""
    try:
        detector = get_face_detector()
        if detector is None:
            return [] if not return_similarities else ([], [])

        # Adaptive resolution scaling for better small face detection
        original_frame = frame.copy()
        h, w = frame.shape[:2]

        # Scale up small frames, keep large frames as-is
        min_dimension = min(h, w)
        if min_dimension < 720:
            # Scale up small videos
            scale_factor = 720 / min_dimension
            new_h, new_w = int(h * scale_factor), int(w * scale_factor)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            logger.debug(
                f"Scaled frame from {w}x{h} to {new_w}x{new_h} for better face detection"
            )
        elif min_dimension > 1920:
            # Scale down very large videos for performance
            scale_factor = 1920 / min_dimension
            new_h, new_w = int(h * scale_factor), int(w * scale_factor)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.debug(
                f"Scaled frame from {w}x{h} to {new_w}x{new_h} for performance"
            )
        else:
            scale_factor = 1.0

        # Detect faces in the (possibly scaled) frame
        faces = detector.detect_faces(frame)

        # Scale bounding boxes back to original frame coordinates if needed
        if scale_factor != 1.0:
            for face in faces:
                if hasattr(face, "bbox"):
                    face.bbox = face.bbox / scale_factor

        matches = []
        frame_similarities = []  # Store all similarity scores for plotting

        for face_idx, face in enumerate(faces):
            try:
                face_embedding = None

                # Try to get embedding from face object first
                if (
                    hasattr(face, "normed_embedding")
                    and face.normed_embedding is not None
                ):
                    face_embedding = face.normed_embedding
                elif hasattr(face, "embedding") and face.embedding is not None:
                    face_embedding = face.embedding

                # If no embedding in face object, extract from face region
                if face_embedding is None:
                    bbox = face.bbox.astype(int)
                    x1, y1, x2, y2 = bbox
                    # Add padding and ensure bounds (use original frame dimensions)
                    orig_h, orig_w = original_frame.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(orig_w, x2), min(orig_h, y2)

                    if x2 > x1 and y2 > y1:
                        face_crop = original_frame[
                            y1:y2, x1:x2
                        ]  # Use original frame for embedding
                        if face_crop.size > 0:
                            face_embedding = detector.extract_face_embedding(face_crop)

                    if face_embedding is None:
                        logger.debug("Could not extract embedding for face")
                        matches.append((face, "Unknown"))
                        continue

                if face_embedding is not None:
                    # Ensure face_embedding is flattened and normalized
                    face_embedding = np.array(face_embedding).flatten()
                    if np.linalg.norm(face_embedding) > 0:
                        face_embedding = face_embedding / np.linalg.norm(face_embedding)

                    # Match against known embeddings and collect all similarities
                    best_match = "Unknown"
                    best_score = 0
                    face_similarities = []

                    for name, known_embedding in known_embeddings.items():
                        try:
                            # Ensure known_embedding is also flattened and normalized
                            known_embedding = np.array(known_embedding).flatten()
                            if np.linalg.norm(known_embedding) > 0:
                                known_embedding = known_embedding / np.linalg.norm(
                                    known_embedding
                                )

                            # Check if dimensions match
                            if face_embedding.shape[0] != known_embedding.shape[0]:
                                logger.debug(
                                    f"Embedding dimension mismatch for {name}: {face_embedding.shape} vs {known_embedding.shape}"
                                )
                                continue

                            # Calculate cosine similarity
                            similarity = np.dot(face_embedding, known_embedding)

                            # Store similarity data for plotting
                            if return_similarities:
                                face_similarities.append(
                                    {
                                        "face_id": f"Face_{face_idx + 1}",
                                        "name": name,
                                        "similarity": float(similarity),
                                        "bbox": face.bbox.tolist()
                                        if hasattr(face, "bbox")
                                        else None,
                                    }
                                )

                            if (
                                similarity > similarity_threshold
                                and similarity > best_score
                            ):
                                best_match = name
                                best_score = similarity
                        except Exception as e:
                            logger.debug(f"Error comparing with {name}: {e}")
                            continue

                    # Add all similarities for this face to the frame data
                    if return_similarities:
                        frame_similarities.extend(face_similarities)

                    matches.append((face, best_match))
            except Exception as e:
                logger.warning(f"Error processing face: {e}")
                matches.append((face, "Unknown"))

        if return_similarities:
            return matches, frame_similarities
        return matches
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return [] if not return_similarities else ([], [])


def calculate_face_similarity(bbox1, bbox2):
    """Calculate similarity between two face bounding boxes for tracking with improved metrics."""
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2

    # Calculate centers
    center1 = ((x1_1 + x2_1) / 2, (y1_1 + y2_1) / 2)
    center2 = ((x1_2 + x2_2) / 2, (y1_2 + y2_2) / 2)

    # Calculate distance between centers
    distance = np.sqrt((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2)

    # Calculate size similarity
    size1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    size2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    size_ratio = min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 0

    # Calculate IoU (Intersection over Union) for better overlap detection
    x_overlap = max(0, min(x2_1, x2_2) - max(x1_1, x1_2))
    y_overlap = max(0, min(y2_1, y2_2) - max(y1_1, y1_2))
    intersection = x_overlap * y_overlap
    union = size1 + size2 - intersection
    iou = intersection / union if union > 0 else 0

    # Weighted combination: distance (40%), size similarity (30%), IoU (30%)
    face_size = max(x2_1 - x1_1, y2_1 - y1_1, 50)
    normalized_distance = distance / face_size

    # Lower score = more similar (good for tracking)
    similarity_score = (
        0.4 * normalized_distance + 0.3 * (1 - size_ratio) + 0.3 * (1 - iou)
    )
    return similarity_score


def calculate_label_positions(labels_to_draw, frame_width, frame_height):
    """Calculate optimal label positions to avoid collisions."""
    positioned_labels = []

    for i, label_info in enumerate(labels_to_draw):
        bbox = label_info["bbox"]
        x1, y1, x2, y2 = bbox

        # Calculate label dimensions (estimate based on name length)
        name = label_info["name"]
        text_width = len(name) * 10 + 20  # Rough estimate
        text_height = 20

        # Preferred position: above the bbox
        preferred_x = x1
        preferred_y = max(y1 - text_height - 5, 5)

        # Check for collisions with previously positioned labels
        best_x, best_y = preferred_x, preferred_y
        collision_found = True
        attempts = 0

        while collision_found and attempts < 10:
            collision_found = False

            # Check against all previously positioned labels
            for prev_label in positioned_labels:
                prev_x, prev_y, prev_w, prev_h = prev_label["position"]

                # Check if rectangles overlap
                if (
                    best_x < prev_x + prev_w
                    and best_x + text_width > prev_x
                    and best_y < prev_y + prev_h
                    and best_y + text_height > prev_y
                ):
                    collision_found = True
                    break

            if collision_found:
                attempts += 1
                # Try different positions
                if attempts == 1:
                    # Try below the bbox
                    best_y = min(y2 + 5, frame_height - text_height - 5)
                elif attempts == 2:
                    # Try left of bbox
                    best_x = max(x1 - text_width - 5, 5)
                    best_y = preferred_y
                elif attempts == 3:
                    # Try right of bbox
                    best_x = min(x2 + 5, frame_width - text_width - 5)
                    best_y = preferred_y
                elif attempts == 4:
                    # Try above-left
                    best_x = max(x1 - text_width // 2, 5)
                    best_y = max(y1 - text_height - 10, 5)
                elif attempts == 5:
                    # Try above-right
                    best_x = min(x2 - text_width // 2, frame_width - text_width - 5)
                    best_y = max(y1 - text_height - 10, 5)
                else:
                    # Stack vertically with offset
                    offset = (attempts - 5) * 25
                    best_y = max(preferred_y - offset, 5)

        # Ensure final position is within frame bounds
        best_x = max(5, min(best_x, frame_width - text_width - 5))
        best_y = max(5, min(best_y, frame_height - text_height - 5))

        # Store the positioned label
        positioned_label = {
            "label_info": label_info,
            "position": (best_x, best_y, text_width, text_height),
            "final_x": best_x,
            "final_y": best_y,
        }
        positioned_labels.append(positioned_label)

    return positioned_labels


def get_confidence_color(confidence, is_current=True):
    """Get color based on confidence level."""
    if confidence >= 0.7:
        # High confidence - green gradient
        if is_current:
            return (0, 255, 0), (0, 255, 0)  # BGR, RGB
        else:
            return (0, 200, 0), (0, 200, 0)
    elif confidence >= 0.4:
        # Medium confidence - yellow/orange gradient
        if is_current:
            return (0, 165, 255), (255, 165, 0)  # BGR, RGB (orange)
        else:
            return (0, 140, 200), (200, 140, 0)
    else:
        # Low confidence - red gradient
        if is_current:
            return (0, 0, 255), (255, 0, 0)  # BGR, RGB
        else:
            return (0, 0, 180), (180, 0, 0)


def calculate_adaptive_opacity(tracking_duration, is_current, confidence):
    """Calculate opacity based on tracking stability."""
    if is_current:
        # Current detections are always more visible
        base_opacity = 1.0
    else:
        # Persistent labels fade based on tracking stability
        base_opacity = 0.7

    # Adjust for tracking duration (more stable = slightly less intrusive)
    if tracking_duration > 30:  # ~1 second at 30fps
        stability_factor = 0.9
    elif tracking_duration > 60:  # ~2 seconds
        stability_factor = 0.8
    else:
        stability_factor = 1.0

    # Adjust for confidence (higher confidence = slightly less intrusive)
    if confidence >= 0.8:
        confidence_factor = 0.9
    elif confidence >= 0.6:
        confidence_factor = 0.95
    else:
        confidence_factor = 1.0  # Low confidence stays visible

    final_opacity = base_opacity * stability_factor * confidence_factor
    return max(0.3, min(1.0, final_opacity))  # Clamp between 30% and 100%


def update_persistent_labels(matches, label_cache, current_frame, persistence_duration):
    """Update the persistent label cache with new detections and smooth tracking."""
    # Clean up expired labels
    expired_keys = [
        key for key, data in label_cache.items() if data["expire_frame"] < current_frame
    ]
    for key in expired_keys:
        del label_cache[key]

    # Process new matches
    for face, name in matches:
        if name == "Unknown":
            continue

        bbox = face.bbox.astype(int)
        face_key = None
        best_similarity = float("inf")

        # Try to match with existing faces - more lenient threshold for smoother tracking
        for existing_key, existing_data in label_cache.items():
            similarity = calculate_face_similarity(bbox, existing_data["bbox"])
            if (
                similarity < 0.8 and similarity < best_similarity
            ):  # More lenient threshold for smoother tracking
                best_similarity = similarity
                face_key = existing_key

        # Create new face key if no match found
        if face_key is None:
            face_key = f"face_{current_frame}_{len(label_cache)}"

        # Smooth bbox transition for existing faces
        if face_key in label_cache:
            old_bbox = label_cache[face_key]["bbox"]
            # Interpolate between old and new bbox for smoother movement
            smooth_factor = 0.7  # 0 = no smoothing, 1 = full smoothing
            smoothed_bbox = [
                int(old_bbox[0] * smooth_factor + bbox[0] * (1 - smooth_factor)),
                int(old_bbox[1] * smooth_factor + bbox[1] * (1 - smooth_factor)),
                int(old_bbox[2] * smooth_factor + bbox[2] * (1 - smooth_factor)),
                int(old_bbox[3] * smooth_factor + bbox[3] * (1 - smooth_factor)),
            ]
            bbox = smoothed_bbox

        # Update or create cache entry
        label_cache[face_key] = {
            "name": name,
            "bbox": bbox,
            "expire_frame": current_frame + persistence_duration,
            "last_seen": current_frame,
            "confidence": getattr(face, "det_score", 1.0)
            if hasattr(face, "det_score")
            else 1.0,
        }

    return label_cache


def draw_rounded_rectangle(img, pt1, pt2, color, thickness, radius=10):
    """Draw a rounded rectangle using OpenCV."""
    x1, y1 = pt1
    x2, y2 = pt2

    # Ensure coordinates are in correct order
    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    # Clamp radius to reasonable size
    radius = min(radius, min(x2 - x1, y2 - y1) // 4)

    if radius <= 3:
        # Fallback to regular rectangle if radius is too small
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        return

    # Draw the rounded rectangle using multiple primitives
    # Top and bottom horizontal lines
    cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness)
    cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness)

    # Left and right vertical lines
    cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness)
    cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness)

    # Corner arcs - make them more visible
    cv2.ellipse(
        img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness
    )
    cv2.ellipse(
        img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness
    )
    cv2.ellipse(
        img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness
    )
    cv2.ellipse(
        img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness
    )

    # Add a distinctive marker to make it obvious this is enhanced UI
    cv2.circle(
        img, (x2 - 10, y1 + 10), 3, (0, 255, 255), -1
    )  # Yellow dot in top-right corner


def draw_confidence_bar(img, confidence, bbox, color):
    """Draw a mini confidence progress bar above the bounding box."""
    x1, y1, x2, y2 = bbox

    # Progress bar dimensions - make it more visible
    bar_width = min(120, x2 - x1)  # Max 120px, or width of bbox
    bar_height = 8  # Slightly taller
    bar_x = x1 + (x2 - x1 - bar_width) // 2  # Center above bbox
    bar_y = max(5, y1 - 20)  # 20px above bbox, minimum 5px from top

    # Background bar (gray)
    cv2.rectangle(
        img,
        (bar_x, bar_y),
        (bar_x + bar_width, bar_y + bar_height),
        (100, 100, 100),
        -1,
    )

    # Confidence bar (colored based on confidence level)
    conf_width = int(bar_width * confidence)
    if conf_width > 0:
        # Color based on confidence: green for high, yellow for medium, red for low
        if confidence >= 0.7:
            conf_color = (0, 255, 0)  # Green
        elif confidence >= 0.5:
            conf_color = (0, 255, 255)  # Yellow
        else:
            conf_color = (0, 0, 255)  # Red

        cv2.rectangle(
            img,
            (bar_x, bar_y),
            (bar_x + conf_width, bar_y + bar_height),
            conf_color,
            -1,
        )

    # Border around the bar
    cv2.rectangle(
        img, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (200, 200, 200), 1
    )

    # Confidence percentage text
    conf_text = f"{int(confidence * 100)}%"
    text_size = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
    text_x = bar_x + bar_width + 5
    text_y = bar_y + bar_height - 1

    # Ensure text doesn't go off screen
    if text_x + text_size[0] > img.shape[1]:
        text_x = bar_x - text_size[0] - 5

    cv2.putText(
        img,
        conf_text,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        color,
        1,
        cv2.LINE_AA,
    )


def add_face_thumbnail(img, face_region, position, size=(40, 40)):
    """Add a small face crop thumbnail next to the label."""
    try:
        if face_region is None or face_region.size == 0:
            return

        # Resize face crop to thumbnail size
        face_thumb = cv2.resize(face_region, size, interpolation=cv2.INTER_AREA)

        x, y = position
        thumb_h, thumb_w = face_thumb.shape[:2]

        # Ensure thumbnail fits within image bounds
        if x + thumb_w > img.shape[1] or y + thumb_h > img.shape[0] or x < 0 or y < 0:
            return

        # Create a border around the thumbnail
        border_size = 2
        bordered_thumb = cv2.copyMakeBorder(
            face_thumb,
            border_size,
            border_size,
            border_size,
            border_size,
            cv2.BORDER_CONSTANT,
            value=(255, 255, 255),
        )

        # Update dimensions after adding border
        thumb_h, thumb_w = bordered_thumb.shape[:2]

        # Check bounds again after border
        if x + thumb_w > img.shape[1] or y + thumb_h > img.shape[0]:
            return

        # Overlay the thumbnail on the image
        img[y : y + thumb_h, x : x + thumb_w] = bordered_thumb

    except Exception as e:
        logger.debug(f"Error adding face thumbnail: {e}")


def draw_boxes_and_labels(
    frame,
    matches,
    timestamp="",
    persistent_labels=None,
    current_frame=0,
    enhanced_ui=True,
):
    """Draw enhanced bounding boxes and labels on detected faces with modern UI improvements."""
    try:
        # logger.info(f"Enhanced UI: {enhanced_ui}, processing {len(matches) if matches else 0} faces")
        # Convert frame to PIL Image for CJKV text rendering
        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(frame_pil)

        # Try to load CJKV-compatible font with caching
        global _global_cjkv_font, _font_cache_info

        # Use cached font if available
        if _global_cjkv_font is not None:
            pil_font = _global_cjkv_font
            logger.debug(f"Using cached font: {_font_cache_info}")
        else:
            # Load and cache font
            pil_font = None
            font_info = ""

            try:
                # Extended font search with more options
                font_candidates = [
                    # Project fonts
                    "/Users/swong/dev/mv-face-recognition/fonts/SourceHanSansTC-VF.ttf",
                    # macOS system fonts
                    "/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/Hiragino Sans GB.ttc",
                    "/System/Library/Fonts/STHeiti Light.ttc",
                    "/System/Library/Fonts/Apple LiGothic Medium.ttc",
                    "/Library/Fonts/Arial Unicode MS.ttf",
                    # Windows fonts
                    "/Windows/Fonts/msyh.ttc",
                    "/Windows/Fonts/simsun.ttc",
                    "/Windows/Fonts/simhei.ttf",
                    # Linux fonts
                    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                    "/usr/share/fonts/truetype/arphic/uming.ttc",
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                ]

                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        try:
                            # Test font with smaller sizes for compact labels
                            for size in [16, 14, 12, 10]:
                                test_font = ImageFont.truetype(font_path, size)

                                # Test if font can render CJKV characters
                                test_chars = ["何", "佩", "燒", "賣", "中", "文"]
                                test_img = Image.new("RGB", (100, 50), "white")
                                test_draw = ImageDraw.Draw(test_img)

                                can_render_cjkv = True
                                for char in test_chars:
                                    try:
                                        bbox = test_draw.textbbox(
                                            (0, 0), char, font=test_font
                                        )
                                        if (
                                            bbox[2] - bbox[0] <= 0
                                        ):  # No width means can't render
                                            can_render_cjkv = False
                                            break
                                    except Exception:
                                        can_render_cjkv = False
                                        break

                                if can_render_cjkv:
                                    pil_font = test_font
                                    font_info = f"Using {os.path.basename(font_path)} (size {size})"
                                    break

                            if pil_font:
                                break

                        except Exception as e:
                            logger.debug(f"Failed to load font {font_path}: {e}")
                            continue

                if pil_font is None:
                    # Final fallback - try to find any system font that supports CJKV
                    try:
                        import matplotlib.font_manager as fm

                        system_fonts = fm.findSystemFonts()

                        for font_file in system_fonts[
                            :20
                        ]:  # Test first 20 system fonts
                            try:
                                test_font = ImageFont.truetype(font_file, 14)
                                # Quick CJKV test
                                test_img = Image.new("RGB", (50, 30), "white")
                                test_draw = ImageDraw.Draw(test_img)
                                bbox = test_draw.textbbox((0, 0), "中", font=test_font)

                                if bbox[2] - bbox[0] > 5:  # Has reasonable width
                                    pil_font = test_font
                                    font_info = f"Using system font {os.path.basename(font_file)}"
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

                if pil_font is None:
                    pil_font = ImageFont.load_default()
                    font_info = "Using PIL default font - CJKV may show as squares"
                    logger.warning("No CJKV-compatible fonts found")
                else:
                    logger.info(font_info)

                # Cache the font for future use
                _global_cjkv_font = pil_font
                _font_cache_info = font_info

            except Exception as e:
                pil_font = ImageFont.load_default()
                font_info = f"Font loading error: {e}"
                logger.error(f"Font system failed: {e}")
                # Cache even the default font
                _global_cjkv_font = pil_font
                _font_cache_info = font_info

        # Combine current detections with persistent labels
        all_labels_to_draw = []

        # Add current frame detections
        for face, name in matches:
            bbox = face.bbox.astype(int)
            # Extract confidence from face object or recognition result
            confidence = (
                getattr(face, "det_score", 0.8) if hasattr(face, "det_score") else 0.8
            )

            # Parse confidence from name if it contains score info
            if name != "Unknown" and "(" in name and ")" in name:
                try:
                    score_part = name.split("(")[-1].split(")")[0]
                    confidence = float(score_part)
                    name = name.split("(")[0].strip()  # Clean name
                except:
                    pass

            all_labels_to_draw.append(
                {
                    "bbox": bbox,
                    "name": name,
                    "is_current": True,
                    "timestamp": timestamp,
                    "confidence": confidence,
                    "tracking_duration": 1,
                }
            )

        # Add persistent labels (from previous frames)
        if persistent_labels:
            for face_key, label_data in persistent_labels.items():
                # Check if this persistent label overlaps with current detections
                overlaps = False
                for face, _ in matches:
                    current_bbox = face.bbox.astype(int)
                    if (
                        calculate_face_similarity(label_data["bbox"], current_bbox)
                        < 0.3
                    ):
                        overlaps = True
                        break

                # Only draw persistent label if it doesn't overlap with current detection
                if not overlaps:
                    # Calculate tracking duration (frames since first seen)
                    tracking_duration = current_frame - (
                        label_data.get("last_seen", current_frame) - 10
                    )
                    tracking_duration = max(
                        1, min(tracking_duration, 90)
                    )  # Cap at persistence duration

                    all_labels_to_draw.append(
                        {
                            "bbox": label_data["bbox"],
                            "name": label_data["name"],
                            "is_current": False,
                            "timestamp": timestamp,
                            "confidence": label_data.get("confidence", 0.6),
                            "tracking_duration": tracking_duration,
                        }
                    )

        # Calculate optimal label positions to avoid collisions
        positioned_labels = calculate_label_positions(
            all_labels_to_draw, frame_pil.width, frame_pil.height
        )

        for positioned_label in positioned_labels:
            label_info = positioned_label["label_info"]
            final_x = positioned_label["final_x"]
            final_y = positioned_label["final_y"]

            # Get bounding box coordinates
            bbox = label_info["bbox"]
            name = label_info["name"]
            is_current = label_info["is_current"]
            confidence = label_info.get("confidence", 0.6)
            tracking_duration = label_info.get("tracking_duration", 1)
            x1, y1, x2, y2 = bbox

            # Get confidence-based colors
            color_bgr, color_rgb = get_confidence_color(confidence, is_current)

            # Calculate adaptive opacity
            adaptive_opacity = calculate_adaptive_opacity(
                tracking_duration, is_current, confidence
            )

            # Determine box thickness based on confidence and tracking
            if name != "Unknown":
                if confidence >= 0.7:
                    box_thickness = 2 if is_current else 1
                else:
                    box_thickness = 2 if is_current else 1
            else:
                box_thickness = 1

            # Apply opacity to colors for bbox
            opacity_factor = adaptive_opacity
            faded_color_bgr = tuple(int(c * opacity_factor) for c in color_bgr)

            # Enhanced bounding box drawing
            if enhanced_ui:
                if name != "Unknown":
                    # Enhanced features for recognized faces
                    radius = max(
                        8, min(15, min(x2 - x1, y2 - y1) // 8)
                    )  # Larger radius for visibility
                    draw_rounded_rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        faded_color_bgr,
                        box_thickness,
                        radius,
                    )

                    # Add confidence progress bar above the face
                    draw_confidence_bar(
                        frame, confidence, (x1, y1, x2, y2), faded_color_bgr
                    )
                else:
                    # Enhanced unknown faces still get rounded corners but no confidence bar
                    radius = max(5, min(10, min(x2 - x1, y2 - y1) // 10))
                    draw_rounded_rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        faded_color_bgr,
                        box_thickness,
                        radius,
                    )
            else:
                # Regular rectangle when enhanced UI is disabled
                cv2.rectangle(frame, (x1, y1), (x2, y2), faded_color_bgr, box_thickness)

            # Add a tiny circle at the center for face indication with adaptive opacity
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.circle(frame, (center_x, center_y), 2, faded_color_bgr, -1)

            # Prepare label text with persistence indicator and character sanitization
            def sanitize_text_for_font(text, font):
                """Remove or replace characters that can't be rendered by the font."""
                try:
                    # Test if the font can render the text
                    test_img = Image.new("RGB", (100, 30), "white")
                    test_draw = ImageDraw.Draw(test_img)

                    # Check each character
                    sanitized_chars = []
                    for char in text:
                        try:
                            bbox = test_draw.textbbox((0, 0), char, font=font)
                            if bbox[2] - bbox[0] > 0:  # Character has width
                                sanitized_chars.append(char)
                            else:
                                # Replace problematic characters
                                if ord(char) > 127:  # Non-ASCII
                                    sanitized_chars.append(
                                        "?"
                                    )  # Use ? for unrenderable chars
                                else:
                                    sanitized_chars.append(char)
                        except Exception:
                            # If testing fails, keep ASCII, replace others
                            if ord(char) <= 127:
                                sanitized_chars.append(char)
                            else:
                                sanitized_chars.append("?")

                    return "".join(sanitized_chars)
                except Exception:
                    # Fallback: keep only basic ASCII and common CJKV ranges
                    safe_chars = []
                    for char in text:
                        code = ord(char)
                        if (
                            code <= 127  # Basic ASCII
                            or (0x4E00 <= code <= 0x9FFF)  # CJK Unified Ideographs
                            or (0x3400 <= code <= 0x4DBF)  # CJK Extension A
                            or (0x3040 <= code <= 0x309F)  # Hiragana
                            or (0x30A0 <= code <= 0x30FF)
                        ):  # Katakana
                            safe_chars.append(char)
                        else:
                            safe_chars.append("?")
                    return "".join(safe_chars)

            # Sanitize the name first
            safe_name = sanitize_text_for_font(name, pil_font)

            # Create confidence-aware label
            if name != "Unknown" and confidence < 1.0:
                # Show confidence for recognized faces
                conf_indicator = (
                    "●●●○○"
                    if confidence >= 0.8
                    else "●●○○○"
                    if confidence >= 0.6
                    else "●○○○○"
                )
                label = f"{safe_name} {conf_indicator}"
            else:
                label = safe_name

            # Add tracking indicator for persistent labels
            if not is_current and tracking_duration > 30:
                label += " ⏰"  # Persistent tracking indicator

            # Use the calculated optimal position from anti-collision system
            label_x, label_y = final_x, final_y

            # Get text dimensions using PIL
            bbox_text = draw.textbbox((0, 0), label, font=pil_font)
            text_width = bbox_text[2] - bbox_text[0]
            text_height = bbox_text[3] - bbox_text[1]

            # Create adaptive background with confidence-based styling
            background_alpha = int(200 * adaptive_opacity)  # Adaptive transparency
            background_coords = [
                label_x - 2,
                label_y - 1,
                label_x + text_width + 4,
                label_y + text_height + 2,
            ]

            # Draw background with adaptive opacity
            overlay = Image.new("RGBA", frame_pil.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                background_coords, fill=color_rgb + (background_alpha,)
            )
            frame_pil = Image.alpha_composite(
                frame_pil.convert("RGBA"), overlay
            ).convert("RGB")
            draw = ImageDraw.Draw(frame_pil)

            # Add face thumbnail if enhanced UI is enabled and face is recognized
            if enhanced_ui and name != "Unknown":
                try:
                    # Extract face crop from the original frame
                    face_crop = frame[
                        max(0, y1) : min(frame.shape[0], y2),
                        max(0, x1) : min(frame.shape[1], x2),
                    ]
                    if face_crop.size > 0:
                        # Position thumbnail to the left of the label
                        thumb_x = max(0, label_x - 50)  # 50px to the left
                        thumb_y = label_y

                        # Ensure thumbnail doesn't overlap with bounding box
                        if (
                            thumb_x + 45 > x1
                            and thumb_y + 45 > y1
                            and thumb_x < x2
                            and thumb_y < y2
                        ):
                            # Move thumbnail to the right of the label instead
                            thumb_x = min(
                                frame.shape[1] - 45, label_x + text_width + 10
                            )

                        add_face_thumbnail(
                            frame, face_crop, (thumb_x, thumb_y), size=(40, 40)
                        )
                except Exception:
                    pass  # Silently handle thumbnail errors

            # Draw text with adaptive brightness
            text_brightness = int(255 * adaptive_opacity)
            text_color = (text_brightness, text_brightness, text_brightness)
            draw.text((label_x, label_y), label, font=pil_font, fill=text_color)

        # Convert back to OpenCV format
        frame_with_text = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)
        return frame_with_text

    except Exception as e:
        logger.error(f"Error drawing boxes and labels: {e}")
        # Fallback to original OpenCV method if PIL fails
        try:
            for face, name in matches:
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                # Use only ASCII characters for fallback
                ascii_name = name.encode("ascii", "ignore").decode("ascii") or "Name"
                cv2.putText(
                    frame,
                    ascii_name,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )
        except Exception:
            pass
        return frame


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceRecognitionApp:
    """Main Gradio application for face recognition."""

    def __init__(self):
        """Initialize the application."""
        self.config = get_config()
        self.face_detector: Optional[Any] = None
        self.known_embeddings = {}
        self.contestant_info = None
        self.processing_stats = {
            "total_processed": 0,
            "faces_detected": 0,
            "faces_recognized": 0,
            "last_updated": datetime.now(),
        }

        # Video title mapping
        self.title_to_path_mapping = {}

        # Visualization service
        self.visualization_service = None

        # Initialize components
        self._initialize_system()

        # UI state
        self.camera_active = False
        self.processing_video = False

    def _initialize_system(self):
        """Initialize face detection and load contestant data."""
        try:
            # Initialize face detector
            self.face_detector = FaceDetector(self.config)
            logger.info("Face detector initialized successfully")

            # Initialize visualization service
            try:
                self.visualization_service = VisualizationService()
                logger.info("Visualization service initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize visualization service: {e}")
                self.visualization_service = None

            # Load contestant information
            contestant_info_path = self.config.project_root / "contestant_info.csv"
            if contestant_info_path.exists():
                self.contestant_info = pd.read_csv(contestant_info_path)
                logger.info(f"Loaded {len(self.contestant_info)} contestants")

            # Load embeddings
            self._load_embeddings()

        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            gr.Error(f"Failed to initialize system: {e}")

    def _load_embeddings(self):
        """Load known face embeddings."""
        try:
            embeddings_dir = self.config.contestants_dir
            self.known_embeddings = {}

            for embedding_file in embeddings_dir.glob("*_embedding.npy"):
                try:
                    contestant_name = embedding_file.stem.replace("_embedding", "")
                    embedding = np.load(embedding_file)

                    # Ensure embedding is properly shaped and normalized
                    embedding = np.array(embedding).flatten()
                    if np.linalg.norm(embedding) > 0:
                        embedding = embedding / np.linalg.norm(embedding)
                        self.known_embeddings[contestant_name] = embedding
                    else:
                        logger.warning(
                            f"Invalid embedding for {contestant_name} - zero norm"
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to load embedding for {embedding_file}: {e}"
                    )
                    continue

            logger.info(f"Loaded {len(self.known_embeddings)} contestant embeddings")

        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")

    def get_video_titles_mapping(self):
        """Get video titles from videos_dl.py"""
        try:
            # Import the url_list from videos_dl.py
            import sys

            sys.path.append(str(Path(__file__).parent))
            from videos_dl import url_list

            return url_list
        except ImportError as e:
            logger.warning(f"Could not import video titles: {e}")
            return {}

    def get_available_videos(self):
        """Get list of available videos with titles from the source directory."""
        # Import video title mapping
        try:
            from src.config.video_titles import VIDEO_TITLE_MAPPING, get_video_display_title
        except ImportError:
            VIDEO_TITLE_MAPPING = {}
            get_video_display_title = lambda x: x
        
        # Try different video directories in order of preference
        videos_dirs = [
            Path("source/videos_hf_clean"),  # For HF Spaces deployment (clean ASCII names)
            Path("source/videos_hf_optimized"),  # For HF Spaces deployment (original names)
            Path("source/videos"),  # For local development
            Path("/Users/swong/dev/mv-face-recognition/source/videos")  # Absolute path fallback
        ]
        
        videos_dir = None
        for dir_path in videos_dirs:
            if dir_path.exists():
                videos_dir = dir_path
                print(f"📁 Using videos directory: {videos_dir}")
                break
        
        if not videos_dir:
            print("⚠️ No videos directory found")
            return [], {}

        # Get video titles mapping
        video_titles = self.get_video_titles_mapping()

        video_files = []
        title_to_path_mapping = {}

        # Cache for checked videos to avoid repeated warnings
        if not hasattr(self, "_checked_videos"):
            self._checked_videos = set()

        for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv"]:
            potential_files = videos_dir.glob(ext)
            for video_file in potential_files:
                # Skip known bad files to avoid repeated warnings
                if str(video_file) in self._checked_videos:
                    continue

                # Check if it's actually a video file and not a Git LFS pointer
                try:
                    import cv2

                    cap = cv2.VideoCapture(str(video_file))
                    if cap.isOpened():
                        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        if frame_count > 0:
                            # Find the corresponding title for this video file
                            filename = video_file.name  # full filename with extension
                            
                            # Use video title mapping if available (for clean ASCII names)
                            if filename in VIDEO_TITLE_MAPPING:
                                display_title = VIDEO_TITLE_MAPPING[filename]
                            else:
                                # Fallback to original title mapping or filename
                                file_stem = video_file.stem
                                display_title = video_titles.get(file_stem, file_stem)
                            
                            # Add to available videos list
                            video_files.append(display_title)
                            title_to_path_mapping[display_title] = str(video_file)
                        cap.release()
                    else:
                        # Mark as checked and log warning only once
                        self._checked_videos.add(str(video_file))
                        logger.warning(f"Cannot open video file: {video_file}")
                except Exception as e:
                    # Mark as checked and log warning only once
                    self._checked_videos.add(str(video_file))
                    logger.warning(f"Error checking video file {video_file}: {e}")

        # Store the mapping in the instance
        self.title_to_path_mapping = title_to_path_mapping
        return video_files, title_to_path_mapping

    def get_video_titles_for_dropdown(self):
        """Get just the video titles for the dropdown."""
        video_titles, _ = self.get_available_videos()
        return video_titles

    def get_video_path_from_title(self, title):
        """Get the file path from the selected title."""
        return self.title_to_path_mapping.get(title, title)

    def _create_timeline_data(self, timeline_df):
        """Create timeline data for Gradio components."""
        try:
            # Validate DataFrame structure
            required_columns = ["Time", "Frame", "Name"]
            if not all(col in timeline_df.columns for col in required_columns):
                raise ValueError(
                    f"DataFrame missing required columns. Expected: {required_columns}, Got: {list(timeline_df.columns)}"
                )

            if len(timeline_df) == 0:
                return [], [], "", []

            # Group data by contestant
            grouped_data = timeline_df.groupby("Name")

            # Create statistics
            recognition_count = len(timeline_df)
            unique_people = timeline_df["Name"].nunique()

            # Load contestant info for enhanced display
            contestant_info_map = {}
            try:
                if (
                    hasattr(self, "contestant_info")
                    and self.contestant_info is not None
                ):
                    for _, row in self.contestant_info.iterrows():
                        name = row.get("暱稱", "")
                        full_name = row.get("姓名", "")
                        number = row.get("編號", "")
                        if name:
                            contestant_info_map[name] = {
                                "full_name": full_name,
                                "nickname": name,
                                "number": number,
                            }
            except Exception as e:
                logger.warning(f"Could not load contestant info: {e}")

            # Prepare data for Gradio components
            timeline_data = []
            contestant_choices = ["All Contestants"]
            search_data = {}

            for contestant_name, contestant_data in grouped_data:
                appearances = len(contestant_data)
                contestant_data = contestant_data.sort_values("Frame")

                # Get contestant info
                contestant_display = contestant_name
                search_terms = [contestant_name.lower()]

                if contestant_name in contestant_info_map:
                    info = contestant_info_map[contestant_name]
                    if info["full_name"] and info["full_name"] != contestant_name:
                        contestant_display += f" ({info['full_name']})"
                        search_terms.append(info["full_name"].lower())
                    if info["number"]:
                        contestant_display += f" #{info['number']}"
                        search_terms.append(str(info["number"]).lower())

                contestant_choices.append(contestant_display)
                search_data[contestant_name] = search_terms

                # Add rows for this contestant
                for i, (_, row) in enumerate(contestant_data.iterrows()):
                    sequence_num = i + 1
                    timeline_data.append(
                        [
                            contestant_display,
                            row["Time"],
                            row["Frame"],
                            sequence_num,
                            appearances,
                        ]
                    )

            # Create statistics HTML
            stats_html = f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 8px; color: white; margin: 10px 0;'>
                <h4 style='margin: 0 0 10px 0;'>📊 Recognition Statistics</h4>
                <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;'>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 6px;'>
                        <div style='font-size: 1.2em; font-weight: bold;'>{recognition_count}</div>
                        <div style='font-size: 0.9em; opacity: 0.9;'>Total Appearances</div>
                    </div>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 6px;'>
                        <div style='font-size: 1.2em; font-weight: bold;'>{unique_people}</div>
                        <div style='font-size: 0.9em; opacity: 0.9;'>Contestants Detected</div>
                    </div>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 6px;'>
                        <div style='font-size: 1.2em; font-weight: bold;'>{recognition_count / unique_people:.1f}</div>
                        <div style='font-size: 0.9em; opacity: 0.9;'>Avg per Contestant</div>
                    </div>
                </div>
            </div>
            """

            return timeline_data, contestant_choices, stats_html, search_data

        except Exception as e:
            logger.error(f"Timeline data creation failed: {e}")
            return [], [], f"Error creating timeline: {e}", {}

    def generate_umap_visualization(self, detected_faces_data):
        """Generate UMAP visualization for detected faces."""
        if not self.visualization_service:
            # Create simple placeholder plot
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 8))
            ax.text(
                0.5,
                0.5,
                "UMAP visualization not available\n(visualization service not initialized)",
                ha="center",
                va="center",
                fontsize=14,
                color="red",
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_title("UMAP Visualization Error", fontsize=16)
            return fig

        try:
            logger.info(
                f"Starting UMAP generation with {len(detected_faces_data)} face detections"
            )

            # Extract embeddings and labels from detected faces with better error handling
            detected_embeddings = []
            detected_labels = []

            for i, (face, name) in enumerate(detected_faces_data):
                embedding = None

                # Try multiple ways to get embedding
                if (
                    hasattr(face, "normed_embedding")
                    and face.normed_embedding is not None
                ):
                    embedding = face.normed_embedding
                elif hasattr(face, "embedding") and face.embedding is not None:
                    embedding = face.embedding
                elif hasattr(face, "bbox"):
                    # Try to extract embedding using face detector
                    try:
                        logger.debug(f"Attempting to extract embedding for face {i}")
                        # This would need the original frame, which we don't have here
                        # Skip this face for now
                        continue
                    except Exception:
                        continue

                if embedding is not None:
                    # Ensure embedding is properly shaped
                    embedding = np.array(embedding).flatten()
                    if len(embedding) > 0 and not np.isnan(embedding).any():
                        detected_embeddings.append(embedding)
                        detected_labels.append(name)
                        logger.debug(
                            f"Added embedding for {name} (shape: {embedding.shape})"
                        )
                    else:
                        logger.warning(
                            f"Invalid embedding for {name}: contains NaN or empty"
                        )
                else:
                    logger.warning(f"No embedding found for face {i} ({name})")

            logger.info(
                f"Extracted {len(detected_embeddings)} valid embeddings from {len(detected_faces_data)} faces"
            )

            if len(detected_embeddings) == 0:
                # No valid embeddings found
                import matplotlib.pyplot as plt

                fig, ax = plt.subplots(figsize=(10, 8))
                ax.text(
                    0.5,
                    0.5,
                    f"No valid face embeddings found\nfrom {len(detected_faces_data)} detected faces\n\nThis could happen if:\n• Face detection didn't extract embeddings\n• Embeddings are corrupted\n• Face crops are too small",
                    ha="center",
                    va="center",
                    fontsize=12,
                    color="orange",
                )
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.set_title("UMAP: No Valid Embeddings", fontsize=16)
                return fig

            # Prepare gallery embeddings
            gallery_embeddings = {}
            gallery_names = {}

            valid_gallery_count = 0
            for name, embedding in self.known_embeddings.items():
                if embedding is not None and len(embedding) > 0:
                    gallery_embeddings[name] = [embedding]
                    gallery_names[name] = name
                    valid_gallery_count += 1

            logger.info(f"Using {valid_gallery_count} gallery embeddings for UMAP")

            if valid_gallery_count == 0:
                import matplotlib.pyplot as plt

                fig, ax = plt.subplots(figsize=(10, 8))
                ax.text(
                    0.5,
                    0.5,
                    "No gallery embeddings available\nPlease ensure contestant embeddings are loaded",
                    ha="center",
                    va="center",
                    fontsize=12,
                    color="red",
                )
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.set_title("UMAP: No Gallery Data", fontsize=16)
                return fig

            # Generate UMAP plot
            logger.info("Calling visualization service to generate UMAP plot")
            umap_plot = self.visualization_service.generate_umap_plot(
                detected_embeddings=detected_embeddings,
                gallery_embeddings=gallery_embeddings,
                gallery_names=gallery_names,
                detected_labels=detected_labels,
                show_current_only=False,
            )

            logger.info("UMAP plot generated successfully")
            return umap_plot

        except Exception as e:
            logger.error(f"Error generating UMAP visualization: {e}")
            import traceback

            traceback.print_exc()

            # Return detailed error plot
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 8))
            error_text = (
                f"Error generating UMAP:\n{str(e)}\n\nCheck console for details"
            )
            ax.text(
                0.5, 0.5, error_text, ha="center", va="center", fontsize=11, color="red"
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_title("UMAP Generation Error", fontsize=16)
            return fig

    @spaces.GPU
    @gpu_safe_decorator
    def process_uploaded_video(self, video_path, progress=gr.Progress()):
        """Process an uploaded video file."""
        if not video_path:
            return None, "No video provided"

        try:
            self.processing_video = True
            results = []
            
            # ZeroGPU timeout management
            if HF_SPACES_GPU:
                print("🚀 Processing on ZeroGPU - optimizing for time limits...")
                # Reduce frame skip for faster processing on GPU
                original_frame_skip = self.config.recognition.frame_skip
                self.config.recognition.frame_skip = max(5, original_frame_skip)  # Process fewer frames

            # Cache for persistent labels (keeps labels visible for multiple frames)
            label_persistence_cache = {}  # {face_id: {'name': str, 'bbox': tuple, 'expire_frame': int}}
            label_persistence_duration = 90  # Keep labels visible for 90 frames (~3 seconds at 30fps) for smoother tracking

            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return (
                    None,
                    f"Error: Cannot open video file {video_path}. The file may be corrupted or in an unsupported format.",
                )

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            if total_frames <= 0 or fps <= 0:
                cap.release()
                return (
                    None,
                    f"Error: Invalid video file {video_path}. Cannot read video properties.",
                )

            # Create output video writer with browser-compatible settings
            output_path = tempfile.mktemp(suffix=".mp4")

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Ensure dimensions are even (required for some codecs)
            width = width if width % 2 == 0 else width - 1
            height = height if height % 2 == 0 else height - 1

            # Try H.264 codec first, fallback to mp4v if not available
            codecs_to_try = [
                cv2.VideoWriter_fourcc(*"avc1"),  # H.264
                cv2.VideoWriter_fourcc(*"mp4v"),  # MPEG-4
                cv2.VideoWriter_fourcc(*"XVID"),  # Xvid
            ]

            out = None
            for fourcc in codecs_to_try:
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                if out.isOpened():
                    break
                out.release()

            if not out or not out.isOpened():
                cap.release()
                return None, "Error: Could not initialize video writer with any codec"

            frame_count = 0

            # Reset processing stats for this video
            self.processing_stats["total_processed"] = 0
            self.processing_stats["faces_detected"] = 0
            self.processing_stats["faces_recognized"] = 0

            # Process frames
            progress(0, desc="Processing video...")
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # Ensure frame is the correct size
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))

                # Process frame for face detection and recognition
                matches = []
                should_process = frame_count % self.config.recognition.frame_skip == 0

                # GPU memory management for ZeroGPU
                if HF_SPACES_GPU and frame_count % 100 == 0:  # Every 100 frames
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except:
                        pass

                if should_process:
                    # Increment processed frame count
                    self.processing_stats["total_processed"] += 1

                    # Process frame for recognition
                    matches = process_frame(
                        frame,
                        self.known_embeddings,
                        self.config.recognition.similarity_threshold,
                    )

                    # Update persistent labels cache
                    label_persistence_cache = update_persistent_labels(
                        matches,
                        label_persistence_cache,
                        frame_count,
                        label_persistence_duration,
                    )

                    # Record matches
                    faces_detected = len(matches)
                    faces_recognized = sum(
                        1 for _, name in matches if name != "Unknown"
                    )

                    # Update processing stats
                    self.processing_stats["faces_detected"] += faces_detected
                    self.processing_stats["faces_recognized"] += faces_recognized

                    for _, name in matches:
                        if name != "Unknown":
                            timestamp = frame_count / fps
                            results.append(
                                {
                                    "frame": frame_count,
                                    "time": f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}",
                                    "name": name,
                                }
                            )

                    # Log progress every 500 processed frames
                    if frame_count % 500 == 0:
                        logger.info(
                            f"Frame {frame_count}: Detected {faces_detected} faces, recognized {faces_recognized}"
                        )

                # Draw results on frame with persistent labels
                timestamp = frame_count / fps
                time_str = f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"

                # Always draw persistent labels, even if no new matches
                if matches or label_persistence_cache:
                    frame = draw_boxes_and_labels(
                        frame,
                        matches,
                        time_str,
                        label_persistence_cache,
                        frame_count,
                        enhanced_ui=self.config.ui.enhanced_ui,
                    )

                # Add frame info overlay (small, unobtrusive) using OpenCV for ASCII text
                if should_process:
                    # Add small processing indicator
                    cv2.putText(
                        frame,
                        "PROCESSING",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )

                # Add timestamp overlay
                timestamp = frame_count / fps
                time_str = f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"
                cv2.putText(
                    frame,
                    time_str,
                    (10, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

                # Ensure frame is still the correct size after processing
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))

                out.write(frame)

                # Update progress
                progress(
                    frame_count / total_frames,
                    desc=f"Processing frame {frame_count}/{total_frames}",
                )

            cap.release()
            out.release()

            # Create results summary and timeline data
            if results:
                df = pd.DataFrame(results)
                summary = "📊 Processing Summary:\n"
                summary += f"• Total frames: {total_frames}\n"
                summary += f"• Frames processed: {self.processing_stats['total_processed']} (every {self.config.recognition.frame_skip})\n"
                summary += (
                    f"• Faces detected: {self.processing_stats['faces_detected']}\n"
                )
                summary += (
                    f"• Faces recognized: {self.processing_stats['faces_recognized']}\n"
                )
                summary += f"• Recognition events: {len(results)}\n\n"

                summary += "🎭 Recognition Results:\n"
                # Count by contestant
                counts = df["name"].value_counts()
                for name, count in counts.items():
                    summary += f"• {name}: {count} appearances\n"

                summary += f"\n📍 **Interactive Timeline**: See detailed timeline with {len(results)} events below ⬇️"

            else:
                summary = "📊 Processing Summary:\n"
                summary += f"• Total frames: {total_frames}\n"
                summary += f"• Frames processed: {self.processing_stats['total_processed']} (every {self.config.recognition.frame_skip})\n"
                summary += (
                    f"• Faces detected: {self.processing_stats['faces_detected']}\n"
                )
                summary += (
                    f"• Faces recognized: {self.processing_stats['faces_recognized']}\n"
                )
                summary += "• Recognition events: 0\n\n"
                summary += "❌ No faces recognized in video"

            self.processing_video = False
            
            # Restore original frame skip setting
            if HF_SPACES_GPU and 'original_frame_skip' in locals():
                self.config.recognition.frame_skip = original_frame_skip
            
            # Final GPU cleanup
            if HF_SPACES_GPU:
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        print("🧹 Final GPU memory cleanup completed")
                except:
                    pass

            # Create timeline data for native Gradio components
            timeline_data = []
            contestant_choices = ["All"]
            timeline_stats_html = "Process a video to see interactive timeline"

            if results:
                results_df = pd.DataFrame(results)
                # Fix column names for timeline
                timeline_df = results_df.copy()
                timeline_df.columns = [
                    "Frame",
                    "Time",
                    "Name",
                ]  # Rename to match expected format

                # Create timeline data using native Gradio components
                timeline_data, contestant_choices, timeline_stats_html = (
                    self._create_timeline_data(timeline_df)
                )

            return (
                output_path,
                summary,
                (timeline_data, contestant_choices, timeline_stats_html),
            )

        except Exception as e:
            self.processing_video = False
            
            # Restore original frame skip setting if error occurred
            if HF_SPACES_GPU and 'original_frame_skip' in locals():
                self.config.recognition.frame_skip = original_frame_skip
            
            # GPU cleanup on error
            if HF_SPACES_GPU:
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        print("🧹 GPU memory cleanup after error")
                except:
                    pass
            
            logger.error(f"Video processing error: {e}")
            return (
                None,
                f"Error processing video: {e}",
                "Error occurred during processing",
            )

    def get_system_status(self):
        """Get current system status information."""
        try:
            status = {
                "Face Detector": "Active" if self.face_detector else "Inactive",
                "Known Contestants": len(self.known_embeddings),
                "ChromaDB": "Connected"
                if self.config.recognition.enable_chromadb
                else "Disabled",
                "GPU Acceleration": "Enabled"
                if self.config.recognition.use_gpu
                else "Disabled",
                "Frames Processed": self.processing_stats["total_processed"],
                "Faces Detected": self.processing_stats["faces_detected"],
                "Faces Recognized": self.processing_stats["faces_recognized"],
                "Last Updated": self.processing_stats["last_updated"].strftime(
                    "%H:%M:%S"
                ),
            }

            # Format as table
            status_text = "## System Status\n\n"
            for key, value in status.items():
                status_text += f"**{key}**: {value}\n\n"

            return status_text

        except Exception as e:
            return f"Error getting system status: {e}"

    def get_performance_chart(self):
        """Create a performance visualization chart."""
        try:
            # Simple performance data
            stats = self.processing_stats
            data = {
                "Metric": ["Total Processed", "Faces Detected", "Faces Recognized"],
                "Count": [
                    stats["total_processed"],
                    stats["faces_detected"],
                    stats["faces_recognized"],
                ],
            }

            fig = px.bar(
                data,
                x="Metric",
                y="Count",
                title="Processing Statistics",
                color="Metric",
            )
            fig.update_layout(showlegend=False)

            return fig

        except Exception as e:
            logger.error(f"Chart creation error: {e}")
            return go.Figure()

    def update_settings(
        self,
        similarity_threshold,
        detection_threshold,
        frame_skip,
        max_faces,
        use_gpu,
        enable_chromadb,
        enhanced_ui,
    ):
        """Update system settings."""
        try:
            self.config.recognition.similarity_threshold = similarity_threshold
            self.config.recognition.detection_threshold = detection_threshold
            self.config.recognition.frame_skip = frame_skip
            self.config.recognition.max_faces_per_frame = max_faces
            self.config.recognition.use_gpu = use_gpu
            self.config.recognition.enable_chromadb = enable_chromadb
            self.config.ui.enhanced_ui = enhanced_ui

            # Save configuration
            save_config()

            return "Settings updated successfully!"

        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return f"Error updating settings: {e}"

    def get_contestant_list(self):
        """Get list of available contestants."""
        if self.contestant_info is not None:
            return self.contestant_info[["編號", "暱稱"]].to_dict("records")
        return []

    def add_contestant_embedding(self, contestant_name, image):
        """Add a new contestant with their face embedding."""
        if not contestant_name or image is None:
            return "Please provide contestant name and image"

        try:
            # Extract embedding from image
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            embedding = self.face_detector.extract_face_embedding(image_cv)

            if embedding is None:
                return "No face detected in the provided image"

            # Save embedding
            embedding_path = (
                self.config.contestants_dir / f"{contestant_name}_embedding.npy"
            )
            np.save(embedding_path, embedding)

            # Update in-memory embeddings
            self.known_embeddings[contestant_name] = embedding

            return f"Successfully added embedding for {contestant_name}"

        except Exception as e:
            logger.error(f"Add contestant error: {e}")
            return f"Error adding contestant: {e}"

    def _create_timeline_data(self, results_df):
        """Create timeline data for native Gradio Dataframe component."""
        try:
            if results_df is None or results_df.empty:
                return [], [], "No timeline data available"

            # Group by contestant and calculate statistics
            timeline_data = []
            contestant_stats = {}

            for _, row in results_df.iterrows():
                frame = int(row.get("Frame", 0))
                time_str = str(row.get("Time", "00:00"))
                name = str(row.get("Name", "Unknown"))

                if name == "Unknown":
                    continue

                # Track sequences for each contestant
                if name not in contestant_stats:
                    contestant_stats[name] = {
                        "appearances": 0,
                        "sequences": [],
                        "current_sequence_start": frame,
                        "last_frame": frame,
                    }

                stats = contestant_stats[name]
                stats["appearances"] += 1

                # Detect sequence breaks (gap > 30 frames indicates new sequence)
                if frame - stats["last_frame"] > 30:
                    # End previous sequence
                    if stats["current_sequence_start"] is not None:
                        stats["sequences"].append(
                            (stats["current_sequence_start"], stats["last_frame"])
                        )
                    # Start new sequence
                    stats["current_sequence_start"] = frame

                stats["last_frame"] = frame

                # Add to timeline data
                sequence_num = len(stats["sequences"]) + 1
                timeline_data.append(
                    [name, time_str, frame, sequence_num, stats["appearances"]]
                )

            # Close any open sequences
            for name, stats in contestant_stats.items():
                if stats["current_sequence_start"] is not None:
                    stats["sequences"].append(
                        (stats["current_sequence_start"], stats["last_frame"])
                    )

            # Get unique contestants for filter dropdown
            contestant_choices = ["All"] + sorted(list(contestant_stats.keys()))

            # Create summary statistics
            total_contestants = len(contestant_stats)
            total_appearances = sum(
                stats["appearances"] for stats in contestant_stats.values()
            )

            stats_html = f"""
            <div style="padding: 10px; background: #f8f9fa; border-radius: 8px; margin: 10px 0;">
                <h4>📊 Recognition Statistics</h4>
                <p><strong>👥 Contestants Detected:</strong> {total_contestants}</p>
                <p><strong>📍 Total Appearances:</strong> {total_appearances}</p>
                <p><strong>📋 Timeline Entries:</strong> {len(timeline_data)}</p>
            </div>
            """

            return timeline_data, contestant_choices, stats_html

        except Exception as e:
            logger.error(f"Error creating timeline data: {e}")
            return [], [], f"Error creating timeline: {str(e)}"

    def _filter_timeline_data(self, timeline_data, search_query, filter_contestant):
        """Filter timeline data based on search query and contestant filter."""
        try:
            if not timeline_data:
                return []

            filtered_data = timeline_data.copy()

            # Apply contestant filter
            if filter_contestant and filter_contestant != "All":
                filtered_data = [
                    row for row in filtered_data if row[0] == filter_contestant
                ]

            # Apply search query
            if search_query:
                search_lower = search_query.lower().strip()
                filtered_data = [
                    row
                    for row in filtered_data
                    if search_lower in row[0].lower()  # Search in contestant name
                ]

            return filtered_data

        except Exception as e:
            logger.error(f"Error filtering timeline data: {e}")
            return timeline_data if timeline_data else []


# Global app instance
app_instance = None


def get_app():
    """Get or create the global app instance."""
    global app_instance
    if app_instance is None:
        app_instance = FaceRecognitionApp()
    return app_instance


def create_gradio_interface():
    """Create the main Gradio interface with Gradio 5.x enhancements."""

    # Use default Gradio theme
    css = None

    with gr.Blocks(
        css=css,
        title="🎬 MV Face Recognition System",
        analytics_enabled=False,
        head="<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
    ) as demo:
        # Simple header
        with gr.Row():
            with gr.Column():
                gr.Markdown("# 🎬 MV Face Recognition System")
                gr.Markdown("*Advanced AI-powered face recognition for video analysis*")

        # Main tabs
        with gr.Tabs():
            # Video Processing Tab
            with gr.Tab("🎬 Video Processing"):
                gr.Markdown("## 🎬 Select and Process Videos")

                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        with gr.Group():
                            gr.Markdown("### 📁 Select from Available Videos")
                            video_dropdown = gr.Dropdown(
                                choices=get_app().get_video_titles_for_dropdown(),
                                label="📹 Choose Video",
                                show_label=True,
                                interactive=True,
                                container=True,
                            )
                            gr.Markdown(
                                "*Available videos will show with their full titles from the video collection*"
                            )

                            refresh_videos_btn = gr.Button(
                                "🔄 Refresh Video List", variant="secondary", size="sm"
                            )

                            with gr.Row():
                                video_button = gr.Button(
                                    "▶️ Process Video",
                                    variant="primary",
                                    size="lg",
                                    scale=2,
                                )
                                video_clear = gr.ClearButton(
                                    [video_dropdown],
                                    value="🗑️ Clear",
                                    size="lg",
                                    scale=1,
                                )

                            # Progress indicator
                            video_progress = gr.HTML("📋 Ready to process video")

                    with gr.Column(scale=1):
                        with gr.Group():
                            video_output = gr.Video(
                                label="🎯 Processed Video",
                                show_label=True,
                                container=True,
                                height=400,
                            )
                            video_results = gr.Textbox(
                                label="📋 Processing Results",
                                lines=8,
                                max_lines=15,
                                show_copy_button=True,
                                container=True,
                            )

                            # Timeline components for interactive navigation
                            with gr.Group():
                                gr.Markdown("### 🎯 Recognition Timeline by Contestant")

                                with gr.Row():
                                    contestant_search = gr.Textbox(
                                        label="🔍 Search Contestants",
                                        placeholder="Search by name, nickname, or number...",
                                        container=True,
                                        scale=2,
                                    )
                                    contestant_filter = gr.Dropdown(
                                        label="📋 Filter by Contestant",
                                        choices=["All"],
                                        value="All",
                                        container=True,
                                        scale=1,
                                    )

                                timeline_stats = gr.HTML(
                                    value="Process a video to see recognition statistics",
                                    visible=True,
                                )

                                recognition_timeline = gr.Dataframe(
                                    headers=[
                                        "👤 Contestant",
                                        "⏰ Time",
                                        "🎬 Frame",
                                        "📊 Sequence",
                                        "📍 Appearances",
                                    ],
                                    datatype=[
                                        "str",
                                        "str",
                                        "number",
                                        "number",
                                        "number",
                                    ],
                                    interactive=False,
                                    wrap=True,
                                    visible=True,
                                )

                def process_selected_video(dropdown_title):
                    """Process video from dropdown selection."""
                    if not dropdown_title:
                        return (
                            None,
                            "Please select a video from the dropdown",
                            [],  # Empty timeline data
                            "No video selected",  # Timeline stats
                        )

                    # Convert title to actual file path
                    video_path = get_app().get_video_path_from_title(dropdown_title)
                    (
                        video_output,
                        summary,
                        (timeline_data, contestant_choices, timeline_stats),
                    ) = get_app().process_uploaded_video(video_path)

                    return video_output, summary, timeline_data, timeline_stats

                def filter_timeline_by_search(
                    timeline_data, search_query, filter_contestant
                ):
                    """Filter timeline data based on search and filter inputs."""
                    try:
                        if not timeline_data:
                            return []
                        filtered_data = get_app()._filter_timeline_data(
                            timeline_data, search_query, filter_contestant
                        )
                        return filtered_data
                    except Exception as e:
                        logger.error(f"Error filtering timeline data: {e}")
                        return timeline_data if timeline_data else []

                def update_contestant_filter(timeline_data):
                    """Update contestant filter choices based on timeline data."""
                    try:
                        # Always start with 'All' as the default choice
                        choices = ["All"]

                        if timeline_data and len(timeline_data) > 0:
                            # Extract unique contestants from timeline data
                            contestants = set()
                            for row in timeline_data:
                                if (
                                    row and len(row) > 0 and row[0]
                                ):  # Check row exists and has content
                                    contestants.add(
                                        str(row[0])
                                    )  # Contestant name is first column

                            # Add sorted contestants to choices
                            if contestants:
                                choices.extend(sorted(list(contestants)))

                        return gr.Dropdown(choices=choices, value="All")
                    except Exception as e:
                        logger.error(f"Error updating contestant filter: {e}")
                        import traceback

                        traceback.print_exc()
                        return gr.Dropdown(choices=["All"], value="All")

                def refresh_video_dropdown():
                    """Refresh the video dropdown with current videos."""
                    return gr.Dropdown(
                        choices=get_app().get_video_titles_for_dropdown()
                    )

                # Store timeline data in State for filtering
                full_timeline_data = gr.State(value=[])

                video_button.click(
                    process_selected_video,
                    inputs=[video_dropdown],
                    outputs=[
                        video_output,
                        video_results,
                        full_timeline_data,
                        timeline_stats,
                    ],
                ).then(
                    lambda data: data,  # Pass through the full timeline data to display
                    inputs=[full_timeline_data],
                    outputs=[recognition_timeline],
                ).then(
                    update_contestant_filter,
                    inputs=[full_timeline_data],
                    outputs=[contestant_filter],
                )

                # Add event handlers for search and filter functionality
                contestant_search.change(
                    filter_timeline_by_search,
                    inputs=[full_timeline_data, contestant_search, contestant_filter],
                    outputs=[recognition_timeline],
                )

                contestant_filter.change(
                    filter_timeline_by_search,
                    inputs=[full_timeline_data, contestant_search, contestant_filter],
                    outputs=[recognition_timeline],
                )

                refresh_videos_btn.click(
                    refresh_video_dropdown, outputs=[video_dropdown]
                )

            # Settings Tab
            with gr.Tab("⚙️ Settings"):
                gr.Markdown("## ⚙️ System Configuration")

                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            gr.Markdown("### 🎯 Recognition Settings")
                            sim_threshold = gr.Slider(
                                0.1,
                                0.9,
                                value=0.2,
                                step=0.02,
                                label="🎯 Similarity Threshold",
                                info="Higher = more strict matching, Lower = more matches",
                            )
                            det_threshold = gr.Slider(
                                0.05,
                                0.8,
                                value=0.15,
                                step=0.02,
                                label="🔍 Detection Threshold",
                                info="Lower = detect more faces (improved: now 0.15 default)",
                            )
                            frame_skip = gr.Slider(
                                1,
                                120,
                                value=15,
                                step=1,
                                label="⏭️ Frame Skip",
                                info="Process every N frames (improved: now 15 default)",
                            )
                            max_faces = gr.Slider(
                                1,
                                50,
                                value=30,
                                step=1,
                                label="👥 Max Faces per Frame",
                                info="Maximum faces to detect (improved: now 30 default)",
                            )

                    with gr.Column():
                        with gr.Group():
                            gr.Markdown("### 🖥️ Hardware Settings")
                            use_gpu = gr.Checkbox(
                                value=True,
                                label="⚡ Use GPU Acceleration",
                                info="Enable CUDA/Metal acceleration",
                            )
                            enable_chromadb = gr.Checkbox(
                                value=True,
                                label="🗄 Enable ChromaDB",
                                info="Use vector database for fast search",
                            )

                        with gr.Group():
                            gr.Markdown("### 🎨 UI Settings")
                            enhanced_ui = gr.Checkbox(
                                value=True,
                                label="✨ Enhanced UI",
                                info="Enable rounded corners, confidence bars, and face thumbnails",
                            )

                            settings_button = gr.Button(
                                "💾 Save Settings", variant="primary", size="lg"
                            )
                            settings_status = gr.HTML("⚙️ Ready to save settings")

                def update_settings_with_feedback(*args):
                    result = get_app().update_settings(*args)
                    return f"✅ {result}"

                settings_button.click(
                    update_settings_with_feedback,
                    inputs=[
                        sim_threshold,
                        det_threshold,
                        frame_skip,
                        max_faces,
                        use_gpu,
                        enable_chromadb,
                        enhanced_ui,
                    ],
                    outputs=[settings_status],
                )

            # UMAP Visualization Tab
            with gr.Tab("🗺️ UMAP Visualization"):
                gr.Markdown("## 🗺️ Face Embedding Visualization (UMAP)")
                gr.Markdown(
                    "*Visualize relationships between detected faces and known contestants using UMAP dimensionality reduction*"
                )

                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Group():
                            umap_plot = gr.Plot(
                                label="Face Embedding UMAP",
                                show_label=True,
                                container=True,
                            )

                    with gr.Column(scale=1):
                        with gr.Group():
                            gr.Markdown("### Controls")
                            umap_video_dropdown = gr.Dropdown(
                                choices=get_app().get_video_titles_for_dropdown(),
                                label="Select Video for Analysis",
                                show_label=True,
                                interactive=True,
                            )

                            generate_umap_btn = gr.Button(
                                "🗺️ Generate UMAP", variant="primary", size="lg"
                            )

                            umap_status = gr.HTML(
                                "Select a video and click Generate UMAP"
                            )

                        with gr.Group():
                            gr.Markdown("### 📖 How to Use UMAP")
                            gr.Markdown("""
                            **Steps:**
                            1. 📹 Select a video from the dropdown
                            2. ⚙️ Adjust frame skip in Settings tab if desired (default: every 15 frames)
                            3. 🗺️ Click "Generate UMAP" button  
                            4. ⏳ Wait for processing (respects your frame skip setting)
                            5. 📊 View the 2D embedding visualization
                            
                            **Settings-Based Processing:**
                            - Uses your current **Frame Skip** setting from Settings tab
                            - Uses your current **Similarity Threshold** setting
                            - Applies improved **Detection Threshold** (0.15) and **Adaptive Resolution**
                            - Processing time depends on frame skip: lower skip = more frames = longer processing
                            
                            **Frame Skip Examples:**
                            - **Skip 15** (default): ~2000 frames for 30min video → ~2-3 minutes processing
                            - **Skip 30**: ~1000 frames for 30min video → ~1-2 minutes processing  
                            - **Skip 1**: All frames → much longer but most comprehensive
                            
                            **Legend:**
                            - **Red stars** ⭐: Currently detected faces
                            - **Colored squares** 🟩: Known gallery faces (matched)
                            - **Gray circles** ⚪: Gallery faces (unmatched)
                            - **Green arrows** ➡️: Similarity connections (>0.5)
                            - **Line thickness**: Proportional to similarity score
                            
                            **💡 Tip:** Adjust frame skip in Settings for balance between speed and completeness.
                            """)

                def generate_umap_for_video(video_title):
                    """Generate UMAP visualization for selected video using settings-based frame selection."""
                    if not video_title:
                        return None, "Please select a video"

                    try:
                        app = get_app()

                        # Check if visualization service is available
                        if not app.visualization_service:
                            return None, "❌ UMAP visualization service not available"

                        # Get video path
                        video_path = app.get_video_path_from_title(video_title)

                        # Use current frame skip settings for consistent processing
                        frame_skip = app.config.recognition.frame_skip
                        similarity_threshold = (
                            app.config.recognition.similarity_threshold
                        )

                        import cv2

                        cap = cv2.VideoCapture(video_path)

                        if not cap.isOpened():
                            return None, f"❌ Could not open video: {video_title}"

                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps = cap.get(cv2.CAP_PROP_FPS)

                        if total_frames <= 0:
                            cap.release()
                            return None, f"❌ Invalid video: {video_title}"

                        all_matches = []
                        faces_found_count = 0
                        frame_count = 0
                        processed_count = 0

                        logger.info(
                            f"Processing frames with skip={frame_skip} (every {frame_skip} frames) from {total_frames} total frames for UMAP analysis"
                        )

                        # Process frames according to frame_skip setting
                        while cap.isOpened():
                            ret, frame = cap.read()
                            if not ret:
                                break

                            frame_count += 1

                            # Only process frames according to frame_skip setting
                            should_process = frame_count % frame_skip == 0

                            if should_process:
                                processed_count += 1

                                # Process frame to get face detections
                                matches = process_frame(
                                    frame, app.known_embeddings, similarity_threshold
                                )
                                if matches:
                                    all_matches.extend(matches)
                                    faces_found_count += len(matches)

                                # Log progress every 100 processed frames
                                if processed_count % 100 == 0:
                                    logger.info(
                                        f"Processed {processed_count} frames (frame {frame_count}/{total_frames}), found {faces_found_count} faces so far"
                                    )

                        logger.info(
                            f"UMAP processing complete: {faces_found_count} total faces from {processed_count} processed frames (frame skip: {frame_skip})"
                        )

                        cap.release()

                        if not all_matches:
                            return (
                                None,
                                f"❌ No faces detected in {processed_count} processed frames (every {frame_skip} frames)",
                            )

                        # Generate UMAP visualization
                        logger.info(
                            f"Generating UMAP for {len(all_matches)} face detections from video"
                        )
                        umap_fig = app.generate_umap_visualization(all_matches)

                        unique_faces = len(
                            set([name for _, name in all_matches if name != "Unknown"])
                        )

                        return (
                            umap_fig,
                            f"✅ Generated UMAP from {processed_count} frames (every {frame_skip}): {len(all_matches)} face detections ({unique_faces} unique people)",
                        )

                    except Exception as e:
                        logger.error(f"Error generating UMAP: {e}")
                        import traceback

                        traceback.print_exc()
                        return None, f"❌ Error: {str(e)}"

                generate_umap_btn.click(
                    generate_umap_for_video,
                    inputs=[umap_video_dropdown],
                    outputs=[umap_plot, umap_status],
                )

            # Similarity Analysis Tab
            with gr.Tab("📊 Similarity Analysis"):
                gr.Markdown("## 📊 Real-time Face Similarity Analysis")
                gr.Markdown(
                    "*Analyze similarity scores of the top 5 most similar faces as you navigate through video frames*"
                )

                with gr.Row():
                    with gr.Column(scale=1):
                        with gr.Group():
                            gr.Markdown("### 🎬 Video Selection")
                            similarity_video_dropdown = gr.Dropdown(
                                choices=get_app().get_video_titles_for_dropdown(),
                                label="Select Video for Analysis",
                                show_label=True,
                                interactive=True,
                            )

                            with gr.Row():
                                frame_number_input = gr.Number(
                                    label="Frame Number",
                                    value=1,
                                    minimum=1,
                                    maximum=10000,
                                    step=1,
                                    interactive=True,
                                )

                                analyze_frame_btn = gr.Button(
                                    "🔍 Analyze Frame", variant="primary", size="lg"
                                )

                            similarity_status = gr.HTML(
                                "Select a video and enter a frame number to analyze"
                            )

                            with gr.Row():
                                prev_frame_btn = gr.Button(
                                    "⬅️ Previous Frame", size="sm"
                                )
                                next_frame_btn = gr.Button("Next Frame ➡️", size="sm")

                        with gr.Group():
                            gr.Markdown("### 🖼️ Frame Preview")
                            frame_preview = gr.Image(
                                label="Current Frame with Face Detection",
                                show_label=True,
                                container=True,
                                height=300,
                                interactive=False,
                            )

                    with gr.Column(scale=2):
                        with gr.Group():
                            similarity_plot = gr.Plot(
                                label="Top 5 Similar Faces",
                                show_label=True,
                                container=True,
                            )

                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            gr.Markdown("### 📈 Timeline Analysis")
                            timeline_plot = gr.Plot(
                                label="Similarity Timeline",
                                show_label=True,
                                container=True,
                            )

                            with gr.Row():
                                timeline_window_size = gr.Slider(
                                    minimum=50,
                                    maximum=500,
                                    value=100,
                                    step=10,
                                    label="Timeline Window Size (frames)",
                                    info="Number of frames to show around current frame",
                                )

                                generate_timeline_btn = gr.Button(
                                    "📈 Generate Timeline",
                                    variant="secondary",
                                    size="lg",
                                )

                # Store video analysis data
                video_analysis_data = gr.State(value={})

                def analyze_single_frame(video_title, frame_number):
                    """Analyze a single frame and return similarity data with frame preview."""
                    if not video_title:
                        return None, None, "Please select a video"

                    if not frame_number or frame_number < 1:
                        return None, None, "Please enter a valid frame number"

                    try:
                        app = get_app()

                        # Get video path
                        video_path = app.get_video_path_from_title(video_title)

                        import cv2

                        cap = cv2.VideoCapture(video_path)

                        if not cap.isOpened():
                            return None, None, f"❌ Could not open video: {video_title}"

                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps = cap.get(cv2.CAP_PROP_FPS)

                        if frame_number > total_frames:
                            cap.release()
                            return (
                                None,
                                None,
                                f"❌ Frame {frame_number} exceeds video length ({total_frames} frames)",
                            )

                        # Seek to the specific frame
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
                        ret, frame = cap.read()
                        cap.release()

                        if not ret:
                            return None, None, f"❌ Could not read frame {frame_number}"

                        # Keep original frame for preview
                        original_frame = frame.copy()

                        # Process the frame with similarity data
                        matches, frame_similarities = process_frame(
                            frame,
                            app.known_embeddings,
                            app.config.recognition.similarity_threshold,
                            return_similarities=True,
                        )

                        # Create annotated frame preview even if no similarities
                        timestamp = frame_number / fps if fps > 0 else 0
                        time_str = (
                            f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"
                        )

                        # Draw face detection boxes and labels on the frame
                        annotated_frame = draw_boxes_and_labels(
                            original_frame,
                            matches,
                            f"Frame {frame_number} ({time_str})",
                            {},  # No persistent labels needed for single frame analysis
                            frame_number,
                            enhanced_ui=get_app().config.ui.enhanced_ui,
                        )

                        # Convert BGR to RGB for Gradio display
                        preview_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)

                        if not frame_similarities:
                            return (
                                None,
                                preview_frame,
                                f"Frame {frame_number}: No faces detected or no similarities above threshold",
                            )

                        # Generate similarity plot
                        similarity_fig = (
                            app.visualization_service.create_similarity_plot(
                                frame_similarities, frame_number, max_faces=5
                            )
                        )

                        detected_faces = len(
                            set([s["face_id"] for s in frame_similarities])
                        )
                        total_comparisons = len(frame_similarities)

                        status_msg = f"✅ Frame {frame_number}: Found {detected_faces} faces, {total_comparisons} similarity comparisons"

                        return similarity_fig, preview_frame, status_msg

                    except Exception as e:
                        logger.error(f"Error analyzing frame {frame_number}: {e}")
                        return (
                            None,
                            None,
                            f"❌ Error analyzing frame {frame_number}: {str(e)}",
                        )

                def navigate_frame(video_title, current_frame, direction):
                    """Navigate to previous or next frame."""
                    if not video_title or not current_frame:
                        return current_frame

                    new_frame = current_frame + direction
                    return max(1, new_frame)  # Ensure frame number is at least 1

                def generate_timeline_analysis(video_title, current_frame, window_size):
                    """Generate timeline analysis for the video around the current frame."""
                    if not video_title:
                        return None, "Please select a video"

                    try:
                        app = get_app()
                        video_path = app.get_video_path_from_title(video_title)

                        import cv2

                        cap = cv2.VideoCapture(video_path)

                        if not cap.isOpened():
                            return None, f"❌ Could not open video: {video_title}"

                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                        # Determine frame range around current frame
                        start_frame = max(1, current_frame - window_size // 2)
                        end_frame = min(total_frames, current_frame + window_size // 2)

                        timeline_data = []

                        # Process frames in the range
                        for frame_num in range(
                            start_frame, end_frame + 1, max(1, window_size // 50)
                        ):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num - 1)
                            ret, frame = cap.read()

                            if ret:
                                matches, frame_similarities = process_frame(
                                    frame,
                                    app.known_embeddings,
                                    app.config.recognition.similarity_threshold,
                                    return_similarities=True,
                                )

                                timeline_data.append(
                                    {
                                        "frame": frame_num,
                                        "similarities": frame_similarities,
                                    }
                                )

                        cap.release()

                        if not timeline_data:
                            return None, "No timeline data generated"

                        # Generate timeline plot
                        timeline_fig = (
                            app.visualization_service.create_frame_timeline_plot(
                                timeline_data, current_frame, window_size
                            )
                        )

                        return (
                            timeline_fig,
                            f"✅ Generated timeline for {len(timeline_data)} frames around frame {current_frame}",
                        )

                    except Exception as e:
                        logger.error(f"Error generating timeline: {e}")
                        return None, f"❌ Error generating timeline: {str(e)}"

                # Event handlers
                analyze_frame_btn.click(
                    analyze_single_frame,
                    inputs=[similarity_video_dropdown, frame_number_input],
                    outputs=[similarity_plot, frame_preview, similarity_status],
                )

                prev_frame_btn.click(
                    lambda video, frame: navigate_frame(video, frame, -1),
                    inputs=[similarity_video_dropdown, frame_number_input],
                    outputs=[frame_number_input],
                ).then(
                    analyze_single_frame,
                    inputs=[similarity_video_dropdown, frame_number_input],
                    outputs=[similarity_plot, frame_preview, similarity_status],
                )

                next_frame_btn.click(
                    lambda video, frame: navigate_frame(video, frame, 1),
                    inputs=[similarity_video_dropdown, frame_number_input],
                    outputs=[frame_number_input],
                ).then(
                    analyze_single_frame,
                    inputs=[similarity_video_dropdown, frame_number_input],
                    outputs=[similarity_plot, frame_preview, similarity_status],
                )

                generate_timeline_btn.click(
                    generate_timeline_analysis,
                    inputs=[
                        similarity_video_dropdown,
                        frame_number_input,
                        timeline_window_size,
                    ],
                    outputs=[timeline_plot, similarity_status],
                )

            # Analytics Tab
            with gr.Tab("📊 Analytics"):
                gr.Markdown("## 📊 Performance Analytics")

                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Group():
                            analytics_chart = gr.Plot(
                                label="📈 Performance Metrics",
                                show_label=True,
                                container=True,
                            )
                            with gr.Row():
                                refresh_button = gr.Button(
                                    "🔄 Refresh Data", variant="secondary", size="sm"
                                )
                                auto_refresh = gr.Checkbox(
                                    label="♾️ Auto-refresh",
                                    value=False,
                                    info="Update every 5 seconds",
                                )

                    with gr.Column(scale=1):
                        with gr.Group():
                            gr.Markdown("### 📊 System Status")
                            status_display = gr.Markdown(get_app().get_system_status())

                refresh_button.click(
                    get_app().get_performance_chart, outputs=[analytics_chart]
                )

                refresh_button.click(
                    get_app().get_system_status, outputs=[status_display]
                )

            # System Status Tab
            with gr.Tab("🔧 System"):
                gr.Markdown("## System Information")

                system_info = gr.Markdown(get_app().get_system_status())
                refresh_status = gr.Button("Refresh Status")

                refresh_status.click(get_app().get_system_status, outputs=[system_info])

        # Simple footer
        gr.Markdown("""
        ---
        **🎬 MV Face Recognition System** - Powered by InsightFace, ChromaDB, and Gradio
        """)

    return demo


def launch_app():
    """Launch the Gradio application."""
    try:
        # Create and launch interface
        demo = create_gradio_interface()
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=True,
            show_error=True,
            favicon_path=None,
            app_kwargs={"docs_url": "/docs", "redoc_url": "/redoc"},
        )

    except Exception as e:
        logger.error(f"Failed to launch app: {e}")
        print(f"Error launching application: {e}")


if __name__ == "__main__":
    launch_app()
