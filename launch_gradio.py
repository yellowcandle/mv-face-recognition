#!/usr/bin/env python3
"""
Launch script for the MV Face Recognition Gradio Interface.
This script provides an easy way to start the web interface.
"""

import sys
import os
import logging
import warnings
from pathlib import Path

# Suppress warnings early
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

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_environment():
    """Setup the environment for running the application."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set environment variables for optimal performance
    os.environ["OPENCV_OPENCL_DEVICE"] = "Auto"
    os.environ["INSIGHTFACE_DISABLE_LOGGING"] = "1"

    # Disable warnings for cleaner output
    os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"

    print("🚀 Starting MV Face Recognition System...")
    print("📁 Project root:", project_root)


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import gradio
        import cv2
        import numpy
        import pandas
        import plotly

        print("✅ All core dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("🎬 MV Face Recognition - Gradio Web Interface")
    print("=" * 60)

    setup_environment()

    if not check_dependencies():
        print("\n⚠️  Please install missing dependencies and try again.")
        sys.exit(1)

    try:
        # Import and launch the Gradio app
        from gradio_app import launch_app

        print("\n🌐 Starting web interface...")
        print("📍 The interface will be available at: http://localhost:7860")
        print("🛑 Press Ctrl+C to stop the server")
        print("-" * 60)

        launch_app()

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        logging.exception("Application startup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
