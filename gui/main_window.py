"""
Main window for MV Face Recognition GUI application.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QLabel,
    QProgressBar,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence

from gui.video_player import VideoPlayer
from gui.recognition_panel import RecognitionPanel
from gui.timeline_widget import TimelineWidget
from gui.settings_panel import SettingsPanel

# Import backend services
import sys

sys.path.append(".")
from src.services.video_processor import VideoProcessor
from src.database.chroma_setup import ChromaDBManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window for MV Face Recognition."""

    # Signals
    video_loaded = pyqtSignal(str)  # video_path
    processing_started = pyqtSignal()
    processing_finished = pyqtSignal(dict)  # results

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Backend services
        self.video_processor: Optional[VideoProcessor] = None
        self.db_manager: Optional[ChromaDBManager] = None

        # Current state
        self.current_video_path: Optional[str] = None
        self.is_processing = False

        # Setup UI
        self.init_ui()
        self.init_backend()

        # Setup status updates
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("MV Face Recognition - Professional Edition")
        self.setGeometry(100, 100, 1400, 900)

        # Create menu bar
        self.create_menu_bar()

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Create main splitter (horizontal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # Left side: Video and timeline
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Video player
        self.video_player = VideoPlayer()
        left_layout.addWidget(self.video_player, stretch=3)

        # Timeline
        self.timeline = TimelineWidget()
        left_layout.addWidget(self.timeline, stretch=0)

        main_splitter.addWidget(left_widget)

        # Right side: Recognition panel and settings
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Recognition panel
        self.recognition_panel = RecognitionPanel()
        right_splitter.addWidget(self.recognition_panel)

        # Settings panel
        self.settings_panel = SettingsPanel()
        right_splitter.addWidget(self.settings_panel)

        main_splitter.addWidget(right_splitter)

        # Set splitter proportions
        main_splitter.setSizes([1000, 400])  # 70/30 split
        right_splitter.setSizes([300, 200])  # 60/40 split

        # Create status bar
        self.create_status_bar()

        # Connect signals
        self.connect_signals()

    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Open video action
        open_action = QAction("&Open Video...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setStatusTip("Open a video file for processing")
        open_action.triggered.connect(self.open_video_dialog)
        file_menu.addAction(open_action)

        # Open video folder action
        open_folder_action = QAction("Open Video &Folder...", self)
        open_folder_action.setShortcut("Ctrl+Shift+O")
        open_folder_action.setStatusTip("Open the videos folder")
        open_folder_action.triggered.connect(self.open_videos_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        # Export menu
        export_menu = file_menu.addMenu("&Export")

        export_video_action = QAction("Export &Annotated Video...", self)
        export_video_action.setShortcut("Ctrl+E")
        export_video_action.setStatusTip("Export video with face annotations")
        export_video_action.triggered.connect(self.export_annotated_video)
        export_menu.addAction(export_video_action)

        export_csv_action = QAction("Export &CSV Results...", self)
        export_csv_action.setShortcut("Ctrl+Shift+E")
        export_csv_action.setStatusTip("Export recognition results as CSV")
        export_csv_action.triggered.connect(self.export_csv_results)
        export_menu.addAction(export_csv_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Processing menu
        process_menu = menubar.addMenu("&Processing")

        # Start processing action
        self.start_processing_action = QAction("&Start Processing", self)
        self.start_processing_action.setShortcut("F5")
        self.start_processing_action.setStatusTip("Start face recognition processing")
        self.start_processing_action.triggered.connect(self.start_processing)
        self.start_processing_action.setEnabled(False)
        process_menu.addAction(self.start_processing_action)

        # Stop processing action
        self.stop_processing_action = QAction("S&top Processing", self)
        self.stop_processing_action.setShortcut("Esc")
        self.stop_processing_action.setStatusTip("Stop current processing")
        self.stop_processing_action.triggered.connect(self.stop_processing)
        self.stop_processing_action.setEnabled(False)
        process_menu.addAction(self.stop_processing_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        # Toggle fullscreen action
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setStatusTip("Toggle fullscreen mode")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # About action
        about_action = QAction("&About", self)
        about_action.setStatusTip("Show information about this application")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = self.statusBar()

        # Main status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Video info label
        self.video_info_label = QLabel("No video loaded")
        self.status_bar.addPermanentWidget(self.video_info_label)

        # Database status
        self.db_status_label = QLabel("Database: Not loaded")
        self.status_bar.addPermanentWidget(self.db_status_label)

    def connect_signals(self):
        """Connect internal signals and slots."""
        # Video player signals
        self.video_player.position_changed.connect(self.timeline.set_position)
        self.video_player.duration_changed.connect(self.timeline.set_duration)

        # Timeline signals
        self.timeline.position_changed.connect(self.video_player.set_position)

        # Settings panel signals
        self.settings_panel.settings_changed.connect(self.on_settings_changed)

        # Recognition panel signals
        self.recognition_panel.start_processing_requested.connect(self.start_processing)
        self.recognition_panel.stop_processing_requested.connect(self.stop_processing)

    def init_backend(self):
        """Initialize backend services."""
        try:
            self.video_processor = VideoProcessor()
            self.db_manager = ChromaDBManager()

            # Get database stats
            stats = self.db_manager.get_database_stats()
            self.db_status_label.setText(
                f"Database: {stats['total_embeddings']} contestants"
            )

            logger.info("Backend services initialized successfully")
            self.status_label.setText("Ready - Backend initialized")

        except Exception as e:
            logger.error(f"Failed to initialize backend: {e}")
            self.status_label.setText(f"Error: {e}")

            # Show error dialog
            QMessageBox.critical(
                self,
                "Initialization Error",
                f"Failed to initialize backend services:\n\n{e}\n\n"
                "Please check your configuration and try again.",
            )

    def open_video_dialog(self):
        """Open file dialog to select a video."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video File",
            "source/videos",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv);;All Files (*)",
        )

        if file_path:
            self.load_video(file_path)

    def open_videos_folder(self):
        """Open the videos folder in file explorer."""
        videos_path = Path("source/videos")
        if videos_path.exists():
            # Open folder in system file manager
            import subprocess
            import platform

            if platform.system() == "Windows":
                subprocess.run(["explorer", str(videos_path)])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(videos_path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(videos_path)])
        else:
            QMessageBox.warning(
                self, "Folder Not Found", f"Videos folder not found: {videos_path}"
            )

    def load_video(self, video_path: str):
        """Load a video file."""
        try:
            # Load video in player
            self.video_player.load_video(video_path)

            # Update current video path
            self.current_video_path = video_path

            # Get video info
            if self.video_processor:
                video_info = self.video_processor.get_video_info(Path(video_path).name)
                duration = video_info.get("duration_formatted", "Unknown")
                resolution = (
                    f"{video_info.get('width', 0)}x{video_info.get('height', 0)}"
                )
                self.video_info_label.setText(
                    f"{Path(video_path).name} | {duration} | {resolution}"
                )

            # Enable processing
            self.start_processing_action.setEnabled(True)

            # Update status
            self.status_label.setText(f"Loaded: {Path(video_path).name}")

            # Emit signal
            self.video_loaded.emit(video_path)

            logger.info(f"Video loaded: {video_path}")

        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            QMessageBox.critical(
                self, "Video Load Error", f"Failed to load video:\n\n{e}"
            )

    def start_processing(self):
        """Start face recognition processing."""
        if not self.current_video_path or self.is_processing:
            return

        try:
            self.is_processing = True
            self.start_processing_action.setEnabled(False)
            self.stop_processing_action.setEnabled(True)

            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate

            # Update status
            self.status_label.setText("Processing video...")

            # Start processing in recognition panel
            self.recognition_panel.start_processing(
                self.current_video_path, self.video_processor
            )

            # Emit signal
            self.processing_started.emit()

            logger.info("Face recognition processing started")

        except Exception as e:
            logger.error(f"Failed to start processing: {e}")
            self.is_processing = False
            self.start_processing_action.setEnabled(True)
            self.stop_processing_action.setEnabled(False)
            self.progress_bar.setVisible(False)

            QMessageBox.critical(
                self, "Processing Error", f"Failed to start processing:\n\n{e}"
            )

    def stop_processing(self):
        """Stop face recognition processing."""
        if not self.is_processing:
            return

        try:
            self.recognition_panel.stop_processing()

            self.is_processing = False
            self.start_processing_action.setEnabled(True)
            self.stop_processing_action.setEnabled(False)

            # Hide progress
            self.progress_bar.setVisible(False)

            # Update status
            self.status_label.setText("Processing stopped")

            logger.info("Face recognition processing stopped")

        except Exception as e:
            logger.error(f"Failed to stop processing: {e}")

    def on_settings_changed(self, settings: dict):
        """Handle settings changes."""
        try:
            # Update backend configuration
            if self.video_processor:
                # Save settings to config.json and reinitialize
                import json

                with open("config.json", "w") as f:
                    json.dump(settings, f, indent=4)

                # Reinitialize video processor
                self.video_processor = VideoProcessor()

            logger.info("Settings updated successfully")

        except Exception as e:
            logger.error(f"Failed to update settings: {e}")

    def export_annotated_video(self):
        """Export annotated video."""
        # TODO: Implement video export
        QMessageBox.information(
            self, "Export Video", "Video export functionality will be implemented soon."
        )

    def export_csv_results(self):
        """Export CSV results."""
        # TODO: Implement CSV export
        QMessageBox.information(
            self, "Export CSV", "CSV export functionality will be implemented soon."
        )

    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About MV Face Recognition",
            """
            <h3>MV Face Recognition</h3>
            <p>Professional Edition with Custom GUI</p>
            <p>Version 2.0</p>
            <br>
            <p>Advanced face recognition system for music video analysis.</p>
            <p>Built with PyQt6, OpenCV, InsightFace, and ChromaDB.</p>
            <br>
            <p>© 2024 MV Face Recognition Team</p>
            """,
        )

    def update_status(self):
        """Update status information periodically."""
        if self.is_processing:
            # Update processing status from recognition panel
            stats = self.recognition_panel.get_processing_stats()
            if stats:
                fps = stats.get("processing_fps", 0)
                frames = stats.get("total_frames_processed", 0)
                faces = stats.get("total_faces_detected", 0)
                recognized = stats.get("total_faces_recognized", 0)

                self.status_label.setText(
                    f"Processing: {frames} frames, {faces} faces, {recognized} recognized | {fps:.1f} FPS"
                )

    def closeEvent(self, event):
        """Handle application close event."""
        if self.is_processing:
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Face recognition is currently running. Do you want to stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.stop_processing()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
