#!/usr/bin/env python3
"""
Initialize HF Spaces environment with proper error handling.
This runs before the main app to ensure all required directories exist.
"""

import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_git_lfs_files():
    """Check if Git LFS files are available."""
    contestants_dir = Path("source/photo/contestants")

    if contestants_dir.exists():
        # Count files in contestants directory
        jpg_files = list(contestants_dir.glob("**/*.jpg"))
        npy_files = list(contestants_dir.glob("**/*.npy"))

        logger.info(f"Found {len(jpg_files)} JPG files and {len(npy_files)} NPY files in contestants directory")

        if len(jpg_files) > 50 and len(npy_files) > 50:
            logger.info("✅ Git LFS files appear to be properly deployed")
            return True
        else:
            logger.warning(f"⚠️ Git LFS files missing - only {len(jpg_files)} JPG and {len(npy_files)} NPY files found")
            return False
    else:
        logger.warning("⚠️ Contestants directory not found")
        return False

def create_minimal_structure():
    """Create minimal directory structure for HF Spaces."""
    logger.info("📁 Creating minimal directory structure...")

    # Create required directories
    directories = [
        "source/photo/contestants",
        "source/videos",
        "cache",
        "output",
        "output_frames",
        "output_mp4s"
    ]

    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")

    # Create a sample contestant for testing
    test_contestant_dir = Path("source/photo/contestants/sample")
    test_contestant_dir.mkdir(exist_ok=True)

    readme_content = """# Sample Contestant Directory

This is a placeholder contestant directory created for HF Spaces deployment.

To use the face recognition features:
1. Upload photos via the Gradio interface
2. Or provide your own contestant directories with numbered folders (1/, 2/, 3/, etc.)
3. Each folder should contain 1-1.jpg, 1-2.jpg (or similar naming)

The system will work without known faces, but recognition will be limited to detecting faces without identifying them.
"""

    (test_contestant_dir / "README.md").write_text(readme_content)
    logger.info("✅ Created sample contestant structure")

def create_contestant_info_csv():
    """Create basic contestant info CSV."""
    try:
        import pandas as pd

        # Basic sample data
        data = [
            {"contestant_number": 1, "name": "Sample 1", "description": "Sample contestant for testing"},
            {"contestant_number": 2, "name": "Sample 2", "description": "Sample contestant for testing"},
        ]

        df = pd.DataFrame(data)
        csv_path = Path("contestant_info.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"✅ Created contestant info CSV: {csv_path}")

    except ImportError:
        # Fallback without pandas
        csv_content = """contestant_number,name,description
1,Sample 1,Sample contestant for testing
2,Sample 2,Sample contestant for testing
"""
        Path("contestant_info.csv").write_text(csv_content)
        logger.info("✅ Created basic contestant info CSV (without pandas)")

def main():
    """Main initialization function."""
    logger.info("🚀 Initializing HF Spaces environment...")

    # Check if Git LFS files are available
    if check_git_lfs_files():
        logger.info("✅ Git LFS files detected - using existing contestants data")
    else:
        logger.info("⚠️ Git LFS files not available - creating minimal structure")
        create_minimal_structure()
        create_contestant_info_csv()

    # Always ensure these directories exist
    for dir_name in ["cache", "output", "output_frames", "output_mp4s"]:
        Path(dir_name).mkdir(exist_ok=True)

    logger.info("✅ HF Spaces initialization complete")

if __name__ == "__main__":
    main()
