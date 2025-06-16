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


def process_frame(frame, known_embeddings, similarity_threshold=0.5):
    """Process a video frame and detect/recognize faces with adaptive scaling."""
    try:
        detector = get_face_detector()
        if detector is None:
            return []

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
        for face in faces:
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

                    # Match against known embeddings
                    best_match = "Unknown"
                    best_score = 0

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

                            if (
                                similarity > similarity_threshold
                                and similarity > best_score
                            ):
                                best_match = name
                                best_score = similarity
                        except Exception as e:
                            logger.debug(f"Error comparing with {name}: {e}")
                            continue

                    matches.append((face, best_match))
            except Exception as e:
                logger.warning(f"Error processing face: {e}")
                matches.append((face, "Unknown"))

        return matches
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return []


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


def draw_boxes_and_labels(
    frame, matches, timestamp="", persistent_labels=None, current_frame=0
):
    """Draw bounding boxes and labels on detected faces with CJKV character support."""
    try:
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

            # Draw bounding box on original frame using OpenCV
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
        videos_dir = Path("/Users/swong/dev/mv-face-recognition/source/videos")
        if not videos_dir.exists():
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
                            file_stem = video_file.stem  # filename without extension

                            # First check if the filename exactly matches a title
                            matching_title = None
                            if file_stem in video_titles:
                                matching_title = file_stem
                            else:
                                # Map numbered video files to titles from videos_dl.py
                                video_number_mapping = {
                                    "v1": list(video_titles.keys())[0]
                                    if len(video_titles) > 0
                                    else None,
                                    "v2": list(video_titles.keys())[1]
                                    if len(video_titles) > 1
                                    else None,
                                    "v3": list(video_titles.keys())[2]
                                    if len(video_titles) > 2
                                    else None,
                                    "v4": list(video_titles.keys())[3]
                                    if len(video_titles) > 3
                                    else None,
                                }

                                # Check if this is a numbered video file
                                matching_title = video_number_mapping.get(file_stem)

                                if not matching_title:
                                    # Look for matching title in video_titles by content
                                    for title in video_titles.keys():
                                        # Check if the filename matches the title (with some normalization)
                                        if file_stem in title or title in file_stem:
                                            matching_title = title
                                            break

                            if matching_title:
                                # Prefer the properly named file over numbered versions
                                if (
                                    matching_title not in title_to_path_mapping
                                    or file_stem == matching_title
                                ):
                                    if matching_title not in video_files:
                                        video_files.append(matching_title)
                                    title_to_path_mapping[matching_title] = str(
                                        video_file
                                    )
                            else:
                                # If no title found, use filename
                                display_title = f"📹 {file_stem}"
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

    def _create_interactive_timeline(self, timeline_df, video_path):
        """Create an interactive HTML timeline for jumping to specific frames."""
        try:
            # Validate DataFrame structure
            required_columns = ["Time", "Frame", "Name"]
            if not all(col in timeline_df.columns for col in required_columns):
                raise ValueError(
                    f"DataFrame missing required columns. Expected: {required_columns}, Got: {list(timeline_df.columns)}"
                )

            if len(timeline_df) == 0:
                return "No recognition events found in video"

            # Create compact and user-friendly timeline
            recognition_count = len(timeline_df)
            unique_people = timeline_df["Name"].nunique()

            table_html = f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; margin: 10px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
                <div style='background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; margin-bottom: 15px;'>
                    <h3 style='color: white; margin: 0 0 10px 0; font-weight: bold;'>🎯 Recognition Timeline</h3>
                    <div style='color: rgba(255,255,255,0.9); font-size: 0.9em;'>
                        📊 <strong>{recognition_count}</strong> recognition events • 
                        👥 <strong>{unique_people}</strong> unique people detected •
                        💡 Click timestamps to navigate
                    </div>
                </div>
                <div style='max-height: 400px; overflow-y: auto; background: white; border-radius: 8px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);'>
                    <table style='width: 100%; border-collapse: collapse;'>
                        <thead style='position: sticky; top: 0; background: #2c3e50; z-index: 10;'>
                            <tr>
                                <th style='padding: 10px 15px; text-align: left; border: none; color: white; font-weight: bold;'>⏰ Time</th>
                                <th style='padding: 10px 15px; text-align: left; border: none; color: white; font-weight: bold;'>🎬 Frame</th>
                                <th style='padding: 10px 15px; text-align: left; border: none; color: white; font-weight: bold;'>👤 Name</th>
                            </tr>
                        </thead>
                        <tbody>
            """

            # Add table rows with better styling and hover effects
            for i, (_, row) in enumerate(timeline_df.iterrows()):
                bg_color = "#f8f9fa" if i % 2 == 0 else "white"
                hover_color = "#e3f2fd"
                table_html += f"""
                        <tr style='background: {bg_color}; transition: background-color 0.2s;' 
                            onmouseover='this.style.backgroundColor="{hover_color}"' 
                            onmouseout='this.style.backgroundColor="{bg_color}"'>
                            <td style='padding: 8px 15px; border: none; font-weight: bold; color: #1976d2; cursor: pointer;'>{row["Time"]}</td>
                            <td style='padding: 8px 15px; border: none; color: #666; font-family: monospace;'>{row["Frame"]}</td>
                            <td style='padding: 8px 15px; border: none; color: #2c3e50; font-weight: 500;'>{row["Name"]}</td>
                        </tr>
                """

            table_html += """
                        </tbody>
                    </table>
                </div>
                <div style='margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 6px;'>
                    <div style='color: rgba(255,255,255,0.9); font-size: 0.85em; text-align: center;'>
                        💡 <strong>Tip:</strong> Use your video player's seek/scrub controls to jump to these timestamps
                    </div>
                </div>
            </div>
            """

            # Try to create Plotly visualization as enhancement
            try:
                import plotly.graph_objects as go

                # Group recognitions by name for color coding
                names = timeline_df["Name"].unique()
                colors = px.colors.qualitative.Set3[: len(names)]
                color_map = dict(zip(names, colors))

                # Create timeline visualization
                fig = go.Figure()

                for name in names:
                    name_data = timeline_df[timeline_df["Name"] == name]
                    # Convert time strings to seconds for plotting
                    time_seconds = []
                    for time_str in name_data["Time"]:
                        try:
                            minutes, seconds = map(int, time_str.split(":"))
                            time_seconds.append(minutes * 60 + seconds)
                        except ValueError:
                            # Handle malformed time strings
                            time_seconds.append(0)

                    if time_seconds:  # Only add trace if we have valid time data
                        fig.add_trace(
                            go.Scatter(
                                x=time_seconds,
                                y=[name] * len(time_seconds),
                                mode="markers",
                                marker=dict(size=12, color=color_map[name]),
                                name=name,
                                text=[
                                    f"Frame {frame}: {name} at {time}"
                                    for frame, time in zip(
                                        name_data["Frame"], name_data["Time"]
                                    )
                                ],
                                hovertemplate="<b>%{text}</b><br>Recognition event<extra></extra>",
                            )
                        )

                fig.update_layout(
                    title="🎬 Recognition Timeline Visualization",
                    xaxis_title="Time (seconds)",
                    yaxis_title="Contestants",
                    height=max(300, len(names) * 50),
                    hovermode="closest",
                    showlegend=True,
                    margin=dict(l=20, r=20, t=40, b=20),
                )

                # Add Plotly chart to the result
                plotly_html = fig.to_html(
                    include_plotlyjs="cdn", div_id="timeline_chart"
                )
                return table_html + plotly_html

            except Exception as plotly_error:
                logger.debug(
                    f"Plotly visualization failed, using table only: {plotly_error}"
                )
                return table_html

        except Exception as e:
            logger.error(f"Timeline creation failed: {e}")
            # Fallback to simple text list
            try:
                timeline_text = "📍 Recognition Timeline:\n"
                for _, row in timeline_df.iterrows():
                    timeline_text += (
                        f"• {row['Time']} - {row['Name']} (Frame {row['Frame']})\n"
                    )
                return timeline_text
            except Exception:
                return "Error creating timeline - please check video processing results"

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

    def process_uploaded_video(self, video_path, progress=gr.Progress()):
        """Process an uploaded video file."""
        if not video_path:
            return None, "No video provided"

        try:
            self.processing_video = True
            results = []

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
                        frame, matches, time_str, label_persistence_cache, frame_count
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

            # Create timeline HTML if we have results
            timeline_html = "Process a video to see interactive timeline"
            if results:
                results_df = pd.DataFrame(results)
                # Fix column names for timeline
                timeline_df = results_df.copy()
                timeline_df.columns = [
                    "Frame",
                    "Time",
                    "Name",
                ]  # Rename to match expected format
                timeline_html = self._create_interactive_timeline(
                    timeline_df, output_path
                )

            return output_path, summary, timeline_html

        except Exception as e:
            self.processing_video = False
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
    ):
        """Update system settings."""
        try:
            self.config.recognition.similarity_threshold = similarity_threshold
            self.config.recognition.detection_threshold = detection_threshold
            self.config.recognition.frame_skip = frame_skip
            self.config.recognition.max_faces_per_frame = max_faces
            self.config.recognition.use_gpu = use_gpu
            self.config.recognition.enable_chromadb = enable_chromadb

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

                            # Timeline component for interactive navigation
                            recognition_timeline = gr.HTML(
                                label="🎯 Recognition Timeline",
                                value="Process a video to see interactive timeline",
                                visible=True,
                            )

                def process_selected_video(dropdown_title):
                    """Process video from dropdown selection."""
                    if not dropdown_title:
                        return (
                            None,
                            "Please select a video from the dropdown",
                            "No video selected",
                        )

                    # Convert title to actual file path
                    video_path = get_app().get_video_path_from_title(dropdown_title)
                    return get_app().process_uploaded_video(video_path)

                def refresh_video_dropdown():
                    """Refresh the video dropdown with current videos."""
                    return gr.Dropdown(
                        choices=get_app().get_video_titles_for_dropdown()
                    )

                video_button.click(
                    process_selected_video,
                    inputs=[video_dropdown],
                    outputs=[video_output, video_results, recognition_timeline],
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
                    ],
                    outputs=[settings_status],
                )

            # Contestant Management Tab
            with gr.Tab("👥 Contestants"):
                gr.Markdown("## Manage Contestant Database")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Add New Contestant")
                        new_name = gr.Textbox(label="Contestant Name")
                        new_image = gr.Image(type="pil", label="Contestant Photo")
                        add_button = gr.Button("Add Contestant", variant="primary")
                        add_status = gr.Textbox(label="Status", interactive=False)

                    with gr.Column():
                        gr.Markdown("### Current Contestants")
                        contestant_list = gr.JSON(label="Contestants Database")

                add_button.click(
                    get_app().add_contestant_embedding,
                    inputs=[new_name, new_image],
                    outputs=[add_status],
                )

                # Load contestant list on tab load
                demo.load(
                    lambda: get_app().get_contestant_list(), outputs=[contestant_list]
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
