"""
Standard face recognition backend.

This module provides a basic face recognizer implementation based
on embedding similarity and dictionary-based matching.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from src.core.recognizer import StandardFaceRecognizer

# Set up logging
logger = logging.getLogger("face_recognition")


class StandardBackend:
    """
    Standard backend for face recognition that uses a dictionary-based approach.

    This implementation wraps the StandardFaceRecognizer to provide a consistent
    interface across different backends.
    """

    def __init__(self, recognizer: StandardFaceRecognizer):
        """
        Initialize the standard backend.

        Args:
            recognizer: Standard face recognizer instance
        """
        self.recognizer = recognizer

        # Statistics
        self.stats = {
            "query_count": 0,
            "match_count": 0,
            "processing_time": 0.0,
        }

        # Target dimension for embeddings
        self.target_dimension = None

    def _normalize_embedding_dimension(self, embedding: np.ndarray) -> np.ndarray:
        """
        Normalize embedding dimensions to match the target dimension.

        Args:
            embedding: The face embedding to normalize

        Returns:
            numpy.ndarray: Normalized face embedding
        """
        if embedding is None:
            return None

        # Convert to numpy array if it's a list
        if isinstance(embedding, list):
            embedding = np.array(embedding)

        # If no target dimension yet, use this embedding's dimension as target
        if self.target_dimension is None:
            self.target_dimension = embedding.shape[0]
            return embedding

        # If dimensions already match, return as is
        if embedding.shape[0] == self.target_dimension:
            return embedding

        # Handle dimension mismatch
        current_dim = embedding.shape[0]
        logger.info(
            f"Normalizing embedding dimension from {current_dim} to {self.target_dimension}"
        )

        if current_dim > self.target_dimension:
            # Truncate to target dimension
            return embedding[: self.target_dimension]
        else:
            # Pad with zeros to reach target dimension
            padding = np.zeros(self.target_dimension - current_dim)
            return np.concatenate([embedding, padding])

    def load_embeddings(
        self,
        contestant_dir: Union[str, Path],
        contestant_info: Any,
        selected_contestants: List[str],
    ) -> Dict[str, List[np.ndarray]]:
        """
        Load or compute embeddings for selected contestants.

        Args:
            contestant_dir: Directory containing contestant photos
            contestant_info: DataFrame with contestant information
            selected_contestants: List of selected contestant names

        Returns:
            dict: Dictionary mapping contestant names to embeddings
        """
        start_time = time.time()
        known_embeddings = {}

        if isinstance(contestant_dir, str):
            contestant_dir = Path(contestant_dir)

        for contestant in selected_contestants:
            # Try to get pre-computed embedding
            embedding = self.recognizer.get_embedding(contestant)

            if embedding is not None:
                # Normalize the embedding dimension
                embedding = self._normalize_embedding_dimension(embedding)
                if embedding is not None:
                    known_embeddings[contestant] = [embedding]
                    continue

            # If not available, compute from contestant images
            try:
                contestant_number = contestant_info.loc[
                    contestant_info["暱稱"] == contestant, "編號"
                ].values[0]

                contestant_path = contestant_dir / str(contestant_number)
                if not contestant_path.is_dir():
                    logger.warning(
                        f"Directory not found for contestant {contestant}: {contestant_path}"
                    )
                    continue

                # Get image paths
                image_paths = [
                    contestant_path / f
                    for f in os.listdir(contestant_path)
                    if str(f).lower().endswith((".jpg", ".png"))
                ]

                if not image_paths:
                    logger.warning(f"No images found for contestant {contestant}")
                    continue

                # Process first image only for now
                img = np.array(image_paths[0])
                faces = self.recognizer.face_detector.detect_faces(img)

                if not faces:
                    logger.warning(f"No face detected for contestant {contestant}")
                    continue

                # Extract and process face
                face_img = self.recognizer.face_detector.extract_face(img, faces[0], padding=0.1)
                if face_img is None:
                    logger.warning(f"Failed to extract face for contestant {contestant}")
                    continue

                # Compute embedding
                preprocessed = self.recognizer.preprocess_face(face_img)
                embedding = self.recognizer.compute_embedding(preprocessed)

                # Normalize the embedding dimension
                embedding = self._normalize_embedding_dimension(embedding)
                if embedding is None:
                    continue

                # Save for future use
                known_embeddings[contestant] = [embedding]
                self.recognizer.save_embedding(contestant, embedding)

            except Exception as e:
                logger.error(f"Error processing contestant {contestant}: {str(e)}")

        self.stats["processing_time"] += time.time() - start_time

        if not known_embeddings:
            logger.error("No embeddings found in gallery! Face recognition will not work.")
        else:
            logger.info(
                f"Loaded embeddings for {len(known_embeddings)} contestants with dimension {self.target_dimension}"
            )

        return known_embeddings

    def identify_face(
        self, face_embedding: np.ndarray, known_embeddings: Dict[str, List[np.ndarray]]
    ) -> Optional[Dict[str, Any]]:
        """
        Match a face embedding against known embeddings.

        Args:
            face_embedding: Face embedding to match
            known_embeddings: Dictionary of known embeddings

        Returns:
            dict: Match result or None if no match
        """
        start_time = time.time()
        self.stats["query_count"] += 1

        # Normalize the query embedding dimension
        face_embedding = self._normalize_embedding_dimension(face_embedding)
        if face_embedding is None:
            return None

        best_match = None
        best_score = 0

        for person_id, embeddings_list in known_embeddings.items():
            for known_embedding in embeddings_list:
                # Ensure both embeddings are in the correct format
                if isinstance(known_embedding, np.ndarray) and known_embedding.size > 0:
                    # Normalize the gallery embedding dimension if needed
                    known_embedding = self._normalize_embedding_dimension(known_embedding)
                    if known_embedding is None:
                        continue

                    similarity = self.recognizer.compute_similarity(face_embedding, known_embedding)
                    if (
                        similarity > self.recognizer.similarity_threshold
                        and similarity > best_score
                    ):
                        best_score = similarity
                        best_match = person_id

        self.stats["processing_time"] += time.time() - start_time

        if best_match:
            self.stats["match_count"] += 1
            return {"id": best_match, "name": best_match, "confidence": best_score}

        return None

    def identify_faces(
        self, image: np.ndarray, known_embeddings: Dict[str, List[np.ndarray]]
    ) -> List[Dict[str, Any]]:
        """
        Identify all faces in an image.

        Args:
            image: Input image
            known_embeddings: Dictionary of known embeddings

        Returns:
            list: List of identification results
        """
        # Delegate to recognizer's implementation
        return self.recognizer.identify_faces(image, known_embeddings)

    def get_stats(self) -> Dict[str, Any]:
        """Get backend statistics."""
        stats = self.stats.copy()

        # Add recognizer stats
        recognizer_stats = self.recognizer.get_stats()
        for key, value in recognizer_stats.items():
            stats[f"recognizer_{key}"] = value

        # Calculate match rate
        if stats["query_count"] > 0:
            stats["match_rate"] = stats["match_count"] / stats["query_count"]
        else:
            stats["match_rate"] = 0

        # Calculate average processing time
        if stats["query_count"] > 0:
            stats["avg_query_time_ms"] = (stats["processing_time"] / stats["query_count"]) * 1000
        else:
            stats["avg_query_time_ms"] = 0

        # Add embedding dimension info
        if self.target_dimension is not None:
            stats["embedding_dimension"] = self.target_dimension

        return stats
