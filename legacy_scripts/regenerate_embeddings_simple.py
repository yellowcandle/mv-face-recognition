#!/usr/bin/env python3
"""
Simple embedding regeneration using the existing face detection system
"""

# Standard library imports
import sys
import os
import logging
from pathlib import Path

# Third-party imports
import numpy as np
import yaml

# Add mvp-processor src to path
# Correcting path to mvp-processor/src relative to the project root
project_root = Path(__file__).parent.parent
mvp_processor_path = project_root / "mvp-processor" / "src"
sys.path.insert(0, str(mvp_processor_path))

# Local imports (must come after path manipulation)
from face_detector import ContestantDatabase  # noqa: E402

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def regenerate_embeddings():
    """Regenerate embeddings using the existing face recognition system"""

    # Load config (run from mvp-processor directory context)
    original_cwd = Path.cwd()
    mvp_processor_dir = Path(__file__).parent / "mvp-processor"
    os.chdir(mvp_processor_dir)

    try:
        config_path = Path("config/processing_config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
    finally:
        os.chdir(original_cwd)

    # Initialize contestant database
    contestant_db = ContestantDatabase(config)
    contestant_db.load_contestants_info()
    contestant_db.build_face_encodings()

    logger.info(f"Loaded {len(contestant_db.face_encodings)} existing embeddings")
    logger.info(
        f"Contestants: {list(contestant_db.contestant_names[:10])}..."
    )  # Show first 10

    # Check embedding files
    photo_dir = Path("source/photo/contestants")
    embedding_files = list(photo_dir.glob("*_embedding.npy"))

    logger.info(f"Found {len(embedding_files)} embedding files:")
    for emb_file in embedding_files[:10]:  # Show first 10
        try:
            embedding = np.load(emb_file)
            logger.info(f"  {emb_file.name}: shape={embedding.shape}")
        except Exception as e:
            logger.error(f"  {emb_file.name}: ERROR - {e}")

    print("\n" + "=" * 50)
    print("EMBEDDING STATUS REPORT")
    print("=" * 50)
    print("✅ Loaded face recognition system")
    print(f"📊 Found {len(contestant_db.face_encodings)} face encodings")
    print(f"📂 Found {len(embedding_files)} embedding files")
    print(f"👥 Total contestants in info: {len(contestant_db.contestants_info)}")

    # Check if some contestants are missing embeddings
    missing_embeddings = []
    for contestant_id in contestant_db.contestants_info:
        if contestant_id not in contestant_db.face_encodings:
            info = contestant_db.contestants_info[contestant_id]
            missing_embeddings.append(f"{info['nickname']} (ID: {contestant_id})")

    if missing_embeddings:
        print(f"\n⚠️  Missing embeddings for {len(missing_embeddings)} contestants:")
        for missing in missing_embeddings[:10]:  # Show first 10
            print(f"   - {missing}")
        if len(missing_embeddings) > 10:
            print(f"   ... and {len(missing_embeddings) - 10} more")
    else:
        print("✅ All contestants have embeddings!")

    return contestant_db


def list_photo_directories():
    """List photo directories to help diagnose missing embeddings"""
    photo_dir = Path("source/photo/contestants")

    print("\n" + "=" * 50)
    print("PHOTO DIRECTORY ANALYSIS")
    print("=" * 50)

    # List numbered directories
    numbered_dirs = []
    for item in photo_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            numbered_dirs.append(int(item.name))

    numbered_dirs.sort()

    print(f"📷 Found {len(numbered_dirs)} numbered photo directories")
    print(
        f"   Range: {min(numbered_dirs) if numbered_dirs else 'N/A'} to {max(numbered_dirs) if numbered_dirs else 'N/A'}"
    )

    # Check for directories without photos
    empty_dirs = []
    dirs_with_photos = []

    for dir_num in numbered_dirs:
        dir_path = photo_dir / str(dir_num)
        photo_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            photo_files.extend(dir_path.glob(ext))

        if photo_files:
            dirs_with_photos.append(dir_num)
        else:
            empty_dirs.append(dir_num)

    print(f"✅ {len(dirs_with_photos)} directories with photos")
    print(f"❌ {len(empty_dirs)} empty directories")

    if empty_dirs:
        print(f"   Empty: {empty_dirs[:10]}")  # Show first 10
        if len(empty_dirs) > 10:
            print(f"   ... and {len(empty_dirs) - 10} more")


def main():
    print("🔍 Face Recognition Embedding Analysis")
    print("=" * 50)

    try:
        regenerate_embeddings()
        list_photo_directories()

        print("\n" + "=" * 50)
        print("NEXT STEPS:")
        print("=" * 50)
        print("1. To regenerate ALL embeddings:")
        print("   python generate_embeddings.py --all --force")
        print()
        print("2. To regenerate specific contestant:")
        print("   python generate_embeddings.py --contestant-id 1")
        print()
        print("3. Current embeddings are working! You may not need to regenerate.")

    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        print("\n❌ Analysis failed. The face recognition system may need setup.")


if __name__ == "__main__":
    main()
