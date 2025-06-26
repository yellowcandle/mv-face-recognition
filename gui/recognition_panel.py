"""
Face recognition panel widget for displaying results and controls.
"""

import logging
from typing import Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QProgressBar,
    QTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot

import numpy as np

logger = logging.getLogger(__name__)


class ProcessingWorker(QThread):
    """Worker thread for video processing to avoid blocking the UI."""

    # Signals
    frame_processed = pyqtSignal(np.ndarray, list)  # frame, face_results
    progress_updated = pyqtSignal(int, int)  # current_frame, total_frames
    processing_finished = pyqtSignal(dict)  # final_results
    error_occurred = pyqtSignal(str)  # error_message

    def __init__(self, video_path: str, video_processor):
        super().__init__()
        self.video_path = video_path
        self.video_processor = video_processor
        self.should_stop = False

    def run(self):
        """Run the processing in a separate thread."""
        try:
            # Process video with real-time updates
            for frame_data in self.video_processor.process_video_realtime(
                self.video_path
            ):
                if self.should_stop:
                    break

                frame = frame_data["frame"]
                face_results = frame_data["face_results"]
                frame_number = frame_data["frame_number"]
                total_frames = frame_data["total_frames"]

                # Emit signals
                self.frame_processed.emit(frame, face_results)
                self.progress_updated.emit(frame_number, total_frames)

            # Processing completed
            if not self.should_stop:
                results = self.video_processor.get_processing_results()
                self.processing_finished.emit(results)

        except Exception as e:
            logger.error(f"Processing error: {e}")
            self.error_occurred.emit(str(e))

    def stop(self):
        """Stop the processing."""
        self.should_stop = True
        self.wait()  # Wait for thread to finish


