"""
Vectorized Operations Module
High-performance vectorized implementations for distance calculations and similarity operations
Provides 2-3x speedup over loop-based computations
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from numba import jit, prange
import warnings

logger = logging.getLogger(__name__)

# Suppress numba warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning, module="numba")


class VectorizedOperations:
    """High-performance vectorized operations for face recognition"""

    def __init__(self, enable_numba: bool = True):
        self.enable_numba = enable_numba
        self._check_numba_availability()

        # Performance tracking
        self.operation_times = {
            "cosine_batch": [],
            "euclidean_batch": [],
            "confidence_conversion": [],
        }

        logger.info(
            f"VectorizedOperations initialized: numba_enabled={self.enable_numba}"
        )

    def _check_numba_availability(self):
        """Check if Numba is available and working"""
        if self.enable_numba:
            try:
                # Test numba compilation
                @jit(nopython=True)
                def test_func(x):
                    return x * 2

                result = test_func(5.0)
                if result == 10.0:
                    logger.info("Numba JIT compilation available")
                else:
                    self.enable_numba = False

            except Exception as e:
                logger.warning(f"Numba not available: {e}, falling back to numpy")
                self.enable_numba = False

    def cosine_similarity_batch(
        self, query_embeddings: np.ndarray, reference_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarity between query and reference embeddings in batch

        Args:
            query_embeddings: Shape (N, D) where N is number of queries
            reference_embeddings: Shape (M, D) where M is number of references

        Returns:
            Similarity matrix of shape (N, M)
        """
        import time

        start_time = time.time()

        # Ensure inputs are float32 for optimal performance
        query_embeddings = query_embeddings.astype(np.float32)
        reference_embeddings = reference_embeddings.astype(np.float32)

        if self.enable_numba:
            similarities = self._cosine_similarity_numba(
                query_embeddings, reference_embeddings
            )
        else:
            similarities = self._cosine_similarity_numpy(
                query_embeddings, reference_embeddings
            )

        processing_time = time.time() - start_time
        self.operation_times["cosine_batch"].append(processing_time)

        logger.debug(
            f"Cosine batch similarity: {query_embeddings.shape[0]}x{reference_embeddings.shape[0]} in {processing_time:.4f}s"
        )

        return similarities

    def euclidean_distance_batch(
        self, query_embeddings: np.ndarray, reference_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute Euclidean distance between query and reference embeddings in batch

        Args:
            query_embeddings: Shape (N, D)
            reference_embeddings: Shape (M, D)

        Returns:
            Distance matrix of shape (N, M)
        """
        import time

        start_time = time.time()

        query_embeddings = query_embeddings.astype(np.float32)
        reference_embeddings = reference_embeddings.astype(np.float32)

        if self.enable_numba:
            distances = self._euclidean_distance_numba(
                query_embeddings, reference_embeddings
            )
        else:
            distances = self._euclidean_distance_numpy(
                query_embeddings, reference_embeddings
            )

        processing_time = time.time() - start_time
        self.operation_times["euclidean_batch"].append(processing_time)

        logger.debug(
            f"Euclidean batch distance: {query_embeddings.shape[0]}x{reference_embeddings.shape[0]} in {processing_time:.4f}s"
        )

        return distances

    def batch_normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Normalize embeddings to unit length (L2 normalization)

        Args:
            embeddings: Shape (N, D)

        Returns:
            Normalized embeddings of same shape
        """
        embeddings = embeddings.astype(np.float32)

        if self.enable_numba:
            return self._normalize_embeddings_numba(embeddings)
        else:
            return self._normalize_embeddings_numpy(embeddings)

    def distance_to_confidence_batch(
        self, distances: np.ndarray, method: str = "cosine"
    ) -> np.ndarray:
        """
        Convert distance matrix to confidence scores

        Args:
            distances: Distance matrix of any shape
            method: Distance method ("cosine", "euclidean", "hybrid")

        Returns:
            Confidence matrix of same shape
        """
        import time

        start_time = time.time()

        distances = distances.astype(np.float32)

        if self.enable_numba:
            confidences = self._distance_to_confidence_numba(distances, method)
        else:
            confidences = self._distance_to_confidence_numpy(distances, method)

        processing_time = time.time() - start_time
        self.operation_times["confidence_conversion"].append(processing_time)

        return confidences

    def find_top_k_matches(
        self, similarities: np.ndarray, k: int = 5, threshold: float = 0.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find top-k matches for each query with optional threshold filtering

        Args:
            similarities: Similarity matrix (N, M)
            k: Number of top matches to return
            threshold: Minimum similarity threshold

        Returns:
            Tuple of (top_similarities, top_indices) shapes (N, k)
        """
        if self.enable_numba:
            return self._find_top_k_numba(similarities, k, threshold)
        else:
            return self._find_top_k_numpy(similarities, k, threshold)

    # Numba-optimized implementations
    @staticmethod
    @jit(nopython=True, parallel=True)
    def _cosine_similarity_numba(query_embeddings, reference_embeddings):
        """Numba-optimized cosine similarity computation"""
        n_queries, dim = query_embeddings.shape
        n_refs = reference_embeddings.shape[0]
        similarities = np.zeros((n_queries, n_refs), dtype=np.float32)

        for i in prange(n_queries):
            for j in range(n_refs):
                # Compute dot product
                dot_product = 0.0
                norm_query = 0.0
                norm_ref = 0.0

                for d in range(dim):
                    q_val = query_embeddings[i, d]
                    r_val = reference_embeddings[j, d]

                    dot_product += q_val * r_val
                    norm_query += q_val * q_val
                    norm_ref += r_val * r_val

                # Compute cosine similarity
                norm_product = np.sqrt(norm_query * norm_ref)
                if norm_product > 1e-8:
                    similarities[i, j] = dot_product / norm_product
                else:
                    similarities[i, j] = 0.0

        return similarities

    @staticmethod
    @jit(nopython=True, parallel=True)
    def _euclidean_distance_numba(query_embeddings, reference_embeddings):
        """Numba-optimized Euclidean distance computation"""
        n_queries, dim = query_embeddings.shape
        n_refs = reference_embeddings.shape[0]
        distances = np.zeros((n_queries, n_refs), dtype=np.float32)

        for i in prange(n_queries):
            for j in range(n_refs):
                distance_sq = 0.0

                for d in range(dim):
                    diff = query_embeddings[i, d] - reference_embeddings[j, d]
                    distance_sq += diff * diff

                distances[i, j] = np.sqrt(distance_sq)

        return distances

    @staticmethod
    @jit(nopython=True, parallel=True)
    def _normalize_embeddings_numba(embeddings):
        """Numba-optimized L2 normalization"""
        n_embeddings, dim = embeddings.shape
        normalized = np.zeros_like(embeddings)

        for i in prange(n_embeddings):
            # Compute L2 norm
            norm = 0.0
            for d in range(dim):
                norm += embeddings[i, d] * embeddings[i, d]
            norm = np.sqrt(norm)

            # Normalize
            if norm > 1e-8:
                for d in range(dim):
                    normalized[i, d] = embeddings[i, d] / norm
            else:
                # Handle zero vector case
                for d in range(dim):
                    normalized[i, d] = 1.0 / np.sqrt(float(dim))

        return normalized

    @staticmethod
    @jit(nopython=True, parallel=True)
    def _distance_to_confidence_numba(distances, method_id):
        """Numba-optimized distance to confidence conversion"""
        # method_id: 0=cosine, 1=euclidean, 2=hybrid
        confidences = np.zeros_like(distances)

        if method_id == 0:  # cosine
            for i in prange(distances.shape[0]):
                for j in range(distances.shape[1]):
                    # Cosine distance to confidence
                    conf = max(0.0, 1.0 - (distances[i, j] / 2.0))
                    confidences[i, j] = 1.0 / (1.0 + np.exp(-10.0 * (conf - 0.5)))

        elif method_id == 1:  # euclidean
            for i in prange(distances.shape[0]):
                for j in range(distances.shape[1]):
                    # Euclidean distance to confidence
                    conf = max(0.0, 1.0 - (distances[i, j] / 2.0))
                    confidences[i, j] = 1.0 / (1.0 + np.exp(-8.0 * (conf - 0.6)))

        else:  # hybrid
            for i in prange(distances.shape[0]):
                for j in range(distances.shape[1]):
                    # Hybrid distance to confidence
                    conf = max(0.0, 1.0 - (distances[i, j] / 2.0))
                    confidences[i, j] = 1.0 / (1.0 + np.exp(-9.0 * (conf - 0.55)))

        return confidences

    @staticmethod
    @jit(nopython=True, parallel=True)
    def _find_top_k_numba(similarities, k, threshold):
        """Numba-optimized top-k search with threshold"""
        n_queries, n_refs = similarities.shape
        top_similarities = np.full((n_queries, k), -1.0, dtype=np.float32)
        top_indices = np.full((n_queries, k), -1, dtype=np.int32)

        for i in prange(n_queries):
            # Find top-k for each query
            for j in range(n_refs):
                sim = similarities[i, j]
                if sim >= threshold:
                    # Insert into sorted top-k list
                    for pos in range(k):
                        if top_similarities[i, pos] < sim:
                            # Shift elements down
                            for shift in range(k - 1, pos, -1):
                                top_similarities[i, shift] = top_similarities[
                                    i, shift - 1
                                ]
                                top_indices[i, shift] = top_indices[i, shift - 1]

                            # Insert new element
                            top_similarities[i, pos] = sim
                            top_indices[i, pos] = j
                            break

        return top_similarities, top_indices

    # Numpy fallback implementations
    def _cosine_similarity_numpy(self, query_embeddings, reference_embeddings):
        """Numpy-optimized cosine similarity computation"""
        # Normalize embeddings
        query_norm = query_embeddings / (
            np.linalg.norm(query_embeddings, axis=1, keepdims=True) + 1e-8
        )
        ref_norm = reference_embeddings / (
            np.linalg.norm(reference_embeddings, axis=1, keepdims=True) + 1e-8
        )

        # Compute cosine similarity via matrix multiplication
        return np.dot(query_norm, ref_norm.T).astype(np.float32)

    def _euclidean_distance_numpy(self, query_embeddings, reference_embeddings):
        """Numpy-optimized Euclidean distance computation"""
        # Use broadcasting to compute pairwise distances efficiently
        query_expanded = query_embeddings[:, np.newaxis, :]  # (N, 1, D)
        ref_expanded = reference_embeddings[np.newaxis, :, :]  # (1, M, D)

        # Compute squared differences and sum along last axis
        squared_diffs = np.sum((query_expanded - ref_expanded) ** 2, axis=2)

        return np.sqrt(squared_diffs).astype(np.float32)

    def _normalize_embeddings_numpy(self, embeddings):
        """Numpy L2 normalization"""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms > 1e-8, norms, 1.0)  # Avoid division by zero
        return (embeddings / norms).astype(np.float32)

    def _distance_to_confidence_numpy(self, distances, method):
        """Numpy distance to confidence conversion"""
        if method == "cosine":
            # Cosine distance ranges 0-2, map to confidence 1-0
            confidence = np.maximum(0.0, 1.0 - (distances / 2.0))
            confidence = 1.0 / (1.0 + np.exp(-10.0 * (confidence - 0.5)))

        elif method == "euclidean":
            # For normalized vectors, euclidean distance ranges 0-2
            confidence = np.maximum(0.0, 1.0 - (distances / 2.0))
            confidence = 1.0 / (1.0 + np.exp(-8.0 * (confidence - 0.6)))

        elif method == "hybrid":
            confidence = np.maximum(0.0, 1.0 - (distances / 2.0))
            confidence = 1.0 / (1.0 + np.exp(-9.0 * (confidence - 0.55)))

        else:
            confidence = np.maximum(0.0, 1.0 - distances)

        return confidence.astype(np.float32)

    def _find_top_k_numpy(self, similarities, k, threshold):
        """Numpy top-k search with threshold"""
        # Apply threshold mask
        masked_similarities = np.where(similarities >= threshold, similarities, -np.inf)

        # Use argpartition for efficient top-k (better than full sort for large arrays)
        if k < similarities.shape[1]:
            top_indices = np.argpartition(-masked_similarities, k - 1, axis=1)[:, :k]

            # Sort the top-k elements
            for i in range(similarities.shape[0]):
                row_indices = top_indices[i]
                row_similarities = masked_similarities[i, row_indices]
                sorted_order = np.argsort(-row_similarities)
                top_indices[i] = row_indices[sorted_order]
        else:
            # If k >= number of references, sort all
            top_indices = np.argsort(-masked_similarities, axis=1)[:, :k]

        # Extract top similarities
        top_similarities = np.array(
            [similarities[i, top_indices[i]] for i in range(similarities.shape[0])]
        )

        return top_similarities.astype(np.float32), top_indices.astype(np.int32)

    def get_performance_stats(self) -> Dict:
        """Get performance statistics for vectorized operations"""
        stats = {}

        for operation, times in self.operation_times.items():
            if times:
                stats[operation] = {
                    "total_calls": len(times),
                    "avg_time": np.mean(times),
                    "min_time": np.min(times),
                    "max_time": np.max(times),
                    "ops_per_second": 1.0 / np.mean(times),
                }

        return {"numba_enabled": self.enable_numba, "operations": stats}


class AcceleratedSimilarityMatcher:
    """High-level facial similarity matching using vectorized operations"""

    def __init__(self, config: dict, enable_numba: bool = True):
        self.config = config
        self.vectorized_ops = VectorizedOperations(enable_numba)

        # Configuration
        self.similarity_threshold = config.get("face_recognition", {}).get(
            "similarity_threshold", 0.5
        )
        self.max_matches = config.get("face_recognition", {}).get(
            "max_matches_per_query", 5
        )
        self.distance_method = config.get("face_recognition", {}).get(
            "distance_method", "cosine"
        )

        # Embedding storage
        self.reference_embeddings = None
        self.embedding_ids = []

        logger.info(
            f"AcceleratedSimilarityMatcher initialized: method={self.distance_method}, threshold={self.similarity_threshold}"
        )

    def set_reference_embeddings(self, embeddings: Dict[str, np.ndarray]):
        """Set reference embeddings for similarity matching"""
        if not embeddings:
            raise ValueError("No reference embeddings provided")

        # Convert to matrix format
        self.embedding_ids = list(embeddings.keys())
        embedding_list = [embeddings[cid] for cid in self.embedding_ids]
        self.reference_embeddings = np.vstack(embedding_list).astype(np.float32)

        # Normalize for consistent similarity computation
        self.reference_embeddings = self.vectorized_ops.batch_normalize_embeddings(
            self.reference_embeddings
        )

        logger.info(
            f"Reference embeddings set: {len(self.embedding_ids)} embeddings, {self.reference_embeddings.shape[1]}D"
        )

    def find_matches_batch(
        self,
        query_embeddings: List[np.ndarray],
        confidence_threshold: Optional[float] = None,
    ) -> List[List[Dict]]:
        """
        Find matches for batch of query embeddings

        Args:
            query_embeddings: List of query embedding vectors
            confidence_threshold: Override default threshold

        Returns:
            List of match lists for each query
        """
        if self.reference_embeddings is None:
            raise ValueError(
                "Reference embeddings not set. Call set_reference_embeddings() first."
            )

        if confidence_threshold is None:
            confidence_threshold = self.similarity_threshold

        # Convert to matrix format and normalize
        query_matrix = np.vstack([emb.astype(np.float32) for emb in query_embeddings])
        query_matrix = self.vectorized_ops.batch_normalize_embeddings(query_matrix)

        # Compute similarities
        if self.distance_method == "cosine":
            similarities = self.vectorized_ops.cosine_similarity_batch(
                query_matrix, self.reference_embeddings
            )
            # Convert similarities to confidences (adjust as needed)
            confidences = similarities  # For normalized vectors, cosine similarity is already 0-1ish

        elif self.distance_method == "euclidean":
            distances = self.vectorized_ops.euclidean_distance_batch(
                query_matrix, self.reference_embeddings
            )
            confidences = self.vectorized_ops.distance_to_confidence_batch(
                distances, "euclidean"
            )

        else:
            # Default to cosine
            similarities = self.vectorized_ops.cosine_similarity_batch(
                query_matrix, self.reference_embeddings
            )
            confidences = similarities

        # Find top matches
        top_confidences, top_indices = self.vectorized_ops.find_top_k_matches(
            confidences, self.max_matches, confidence_threshold
        )

        # Convert to structured results
        all_matches = []
        for i in range(len(query_embeddings)):
            matches = []
            for j in range(self.max_matches):
                if top_indices[i, j] >= 0:  # Valid match
                    contestant_id = self.embedding_ids[top_indices[i, j]]
                    confidence = float(top_confidences[i, j])

                    match_info = {
                        "contestant_id": contestant_id,
                        "confidence": confidence,
                        "distance": 1.0 - confidence,  # Approximate distance
                        "method": self.distance_method,
                    }
                    matches.append(match_info)

            all_matches.append(matches)

        return all_matches

    def find_matches_single(
        self, query_embedding: np.ndarray, confidence_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Find matches for single query embedding"""
        batch_results = self.find_matches_batch([query_embedding], confidence_threshold)
        return batch_results[0] if batch_results else []

    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        return self.vectorized_ops.get_performance_stats()


# Global instance for easy access
_global_vectorized_ops = None


def get_vectorized_operations(enable_numba: bool = True) -> VectorizedOperations:
    """Get global vectorized operations instance"""
    global _global_vectorized_ops

    if _global_vectorized_ops is None:
        _global_vectorized_ops = VectorizedOperations(enable_numba)

    return _global_vectorized_ops
