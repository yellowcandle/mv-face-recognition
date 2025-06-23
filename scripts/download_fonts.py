#!/usr/bin/env python3
"""
Download required fonts for HF Spaces deployment.
This script downloads the SourceHanSansTC-VF.ttf font if it's not available.
"""

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

def download_source_han_font():
    """Download SourceHanSansTC-VF.ttf from Google Fonts or GitHub."""
    fonts_dir = Path("fonts")
    fonts_dir.mkdir(exist_ok=True)

    font_path = fonts_dir / "SourceHanSansTC-VF.ttf"

    if font_path.exists():
        logger.info(f"Font already exists at {font_path}")
        return True

    # Alternative: Download a smaller open source Chinese font
    urls = [
        # Noto Sans CJK - smaller alternative
        "https://github.com/googlefonts/noto-cjk/raw/main/Sans/Variable/TTF/NotoSansCJK-VF.ttf",
        # Backup: Source Han Sans from Adobe
        "https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansTC.zip"
    ]

    for url in urls:
        try:
            logger.info(f"Downloading font from {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            if url.endswith('.zip'):
                # Handle ZIP file
                import tempfile
                import zipfile

                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        tmp_file.write(chunk)
                    tmp_file.flush()

                    # Extract TTF files from zip
                    with zipfile.ZipFile(tmp_file.name, 'r') as zip_ref:
                        for file_info in zip_ref.filelist:
                            if file_info.filename.endswith('.ttf') and 'Regular' in file_info.filename:
                                with zip_ref.open(file_info) as ttf_file:
                                    font_path.write_bytes(ttf_file.read())
                                logger.info(f"✅ Font downloaded and extracted to {font_path}")
                                os.unlink(tmp_file.name)
                                return True

                os.unlink(tmp_file.name)
            else:
                # Direct TTF file
                with open(font_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"✅ Font downloaded to {font_path}")
                return True

        except Exception as e:
            logger.warning(f"Failed to download font from {url}: {e}")
            continue

    logger.error("Failed to download font from all sources")
    return False

def ensure_fonts_available():
    """Ensure fonts are available, download if necessary."""
    try:
        return download_source_han_font()
    except Exception as e:
        logger.error(f"Font setup failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = ensure_fonts_available()
    if success:
        print("✅ Font setup completed successfully")
    else:
        print("⚠️ Font setup failed - will use system fonts")
