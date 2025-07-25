"""
FAISS-powered Similarity Search Engine
Provides 3-5x speedup over numpy-based similarity search using optimized vector operations
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Optional, Union
from pathlib import Path
import json
import time

logger = logging.getLogger(__name__)


class FAISSimilarityEngine:
    """High-performance similarity search using FAISS library"""

    def __init__(self, config: dict, embedding_dimension: int = 512):
        self.config = config
        self.embedding_dimension = embedding_dimension

        # FAISS configuration
        self.use_gpu = config.get("face_recognition", {}).get("use_faiss_gpu", True)
        self.index_type = config.get("face_recognition", {}).get(
            "faiss_index_type", "IVFFlat"
        )
        self.nprobe = config.get("face_recognition", {}).get("faiss_nprobe", 1)

        # Performance tracking
        self.search_times = []
        self.index_build_time = 0.0

        # Index and data storage
        self.faiss_index = None
        self.embedding_ids = []  # Maps index positions to contestant IDs
        self.embedding_metadata = {}  # Stores contestant info

        self._initialize_faiss()

        logger.info(
            f"FAISSimilarityEngine initialized: dimension={embedding_dimension}, gpu={self.use_gpu}"
        )

    def _initialize_faiss(self):
        """Initialize FAISS library and check GPU availability"""
        try:
            import faiss

            self.faiss = faiss

            # Check GPU availability
            if self.use_gpu:
                try:
                    gpu_count = faiss.get_num_gpus()
                    if gpu_count > 0:
                        logger.info(
                            f"FAISS GPU acceleration available: {gpu_count} GPU(s)"
                        )
                    else:
                        logger.warning("No GPUs available for FAISS, using CPU")
                        self.use_gpu = False
                except Exception as e:
                    logger.warning(f"FAISS GPU check failed: {e}, using CPU")
                    self.use_gpu = False

        except ImportError:
            logger.error(
                "FAISS not installed. Install with: pip install faiss-cpu faiss-gpu"
            )
            raise ImportError("FAISS required for accelerated similarity search")

    def build_index(
        self, embeddings: Dict[str, np.ndarray], force_rebuild: bool = False
    ) -> Dict:
        """
        Build FAISS index from contestant embeddings

        Args:
            embeddings: Dict mapping contestant_id to embedding vector
            force_rebuild: Force rebuilding even if index exists

        Returns:
            Build statistics
        """
        start_time = time.time()

        if len(embeddings) == 0:
            raise ValueError("No embeddings provided for index building")

        # Convert embeddings to FAISS format
        embedding_matrix, embedding_ids = self._prepare_embeddings(embeddings)

        # Store mapping for later retrieval
        self.embedding_ids = embedding_ids
        self.embedding_metadata = {
            contestant_id: {"embedding": embeddings[contestant_id]}
            for contestant_id in embedding_ids
        }

        # Create FAISS index
        self.faiss_index = self._create_faiss_index(embedding_matrix)

        self.index_build_time = time.time() - start_time

        stats = {
            "num_embeddings": len(embedding_ids),
            "embedding_dimension": self.embedding_dimension,
            "index_type": self.index_type,
            "build_time": self.index_build_time,
            "use_gpu": self.use_gpu,
            "memory_usage_mb": self._estimate_index_memory(),
        }

        logger.info(f"FAISS index built: {stats}")
        return stats

    def _prepare_embeddings(
        self, embeddings: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, List[str]]:
        """Convert embeddings dict to FAISS-compatible matrix format"""
        embedding_ids = list(embeddings.keys())
        embedding_vectors = []

        for contestant_id in embedding_ids:
            embedding = embeddings[contestant_id]

            # Ensure correct dimension
            if len(embedding) != self.embedding_dimension:
                if len(embedding) > self.embedding_dimension:
                    embedding = embedding[: self.embedding_dimension]
                else:
                    # Pad with zeros
                    padded = np.zeros(self.embedding_dimension, dtype=np.float32)
                    padded[: len(embedding)] = embedding
                    embedding = padded

            # Ensure float32 for FAISS
            embedding = embedding.astype(np.float32)

            # Normalize for cosine similarity
            norm = np.linalg.norm(embedding)
            if norm > 1e-8:
                embedding = embedding / norm

            embedding_vectors.append(embedding)

        return np.vstack(embedding_vectors), embedding_ids

    def _create_faiss_index(self, embedding_matrix: np.ndarray):
        """Create and train FAISS index"""
        n_vectors, dimension = embedding_matrix.shape

        if self.index_type == "Flat":
            # Exact search (slower but most accurate)
            index = self.faiss.IndexFlatIP(
                dimension
            )  # Inner product for normalized vectors

        elif self.index_type == "IVFFlat":
            # Inverted file index (good balance of speed/accuracy)
            nlist = min(int(np.sqrt(n_vectors)), 100)  # Number of Voronoi cells
            quantizer = self.faiss.IndexFlatIP(dimension)
            index = self.faiss.IndexIVFFlat(
                quantizer, dimension, nlist, self.faiss.METRIC_INNER_PRODUCT
            )

            # Train the index
            logger.info(f"Training FAISS IVFFlat index with {nlist} clusters...")
            index.train(embedding_matrix)
            index.nprobe = self.nprobe

        elif self.index_type == "HNSW":
            # Hierarchical Navigable Small World (fast approximate search)
            index = self.faiss.IndexHNSWFlat(
                dimension, 32, self.faiss.METRIC_INNER_PRODUCT
            )
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 128

        else:
            raise ValueError(f"Unsupported FAISS index type: {self.index_type}")

        # Move to GPU if available
        if self.use_gpu and hasattr(self.faiss, "StandardGpuResources"):
            try:
                res = self.faiss.StandardGpuResources()
                index = self.faiss.index_cpu_to_gpu(res, 0, index)
                logger.info("FAISS index moved to GPU")
            except Exception as e:
                logger.warning(f"Failed to move FAISS index to GPU: {e}")

        # Add vectors to index
        index.add(embedding_matrix)

        logger.info(f"FAISS index created: {n_vectors} vectors, {dimension}D")
        return index

    def search_similar(
        self, query_embedding: np.ndarray, k: int = 5, confidence_threshold: float = 0.5
    ) -> List[Dict]:
        """
        Search for most similar embeddings using FAISS

        Args:
            query_embedding: Query embedding vector
            k: Number of nearest neighbors to return
            confidence_threshold: Minimum similarity threshold

        Returns:
            List of matches with contestant info and distances
        """
        if self.faiss_index is None:
            raise ValueError("FAISS index not built. Call build_index() first.")

        start_time = time.time()

        try:
            # Prepare query
            query = self._prepare_query_embedding(query_embedding)

            # Search using FAISS
            similarities, indices = self.faiss_index.search(query, k)

            # Convert results
            matches = self._process_search_results(
                similarities[0], indices[0], confidence_threshold
            )

            search_time = time.time() - start_time
            self.search_times.append(search_time)

            logger.debug(
                f"FAISS search completed in {search_time:.4f}s, found {len(matches)} matches"
            )

            return matches

        except Exception as e:
            logger.error(f"FAISS search error: {e}")
            return []

    def batch_search(
        self,
        query_embeddings: List[np.ndarray],
        k: int = 5,
        confidence_threshold: float = 0.5,
    ) -> List[List[Dict]]:
        """
        Batch search for multiple query embeddings (more efficient)

        Args:
            query_embeddings: List of query embedding vectors
            k: Number of nearest neighbors per query
            confidence_threshold: Minimum similarity threshold

        Returns:
            List of match lists (one per query)
        """
        if self.faiss_index is None:
            raise ValueError("FAISS index not built. Call build_index() first.")

        start_time = time.time()

        try:
            # Prepare batch queries
            query_matrix = self._prepare_batch_queries(query_embeddings)

            # Batch search using FAISS
            similarities, indices = self.faiss_index.search(query_matrix, k)

            # Process results for each query
            all_matches = []
            for i in range(len(query_embeddings)):
                matches = self._process_search_results(
                    similarities[i], indices[i], confidence_threshold
                )
                all_matches.append(matches)

            search_time = time.time() - start_time
            batch_fps = len(query_embeddings) / search_time if search_time > 0 else 0

            logger.debug(
                f"FAISS batch search: {len(query_embeddings)} queries in {search_time:.4f}s "
                f"({batch_fps:.1f} queries/sec)"
            )

            return all_matches

        except Exception as e:
            logger.error(f"FAISS batch search error: {e}")
            return [[] for _ in query_embeddings]

    def _prepare_query_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """Prepare single query embedding for FAISS search"""
        # Ensure correct dimension and type
        if len(embedding) != self.embedding_dimension:
            if len(embedding) > self.embedding_dimension:
                embedding = embedding[: self.embedding_dimension]
            else:
                padded = np.zeros(self.embedding_dimension, dtype=np.float32)
                padded[: len(embedding)] = embedding
                embedding = padded

        embedding = embedding.astype(np.float32)

        # Normalize for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 1e-8:
            embedding = embedding / norm

        return embedding.reshape(1, -1)  # FAISS expects 2D array

    def _prepare_batch_queries(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """Prepare batch of query embeddings for FAISS search"""
        processed_embeddings = []

        for embedding in embeddings:
            processed = self._prepare_query_embedding(embedding)
            processed_embeddings.append(processed[0])  # Remove batch dimension

        return np.vstack(processed_embeddings)

    def _process_search_results(
        self, similarities: np.ndarray, indices: np.ndarray, confidence_threshold: float
    ) -> List[Dict]:
        """Process FAISS search results into structured format"""
        matches = []

        for similarity, index in zip(similarities, indices):
            # FAISS returns -1 for invalid indices
            if index == -1:
                continue

            # Convert inner product back to cosine similarity (for normalized vectors)
            cosine_similarity = float(similarity)

            # Convert to confidence (0-1 scale)
            confidence = self._similarity_to_confidence(cosine_similarity)

            if confidence >= confidence_threshold:
                contestant_id = self.embedding_ids[index]

                match_info = {
                    "contestant_id": contestant_id,
                    "similarity": cosine_similarity,
                    "confidence": confidence,
                    "distance": 1.0 - cosine_similarity,  # Cosine distance
                    "faiss_index": int(index),
                }

                matches.append(match_info)

        return matches

    def _similarity_to_confidence(self, similarity: float) -> float:
        """Convert cosine similarity to confidence score"""
        # For normalized vectors, cosine similarity is in [-1, 1]
        # Convert to [0, 1] confidence scale
        confidence = (similarity + 1.0) / 2.0

        # Apply sigmoid for better separation
        confidence = 1.0 / (1.0 + np.exp(-10 * (confidence - 0.5)))

        return float(confidence)

    def _estimate_index_memory(self) -> float:
        """Estimate FAISS index memory usage in MB"""
        if self.faiss_index is None:
            return 0.0

        # Rough estimation based on index type and size
        n_vectors = len(self.embedding_ids)
        dimension = self.embedding_dimension

        if self.index_type == "Flat":
            # Each vector is 4 bytes (float32) * dimension
            memory_mb = (n_vectors * dimension * 4) / (1024 * 1024)
        elif self.index_type == "IVFFlat":
            # Additional overhead for inverted lists
            memory_mb = (n_vectors * dimension * 4 * 1.2) / (1024 * 1024)
        elif self.index_type == "HNSW":
            # HNSW has additional graph structure overhead
            memory_mb = (n_vectors * dimension * 4 * 1.5) / (1024 * 1024)
        else:
            memory_mb = (n_vectors * dimension * 4) / (1024 * 1024)

        return memory_mb

    def save_index(self, filepath: Union[str, Path]) -> Dict:
        """Save FAISS index to disk"""
        if self.faiss_index is None:
            raise ValueError("No index to save. Build index first.")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Save FAISS index
            index_path = filepath.with_suffix(".faiss")
            self.faiss.write_index(self.faiss_index, str(index_path))

            # Save metadata
            metadata = {
                "embedding_ids": self.embedding_ids,
                "embedding_dimension": self.embedding_dimension,
                "index_type": self.index_type,
                "use_gpu": self.use_gpu,
                "nprobe": self.nprobe,
                "build_time": self.index_build_time,
            }

            metadata_path = filepath.with_suffix(".json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"FAISS index saved to {index_path}")

            return {
                "index_path": str(index_path),
                "metadata_path": str(metadata_path),
                "size_mb": index_path.stat().st_size / (1024 * 1024),
            }

        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise

    def load_index(self, filepath: Union[str, Path]) -> Dict:
        """Load FAISS index from disk"""
        filepath = Path(filepath)
        index_path = filepath.with_suffix(".faiss")
        metadata_path = filepath.with_suffix(".json")

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {index_path}")

        try:
            # Load FAISS index
            self.faiss_index = self.faiss.read_index(str(index_path))

            # Load metadata
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)

                self.embedding_ids = metadata.get("embedding_ids", [])
                self.embedding_dimension = metadata.get("embedding_dimension", 512)
                self.index_type = metadata.get("index_type", "IVFFlat")
                self.build_time = metadata.get("build_time", 0.0)

            # Move to GPU if available
            if self.use_gpu and hasattr(self.faiss, "StandardGpuResources"):
                try:
                    res = self.faiss.StandardGpuResources()
                    self.faiss_index = self.faiss.index_cpu_to_gpu(
                        res, 0, self.faiss_index
                    )
                    logger.info("Loaded FAISS index moved to GPU")
                except:
                    logger.warning("Could not move loaded FAISS index to GPU")

            logger.info(f"FAISS index loaded: {len(self.embedding_ids)} embeddings")

            return {
                "num_embeddings": len(self.embedding_ids),
                "dimension": self.embedding_dimension,
                "index_type": self.index_type,
                "loaded_from": str(index_path),
            }

        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            raise

    def get_performance_stats(self) -> Dict:
        """Get FAISS performance statistics"""
        if not self.search_times:
            return {}

        return {
            "index": {
                "type": self.index_type,
                "num_embeddings": len(self.embedding_ids),
                "dimension": self.embedding_dimension,
                "build_time": self.index_build_time,
                "memory_mb": self._estimate_index_memory(),
                "use_gpu": self.use_gpu,
            },
            "performance": {
                "total_searches": len(self.search_times),
                "avg_search_time": np.mean(self.search_times),
                "min_search_time": np.min(self.search_times),
                "max_search_time": np.max(self.search_times),
                "searches_per_second": 1.0 / np.mean(self.search_times)
                if self.search_times
                else 0,
            },
        }


def create_faiss_engine(
    config: dict, embedding_dimension: int = 512
) -> Optional[FAISSimilarityEngine]:
    """Factory function to create FAISS similarity engine with error handling"""
    try:
        return FAISSimilarityEngine(config, embedding_dimension)
    except ImportError:
        logger.warning("FAISS not available, falling back to numpy similarity search")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize FAISS engine: {e}")
        return None
