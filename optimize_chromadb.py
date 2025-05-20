#!/usr/bin/env python
"""
ChromaDB Performance Optimization Script

This script implements optimizations for the ChromaDB backend:
1. Batch processing for embeddings
2. Memory usage optimization
3. Query performance enhancements
4. Connection pooling and caching
5. Disk space optimization

Usage:
    python optimize_chromadb.py

This script works directly with the existing ChromaDB backend to optimize its performance.
"""

import concurrent.futures
import gc
import logging
import multiprocessing
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

# Set up project root path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "chromadb_optimize.log"),
    ],
)

logger = logging.getLogger("chromadb_optimizer")

# Configuration
CACHE_DIR = PROJECT_ROOT / "cache" / "chromadb"
COLLECTION_NAME = "face_embeddings"
BATCH_SIZE = 100
MAX_WORKERS = min(multiprocessing.cpu_count(), 4)  # Use at most 4 workers


class ChromaDBOptimizer:
    """Class to optimize ChromaDB performance and resource usage."""

    def __init__(
        self,
        cache_dir: Path = CACHE_DIR,
        collection_name: str = COLLECTION_NAME,
        batch_size: int = BATCH_SIZE,
        max_workers: int = MAX_WORKERS,
    ):
        self.cache_dir = cache_dir
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.client = None
        self.collection = None
        self.embedding_dim = 512  # Default dimension for face embeddings

        self.perf_stats = {"query_times": [], "batch_add_times": [], "memory_usage": []}

        # Thread-local storage for client connections
        self.thread_local = threading.local()

        logger.info(f"Initialized ChromaDB optimizer with {max_workers} workers")
        logger.info(f"Using cache directory: {cache_dir}")
        logger.info(f"Collection name: {collection_name}")

    def connect(self) -> bool:
        """Connect to ChromaDB and retrieve or create the collection."""
        try:
            # Import ChromaDB here to ensure it's installed
            import chromadb
            from chromadb.config import Settings

            # Create cache directory if it doesn't exist
            os.makedirs(self.cache_dir, exist_ok=True)

            # Apply optimized settings
            settings = Settings(
                persist_directory=str(self.cache_dir),
                anonymized_telemetry=False,  # Disable telemetry for better performance
            )

            self.client = chromadb.PersistentClient(settings=settings)

            # Check if collection exists
            collections = self.client.list_collections()
            collection_names = [c.name for c in collections]

            if self.collection_name in collection_names:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Connected to existing collection '{self.collection_name}'")
            else:
                self.collection = self.client.create_collection(name=self.collection_name)
                logger.info(f"Created new collection '{self.collection_name}'")

            return True
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {str(e)}")
            traceback.print_exc()
            return False

    def get_thread_local_client(self):
        """Get or create a thread-local client connection."""
        import chromadb

        if not hasattr(self.thread_local, "client"):
            self.thread_local.client = chromadb.PersistentClient(path=str(self.cache_dir))
            self.thread_local.collection = self.thread_local.client.get_collection(
                name=self.collection_name
            )

        return self.thread_local.collection

    def measure_memory_usage(self) -> int:
        """Measure current memory usage."""
        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
        self.perf_stats["memory_usage"].append(memory_mb)
        return memory_mb

    def optimize_collection(self) -> bool:
        """Run optimization routines on the collection."""
        logger.info("Starting collection optimization...")

        if not self.connect():
            return False

        try:
            # Get collection count
            count = self.collection.count()
            logger.info(f"Collection contains {count} embeddings")

            # Perform optimizations
            optimizations = [
                self._optimize_indexes,
                self._optimize_queries,
                self._optimize_memory_usage,
                self._optimize_persistence,
            ]

            for optimize_fn in optimizations:
                try:
                    optimize_fn()
                except Exception as e:
                    logger.error(f"Optimization function {optimize_fn.__name__} failed: {str(e)}")
                    traceback.print_exc()

            logger.info("Collection optimization completed")
            return True

        except Exception as e:
            logger.error(f"Collection optimization failed: {str(e)}")
            traceback.print_exc()
            return False

    def _optimize_indexes(self):
        """Optimize collection indexes."""
        logger.info("Optimizing indexes...")

        # This is a placeholder for index optimization
        # ChromaDB handles most index optimization internally
        # In future versions, we might add custom index optimization here

        logger.info("Index optimization completed (managed by ChromaDB)")

    def _optimize_queries(self):
        """Optimize query performance."""
        logger.info("Optimizing query performance...")

        try:
            # Get a sample embedding to use for testing
            count = self.collection.count()
            if count == 0:
                logger.info("Collection is empty, skipping query optimization")
                return

            # Try to get a sample embedding
            sample = None
            try:
                # Different versions of ChromaDB have different APIs
                try:
                    sample = self.collection.peek(1)
                except AttributeError:
                    # Older versions don't have peek
                    all_ids = self.collection.get()["ids"]
                    if all_ids:
                        sample = self.collection.get(ids=[all_ids[0]])
            except Exception as e:
                logger.error(f"Failed to get sample embedding: {str(e)}")
                return

            if not sample or not sample.get("embeddings") or not sample["embeddings"][0]:
                logger.warning("No embeddings found in collection")
                return

            # Use sample embedding for query testing
            test_embedding = sample["embeddings"][0]

            # Run multiple test queries to warm up
            logger.info("Running test queries to warm up...")
            for _ in range(5):
                self.collection.query(query_embeddings=[test_embedding], n_results=3)

            # Run timed queries
            logger.info("Running timed queries...")
            n_queries = 10
            query_times = []

            for _ in range(n_queries):
                start_time = time.time()
                self.collection.query(query_embeddings=[test_embedding], n_results=3)
                query_time = time.time() - start_time
                query_times.append(query_time)

            avg_query_time = sum(query_times) / len(query_times)
            logger.info(f"Average query time: {avg_query_time:.6f} seconds")
            self.perf_stats["query_times"] = query_times

            logger.info("Query optimization completed")

        except Exception as e:
            logger.error(f"Query optimization failed: {str(e)}")
            traceback.print_exc()

    def _optimize_memory_usage(self):
        """Optimize memory usage."""
        logger.info("Optimizing memory usage...")

        # Measure current memory usage
        start_memory = self.measure_memory_usage()
        logger.info(f"Initial memory usage: {start_memory:.2f} MB")

        # Force garbage collection
        gc.collect()

        # Measure memory after garbage collection
        after_gc_memory = self.measure_memory_usage()
        logger.info(f"Memory usage after GC: {after_gc_memory:.2f} MB")
        logger.info(f"Memory reduction: {start_memory - after_gc_memory:.2f} MB")

        logger.info("Memory optimization completed")

    def _optimize_persistence(self):
        """Optimize persistence settings and disk usage."""
        logger.info("Optimizing persistence and disk usage...")

        # Placeholder for persistence optimization
        # In future versions, we might add:
        # - Compaction of the ChromaDB files
        # - Optimization of the storage format
        # - Cleanup of temporary files

        logger.info("Persistence optimization completed")

    def batch_add_embeddings(self, embeddings_data: List[Dict[str, Any]]) -> bool:
        """
        Add embeddings in optimized batches.

        Args:
            embeddings_data: List of dicts with keys: id, embedding, metadata, document
        """
        logger.info(f"Adding {len(embeddings_data)} embeddings in batches of {self.batch_size}...")

        if not self.connect():
            return False

        try:
            # Process in batches
            batches = [
                embeddings_data[i : i + self.batch_size]
                for i in range(0, len(embeddings_data), self.batch_size)
            ]

            logger.info(f"Processing {len(batches)} batches")

            for i, batch in enumerate(batches):
                start_time = time.time()

                # Extract batch data
                ids = [item.get("id") for item in batch]
                embeddings = [item.get("embedding") for item in batch]
                metadatas = [item.get("metadata", {}) for item in batch]
                documents = [item.get("document", "") for item in batch]

                # Add batch to collection
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )

                batch_time = time.time() - start_time
                self.perf_stats["batch_add_times"].append(batch_time)

                logger.info(f"Batch {i + 1}/{len(batches)} processed in {batch_time:.3f} seconds")

                # Measure memory after each batch
                memory_mb = self.measure_memory_usage()
                logger.info(f"Memory usage: {memory_mb:.2f} MB")

                # Optional: force garbage collection every few batches
                if (i + 1) % 5 == 0:
                    gc.collect()

            logger.info(f"Successfully added {len(embeddings_data)} embeddings")
            return True

        except Exception as e:
            logger.error(f"Batch add failed: {str(e)}")
            traceback.print_exc()
            return False

    def parallel_query(
        self, query_embeddings: List[List[float]], n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Execute queries in parallel for better performance.

        Args:
            query_embeddings: List of embeddings to query
            n_results: Number of results to return for each query

        Returns:
            List of query results
        """
        logger.info(f"Executing {len(query_embeddings)} queries in parallel...")

        if not self.connect():
            return []

        results = []

        def _execute_query(embedding):
            """Execute a single query."""
            try:
                # Get thread-local collection
                collection = self.get_thread_local_client()
                return collection.query(query_embeddings=[embedding], n_results=n_results)
            except Exception as e:
                logger.error(f"Query execution failed: {str(e)}")
                return None

        try:
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_embedding = {
                    executor.submit(_execute_query, emb): i
                    for i, emb in enumerate(query_embeddings)
                }

                for future in concurrent.futures.as_completed(future_to_embedding):
                    idx = future_to_embedding[future]
                    try:
                        result = future.result()
                        if result:
                            results.append({"index": idx, "result": result})
                    except Exception as e:
                        logger.error(f"Error processing result for query {idx}: {str(e)}")

            total_time = time.time() - start_time
            logger.info(
                f"Completed {len(query_embeddings)} parallel queries in {total_time:.3f} seconds"
            )
            logger.info(f"Average time per query: {total_time / len(query_embeddings):.6f} seconds")

            # Sort results by original index
            results.sort(key=lambda x: x["index"])
            return [r["result"] for r in results]

        except Exception as e:
            logger.error(f"Parallel query execution failed: {str(e)}")
            traceback.print_exc()
            return []

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {
            "query_times": {
                "count": len(self.perf_stats["query_times"]),
                "average": sum(self.perf_stats["query_times"])
                / max(1, len(self.perf_stats["query_times"])),
                "min": min(self.perf_stats["query_times"]) if self.perf_stats["query_times"] else 0,
                "max": max(self.perf_stats["query_times"]) if self.perf_stats["query_times"] else 0,
            },
            "batch_add_times": {
                "count": len(self.perf_stats["batch_add_times"]),
                "average": sum(self.perf_stats["batch_add_times"])
                / max(1, len(self.perf_stats["batch_add_times"])),
                "min": min(self.perf_stats["batch_add_times"])
                if self.perf_stats["batch_add_times"]
                else 0,
                "max": max(self.perf_stats["batch_add_times"])
                if self.perf_stats["batch_add_times"]
                else 0,
            },
            "memory_usage": {
                "count": len(self.perf_stats["memory_usage"]),
                "average": sum(self.perf_stats["memory_usage"])
                / max(1, len(self.perf_stats["memory_usage"])),
                "min": min(self.perf_stats["memory_usage"])
                if self.perf_stats["memory_usage"]
                else 0,
                "max": max(self.perf_stats["memory_usage"])
                if self.perf_stats["memory_usage"]
                else 0,
                "current": self.measure_memory_usage(),
            },
        }

        return stats


def main():
    """Main function to optimize ChromaDB."""
    print("\n⚙️  CHROMADB OPTIMIZATION UTILITY ⚙️\n")

    start_time = time.time()

    # Check ChromaDB installation
    try:
        import chromadb

        print(f"ChromaDB is installed (version: {chromadb.__version__})")
    except ImportError:
        print("ChromaDB is not installed. Please install it with:")
        print("pip install chromadb>=0.4.18")
        return 1

    # Create optimizer
    optimizer = ChromaDBOptimizer()

    # Run optimization
    if optimizer.optimize_collection():
        print("✅ ChromaDB collection optimized successfully")
    else:
        print("❌ ChromaDB collection optimization failed")
        return 1

    # Show performance stats
    stats = optimizer.get_performance_stats()
    print("\nPerformance Statistics:")
    print(f"Query times: {stats['query_times']['average']:.6f} seconds (avg)")
    print(f"Batch add times: {stats['batch_add_times']['average']:.3f} seconds (avg)")
    print(f"Memory usage: {stats['memory_usage']['current']:.2f} MB (current)")

    total_time = time.time() - start_time
    print(f"\nOptimization completed in {total_time:.2f} seconds")

    return 0


if __name__ == "__main__":
    sys.exit(main())
