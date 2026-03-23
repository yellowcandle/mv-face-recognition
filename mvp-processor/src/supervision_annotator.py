"""
Supervision-powered video annotation with face tracking and timeline overlay.

Replaces the legacy cv2.rectangle/putText annotation with:
- sv.RoundBoxAnnotator for beautiful bounding boxes
- sv.LabelAnnotator for clean text labels
- sv.TraceAnnotator for face movement paths
- sv.ByteTrack for persistent face tracking across frames
- Custom timeline bar showing contestant screen time
"""

import logging
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Optional, Tuple

import supervision as sv

logger = logging.getLogger(__name__)

# --- CJK Font Support ---
_cjk_font_cache = {}

def _get_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a CJK-compatible font, cached by size."""
    if size in _cjk_font_cache:
        return _cjk_font_cache[size]
    # Try macOS, then Linux, then fallback
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, size=size)
            _cjk_font_cache[size] = font
            return font
    font = ImageFont.load_default()
    _cjk_font_cache[size] = font
    return font


def _put_cjk_text(frame, text, position, font_size=24, color=(255, 255, 255)):
    """Draw CJK-compatible text on a BGR frame using PIL."""
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = _get_cjk_font(font_size)
    draw.text(position, text, font=font, fill=color)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def insightface_to_sv_detections(recognitions, unmatched, contestant_id_map):
    """
    Convert face recognition results to Supervision's detection format.

    Args:
        recognitions: List of FaceRecognition objects (each has .detection.location
            as (top, right, bottom, left), .contestant_nickname, .match_confidence,
            .contestant_id)
        unmatched: List of FaceDetection objects (each has .location as
            (top, right, bottom, left), .confidence)
        contestant_id_map: dict mapping nickname -> stable int for color mapping

    Returns:
        sv.Detections with xyxy, confidence, class_id, and labels in data dict
    """
    xyxy_list = []
    confidences = []
    class_ids = []
    labels = []

    for r in recognitions:
        top, right, bottom, left = r.detection.location
        xyxy_list.append([left, top, right, bottom])
        confidences.append(float(r.match_confidence))
        class_ids.append(contestant_id_map.get(r.contestant_nickname, -1))
        labels.append(str(r.contestant_nickname))

    for det in unmatched:
        top, right, bottom, left = det.location
        xyxy_list.append([left, top, right, bottom])
        confidences.append(float(det.confidence))
        class_ids.append(0)
        labels.append("Unknown")

    if not xyxy_list:
        return sv.Detections.empty()

    return sv.Detections(
        xyxy=np.array(xyxy_list, dtype=np.float32),
        confidence=np.array(confidences, dtype=np.float32),
        class_id=np.array(class_ids, dtype=int),
        data={"labels": labels},
    )


def create_tracker(frame_rate=6):
    """Returns a configured ByteTrack instance for persistent face tracking."""
    return sv.ByteTrack(
        track_activation_threshold=0.25,
        lost_track_buffer=30,
        minimum_matching_threshold=0.3,
        frame_rate=frame_rate,
    )


def create_annotator_pipeline():
    """Returns a dict of Supervision annotators for the annotation pipeline."""
    return {
        "box": sv.RoundBoxAnnotator(thickness=2, roundness=0.3),
        "label": sv.LabelAnnotator(text_scale=0.5, text_padding=5),
        "trace": sv.TraceAnnotator(
            thickness=2, trace_length=30, position=sv.Position.BOTTOM_CENTER
        ),
    }


def draw_timeline_bar(frame, active_contestants, screen_time, color_map):
    """
    Draw a 60px timeline bar at the bottom of the frame.

    Args:
        frame: np.ndarray (BGR)
        active_contestants: list of nicknames currently on screen
        screen_time: dict[str, float] mapping nickname -> cumulative seconds
        color_map: dict[str, tuple] mapping nickname -> BGR color tuple

    Returns:
        Modified frame with timeline bar overlay
    """
    h, w = frame.shape[:2]
    bar_height = 60
    bar_top = h - bar_height

    # Semi-transparent overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, bar_top), (w, h), (20, 20, 20), -1)
    frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)

    # Use PIL for CJK-compatible text rendering
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = _get_cjk_font(28)
    font_small = _get_cjk_font(22)

    # Draw active contestant names with their colors
    x_offset = 10
    for name in active_contestants:
        bgr_color = color_map.get(name, (128, 128, 128))
        rgb_color = (bgr_color[2], bgr_color[1], bgr_color[0])
        draw.text((x_offset, bar_top + 8), name, font=font, fill=rgb_color)
        bbox = font.getbbox(name)
        text_width = bbox[2] - bbox[0] if bbox else len(name) * 20
        x_offset += text_width + 25

    # Show screen time summary
    if screen_time:
        top_name = max(screen_time, key=screen_time.get)
        top_time = screen_time[top_name]
        mins, secs = divmod(int(top_time), 60)
        summary = f"On screen: {len(active_contestants)} | Top: {top_name} {mins}:{secs:02d}"
        draw.text((10, bar_top + 38), summary, font=font_small, fill=(180, 180, 180))

    frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    return frame


def annotate_frame(frame, detections, annotators, screen_time=None, color_map=None):
    """
    Compose all annotations onto a single frame.

    Args:
        frame: np.ndarray (BGR)
        detections: sv.Detections instance
        annotators: dict from create_annotator_pipeline()
        screen_time: optional dict[str, float] for timeline bar
        color_map: optional dict[str, tuple] for timeline bar colors

    Returns:
        Annotated frame
    """
    if detections is None or len(detections) == 0:
        if screen_time and color_map:
            frame = draw_timeline_bar(frame, [], screen_time, color_map)
        return frame

    labels = detections.data.get("labels", [])

    frame = annotators["box"].annotate(scene=frame, detections=detections)

    # Draw labels with PIL for CJK support (Supervision's LabelAnnotator can't render CJK)
    if labels:
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        font = _get_cjk_font(28)
        for i, label in enumerate(labels):
            if i >= len(detections.xyxy):
                break
            x1, y1, x2, y2 = detections.xyxy[i].astype(int)
            conf = detections.confidence[i] if detections.confidence is not None else 0
            text = f"{label} ({conf:.2f})"
            bbox = font.getbbox(text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # Draw label background
            draw.rectangle([x1, y1 - th - 8, x1 + tw + 8, y1], fill=(0, 0, 0, 180))
            draw.text((x1 + 4, y1 - th - 6), text, font=font, fill=(255, 255, 255))
        frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    # TraceAnnotator requires tracker_id — skip if not available
    if detections.tracker_id is not None:
        frame = annotators["trace"].annotate(scene=frame, detections=detections)

    # Draw timeline bar
    active = [l for l in labels if l != "Unknown"]
    if screen_time is not None and color_map is not None:
        frame = draw_timeline_bar(frame, active, screen_time, color_map)

    return frame


def build_contestant_id_map(contestants_info: dict) -> dict:
    """Map contestant nicknames to stable integer IDs for color palette."""
    return {info["nickname"]: int(cid) for cid, info in contestants_info.items()}


def get_color_for_contestant(contestant_id: int, palette_size: int = 20) -> Tuple[int, int, int]:
    """Get a stable BGR color for a contestant ID."""
    PALETTE = [
        (75, 25, 230), (75, 180, 60), (25, 225, 255), (200, 130, 0),
        (49, 130, 245), (180, 30, 145), (244, 212, 66), (230, 50, 240),
        (69, 239, 191), (212, 190, 250), (144, 153, 70), (255, 190, 220),
        (36, 99, 154), (200, 250, 255), (0, 0, 128), (195, 255, 170),
        (0, 128, 128), (177, 216, 255), (117, 0, 0), (169, 169, 169),
    ]
    return PALETTE[contestant_id % len(PALETTE)]
