"""
Drawing utilities for face recognition video processing.
Provides basic drawing functions for bounding boxes, labels, and timestamps.
"""


import cv2
import numpy as np


def draw_bounding_box(frame: np.ndarray, bbox: tuple[int, int, int, int],
                     color: tuple[int, int, int], padding: int = 0) -> None:
    """
    Draw a bounding box on the frame.

    Args:
        frame: The image frame to draw on
        bbox: Bounding box coordinates (x1, y1, x2, y2)
        color: Color for the bounding box (B, G, R)
        padding: Additional padding around the box
    """
    x1, y1, x2, y2 = bbox
    x1 -= padding
    y1 -= padding
    x2 += padding
    y2 += padding

    # Ensure coordinates are within frame bounds
    h, w = frame.shape[:2]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)


def draw_timestamp(frame: np.ndarray, timestamp: str,
                  position: tuple[int, int] | None = None) -> np.ndarray:
    """
    Draw timestamp on the frame.

    Args:
        frame: The image frame to draw on
        timestamp: Timestamp string to display
        position: Position to place the timestamp (x, y). If None, places at bottom-right

    Returns:
        Frame with timestamp drawn
    """
    h, w = frame.shape[:2]

    if position is None:
        # Default to bottom-right corner
        font_scale = 0.7
        thickness = 2
        (text_width, text_height), _ = cv2.getTextSize(
            timestamp, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        position = (w - text_width - 10, h - 10)

    # Draw text background for better visibility
    font_scale = 0.7
    thickness = 2
    (text_width, text_height), baseline = cv2.getTextSize(
        timestamp, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
    )

    # Background rectangle
    cv2.rectangle(
        frame,
        (position[0] - 5, position[1] - text_height - 5),
        (position[0] + text_width + 5, position[1] + baseline + 5),
        (0, 0, 0),  # Black background
        -1
    )

    # Text
    cv2.putText(
        frame,
        timestamp,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 255, 255),  # Yellow text
        thickness
    )

    return frame


def draw_label(frame: np.ndarray, text: str, position: tuple[int, int],
              color: tuple[int, int, int] = (0, 255, 0),
              font_scale: float = 0.6, thickness: int = 2) -> None:
    """
    Draw a text label on the frame.

    Args:
        frame: The image frame to draw on
        text: Text to display
        position: Position to place the text (x, y)
        color: Text color (B, G, R)
        font_scale: Scale of the font
        thickness: Thickness of the text
    """
    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        thickness
    )
