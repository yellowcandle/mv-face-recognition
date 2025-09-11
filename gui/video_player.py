"""
Custom video player widget with OpenCV integration for real-time face recognition overlay.
"""

import logging
from typing import Optional
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

logger = logging.getLogger(__name__)


class VideoPlayerWidget(QWidget):
    """Custom video player widget with face recognition overlay."""

    # Signals
    position_changed = pyqtSignal(int)  # position in ms
    duration_changed = pyqtSignal(int)  # duration in ms
    frame_changed = pyqtSignal(np.ndarray)  # current frame

    def __init__(self):
        """Initialize the video player widget."""
        super().__init__()

        # Video state
        self.video_capture: Optional[cv2.VideoCapture] = None
        self.current_frame: Optional[np.ndarray] = None
        self.is_playing = False
        self.fps = 30.0
        self.total_frames = 0
        self.current_frame_number = 0

        # Face recognition overlay
        self.face_results = []
        self.show_overlay = True

        # Timer for playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Video display area
        self.video_label = QLabel()
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setScaledContents(True)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 2px solid #404040;
                border-radius: 8px;
            }
        """)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("No video loaded")
        layout.addWidget(self.video_label, stretch=1)

        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Play/Pause button
        self.play_button = QPushButton("▶️")
        self.play_button.setMaximumWidth(60)
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_button)

        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setEnabled(False)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.position_slider.valueChanged.connect(self.on_slider_moved)
        controls_layout.addWidget(self.position_slider, stretch=1)

        # Time labels
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        controls_layout.addWidget(self.time_label)

        # Overlay toggle button
        self.overlay_button = QPushButton("👁️")
        self.overlay_button.setMaximumWidth(40)
        self.overlay_button.setToolTip("Toggle face recognition overlay")
        self.overlay_button.clicked.connect(self.toggle_overlay)
        controls_layout.addWidget(self.overlay_button)

        layout.addLayout(controls_layout)

        # Slider tracking
        self.slider_pressed = False

    def load_video(self, video_path: str):
        """Load a video file."""
        try:
            # Stop current playback
            self.stop()

            # Open video capture
            self.video_capture = cv2.VideoCapture(video_path)

            if not self.video_capture.isOpened():
                raise ValueError(f"Could not open video: {video_path}")

            # Get video properties
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

            # Calculate duration
            duration_ms = (
                int((self.total_frames / self.fps) * 1000) if self.fps > 0 else 0
            )

            # Setup slider
            self.position_slider.setMaximum(duration_ms)
            self.position_slider.setEnabled(True)

            # Load first frame
            self.current_frame_number = 0
            self.seek_to_frame(0)

            # Enable controls
            self.play_button.setEnabled(True)

            # Update display
            self.update_time_display()

            # Emit signals
            self.duration_changed.emit(duration_ms)

            logger.info(
                f"Video loaded: {video_path}, FPS: {self.fps:.1f}, Frames: {self.total_frames}"
            )

        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            raise

    def play(self):
        """Start video playback."""
        if self.video_capture and not self.is_playing:
            self.is_playing = True
            self.play_button.setText("⏸️")

            # Calculate timer interval from FPS
            interval = int(1000 / self.fps) if self.fps > 0 else 33  # Default 30 FPS
            self.timer.start(interval)

    def pause(self):
        """Pause video playback."""
        if self.is_playing:
            self.is_playing = False
            self.play_button.setText("▶️")
            self.timer.stop()

    def stop(self):
        """Stop video playback."""
        self.pause()
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None

        self.current_frame = None
        self.current_frame_number = 0
        self.face_results = []

        # Reset UI
        self.video_label.setText("No video loaded")
        self.play_button.setEnabled(False)
        self.position_slider.setEnabled(False)
        self.position_slider.setValue(0)
        self.time_label.setText("00:00 / 00:00")

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def toggle_overlay(self):
        """Toggle face recognition overlay."""
        self.show_overlay = not self.show_overlay
        self.overlay_button.setText("👁️" if self.show_overlay else "👁️‍🗨️")
        self.update_display()

    def next_frame(self):
        """Advance to the next frame."""
        if not self.video_capture or self.slider_pressed:
            return

        ret, frame = self.video_capture.read()
        if ret:
            self.current_frame = frame
            self.current_frame_number += 1

            # Update display
            self.update_display()

            # Update slider
            position_ms = int((self.current_frame_number / self.fps) * 1000)
            self.position_slider.setValue(position_ms)
            self.position_changed.emit(position_ms)

            # Update time display
            self.update_time_display()

            # Emit frame signal
            self.frame_changed.emit(frame)

        else:
            # End of video
            self.pause()

    def seek_to_frame(self, frame_number: int):
        """Seek to a specific frame."""
        if not self.video_capture:
            return

        frame_number = max(0, min(frame_number, self.total_frames - 1))

        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_capture.read()

        if ret:
            self.current_frame = frame
            self.current_frame_number = frame_number
            self.update_display()

            # Update position
            position_ms = int((frame_number / self.fps) * 1000)
            self.position_slider.setValue(position_ms)
            self.position_changed.emit(position_ms)
            self.update_time_display()

            # Emit frame signal
            self.frame_changed.emit(frame)

    def set_position(self, position_ms: int):
        """Set playback position in milliseconds."""
        if not self.video_capture:
            return

        frame_number = int((position_ms / 1000.0) * self.fps)
        self.seek_to_frame(frame_number)

    def on_slider_pressed(self):
        """Handle slider press."""
        self.slider_pressed = True

    def on_slider_released(self):
        """Handle slider release."""
        self.slider_pressed = False
        position_ms = self.position_slider.value()
        self.set_position(position_ms)

    def on_slider_moved(self, value):
        """Handle slider movement while pressed."""
        if self.slider_pressed:
            self.update_time_display()

    def update_display(self):
        """Update the video display with current frame and overlay."""
        if self.current_frame is None:
            return

        frame = self.current_frame.copy()

        # Apply face recognition overlay
        if self.show_overlay and self.face_results:
            frame = self.draw_face_overlay(frame)

        # Convert frame to QPixmap and display
        qt_image = self.convert_cv_to_qt(frame)
        self.video_label.setPixmap(qt_image)

    def draw_face_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw face recognition overlay on frame."""
        overlay_frame = frame.copy()

        for face_result in self.face_results:
            bbox = face_result.get("bbox", [])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            matched = face_result.get("matched", False)

            # Choose color
            if matched:
                color = (0, 255, 0)  # Green for recognized
                name = face_result.get("contestant_name", "Unknown")
                confidence = face_result.get("recognition_confidence", 0.0)
                label = f"{name} ({confidence:.2f})"
            else:
                color = (0, 0, 255)  # Red for unrecognized
                det_confidence = face_result.get("detection_confidence", 0.0)
                label = f"Unknown ({det_confidence:.2f})"

            # Draw bounding box
            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, 3)

            # Draw label
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.rectangle(
                overlay_frame,
                (x1, y1 - label_size[1] - 15),
                (x1 + label_size[0] + 10, y1),
                color,
                -1,
            )
            cv2.putText(
                overlay_frame,
                label,
                (x1 + 5, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

        return overlay_frame

    def convert_cv_to_qt(self, cv_image: np.ndarray) -> QPixmap:
        """Convert OpenCV image to Qt QPixmap."""
        height, width, channel = cv_image.shape
        bytes_per_line = 3 * width

        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

        # Create QImage
        qt_image = QImage(
            rgb_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
        )

        # Convert to QPixmap
        return QPixmap.fromImage(qt_image)

    def update_time_display(self):
        """Update the time display."""
        if not self.video_capture:
            return

        current_ms = self.position_slider.value()
        total_ms = self.position_slider.maximum()

        current_time = self.ms_to_time_string(current_ms)
        total_time = self.ms_to_time_string(total_ms)

        self.time_label.setText(f"{current_time} / {total_time}")

    def ms_to_time_string(self, ms: int) -> str:
        """Convert milliseconds to time string (MM:SS)."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def set_face_results(self, face_results: list):
        """Set face recognition results for overlay."""
        self.face_results = face_results
        if self.show_overlay:
            self.update_display()


# Alias for backward compatibility
VideoPlayer = VideoPlayerWidget
