"""
Async face matching service using ChromaDB for high-performance similarity search.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.memory_manager import get_memory_manager

logger = logging.getLogger(__name__)


class FaceMatcherAsync:
    """Async face matcher using ChromaDB for fast similarity search."""

    def __init__(self):
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        self.max_results = settings.MAX_RESULTS
        self.chroma_db_path = settings.CHROMA_DB_PATH
        self.contestants_dir = settings.CONTESTANTS_DIR

        # ChromaDB client and collection
        self.client = None
        self.collection = None
        self._initialized = False

        # Memory-optimized cache for frequent queries
        self._match_cache = {}
        self._cache_size_limit = 500  # Reduced from 1000
        self._cache_memory_limit = 50 * 1024 * 1024  # 50MB cache limit
        self._current_cache_size = 0

        # Memory management
        self.memory_manager = get_memory_manager()

        logger.info("Async face matcher initialized")

    async def initialize(self):
        """Initialize ChromaDB connection and load embeddings asynchronously."""
        if self._initialized:
            return

        loop = asyncio.get_event_loop()

        def _init_chroma():
            try:
                # Create ChromaDB client
                self.client = chromadb.PersistentClient(
                    path=self.chroma_db_path,
                    settings=ChromaSettings(
                        anonymized_telemetry=False, allow_reset=True
                    ),
                )

                # Get or create collection
                try:
                    self.collection = self.client.get_collection(name="face_embeddings")
                    logger.info("Loaded existing ChromaDB collection")
                except:
                    self.collection = self.client.create_collection(
                        name="face_embeddings", metadata={"hnsw:space": "cosine"}
                    )
                    logger.info("Created new ChromaDB collection")

                return True

            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")
                return False

        success = await loop.run_in_executor(None, _init_chroma)

        if success:
            # Load embeddings if collection is empty
            count = await self._get_collection_count()
            if count == 0:
                await self._load_embeddings_async()

            self._initialized = True
            logger.info(f"Face matcher initialized with {count} contestants")
        else:
            raise RuntimeError("Failed to initialize face matcher")

    async def _get_collection_count(self) -> int:
        """Get the number of items in the collection."""
        loop = asyncio.get_event_loop()

        def _count():
            try:
                return self.collection.count()
            except:
                return 0

        return await loop.run_in_executor(None, _count)

    async def _load_embeddings_async(self):
        """Load face embeddings from .npy files into ChromaDB asynchronously."""
        loop = asyncio.get_event_loop()

        def _load_embeddings():
            contestants_path = Path(self.contestants_dir)

            if not contestants_path.exists():
                logger.error(f"Contestants directory not found: {self.contestants_dir}")
                return 0

            # Find all .npy embedding files
            embedding_files = list(contestants_path.glob("*_embedding.npy"))

            if not embedding_files:
                logger.warning("No embedding files found")
                return 0

            # Load embeddings
            embeddings = []
            names = []
            ids = []

            for i, embedding_file in enumerate(embedding_files):
                try:
                    # Extract contestant name from filename
                    name = embedding_file.stem.replace("_embedding", "")

                    # Load embedding
                    embedding = np.load(embedding_file)

                    # Ensure embedding is 1D
                    if embedding.ndim > 1:
                        embedding = embedding.flatten()

                    embeddings.append(embedding.tolist())
                    names.append(name)
                    ids.append(f"contestant_{i}")

                except Exception as e:
                    logger.error(f"Error loading embedding {embedding_file}: {e}")
                    continue

            if embeddings:
                # Add to ChromaDB collection
                self.collection.add(
                    embeddings=embeddings,
                    metadatas=[{"name": name} for name in names],
                    ids=ids,
                )

                logger.info(f"Loaded {len(embeddings)} embeddings into ChromaDB")
                return len(embeddings)

            return 0

        return await loop.run_in_executor(None, _load_embeddings)

    async def match_face_async(
        self, embedding: np.ndarray
    ) -> Optional[Tuple[str, float]]:
        """
        Match a face embedding against the database asynchronously.

        Args:
            embedding: Face embedding to match

        Returns:
            Tuple of (contestant_name, similarity_score) or None if no match
        """
        if not self._initialized:
            await self.initialize()

        if self.collection is None:
            logger.error("ChromaDB collection not initialized")
            return None

        # Generate cache key
        embedding_hash = hash(embedding.tobytes())

        if embedding_hash in self._match_cache:
            logger.debug("Using cached match result")
            return self._match_cache[embedding_hash]

        loop = asyncio.get_event_loop()

        def _search_embedding():
            try:
                # Ensure embedding is 1D
                if embedding.ndim > 1:
                    search_embedding = embedding.flatten()
                else:
                    search_embedding = embedding

                # Query ChromaDB
                results = self.collection.query(
                    query_embeddings=[search_embedding.tolist()],
                    n_results=self.max_results,
                    include=["metadatas", "distances"],
                )

                if not results["metadatas"] or not results["metadatas"][0]:
                    return None

                # Get the best match
                best_metadata = results["metadatas"][0][0]
                best_distance = results["distances"][0][0]

                # Convert distance to similarity (cosine similarity)
                similarity = 1 - best_distance

                # Check if similarity meets threshold
                if similarity >= self.similarity_threshold:
                    contestant_name = best_metadata["name"]
                    return (contestant_name, similarity)

                return None

            except Exception as e:
                logger.error(f"Error searching face embedding: {e}")
                return None

        # Run search in executor with memory monitoring
        await self.memory_manager.cleanup_if_needed()
        result = await loop.run_in_executor(None, _search_embedding)

        # Cache result with memory-aware eviction
        result_size = self._estimate_result_size(result)

        # Check memory limit
        while (
            self._current_cache_size + result_size > self._cache_memory_limit
            or len(self._match_cache) >= self._cache_size_limit
        ):
            if not self._match_cache:
                break
            # Remove oldest entry
            oldest_key = next(iter(self._match_cache))
            old_result = self._match_cache[oldest_key]
            self._current_cache_size -= self._estimate_result_size(old_result)
            del self._match_cache[oldest_key]

        self._match_cache[embedding_hash] = result
        self._current_cache_size += result_size

        return result

    async def match_faces_batch_async(
        self, embeddings: List[np.ndarray]
    ) -> List[Optional[Tuple[str, float]]]:
        """
        Match multiple face embeddings concurrently.

        Args:
            embeddings: List of face embeddings to match

        Returns:
            List of match results for each embedding
        """
        if not self._initialized:
            await self.initialize()

        # Process embeddings concurrently
        tasks = []
        for embedding in embeddings:
            task = self.match_face_async(embedding)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error matching embedding {i}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    async def get_top_matches_async(
        self, embedding: np.ndarray, top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Get top K matches for a face embedding.

        Args:
            embedding: Face embedding to match
            top_k: Number of top matches to return

        Returns:
            List of (contestant_name, similarity_score) tuples
        """
        if not self._initialized:
            await self.initialize()

        if self.collection is None:
            logger.error("ChromaDB collection not initialized")
            return []

        loop = asyncio.get_event_loop()

        def _get_top_matches():
            try:
                # Ensure embedding is 1D
                if embedding.ndim > 1:
                    search_embedding = embedding.flatten()
                else:
                    search_embedding = embedding

                # Query ChromaDB for top K results
                results = self.collection.query(
                    query_embeddings=[search_embedding.tolist()],
                    n_results=min(top_k, self.max_results),
                    include=["metadatas", "distances"],
                )

                if not results["metadatas"] or not results["metadatas"][0]:
                    return []

                # Convert results to list of tuples
                matches = []
                for metadata, distance in zip(
                    results["metadatas"][0], results["distances"][0]
                ):
                    similarity = 1 - distance
                    if similarity >= self.similarity_threshold:
                        contestant_name = metadata["name"]
                        matches.append((contestant_name, similarity))

                return matches

            except Exception as e:
                logger.error(f"Error getting top matches: {e}")
                return []

        return await loop.run_in_executor(None, _get_top_matches)

    async def get_database_stats_async(self) -> Dict:
        """Get database statistics asynchronously."""
        if not self._initialized:
            await self.initialize()

        loop = asyncio.get_event_loop()

        def _get_stats():
            try:
                count = self.collection.count() if self.collection else 0

                return {
                    "total_embeddings": count,
                    "similarity_threshold": self.similarity_threshold,
                    "max_results": self.max_results,
                    "cache_size": len(self._match_cache),
                    "initialized": self._initialized,
                }

            except Exception as e:
                logger.error(f"Error getting database stats: {e}")
                return {
                    "total_embeddings": 0,
                    "similarity_threshold": self.similarity_threshold,
                    "max_results": self.max_results,
                    "cache_size": len(self._match_cache),
                    "initialized": self._initialized,
                    "error": str(e),
                }

        return await loop.run_in_executor(None, _get_stats)

    async def add_contestant_async(self, name: str, embedding: np.ndarray) -> bool:
        """
        Add a new contestant embedding to the database.

        Args:
            name: Contestant name
            embedding: Face embedding

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        if self.collection is None:
            logger.error("ChromaDB collection not initialized")
            return False

        loop = asyncio.get_event_loop()

        def _add_contestant():
            try:
                # Ensure embedding is 1D
                if embedding.ndim > 1:
                    add_embedding = embedding.flatten()
                else:
                    add_embedding = embedding

                # Generate unique ID
                contestant_id = f"contestant_{name}_{len(self._match_cache)}"

                # Add to collection
                self.collection.add(
                    embeddings=[add_embedding.tolist()],
                    metadatas=[{"name": name}],
                    ids=[contestant_id],
                )

                # Clear cache to ensure fresh results
                self.clear_cache()

                logger.info(f"Added contestant {name} to database")
                return True

            except Exception as e:
                logger.error(f"Error adding contestant {name}: {e}")
                return False

        return await loop.run_in_executor(None, _add_contestant)

    def update_similarity_threshold(self, threshold: float):
        """Update similarity threshold."""
        self.similarity_threshold = threshold
        # Clear cache when threshold changes
        self.clear_cache()
        logger.info(f"Similarity threshold updated to: {threshold}")

    def clear_cache(self):
        """Clear match cache."""
        self._match_cache.clear()
        self._current_cache_size = 0
        logger.info("Match cache cleared")

    def _estimate_result_size(self, result) -> int:
        """Estimate memory size of match result in bytes."""
        if result is None:
            return 8  # None reference

        # Tuple with name (string) and similarity (float)
        name, similarity = result
        # String: ~50 chars average * 1 byte = 50 bytes
        # Float: 8 bytes
        # Tuple overhead: 16 bytes
        return len(name.encode("utf-8")) + 8 + 16

    async def reset_database_async(self):
        """Reset the database and reload embeddings."""
        if self.client and self.collection:
            loop = asyncio.get_event_loop()

            def _reset():
                try:
                    self.client.delete_collection(name="face_embeddings")
                    self.collection = self.client.create_collection(
                        name="face_embeddings", metadata={"hnsw:space": "cosine"}
                    )
                    return True
                except Exception as e:
                    logger.error(f"Error resetting database: {e}")
                    return False

            success = await loop.run_in_executor(None, _reset)

            if success:
                # Clear cache
                self.clear_cache()

                # Reload embeddings
                await self._load_embeddings_async()

                logger.info("Database reset and reloaded successfully")
                return True

        return False
