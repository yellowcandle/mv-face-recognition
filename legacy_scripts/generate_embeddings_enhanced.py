#!/usr/bin/env python3
"""
Enhanced embedding generator using the hardware-accelerated face detector
Uses the same enhanced detector as the video processing pipeline
"""

import sys
import numpy as np
import cv2
from pathlib import Path
import pandas as pd
import logging
import yaml

# Add mvp-processor to path
sys.path.append(str(Path(__file__).parent / "mvp-processor" / "src"))

from enhanced_face_detector import AcceleratedFaceDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedEmbeddingGenerator:
    """Generate embeddings using the enhanced hardware-accelerated detector"""

    def __init__(self):
        # Load configuration
        config_path = Path("mvp-processor/config/processing_config.yaml")
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Initialize enhanced detector
        self.detector = AcceleratedFaceDetector(self.config)

        # Load contestant info
        self.photo_dir = Path("source/photo/contestants")
        self.contestant_info_file = Path("source/contestant_info.csv")
        self.contestants_info = {}
        self._load_contestant_info()

    def _load_contestant_info(self):
        """Load contestant information from CSV"""
        try:
            df = pd.read_csv(self.contestant_info_file)
            for _, row in df.iterrows():
                contestant_id = str(row["編號"])
                self.contestants_info[contestant_id] = {
                    "name": row["姓名"],
                    "nickname": row["暱稱"],
                    "age": row["年齡"],
                }
            logger.info(f"Loaded info for {len(self.contestants_info)} contestants")
        except Exception as e:
            logger.error(f"Failed to load contestant info: {e}")

    def generate_enhanced_embeddings(self):
        """Generate embeddings using enhanced detector"""
        logger.info("Generating embeddings with enhanced face detector")

        success_count = 0
        error_count = 0

        for contestant_id, info in self.contestants_info.items():
            try:
                # Get photos for contestant
                photos = self._get_contestant_photos(contestant_id)

                if not photos:
                    logger.warning(f"No photos found for contestant {contestant_id}")
                    continue

                embeddings = []

                # Process each photo
                for photo_path in photos:
                    try:
                        # Load image with OpenCV
                        frame = cv2.imread(str(photo_path))
                        if frame is None:
                            logger.warning(f"Could not load image {photo_path}")
                            continue

                        # Use enhanced detector
                        detection_results = self.detector.detect_faces(frame)

                        if detection_results and len(detection_results) > 0:
                            # Get the first face encoding
                            face_detection = detection_results[0]
                            if (
                                hasattr(face_detection, "encoding")
                                and face_detection.encoding is not None
                            ):
                                embeddings.append(face_detection.encoding)
                                logger.debug(f"Encoded {photo_path}")
                            else:
                                logger.warning(f"No face encoding in {photo_path}")
                        else:
                            logger.warning(f"No faces detected in {photo_path}")

                    except Exception as e:
                        logger.error(f"Error processing {photo_path}: {e}")

                if embeddings:
                    # Average the embeddings
                    average_embedding = np.mean(embeddings, axis=0)

                    # Save embedding
                    self._save_embedding(contestant_id, average_embedding)
                    success_count += 1
                    logger.info(
                        f"Generated enhanced embedding for {info['nickname']} from {len(embeddings)} photos"
                    )
                else:
                    logger.error(f"No valid embeddings for contestant {contestant_id}")
                    error_count += 1

            except Exception as e:
                logger.error(f"Error processing contestant {contestant_id}: {e}")
                error_count += 1

        logger.info(
            f"Enhanced embedding generation complete: {success_count} success, {error_count} errors"
        )

    def _get_contestant_photos(self, contestant_id: str):
        """Get photo paths for contestant"""
        photos = []
        numbered_dir = self.photo_dir / contestant_id

        if numbered_dir.exists():
            photos.extend(numbered_dir.glob("*.jpg"))
            photos.extend(numbered_dir.glob("*.png"))
            photos.extend(numbered_dir.glob("*.jpeg"))

        return sorted(photos)

    def _save_embedding(self, contestant_id: str, embedding: np.ndarray):
        """Save embedding with multiple naming patterns"""
        info = self.contestants_info[contestant_id]
        nickname = info["nickname"]
        name = info["name"]

        save_paths = [
            self.photo_dir / f"{nickname}_embedding.npy",
            self.photo_dir / f"{name}_embedding.npy",
            self.photo_dir / f"contestant_{contestant_id}_embedding.npy",
        ]

        for save_path in save_paths:
            np.save(save_path, embedding)


def main():
    try:
        logger.info("Starting enhanced embedding generation")
        generator = EnhancedEmbeddingGenerator()
        generator.generate_enhanced_embeddings()
        print("✅ Enhanced embedding generation complete!")

    except Exception as e:
        logger.error(f"Failed to generate enhanced embeddings: {e}")
        print("❌ Enhanced embedding generation failed")


if __name__ == "__main__":
    main()
