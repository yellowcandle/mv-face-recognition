"""
ChromaDB setup for loading and managing face embeddings.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """Manages ChromaDB for face embeddings storage and similarity search."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize ChromaDB manager with configuration."""
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.chroma_path = self.config["paths"]["chroma_db_path"]
        self.contestants_dir = self.config["paths"]["contestants_dir"]
        self.similarity_threshold = self.config["face_matching"]["similarity_threshold"]

        # Ensure ChromaDB directory exists
        os.makedirs(self.chroma_path, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="contestants_faces",
            metadata={"description": "Face embeddings for contestants"},
        )

    def load_embeddings_from_npy(self) -> Dict[str, np.ndarray]:
        """Load all .npy embedding files from contestants directory."""
        embeddings = {}
        contestants_path = Path(self.contestants_dir)

        # Find all .npy files
        npy_files = list(contestants_path.glob("*.npy"))

        logger.info(f"Found {len(npy_files)} embedding files")

        for npy_file in npy_files:
            try:
                # Extract name from filename (remove "_embedding.npy")
                name = npy_file.stem.replace("_embedding", "")

                # Load embedding
                embedding = np.load(npy_file)

                # Validate and reshape embedding
                if embedding.ndim == 2 and embedding.shape == (1, 512):
                    # Reshape from (1, 512) to (512,)
                    embedding = embedding.flatten()
                    embeddings[name] = embedding
                    logger.debug(
                        f"Loaded and reshaped embedding for {name}: shape {embedding.shape}"
                    )
                elif embedding.ndim == 1 and len(embedding) == 512:
                    embeddings[name] = embedding
                    logger.debug(
                        f"Loaded embedding for {name}: shape {embedding.shape}"
                    )
                else:
                    logger.warning(
                        f"Invalid embedding shape for {name}: {embedding.shape}"
                    )

            except Exception as e:
                logger.error(f"Error loading {npy_file}: {e}")

        logger.info(f"Successfully loaded {len(embeddings)} embeddings")
        return embeddings

    def populate_database(self, force_refresh: bool = False) -> int:
        """Populate ChromaDB with face embeddings from .npy files."""

        # Check if already populated
        if not force_refresh and self.collection.count() > 0:
            logger.info(
                f"Database already contains {self.collection.count()} embeddings"
            )
            return self.collection.count()

        # Clear existing data if force refresh
        if force_refresh:
            self.client.delete_collection("contestants_faces")
            self.collection = self.client.create_collection(
                name="contestants_faces",
                metadata={"description": "Face embeddings for contestants"},
            )

        # Load embeddings from .npy files
        embeddings = self.load_embeddings_from_npy()

        if not embeddings:
            logger.warning("No embeddings found to populate database")
            return 0

        # Prepare data for ChromaDB
        ids = []
        embeddings_list = []
        metadatas = []

        for name, embedding in embeddings.items():
            ids.append(name)
            embeddings_list.append(embedding.tolist())  # ChromaDB needs lists
            metadatas.append({"name": name, "embedding_dim": len(embedding)})

        # Add to ChromaDB
        self.collection.add(embeddings=embeddings_list, metadatas=metadatas, ids=ids)

        logger.info(
            f"Successfully populated database with {len(embeddings)} embeddings"
        )
        return len(embeddings)

    def search_similar_faces(
        self, query_embedding: np.ndarray, n_results: int = None
    ) -> List[Tuple[str, float]]:
        """Search for similar faces in the database."""
        if n_results is None:
            n_results = self.config["face_matching"]["max_results"]

        # Ensure embedding is the right format
        if isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()

        # Search in ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["metadatas", "distances"],
        )

        # Process results
        matches = []
        if results["ids"] and results["ids"][0]:  # Check if we have results
            for i, (id_, distance) in enumerate(
                zip(results["ids"][0], results["distances"][0])
            ):
                # Convert distance to similarity (ChromaDB uses cosine distance)
                similarity = 1.0 - distance

                # Only include if above threshold
                if similarity >= self.similarity_threshold:
                    matches.append((id_, similarity))

        return matches

    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        count = self.collection.count()

        if count > 0:
            # Get a sample to check embedding dimensions
            sample = self.collection.peek(limit=1)
            if sample["metadatas"]:
                embedding_dim = sample["metadatas"][0].get("embedding_dim", "unknown")
            else:
                embedding_dim = "unknown"
        else:
            embedding_dim = "N/A"

        return {
            "total_embeddings": count,
            "embedding_dimension": embedding_dim,
            "collection_name": self.collection.name,
            "similarity_threshold": self.similarity_threshold,
        }

    def reset_database(self):
        """Reset the database (delete and recreate)."""
        self.client.delete_collection("contestants_faces")
        self.collection = self.client.create_collection(
            name="contestants_faces",
            metadata={"description": "Face embeddings for contestants"},
        )
        logger.info("Database reset successfully")


def initialize_database(
    config_path: str = "config.json", force_refresh: bool = False
) -> ChromaDBManager:
    """Initialize and populate ChromaDB with face embeddings."""
    manager = ChromaDBManager(config_path)
    count = manager.populate_database(force_refresh=force_refresh)

    if count > 0:
        logger.info(f"Database initialized with {count} contestants")
    else:
        logger.warning("Database initialization failed - no embeddings loaded")

    return manager


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Initialize database
    db_manager = initialize_database(force_refresh=True)

    # Print stats
    stats = db_manager.get_database_stats()
    print(f"Database Stats: {stats}")
