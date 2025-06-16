#!/usr/bin/env python3
"""
Script to fix dependency issues for the video downloader.
Run this if you encounter fsspec or other dependency warnings.
"""

import subprocess
import sys


def upgrade_dependencies():
    """Upgrade problematic dependencies."""
    packages_to_upgrade = ["fsspec", "yt-dlp", "rich"]

    for package in packages_to_upgrade:
        try:
            print(f"Upgrading {package}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", package]
            )
            print(f"✅ Successfully upgraded {package}")
        except Exception as e:
            print(f"❌ Failed to upgrade {package}: {e}")


if __name__ == "__main__":
    print("🔧 Fixing dependencies...")
    upgrade_dependencies()
    print("✅ Done! You can now run videos_dl.py")
