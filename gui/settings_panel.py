"""
Settings panel widget for configuring face recognition parameters.
"""

import logging
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QSlider,
    QSpinBox,
    QComboBox,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


class SettingsPanel(QWidget):
    """Panel for face recognition settings and configuration."""

    # Signals
    settings_changed = pyqtSignal(dict)  # settings dictionary

    def __init__(self):
        super().__init__()

        # Current settings
        self.current_settings = {}

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Face Detection Settings
        detection_group = QGroupBox("Face Detection")
        detection_layout = QVBoxLayout(detection_group)

        # Detection threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Detection Threshold:"))

        self.detection_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.detection_threshold_slider.setRange(10, 90)  # 0.1 to 0.9
        self.detection_threshold_slider.setValue(50)  # 0.5 default
        self.detection_threshold_slider.valueChanged.connect(self.on_settings_changed)
        threshold_layout.addWidget(self.detection_threshold_slider)

        self.detection_threshold_label = QLabel("0.50")
        self.detection_threshold_label.setMinimumWidth(40)
        threshold_layout.addWidget(self.detection_threshold_label)

        detection_layout.addLayout(threshold_layout)

        # Input size
        input_size_layout = QHBoxLayout()
        input_size_layout.addWidget(QLabel("Input Size:"))

        self.input_size_combo = QComboBox()
        self.input_size_combo.addItems(["320x320", "640x640", "1280x1280"])
        self.input_size_combo.setCurrentText("640x640")
        self.input_size_combo.currentTextChanged.connect(self.on_settings_changed)
        input_size_layout.addWidget(self.input_size_combo)

        input_size_layout.addStretch()
        detection_layout.addLayout(input_size_layout)

        layout.addWidget(detection_group)

        # Face Matching Settings
        matching_group = QGroupBox("Face Matching")
        matching_layout = QVBoxLayout(matching_group)

        # Similarity threshold
        similarity_layout = QHBoxLayout()
        similarity_layout.addWidget(QLabel("Similarity Threshold:"))

        self.similarity_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_threshold_slider.setRange(1, 80)  # 0.01 to 0.8
        self.similarity_threshold_slider.setValue(40)  # 0.4 default
        self.similarity_threshold_slider.valueChanged.connect(self.on_settings_changed)
        similarity_layout.addWidget(self.similarity_threshold_slider)

        self.similarity_threshold_label = QLabel("0.40")
        self.similarity_threshold_label.setMinimumWidth(40)
        similarity_layout.addWidget(self.similarity_threshold_label)

        matching_layout.addLayout(similarity_layout)

        # Max results
        max_results_layout = QHBoxLayout()
        max_results_layout.addWidget(QLabel("Max Results:"))

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 20)
        self.max_results_spin.setValue(5)
        self.max_results_spin.valueChanged.connect(self.on_settings_changed)
        max_results_layout.addWidget(self.max_results_spin)

        max_results_layout.addStretch()
        matching_layout.addLayout(max_results_layout)

        layout.addWidget(matching_group)

        # Video Processing Settings
        video_group = QGroupBox("Video Processing")
        video_layout = QVBoxLayout(video_group)

        # Frame skip
        frame_skip_layout = QHBoxLayout()
        frame_skip_layout.addWidget(QLabel("Frame Skip:"))

        self.frame_skip_spin = QSpinBox()
        self.frame_skip_spin.setRange(1, 30)
        self.frame_skip_spin.setValue(5)
        self.frame_skip_spin.setSuffix(" frames")
        self.frame_skip_spin.valueChanged.connect(self.on_settings_changed)
        frame_skip_layout.addWidget(self.frame_skip_spin)

        frame_skip_layout.addStretch()
        video_layout.addLayout(frame_skip_layout)

        # Output FPS
        output_fps_layout = QHBoxLayout()
        output_fps_layout.addWidget(QLabel("Output FPS:"))

        self.output_fps_spin = QSpinBox()
        self.output_fps_spin.setRange(1, 60)
        self.output_fps_spin.setValue(24)
        self.output_fps_spin.setSuffix(" fps")
        self.output_fps_spin.valueChanged.connect(self.on_settings_changed)
        output_fps_layout.addWidget(self.output_fps_spin)

        output_fps_layout.addStretch()
        video_layout.addLayout(output_fps_layout)

        # Annotation settings
        annotation_layout = QHBoxLayout()
        annotation_layout.addWidget(QLabel("Annotation Scale:"))

        self.annotation_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.annotation_scale_slider.setRange(1, 20)  # 0.1 to 2.0
        self.annotation_scale_slider.setValue(7)  # 0.7 default
        self.annotation_scale_slider.valueChanged.connect(self.on_settings_changed)
        annotation_layout.addWidget(self.annotation_scale_slider)

        self.annotation_scale_label = QLabel("0.7")
        self.annotation_scale_label.setMinimumWidth(30)
        annotation_layout.addWidget(self.annotation_scale_label)

        video_layout.addLayout(annotation_layout)

        layout.addWidget(video_group)

        # Paths Settings
        paths_group = QGroupBox("Paths")
        paths_layout = QVBoxLayout(paths_group)

        # Videos directory
        videos_layout = QHBoxLayout()
        videos_layout.addWidget(QLabel("Videos Dir:"))

        self.videos_path_edit = QLineEdit("source/videos")
        self.videos_path_edit.textChanged.connect(self.on_settings_changed)
        videos_layout.addWidget(self.videos_path_edit)

        videos_browse_btn = QPushButton("Browse")
        videos_browse_btn.clicked.connect(self.browse_videos_dir)
        videos_layout.addWidget(videos_browse_btn)

        paths_layout.addLayout(videos_layout)

        # Contestants directory
        contestants_layout = QHBoxLayout()
        contestants_layout.addWidget(QLabel("Contestants Dir:"))

        self.contestants_path_edit = QLineEdit("source/photo/contestants")
        self.contestants_path_edit.textChanged.connect(self.on_settings_changed)
        contestants_layout.addWidget(self.contestants_path_edit)

        contestants_browse_btn = QPushButton("Browse")
        contestants_browse_btn.clicked.connect(self.browse_contestants_dir)
        contestants_layout.addWidget(contestants_browse_btn)

        paths_layout.addLayout(contestants_layout)

        layout.addWidget(paths_group)

        # Control buttons
        buttons_layout = QHBoxLayout()

        # Reset to defaults
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        buttons_layout.addWidget(reset_btn)

        buttons_layout.addStretch()

        # Save settings
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_btn)

        # Apply settings
        apply_btn = QPushButton("✅ Apply")
        apply_btn.clicked.connect(self.apply_settings)
        buttons_layout.addWidget(apply_btn)

        layout.addLayout(buttons_layout)

        layout.addStretch()

        # Connect slider value changes to labels
        self.detection_threshold_slider.valueChanged.connect(
            self.update_detection_threshold_label
        )
        self.similarity_threshold_slider.valueChanged.connect(
            self.update_similarity_threshold_label
        )
        self.annotation_scale_slider.valueChanged.connect(
            self.update_annotation_scale_label
        )

    def update_detection_threshold_label(self, value):
        """Update detection threshold label."""
        threshold = value / 100.0
        self.detection_threshold_label.setText(f"{threshold:.2f}")

    def update_similarity_threshold_label(self, value):
        """Update similarity threshold label."""
        threshold = value / 100.0
        self.similarity_threshold_label.setText(f"{threshold:.2f}")

    def update_annotation_scale_label(self, value):
        """Update annotation scale label."""
        scale = value / 10.0
        self.annotation_scale_label.setText(f"{scale:.1f}")

    def load_settings(self):
        """Load settings from config.json."""
        try:
            config_path = Path("config.json")
            if config_path.exists():
                with open(config_path, "r") as f:
                    settings = json.load(f)

                # Face detection settings
                detection_threshold = settings.get("face_detection", {}).get(
                    "detection_threshold", 0.5
                )
                self.detection_threshold_slider.setValue(int(detection_threshold * 100))

                input_size = settings.get("face_detection", {}).get(
                    "input_size", [640, 640]
                )
                size_text = f"{input_size[0]}x{input_size[1]}"
                index = self.input_size_combo.findText(size_text)
                if index >= 0:
                    self.input_size_combo.setCurrentIndex(index)

                # Face matching settings
                similarity_threshold = settings.get("face_matching", {}).get(
                    "similarity_threshold", 0.4
                )
                self.similarity_threshold_slider.setValue(
                    int(similarity_threshold * 100)
                )

                max_results = settings.get("face_matching", {}).get("max_results", 5)
                self.max_results_spin.setValue(max_results)

                # Video processing settings
                frame_skip = settings.get("video_processing", {}).get("frame_skip", 5)
                self.frame_skip_spin.setValue(frame_skip)

                output_fps = settings.get("video_processing", {}).get("output_fps", 24)
                self.output_fps_spin.setValue(output_fps)

                annotation_scale = settings.get("video_processing", {}).get(
                    "annotation_font_scale", 0.7
                )
                self.annotation_scale_slider.setValue(int(annotation_scale * 10))

                # Paths
                videos_dir = settings.get("paths", {}).get(
                    "videos_dir", "source/videos"
                )
                self.videos_path_edit.setText(videos_dir)

                contestants_dir = settings.get("paths", {}).get(
                    "contestants_dir", "source/photo/contestants"
                )
                self.contestants_path_edit.setText(contestants_dir)

                self.current_settings = settings
                logger.info("Settings loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self.reset_to_defaults()

    def save_settings(self):
        """Save current settings to config.json."""
        try:
            settings = self.get_current_settings()

            with open("config.json", "w") as f:
                json.dump(settings, f, indent=4)

            self.current_settings = settings
            logger.info("Settings saved successfully")

            QMessageBox.information(
                self, "Settings Saved", "Settings have been saved to config.json"
            )

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save settings:\\n\\n{e}"
            )

    def apply_settings(self):
        """Apply current settings."""
        settings = self.get_current_settings()
        self.current_settings = settings
        self.settings_changed.emit(settings)
        logger.info("Settings applied")

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        # Face detection defaults
        self.detection_threshold_slider.setValue(50)  # 0.5
        self.input_size_combo.setCurrentText("640x640")

        # Face matching defaults
        self.similarity_threshold_slider.setValue(40)  # 0.4
        self.max_results_spin.setValue(5)

        # Video processing defaults
        self.frame_skip_spin.setValue(5)
        self.output_fps_spin.setValue(24)
        self.annotation_scale_slider.setValue(7)  # 0.7

        # Path defaults
        self.videos_path_edit.setText("source/videos")
        self.contestants_path_edit.setText("source/photo/contestants")

        logger.info("Settings reset to defaults")

    def get_current_settings(self) -> dict:
        """Get current settings as a dictionary."""
        # Parse input size
        size_text = self.input_size_combo.currentText()
        width, height = map(int, size_text.split("x"))

        settings = {
            "face_detection": {
                "model_name": "buffalo_l",
                "detection_threshold": self.detection_threshold_slider.value() / 100.0,
                "input_size": [width, height],
            },
            "face_matching": {
                "similarity_threshold": self.similarity_threshold_slider.value()
                / 100.0,
                "max_results": self.max_results_spin.value(),
            },
            "video_processing": {
                "frame_skip": self.frame_skip_spin.value(),
                "output_fps": self.output_fps_spin.value(),
                "annotation_font_scale": self.annotation_scale_slider.value() / 10.0,
                "annotation_thickness": 2,
            },
            "paths": {
                "videos_dir": self.videos_path_edit.text(),
                "contestants_dir": self.contestants_path_edit.text(),
                "chroma_db_path": "data/chroma_db",
            },
        }

        return settings

    def browse_videos_dir(self):
        """Browse for videos directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Videos Directory", self.videos_path_edit.text()
        )

        if dir_path:
            self.videos_path_edit.setText(dir_path)

    def browse_contestants_dir(self):
        """Browse for contestants directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Contestants Directory", self.contestants_path_edit.text()
        )

        if dir_path:
            self.contestants_path_edit.setText(dir_path)

    def on_settings_changed(self):
        """Handle any settings change."""
        # Update labels
        self.update_detection_threshold_label(self.detection_threshold_slider.value())
        self.update_similarity_threshold_label(self.similarity_threshold_slider.value())
        self.update_annotation_scale_label(self.annotation_scale_slider.value())
