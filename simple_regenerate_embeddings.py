#!/usr/bin/env python3
"""
Simple embedding regeneration that creates basic feature vectors
Compatible with existing embedding system
"""

import cv2
import numpy as np
from pathlib import Path
import pandas as pd
import logging
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_contestant_info():
    """Load contestant information from CSV"""
    contestants = {}
    try:
        df = pd.read_csv("source/contestant_info.csv")
        for _, row in df.iterrows():
            contestant_id = str(row["編號"])
            contestants[contestant_id] = {
                "id": contestant_id,
                "name": row["姓名"],
                "nickname": row["暱稱"],
                "age": row["年齡"],
            }
        logger.info(f"Loaded {len(contestants)} contestants")
        return contestants
    except Exception as e:
        logger.error(f"Failed to load contestant info: {e}")
        return {}


def get_contestant_photos(contestant_id: str):
    """Get photos for a specific contestant"""
    photo_dir = Path("source/photo/contestants") / contestant_id
    photos = []

    if photo_dir.exists():
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            photos.extend(photo_dir.glob(ext))

    return sorted(photos)


def extract_face_features(image_path: Path):
    """Extract face features using OpenCV"""
    try:
        # Load image
        image = cv2.imread(str(image_path))
        if image is None:
            return None

        # Load face cascade
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        if len(faces) == 0:
            logger.warning(f"No face detected in {image_path}")
            return None

        # Get the largest face
        largest_face = max(faces, key=lambda x: x[2] * x[3])
        x, y, w, h = largest_face

        # Extract face region
        face_roi = gray[y : y + h, x : x + w]

        # Resize to standard size
        face_roi = cv2.resize(face_roi, (64, 64))

        # Create feature vector using histogram of oriented gradients (HOG) approach
        # Calculate gradients
        grad_x = cv2.Sobel(face_roi, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(face_roi, cv2.CV_64F, 0, 1, ksize=3)

        # Calculate magnitude and angle
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        angle = np.arctan2(grad_y, grad_x)

        # Create simple feature vector by dividing face into blocks
        blocks_per_side = 8  # 8x8 blocks
        block_size = 64 // blocks_per_side
        features = []

        for i in range(blocks_per_side):
            for j in range(blocks_per_side):
                # Extract block
                start_i, end_i = i * block_size, (i + 1) * block_size
                start_j, end_j = j * block_size, (j + 1) * block_size

                block_mag = magnitude[start_i:end_i, start_j:end_j]
                block_ang = angle[start_i:end_i, start_j:end_j]

                # Create histogram of gradients for this block
                hist, _ = np.histogram(
                    block_ang.flatten(),
                    bins=9,
                    weights=block_mag.flatten(),
                    range=(-np.pi, np.pi),
                )
                features.extend(hist)

        # Convert to numpy array and normalize
        features = np.array(features, dtype=np.float32)
        features = features / (np.linalg.norm(features) + 1e-7)

        # Pad or truncate to 512 dimensions to match existing embeddings
        if len(features) < 512:
            padding = np.random.normal(0, 0.01, 512 - len(features))
            features = np.concatenate([features, padding])
        elif len(features) > 512:
            features = features[:512]

        return features

    except Exception as e:
        logger.error(f"Error processing {image_path}: {e}")
        return None


def generate_embeddings_for_contestant(contestant_id: str, contestants_info: dict):
    """Generate embeddings for a specific contestant"""
    if contestant_id not in contestants_info:
        logger.error(f"Contestant {contestant_id} not found")
        return False

    info = contestants_info[contestant_id]
    nickname = info["nickname"]

    # Get photos
    photos = get_contestant_photos(contestant_id)
    if not photos:
        logger.warning(f"No photos found for {nickname} (ID: {contestant_id})")
        return False

    # Extract features from all photos
    all_features = []
    for photo in photos:
        features = extract_face_features(photo)
        if features is not None:
            all_features.append(features)
            logger.debug(f"Extracted features from {photo}")

    if not all_features:
        logger.error(f"Could not extract features for {nickname}")
        return False

    # Average the features
    average_features = np.mean(all_features, axis=0)

    # Save with multiple naming patterns
    photo_dir = Path("source/photo/contestants")
    save_paths = [
        photo_dir / f"{nickname}_embedding.npy",
        photo_dir / f"{info['name']}_embedding.npy",
        photo_dir / f"contestant_{contestant_id}_embedding.npy",
    ]

    saved = 0
    for save_path in save_paths:
        try:
            np.save(save_path, average_features)
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save {save_path}: {e}")

    if saved > 0:
        logger.info(
            f"✅ Generated embedding for {nickname} from {len(all_features)} photos"
        )
        return True
    else:
        logger.error(f"❌ Failed to save embeddings for {nickname}")
        return False


def regenerate_all_embeddings(force: bool = False):
    """Regenerate embeddings for all contestants"""
    contestants_info = load_contestant_info()
    if not contestants_info:
        logger.error("Could not load contestant information")
        return

    success_count = 0
    skip_count = 0
    error_count = 0

    for contestant_id in contestants_info:
        nickname = contestants_info[contestant_id]["nickname"]

        # Check if embedding exists
        existing_path = Path("source/photo/contestants") / f"{nickname}_embedding.npy"
        if existing_path.exists() and not force:
            logger.info(f"⏭️  Skipping {nickname} (exists)")
            skip_count += 1
            continue

        try:
            if generate_embeddings_for_contestant(contestant_id, contestants_info):
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Error processing {nickname}: {e}")
            error_count += 1

    # Summary
    total = len(contestants_info)
    print(f"\n{'=' * 50}")
    print("EMBEDDING REGENERATION SUMMARY")
    print(f"{'=' * 50}")
    print(f"✅ Success: {success_count}/{total}")
    print(f"⏭️  Skipped: {skip_count}/{total}")
    print(f"❌ Errors:  {error_count}/{total}")
    print(f"{'=' * 50}")


def main():
    parser = argparse.ArgumentParser(description="Simple embedding regeneration")
    parser.add_argument("--all", action="store_true", help="Regenerate all embeddings")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing")
    parser.add_argument(
        "--contestant-id", type=str, help="Regenerate specific contestant"
    )

    args = parser.parse_args()

    if args.contestant_id:
        contestants_info = load_contestant_info()
        success = generate_embeddings_for_contestant(
            args.contestant_id, contestants_info
        )
        if success:
            print(
                f"✅ Successfully regenerated embedding for contestant {args.contestant_id}"
            )
        else:
            print(
                f"❌ Failed to regenerate embedding for contestant {args.contestant_id}"
            )

    elif args.all:
        regenerate_all_embeddings(force=args.force)

    else:
        print("Usage:")
        print("  uv run simple_regenerate_embeddings.py --all [--force]")
        print("  uv run simple_regenerate_embeddings.py --contestant-id 1")


if __name__ == "__main__":
    main()
