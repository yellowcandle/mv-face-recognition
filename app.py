#!/usr/bin/env python3
"""
Hugging Face Spaces entry point for MV Face Recognition.
This is the main file that HF Spaces will execute.
"""

import os
import logging
from pathlib import Path

# Configure logging for HF Spaces
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_hf_spaces_environment():
    """Setup environment for HF Spaces deployment."""

    # Set environment variables for HF Spaces
    os.environ.setdefault("GRADIO_SERVER_NAME", "0.0.0.0")
    os.environ.setdefault("GRADIO_SERVER_PORT", "7860")

    # Ensure required directories exist
    required_dirs = [
        "processed_videos",
        "metadata",
        "clips",
        "source/photo/contestants",
    ]

    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")

    # Check if we have pre-processed data
    processed_videos = list(Path("processed_videos").glob("*.mp4"))
    metadata_files = list(Path("metadata").glob("*.json"))

    logger.info(f"Found {len(processed_videos)} processed videos")
    logger.info(f"Found {len(metadata_files)} metadata files")

    if len(processed_videos) == 0:
        logger.warning(
            "No processed videos found - demo will run with limited functionality"
        )

    return True


def main():
    """Main entry point for HF Spaces."""
    try:
        logger.info("Starting MV Face Recognition on Hugging Face Spaces")

        # Setup HF Spaces environment
        setup_hf_spaces_environment()

        # Import and launch the Gradio app
        from gradio_app import main as launch_gradio

        launch_gradio()

    except ImportError as e:
        logger.error(f"Import error - missing dependencies: {e}")

        # Fallback simple interface if main app fails
        import gradio as gr

        def error_interface():
            return gr.Interface(
                fn=lambda: "⚠️ System not properly configured. Please check logs.",
                inputs=[],
                outputs=gr.Textbox(label="Status"),
                title="MV Face Recognition - Configuration Error",
                description="The system encountered configuration issues. Please contact the space owner.",
            )

        error_interface().launch()

    except Exception as e:
        logger.error(f"Error launching application: {e}")
        raise


if __name__ == "__main__":
    main()
