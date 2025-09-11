"""
Face matching module using ChromaDB for similarity search.
"""

import json
import logging
from typing import List, Tuple, Optional, Dict
import numpy as np
from src.database.chroma_setup import ChromaDBManager

logger = logging.getLogger(__name__)


class FaceMatcher:
    """Face matching using ChromaDB vector similarity search."""

    def __init__(self, config_path: str = "config.json", config: Optional[dict] = None):
        """Initialize face matcher with ChromaDB using config dict or file path."""
        if config is not None:
            # Use provided config dict
            self.config = config
        else:
            # Load from file path
            with open(config_path, "r") as f:
                self.config = json.load(f)

        self.similarity_threshold = self.config.get("face_matching", {}).get(
            "similarity_threshold",
            self.config.get("face_recognition", {}).get("similarity_threshold", 0.6),
        )
        self.max_results = self.config.get("face_matching", {}).get(
            "max_results",
            self.config.get("face_recognition", {}).get("max_faces_per_frame", 50),
        )

        # Initialize ChromaDB manager
        if config is not None:
            # Pass config dict to ChromaDB manager
            self.db_manager = ChromaDBManager(config=config["database"])
        else:
            # Pass config file path to ChromaDB manager
            self.db_manager = ChromaDBManager(config_path)

        # Ensure database is populated
        self._ensure_database_ready()

    def _ensure_database_ready(self):
        """Ensure ChromaDB is populated with embeddings."""
        stats = self.db_manager.get_database_stats()

        if stats["total_embeddings"] == 0:
            logger.info("Database empty, populating with embeddings...")
            count = self.db_manager.populate_database()
            logger.info(f"Populated database with {count} embeddings")
        else:
            logger.info(f"Database ready with {stats['total_embeddings']} embeddings")

    def match_face(self, embedding: np.ndarray) -> Optional[Tuple[str, float]]:
        """
        Match a face embedding against the database.

        Args:
            embedding: Face embedding to match

        Returns:
            Tuple of (contestant_name, similarity_score) if match found, None otherwise
        """
        if embedding is None:
            return None

        try:
            # Search for similar faces
            matches = self.db_manager.search_similar_faces(embedding, n_results=1)

            if matches:
                name, similarity = matches[0]
                logger.debug(f"Best match: {name} (similarity: {similarity:.3f})")
                return (name, similarity)
            else:
                logger.debug("No matches found above threshold")
                return None

        except Exception as e:
            logger.error(f"Error matching face: {e}")
            return None

    def match_faces_batch(
        self, embeddings: List[np.ndarray]
    ) -> List[Optional[Tuple[str, float]]]:
        """
        Match multiple face embeddings in batch.

        Args:
            embeddings: List of face embeddings

        Returns:
            List of match results (same order as input)
        """
        results = []

        for embedding in embeddings:
            match = self.match_face(embedding)
            results.append(match)

        return results

    def get_top_matches(
        self, embedding: np.ndarray, n_results: int = None
    ) -> List[Tuple[str, float]]:
        """
        Get top N matches for a face embedding.

        Args:
            embedding: Face embedding to match
            n_results: Number of top results to return

        Returns:
            List of (contestant_name, similarity_score) tuples
        """
        if n_results is None:
            n_results = self.max_results

        try:
            matches = self.db_manager.search_similar_faces(
                embedding, n_results=n_results
            )
            return matches
        except Exception as e:
            logger.error(f"Error getting top matches: {e}")
            return []

    def match_with_details(self, embedding: np.ndarray) -> Dict:
        """
        Match face with detailed information.

        Args:
            embedding: Face embedding to match

        Returns:
            Dictionary with match details
        """
        result = {
            "matched": False,
            "contestant_name": None,
            "similarity_score": 0.0,
            "confidence_level": "none",
            "all_matches": [],
        }

        try:
            # Get top matches
            matches = self.get_top_matches(embedding, n_results=self.max_results)
            result["all_matches"] = matches

            if matches:
                best_name, best_similarity = matches[0]
                result["matched"] = True
                result["contestant_name"] = best_name
                result["similarity_score"] = best_similarity

                # Determine confidence level
                if best_similarity >= 0.8:
                    result["confidence_level"] = "high"
                elif best_similarity >= 0.7:
                    result["confidence_level"] = "medium"
                else:
                    result["confidence_level"] = "low"

            return result

        except Exception as e:
            logger.error(f"Error in detailed matching: {e}")
            return result

    def update_similarity_threshold(self, new_threshold: float):
        """Update similarity threshold for matching."""
        self.similarity_threshold = new_threshold
        self.db_manager.similarity_threshold = new_threshold
        logger.info(f"Updated similarity threshold to {new_threshold}")

    def get_database_info(self) -> Dict:
        """Get information about the face database."""
        return self.db_manager.get_database_stats()

    def refresh_database(self):
        """Refresh the database with latest embeddings."""
        logger.info("Refreshing face database...")
        count = self.db_manager.populate_database(force_refresh=True)
        logger.info(f"Database refreshed with {count} embeddings")


class BatchFaceMatcher:
    """Optimized face matcher for batch processing."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize batch face matcher."""
        self.matcher = FaceMatcher(config_path)
        self.match_cache = {}  # Cache for repeated embeddings

    def process_video_faces(
        self, frame_embeddings: List[Tuple[int, List[np.ndarray]]]
    ) -> Dict[int, List[Tuple[str, float]]]:
        """
        Process faces from multiple video frames efficiently.

        Args:
            frame_embeddings: List of (frame_number, [embeddings]) tuples

        Returns:
            Dictionary mapping frame_number to list of matches
        """
        results = {}

        for frame_num, embeddings in frame_embeddings:
            frame_matches = []

            for embedding in embeddings:
                # Convert to hashable key for caching
                embedding_key = hash(embedding.tobytes())

                # Check cache first
                if embedding_key in self.match_cache:
                    match = self.match_cache[embedding_key]
                else:
                    # Perform matching
                    match = self.matcher.match_face(embedding)
                    # Cache result
                    self.match_cache[embedding_key] = match

                frame_matches.append(match)

            results[frame_num] = frame_matches

        return results

    def clear_cache(self):
        """Clear the match cache."""
        self.match_cache.clear()
        logger.info("Match cache cleared")


def test_face_matcher():
    """Test the face matcher with sample embeddings."""
    import os
    import numpy as np

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Initialize matcher
    matcher = FaceMatcher()

    # Get database info
    db_info = matcher.get_database_info()
    print(f"Database info: {db_info}")

    # Test with a sample embedding file
    test_embedding_path = "source/photo/contestants/Alice_embedding.npy"

    if os.path.exists(test_embedding_path):
        # Load test embedding
        embedding = np.load(test_embedding_path)
        print(f"Loaded test embedding shape: {embedding.shape}")

        # Test matching
        match = matcher.match_face(embedding)
        if match:
            name, similarity = match
            print(f"Match found: {name} (similarity: {similarity:.3f})")
        else:
            print("No match found")

        # Test detailed matching
        details = matcher.match_with_details(embedding)
        print(f"Detailed match: {details}")

        # Test top matches
        top_matches = matcher.get_top_matches(embedding, n_results=3)
        print(f"Top 3 matches: {top_matches}")

    else:
        print(f"Test embedding not found: {test_embedding_path}")
        print("Available embedding files:")
        contestants_dir = "source/photo/contestants"
        for file in os.listdir(contestants_dir):
            if file.endswith("_embedding.npy"):
                print(f"  {file}")


if __name__ == "__main__":
    test_face_matcher()
