#!/usr/bin/env python3
"""
Setup script for HF Spaces to initialize contestants directory and embeddings.
This runs at startup to ensure the face recognition database is available.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def create_minimal_contestants_data():
    """Creates a minimal contestants directory structure for HF Spaces."""

    # Define paths
    contestants_dir = Path("source/photo/contestants")
    contestants_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"✅ Created contestants directory: {contestants_dir}")

    # Create a few sample contestant directories with placeholder images
    sample_contestants = [
        {"id": "1", "name": "Sample Contestant 1"},
        {"id": "2", "name": "Sample Contestant 2"},
        {"id": "3", "name": "Sample Contestant 3"},
    ]

    for contestant in sample_contestants:
        contestant_path = contestants_dir / contestant["id"]
        contestant_path.mkdir(exist_ok=True)

        # Create placeholder text file instead of actual images for now
        placeholder_file = contestant_path / "README.txt"
        placeholder_file.write_text(
            f"Placeholder for {contestant['name']}\n"
            f"To use face recognition, add photos named:\n"
            f"- {contestant['id']}-1.jpg\n"
            f"- {contestant['id']}-2.jpg\n"
            f"Upload photos via the Gradio interface."
        )

    logger.info(f"✅ Created {len(sample_contestants)} sample contestant directories")

    return contestants_dir

def create_contestant_info_csv():
    """Creates a basic contestant_info.csv file."""

    import pandas as pd

    # Create basic contestant info
    contestants_data = [
        {"contestant_number": 1, "name": "Sample Contestant 1", "description": "Placeholder contestant"},
        {"contestant_number": 2, "name": "Sample Contestant 2", "description": "Placeholder contestant"},
        {"contestant_number": 3, "name": "Sample Contestant 3", "description": "Placeholder contestant"},
    ]

    df = pd.DataFrame(contestants_data)
    csv_path = Path("contestant_info.csv")
    df.to_csv(csv_path, index=False)

    logger.info(f"✅ Created contestant info CSV: {csv_path}")
    return csv_path

def download_from_huggingface_hub():
    """
    Alternative: Download contestants data from HF Hub if available.
    This would be used if you upload your contestants data as a dataset.
    """
    try:
        # This is a placeholder - you would need to upload your data as an HF dataset first
        # from huggingface_hub import hf_hub_download
        # hf_hub_download(repo_id="your-username/mv-face-recognition-data", filename="contestants.zip")
        logger.info("HF Hub download not configured - using local setup")
        return False
    except Exception as e:
        logger.warning(f"Could not download from HF Hub: {e}")
        return False

def setup_for_hf_spaces():
    """Main setup function for HF Spaces deployment."""

    logger.info("🚀 Setting up contestants data for HF Spaces...")

    # Check if contestants directory already exists
    contestants_dir = Path("source/photo/contestants")
    if contestants_dir.exists() and any(contestants_dir.iterdir()):
        logger.info("✅ Contestants directory already exists and has content")
        return True

    # Try to download from HF Hub first
    if not download_from_huggingface_hub():
        # Fallback to creating minimal structure
        create_minimal_contestants_data()
        create_contestant_info_csv()

    # Create videos directory if it doesn't exist
    videos_dir = Path("source/videos")
    videos_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Ensured videos directory exists: {videos_dir}")

    # Create other necessary directories
    for dir_name in ["cache", "output", "output_frames", "output_mp4s"]:
        Path(dir_name).mkdir(exist_ok=True)

    logger.info("✅ HF Spaces setup completed successfully")
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_for_hf_spaces()
