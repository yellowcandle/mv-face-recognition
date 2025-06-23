#!/usr/bin/env python3
"""
Launch script for MV Face Recognition application.
"""

import subprocess
import sys
import os


def main():
    """Launch the Streamlit application."""

    # Check if we're in the right directory
    if not os.path.exists("app.py"):
        print(
            "Error: app.py not found. Please run this script from the project root directory."
        )
        sys.exit(1)

    # Check if source/videos directory exists
    if not os.path.exists("source/videos"):
        print("Warning: source/videos directory not found. Creating it...")
        os.makedirs("source/videos", exist_ok=True)
        print(
            "Please add video files to the source/videos/ directory before processing."
        )

    # Check if contestants directory exists
    if not os.path.exists("source/photo/contestants"):
        print("Error: source/photo/contestants directory not found.")
        print("This directory should contain contestant photos and embedding files.")
        sys.exit(1)

    print("🎬 Starting MV Face Recognition System...")
    print("📁 Videos directory: source/videos/")
    print("👥 Contestants directory: source/photo/contestants/")
    print("🚀 Launching Streamlit interface...")
    print()

    try:
        # Launch Streamlit
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.port",
                "8501",
                "--server.address",
                "localhost",
                "--browser.gatherUsageStats",
                "false",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