class RecognitionPanel(QWidget):
    """Panel for face recognition results and processing controls."""

    # Signals
    start_processing_requested = pyqtSignal()
    stop_processing_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Processing state
        self.is_processing = False
        self.processing_worker: Optional[ProcessingWorker] = None
        self.processing_stats = {}
        self.recognition_results = []

        # Statistics tracking
        self.total_frames_processed = 0
        self.total_faces_detected = 0
        self.total_faces_recognized = 0
        self.processing_start_time = None

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Processing controls
        controls_group = QGroupBox("Processing Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Start/Stop buttons
        buttons_layout = QHBoxLayout()

        self.start_button = QPushButton("🚀 Start Recognition")
        self.start_button.clicked.connect(self.request_start_processing)
        buttons_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹️ Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.request_stop_processing)
        buttons_layout.addWidget(self.stop_button)

        controls_layout.addLayout(buttons_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        controls_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready to process")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.status_label)

        layout.addWidget(controls_group)

        # Statistics panel
        stats_group = QGroupBox("Processing Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.frames_label = QLabel("Frames: 0")
        self.faces_label = QLabel("Faces detected: 0")
        self.recognized_label = QLabel("Faces recognized: 0")
        self.fps_label = QLabel("Processing FPS: 0.0")

        stats_layout.addWidget(self.frames_label)
        stats_layout.addWidget(self.faces_label)
        stats_layout.addWidget(self.recognized_label)
        stats_layout.addWidget(self.fps_label)

        layout.addWidget(stats_group)

        # Results panel
        results_group = QGroupBox("Recognition Results")
        results_layout = QVBoxLayout(results_group)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(200)
        results_layout.addWidget(self.results_list)

        # Details text
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(150)
        self.details_text.setReadOnly(True)
        self.details_text.setPlainText("Processing results will appear here...")
        results_layout.addWidget(self.details_text)

        layout.addWidget(results_group, stretch=1)

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # Update every 100ms

    def request_start_processing(self):
        """Request to start processing."""
        self.start_processing_requested.emit()

    def request_stop_processing(self):
        """Request to stop processing."""
        self.stop_processing_requested.emit()

    def start_processing(self, video_path: str, video_processor):
        """Start the processing workflow."""
        if self.is_processing:
            return

        try:
            self.is_processing = True
            self.processing_start_time = datetime.now()

            # Reset statistics
            self.total_frames_processed = 0
            self.total_faces_detected = 0
            self.total_faces_recognized = 0
            self.recognition_results = []

            # Update UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            self.status_label.setText("Processing started...")

            # Clear results
            self.results_list.clear()
            self.details_text.setPlainText("Processing video...")

            # Start worker thread
            self.processing_worker = ProcessingWorker(video_path, video_processor)
            self.processing_worker.frame_processed.connect(self.on_frame_processed)
            self.processing_worker.progress_updated.connect(self.on_progress_updated)
            self.processing_worker.processing_finished.connect(
                self.on_processing_finished
            )
            self.processing_worker.error_occurred.connect(self.on_error_occurred)
            self.processing_worker.start()

            logger.info(f"Started processing: {video_path}")

        except Exception as e:
            logger.error(f"Failed to start processing: {e}")
            self.is_processing = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.setVisible(False)

    def stop_processing(self):
        """Stop the processing workflow."""
        if not self.is_processing:
            return

        try:
            if self.processing_worker:
                self.processing_worker.stop()
                self.processing_worker = None

            self.is_processing = False

            # Update UI
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Processing stopped")

            logger.info("Processing stopped by user")

        except Exception as e:
            logger.error(f"Failed to stop processing: {e}")

    @pyqtSlot(np.ndarray, list)
    def on_frame_processed(self, frame: np.ndarray, face_results: list):
        """Handle a processed frame."""
        self.total_frames_processed += 1
        self.total_faces_detected += len(face_results)

        # Count recognized faces
        recognized_count = sum(
            1 for result in face_results if result.get("matched", False)
        )
        self.total_faces_recognized += recognized_count

        # Add to results
        for result in face_results:
            if result.get("matched", False):
                self.recognition_results.append(
                    {
                        "frame_number": self.total_frames_processed,
                        "contestant_name": result.get("contestant_name", "Unknown"),
                        "confidence": result.get("recognition_confidence", 0.0),
                        "timestamp": result.get("timestamp", 0.0),
                    }
                )

    @pyqtSlot(int, int)
    def on_progress_updated(self, current_frame: int, total_frames: int):
        """Handle progress update."""
        if total_frames > 0:
            progress = int((current_frame / total_frames) * 100)
            self.progress_bar.setValue(progress)

            # Update status
            self.status_label.setText(
                f"Processing frame {current_frame}/{total_frames} ({progress}%)"
            )

    @pyqtSlot(dict)
    def on_processing_finished(self, results: dict):
        """Handle processing completion."""
        self.is_processing = False

        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)

        # Calculate final statistics
        processing_time = (datetime.now() - self.processing_start_time).total_seconds()
        avg_fps = (
            self.total_frames_processed / processing_time if processing_time > 0 else 0
        )

        self.status_label.setText(f"Processing completed in {processing_time:.1f}s")

        # Update results display
        self.update_results_display(results)

        logger.info(
            f"Processing completed: {len(self.recognition_results)} recognitions"
        )

    @pyqtSlot(str)
    def on_error_occurred(self, error_message: str):
        """Handle processing error."""
        self.is_processing = False

        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error_message}")

        logger.error(f"Processing error: {error_message}")

    def update_results_display(self, results: dict):
        """Update the results display with final data."""
        # Clear existing results
        self.results_list.clear()

        # Group results by contestant
        contestant_counts = {}
        for result in self.recognition_results:
            name = result["contestant_name"]
            if name not in contestant_counts:
                contestant_counts[name] = {
                    "count": 0,
                    "total_confidence": 0.0,
                    "appearances": [],
                }

            contestant_counts[name]["count"] += 1
            contestant_counts[name]["total_confidence"] += result["confidence"]
            contestant_counts[name]["appearances"].append(result)

        # Sort by count (most appearances first)
        sorted_contestants = sorted(
            contestant_counts.items(), key=lambda x: x[1]["count"], reverse=True
        )

        # Add to results list
        for name, data in sorted_contestants:
            avg_confidence = data["total_confidence"] / data["count"]
            item_text = f"{name}: {data['count']} appearances (avg confidence: {avg_confidence:.2f})"

            item = QListWidgetItem(item_text)
            self.results_list.addItem(item)

        # Update details text
        details = "Processing Summary:\n"
        details += f"Total frames processed: {self.total_frames_processed}\n"
        details += f"Total faces detected: {self.total_faces_detected}\n"
        details += f"Total faces recognized: {self.total_faces_recognized}\n"
        details += f"Recognition rate: {(self.total_faces_recognized / max(1, self.total_faces_detected) * 100):.1f}%\n"
        details += f"Unique contestants found: {len(contestant_counts)}\n\n"

        if sorted_contestants:
            details += "Top recognitions:\n"
            for name, data in sorted_contestants[:5]:  # Top 5
                avg_conf = data["total_confidence"] / data["count"]
                details += f"  {name}: {data['count']} times (avg: {avg_conf:.2f})\n"

        self.details_text.setPlainText(details)

    def update_display(self):
        """Update the display with current statistics."""
        if not self.is_processing:
            return

        # Calculate FPS
        if self.processing_start_time:
            elapsed = (datetime.now() - self.processing_start_time).total_seconds()
            fps = self.total_frames_processed / elapsed if elapsed > 0 else 0
        else:
            fps = 0

        # Update labels
        self.frames_label.setText(f"Frames: {self.total_frames_processed}")
        self.faces_label.setText(f"Faces detected: {self.total_faces_detected}")
        self.recognized_label.setText(
            f"Faces recognized: {self.total_faces_recognized}"
        )
        self.fps_label.setText(f"Processing FPS: {fps:.1f}")

    def get_processing_stats(self) -> dict:
        """Get current processing statistics."""
        if self.processing_start_time:
            elapsed = (datetime.now() - self.processing_start_time).total_seconds()
            fps = self.total_frames_processed / elapsed if elapsed > 0 else 0
        else:
            fps = 0

        return {
            "total_frames_processed": self.total_frames_processed,
            "total_faces_detected": self.total_faces_detected,
            "total_faces_recognized": self.total_faces_recognized,
            "processing_fps": fps,
            "is_processing": self.is_processing,
        }
