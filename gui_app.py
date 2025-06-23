#!/usr/bin/env python3
"""
MV Face Recognition - Custom GUI Application
Modern PyQt6-based interface with real-time video processing and face recognition.
"""

import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
except ImportError:
    print("PyQt6 not found. Please install it with: pip install PyQt6")
    sys.exit(1)

from gui.main_window import MainWindow


class MVFaceRecognitionApp:
    """Main application class for MV Face Recognition GUI."""

    def __init__(self):
        """Initialize the application."""
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("MV Face Recognition")
        self.app.setApplicationVersion("2.0")
        self.app.setOrganizationName("MV Face Recognition Team")

        # Set application style
        self.app.setStyle("Fusion")  # Modern cross-platform style

        # Apply dark theme
        self.apply_dark_theme()

        # Create main window
        self.main_window = MainWindow()

    def apply_dark_theme(self):
        """Apply a modern dark theme to the application."""
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 10pt;
        }
        
        QPushButton {
            background-color: #0d7377;
            border: 2px solid #14a085;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #14a085;
            border-color: #2bb3a0;
        }
        
        QPushButton:pressed {
            background-color: #0a5d61;
        }
        
        QPushButton:disabled {
            background-color: #404040;
            border-color: #606060;
            color: #808080;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #404040;
            height: 8px;
            background: #404040;
            border-radius: 4px;
        }
        
        QSlider::handle:horizontal {
            background: #14a085;
            border: 1px solid #2bb3a0;
            width: 18px;
            margin: -2px 0;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #2bb3a0;
        }
        
        QProgressBar {
            border: 2px solid #404040;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
        }
        
        QProgressBar::chunk {
            background-color: #14a085;
            border-radius: 6px;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #404040;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        
        QLabel {
            color: #ffffff;
        }
        
        QComboBox {
            border: 2px solid #404040;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: #404040;
        }
        
        QComboBox:hover {
            border-color: #14a085;
        }
        
        QComboBox::drop-down {
            border: none;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #ffffff;
        }
        
        QListWidget {
            background-color: #404040;
            border: 2px solid #606060;
            border-radius: 4px;
            alternate-background-color: #505050;
        }
        
        QListWidget::item {
            padding: 4px;
            border-bottom: 1px solid #606060;
        }
        
        QListWidget::item:selected {
            background-color: #14a085;
        }
        
        QTextEdit, QPlainTextEdit {
            background-color: #404040;
            border: 2px solid #606060;
            border-radius: 4px;
            padding: 4px;
        }
        
        QMenuBar {
            background-color: #363636;
            border-bottom: 1px solid #606060;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #14a085;
            border-radius: 4px;
        }
        
        QMenu {
            background-color: #363636;
            border: 1px solid #606060;
        }
        
        QMenu::item {
            padding: 4px 16px;
        }
        
        QMenu::item:selected {
            background-color: #14a085;
        }
        
        QStatusBar {
            background-color: #363636;
            border-top: 1px solid #606060;
        }
        """

        self.app.setStyleSheet(dark_stylesheet)

    def run(self):
        """Start the application main loop."""
        try:
            self.main_window.show()
            logger.info("MV Face Recognition GUI started successfully")
            return self.app.exec()
        except Exception as e:
            logger.error(f"Application error: {e}")
            return 1


def main():
    """Main entry point for the GUI application."""
    try:
        app = MVFaceRecognitionApp()
        sys.exit(app.run())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
