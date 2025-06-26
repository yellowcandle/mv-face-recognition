"""
Timeline widget for video navigation and face recognition annotations.
"""

import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics

logger = logging.getLogger(__name__)


class TimelineWidget(QWidget):
    """Custom timeline widget with face recognition annotations."""

    # Signals
    position_changed = pyqtSignal(int)  # position in ms

    def __init__(self):
        super().__init__()

        # Timeline state
        self.duration_ms = 0
        self.current_position_ms = 0
        self.face_annotations = []  # List of face detection annotations

        # UI properties
        self.timeline_height = 60
        self.annotation_height = 20

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Timeline header
        header_layout = QHBoxLayout()

        timeline_label = QLabel("Timeline")
        timeline_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(timeline_label)

        header_layout.addStretch()

        # Time display
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont("Courier", 9))
        header_layout.addWidget(self.time_label)

        layout.addLayout(header_layout)

        # Main timeline area
        self.timeline_area = TimelineArea()
        self.timeline_area.setMinimumHeight(self.timeline_height)
        self.timeline_area.setMaximumHeight(self.timeline_height)
        self.timeline_area.position_clicked.connect(self.on_position_clicked)
        layout.addWidget(self.timeline_area)

        # Annotation area
        self.annotation_area = AnnotationArea()
        self.annotation_area.setMinimumHeight(self.annotation_height)
        self.annotation_area.setMaximumHeight(self.annotation_height)
        layout.addWidget(self.annotation_area)

        # Navigation controls
        controls_layout = QHBoxLayout()

        # Previous/Next buttons
        self.prev_button = QPushButton("⏮️")
        self.prev_button.setMaximumWidth(40)
        self.prev_button.clicked.connect(self.previous_annotation)
        controls_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("⏭️")
        self.next_button.setMaximumWidth(40)
        self.next_button.clicked.connect(self.next_annotation)
        controls_layout.addWidget(self.next_button)

        controls_layout.addStretch()

        # Zoom controls
        zoom_label = QLabel("Zoom:")
        controls_layout.addWidget(zoom_label)

        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setMaximumWidth(30)
        controls_layout.addWidget(self.zoom_out_button)

        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setMaximumWidth(30)
        controls_layout.addWidget(self.zoom_in_button)

        layout.addLayout(controls_layout)

        # Initially disable controls
        self.set_enabled(False)

    def set_duration(self, duration_ms: int):
        """Set the timeline duration."""
        self.duration_ms = duration_ms
        self.timeline_area.set_duration(duration_ms)
        self.annotation_area.set_duration(duration_ms)
        self.update_time_display()
        self.set_enabled(duration_ms > 0)

    def set_position(self, position_ms: int):
        """Set the current playback position."""
        self.current_position_ms = max(0, min(position_ms, self.duration_ms))
        self.timeline_area.set_position(self.current_position_ms)
        self.annotation_area.set_position(self.current_position_ms)
        self.update_time_display()

    def add_face_annotation(
        self, timestamp_ms: int, contestant_name: str, confidence: float
    ):
        """Add a face recognition annotation."""
        annotation = {
            "timestamp_ms": timestamp_ms,
            "contestant_name": contestant_name,
            "confidence": confidence,
        }
        self.face_annotations.append(annotation)
        self.annotation_area.add_annotation(annotation)

    def clear_annotations(self):
        """Clear all face annotations."""
        self.face_annotations = []
        self.annotation_area.clear_annotations()

    def set_enabled(self, enabled: bool):
        """Enable or disable timeline controls."""
        self.prev_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
        self.zoom_in_button.setEnabled(enabled)
        self.zoom_out_button.setEnabled(enabled)
        self.timeline_area.setEnabled(enabled)
        self.annotation_area.setEnabled(enabled)

    def on_position_clicked(self, position_ms: int):
        """Handle timeline position click."""
        self.set_position(position_ms)
        self.position_changed.emit(position_ms)

    def previous_annotation(self):
        """Jump to previous face annotation."""
        if not self.face_annotations:
            return

        # Find previous annotation
        prev_annotation = None
        for annotation in reversed(self.face_annotations):
            if annotation["timestamp_ms"] < self.current_position_ms:
                prev_annotation = annotation
                break

        if prev_annotation:
            self.on_position_clicked(prev_annotation["timestamp_ms"])

    def next_annotation(self):
        """Jump to next face annotation."""
        if not self.face_annotations:
            return

        # Find next annotation
        next_annotation = None
        for annotation in self.face_annotations:
            if annotation["timestamp_ms"] > self.current_position_ms:
                next_annotation = annotation
                break

        if next_annotation:
            self.on_position_clicked(next_annotation["timestamp_ms"])

    def update_time_display(self):
        """Update the time display."""
        current_time = self.ms_to_time_string(self.current_position_ms)
        total_time = self.ms_to_time_string(self.duration_ms)
        self.time_label.setText(f"{current_time} / {total_time}")

    def ms_to_time_string(self, ms: int) -> str:
        """Convert milliseconds to time string (MM:SS)."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


class TimelineArea(QWidget):
    """Custom widget for the main timeline visualization."""

    position_clicked = pyqtSignal(int)  # position in ms

    def __init__(self):
        super().__init__()
        self.duration_ms = 0
        self.position_ms = 0
        self.setMouseTracking(True)

    def set_duration(self, duration_ms: int):
        """Set timeline duration."""
        self.duration_ms = duration_ms
        self.update()

    def set_position(self, position_ms: int):
        """Set current position."""
        self.position_ms = position_ms
        self.update()

    def paintEvent(self, event):
        """Paint the timeline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Background
        painter.fillRect(rect, QColor(60, 60, 60))

        # Timeline track
        track_rect = QRect(10, rect.height() // 2 - 2, rect.width() - 20, 4)
        painter.fillRect(track_rect, QColor(100, 100, 100))

        if self.duration_ms > 0:
            # Progress
            progress_width = int(
                (self.position_ms / self.duration_ms) * track_rect.width()
            )
            progress_rect = QRect(
                track_rect.x(), track_rect.y(), progress_width, track_rect.height()
            )
            painter.fillRect(progress_rect, QColor(20, 163, 133))

            # Position indicator
            pos_x = track_rect.x() + progress_width
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(pos_x, rect.y() + 5, pos_x, rect.bottom() - 5)

            # Time markers
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            painter.setFont(QFont("Arial", 8))

            # Draw markers every 30 seconds
            marker_interval_ms = 30000  # 30 seconds
            num_markers = self.duration_ms // marker_interval_ms

            for i in range(num_markers + 1):
                time_ms = i * marker_interval_ms
                if time_ms > self.duration_ms:
                    break

                x = track_rect.x() + int(
                    (time_ms / self.duration_ms) * track_rect.width()
                )
                painter.drawLine(x, track_rect.bottom() + 2, x, track_rect.bottom() + 8)

                # Time label
                time_str = self.ms_to_time_string(time_ms)
                fm = QFontMetrics(painter.font())
                text_width = fm.horizontalAdvance(time_str)
                text_x = x - text_width // 2
                painter.drawText(text_x, track_rect.bottom() + 20, time_str)

    def mousePressEvent(self, event):
        """Handle mouse click to seek."""
        if event.button() == Qt.MouseButton.LeftButton and self.duration_ms > 0:
            rect = self.rect()
            track_rect = QRect(10, rect.height() // 2 - 2, rect.width() - 20, 4)

            if track_rect.contains(event.pos()):
                # Calculate position
                relative_x = event.pos().x() - track_rect.x()
                position_ratio = relative_x / track_rect.width()
                position_ms = int(position_ratio * self.duration_ms)

                self.position_clicked.emit(position_ms)

    def ms_to_time_string(self, ms: int) -> str:
        """Convert milliseconds to time string (MM:SS)."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


class AnnotationArea(QWidget):
    """Custom widget for face recognition annotations."""

    def __init__(self):
        super().__init__()
        self.duration_ms = 0
        self.position_ms = 0
        self.annotations = []

        # Color mapping for contestants
        self.contestant_colors = {}
        self.color_palette = [
            QColor(255, 87, 87),  # Red
            QColor(87, 255, 87),  # Green
            QColor(87, 87, 255),  # Blue
            QColor(255, 255, 87),  # Yellow
            QColor(255, 87, 255),  # Magenta
            QColor(87, 255, 255),  # Cyan
            QColor(255, 165, 87),  # Orange
            QColor(165, 87, 255),  # Purple
        ]
        self.next_color_index = 0

    def set_duration(self, duration_ms: int):
        """Set annotation area duration."""
        self.duration_ms = duration_ms
        self.update()

    def set_position(self, position_ms: int):
        """Set current position."""
        self.position_ms = position_ms
        self.update()

    def add_annotation(self, annotation: dict):
        """Add a face recognition annotation."""
        self.annotations.append(annotation)

        # Assign color to new contestant
        name = annotation["contestant_name"]
        if name not in self.contestant_colors:
            color_index = self.next_color_index % len(self.color_palette)
            self.contestant_colors[name] = self.color_palette[color_index]
            self.next_color_index += 1

        self.update()

    def clear_annotations(self):
        """Clear all annotations."""
        self.annotations = []
        self.contestant_colors = {}
        self.next_color_index = 0
        self.update()

    def paintEvent(self, event):
        """Paint the annotations."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Background
        painter.fillRect(rect, QColor(40, 40, 40))

        if self.duration_ms > 0:
            # Draw annotations
            for annotation in self.annotations:
                timestamp_ms = annotation["timestamp_ms"]
                name = annotation["contestant_name"]
                confidence = annotation["confidence"]

                # Calculate position
                x = int((timestamp_ms / self.duration_ms) * rect.width())

                # Get color
                color = self.contestant_colors.get(name, QColor(255, 255, 255))

                # Draw annotation marker
                marker_width = max(2, min(8, rect.width() // 100))  # Adaptive width
                marker_rect = QRect(
                    x - marker_width // 2, 2, marker_width, rect.height() - 4
                )

                # Set opacity based on confidence
                color.setAlpha(int(confidence * 255))
                painter.fillRect(marker_rect, color)

            # Draw current position indicator
            if self.position_ms <= self.duration_ms:
                pos_x = int((self.position_ms / self.duration_ms) * rect.width())
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawLine(pos_x, 0, pos_x, rect.height())
