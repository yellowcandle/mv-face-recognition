import logging

import numpy as np

logger = logging.getLogger(__name__)

# Check if ChromaDB is available
try:
    from chroma_db import get_contestant_collection
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not available. Falling back to standard similarity search.")

class RecognitionService:
    """
    Service for matching face embeddings against a gallery of known faces.
    """

    def __init__(self, use_chroma: bool = True):
        """
        Initialize the RecognitionService.

        Args:
            use_chroma: Whether to attempt using ChromaDB for matching if available.
        """
        self.use_chroma = use_chroma and CHROMA_AVAILABLE
        if self.use_chroma:
            try:
                self.chroma_collection = get_contestant_collection()
                logger.info("✅ ChromaDB collection loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to get ChromaDB collection: {e}. Disabling ChromaDB.")
                self.use_chroma = False
        else:
            logger.info("ChromaDB is disabled or unavailable.")

    def match_face(
        self,
        face_embedding: np.ndarray,
        known_embeddings: dict[str, np.ndarray]
    ) -> tuple[str, float]:
        """
        Compare a face embedding against known embeddings.

        Args:
            face_embedding: The embedding of the face to recognize.
            known_embeddings: A dictionary mapping names to matrices of their known embeddings.

        Returns:
            A tuple of (best_match_name, best_score).
        """
        try:
            face_emb = face_embedding.flatten().astype(np.float32)
            norm = np.linalg.norm(face_emb)
            if norm == 0:
                return "Unknown", 0.0
            face_emb /= norm

            # 1. ANN lookup with ChromaDB (if enabled and available)
            if self.use_chroma:
                try:
                    results = self.chroma_collection.query(
                        query_embeddings=[face_emb.tolist()],
                        n_results=1
                    )
                    if results and results.get("distances") and results.get("metadatas"):
                        if results["distances"][0]:
                            best_distance = results["distances"][0][0]
                            best_name = results["metadatas"][0][0].get("name", "Unknown")
                            # ChromaDB returns L2 distance, convert to cosine similarity
                            # This is an approximation: sim = 1 - (dist^2 / 2)
                            similarity = 1 - (best_distance**2 / 2)
                            logger.debug(f"ChromaDB match: {best_name} (sim: {similarity:.3f})")
                            return best_name, similarity
                except Exception as e:
                    logger.error(f"ChromaDB query failed: {e}. Falling back to vector search.")
                    # Fallback to vector search on this run
                    pass

            # 2. Fallback: vectorized cosine similarity search
            best_match_name = "Unknown"
            best_score = 0.0
            for name, emb_mat in known_embeddings.items():
                # emb_mat is already normalized from EmbeddingService
                similarities = emb_mat @ face_emb
                max_sim_for_person = float(np.max(similarities))
                if max_sim_for_person > best_score:
                    best_score = max_sim_for_person
                    best_match_name = name

            logger.debug(f"Vector search match: {best_match_name} (score: {best_score:.3f})")
            return best_match_name, best_score

        except Exception as e:
            logger.error(f"Error in match_face: {e}", exc_info=True)
            return "Unknown", 0.0
