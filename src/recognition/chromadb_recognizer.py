import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import chromadb
import numpy as np

from src.utils.performance import profile_execution


class ChromaDBFaceRecognizer:
    """
    Face recognizer implementation using ChromaDB for fast embedding matching.

    This class provides an alternative to the standard dictionary-based face recognition
    by using ChromaDB's vector database capabilities for efficient similarity search.
    """

    def __init__(
        self,
        project_root: Union[str, Path],
        similarity_threshold: float = 0.6,
        persistent: bool = True,
        collection_name: str = "face_embeddings",
        cache_dir: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize the ChromaDB face recognizer.

        Args:
            project_root: Project root directory path
            similarity_threshold: Threshold for face matching (default: 0.6)
            persistent: Whether to use persistent storage (default: True)
            collection_name: Name of the ChromaDB collection (default: "face_embeddings")
            cache_dir: Directory for cache storage (default: project_root/cache/chromadb)
        """
        if isinstance(project_root, str):
            self.project_root = Path(project_root)
        else:
            self.project_root = project_root

        self.similarity_threshold = similarity_threshold
        self.persistent = persistent
        self.collection_name = collection_name

        # Set up cache directory
        if cache_dir is None:
            self.cache_dir = self.project_root / "cache" / "chromadb"
        else:
            self.cache_dir = Path(cache_dir)

        os.makedirs(self.cache_dir, exist_ok=True)

        # Performance metrics
        self.query_count = 0
        self.query_time = 0
        self.cache_hits = 0
        self.cache_misses = 0

        # Initialize ChromaDB client and collection
        self._setup_chromadb()

    def _setup_chromadb(self):
        """Set up the ChromaDB client and collection."""
        try:
            if self.persistent:
                self.client = chromadb.PersistentClient(path=str(self.cache_dir))
            else:
                self.client = chromadb.Client()

            # Try to get existing collection or create a new one
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                print(
                    f"Loaded existing ChromaDB collection with {self.collection.count()} embeddings"
                )
            except Exception:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},  # Use cosine similarity for face embeddings
                )
                print(f"Created new ChromaDB collection '{self.collection_name}'")

        except Exception as e:
            print(f"Error setting up ChromaDB: {str(e)}")
            # Fallback to in-memory dictionary if ChromaDB fails
            self.client = None
            self.collection = None
            self._fallback_embeddings = {}
            print("WARNING: Using fallback in-memory dictionary for embeddings")

    @profile_execution
    def add_embedding(
        self,
        face_id: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add a face embedding to the database.

        Args:
            face_id: Unique identifier for the face
            embedding: Face embedding vector
            metadata: Additional metadata (e.g., {"name": "Person Name"})
        """
        if metadata is None:
            metadata = {}

        # Ensure embedding is properly formatted for ChromaDB
        if isinstance(embedding, np.ndarray):
            if embedding.ndim > 1:
                embedding = embedding.flatten()

        if self.collection is None:
            # Fallback to dictionary storage
            self._fallback_embeddings[face_id] = {
                "embedding": embedding,
                "metadata": metadata,
            }
            return

        try:
            # Check if ID already exists
            try:
                existing = self.collection.get(ids=[face_id], include=["metadatas"])

                if existing and existing["ids"]:
                    # Update existing embedding
                    self.collection.update(
                        ids=[face_id],
                        embeddings=[embedding.tolist()],
                        metadatas=[metadata],
                    )
                else:
                    # Add new embedding
                    self.collection.add(
                        ids=[face_id],
                        embeddings=[embedding.tolist()],
                        metadatas=[metadata],
                    )
            except Exception:
                # Add new embedding if checking fails
                self.collection.add(
                    ids=[face_id], embeddings=[embedding.tolist()], metadatas=[metadata]
                )

        except Exception as e:
            print(f"Error adding embedding for {face_id}: {str(e)}")
            # Fallback to dictionary storage
            if hasattr(self, "_fallback_embeddings"):
                self._fallback_embeddings[face_id] = {
                    "embedding": embedding,
                    "metadata": metadata,
                }

    @profile_execution
    def add_embeddings_batch(self, embeddings_dict: Dict[str, Union[List[np.ndarray], np.ndarray]]):
        """
        Add multiple embeddings in batch.

        Args:
            embeddings_dict: Dictionary mapping IDs to embeddings or embedding lists
                Format: {
                    "person1": [embedding1, embedding2, ...],
                    "person2": embedding3,
                    ...
                }
        """
        if self.collection is None:
            # Fallback to dictionary storage
            for face_id, embs in embeddings_dict.items():
                if isinstance(embs, list):
                    for i, emb in enumerate(embs):
                        self._fallback_embeddings[f"{face_id}_{i}"] = {
                            "embedding": emb,
                            "metadata": {"name": face_id},
                        }
                else:
                    self._fallback_embeddings[face_id] = {
                        "embedding": embs,
                        "metadata": {"name": face_id},
                    }
            return

        # Prepare batch data
        ids = []
        embeddings = []
        metadatas = []

        for face_id, embs in embeddings_dict.items():
            if isinstance(embs, list):
                for i, emb in enumerate(embs):
                    ids.append(f"{face_id}_{i}")
                    embeddings.append(emb.tolist() if isinstance(emb, np.ndarray) else emb)
                    metadatas.append({"name": face_id})
            else:
                ids.append(face_id)
                embeddings.append(embs.tolist() if isinstance(embs, np.ndarray) else embs)
                metadatas.append({"name": face_id})

        if not ids:
            return

        try:
            # Add in batches to avoid issues with large datasets
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                end = min(i + batch_size, len(ids))
                self.collection.add(
                    ids=ids[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                )

        except Exception as e:
            print(f"Error adding batch embeddings: {str(e)}")
            # Fallback to individual adds
            for i, face_id in enumerate(ids):
                try:
                    self.add_embedding(
                        face_id=face_id,
                        embedding=np.array(embeddings[i]),
                        metadata=metadatas[i],
                    )
                except Exception as inner_e:
                    print(f"Error adding individual embedding {face_id}: {str(inner_e)}")

    @profile_execution
    def match_face(
        self, face_embedding: np.ndarray, n_results: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Match a face embedding against the database.

        Args:
            face_embedding: The embedding to match
            n_results: Number of top results to return

        Returns:
            Dictionary with match information or None if no match found
        """
        start_time = time.time()
        self.query_count += 1

        if self.collection is None or self.collection.count() == 0:
            # Fallback to dictionary-based matching
            if not hasattr(self, "_fallback_embeddings") or not self._fallback_embeddings:
                return None

            best_match = None
            best_score = 0

            for face_id, data in self._fallback_embeddings.items():
                known_embedding = data["embedding"]
                similarity = self._compute_similarity(face_embedding, known_embedding)

                if similarity > self.similarity_threshold and similarity > best_score:
                    best_score = similarity
                    best_match = {
                        "id": face_id,
                        "name": data["metadata"].get("name", face_id),
                        "similarity": similarity,
                    }

            self.query_time += time.time() - start_time
            return best_match

        try:
            # Convert embedding to proper format
            if isinstance(face_embedding, np.ndarray):
                face_embedding = face_embedding.tolist()

            # Query ChromaDB for similar faces
            results = self.collection.query(
                query_embeddings=[face_embedding],
                n_results=n_results,
                include=["metadatas", "distances"],
            )

            if not results or not results["ids"] or not results["ids"][0]:
                self.query_time += time.time() - start_time
                return None

            # ChromaDB cosine distance is in range [0, 2], convert to similarity [0, 1]
            distance = results["distances"][0][0]
            similarity = 1.0 - (distance / 2.0)

            if similarity >= self.similarity_threshold:
                match_id = results["ids"][0][0]
                metadata = results["metadatas"][0][0]
                name = metadata.get("name", match_id)

                match_result = {
                    "id": match_id,
                    "name": name,
                    "similarity": similarity,
                    "metadata": metadata,
                }

                self.query_time += time.time() - start_time
                return match_result

            self.query_time += time.time() - start_time
            return None

        except Exception as e:
            print(f"Error matching face: {str(e)}")
            self.query_time += time.time() - start_time
            return None

    @profile_execution
    def identify_faces(
        self, image: np.ndarray, face_detector, face_processor=None
    ) -> List[Dict[str, Any]]:
        """
        Detect and identify faces in an image.

        Args:
            image: Input image
            face_detector: Face detector instance
            face_processor: Optional face processor for computing embeddings

        Returns:
            List of results with detected faces and matches
        """
        results = []

        # Use the provided detector to find faces
        try:
            # Detect faces
            face_bboxes = face_detector.detect(image)

            for i, bbox in enumerate(face_bboxes):
                # Extract face
                face_img = face_detector.extract_face(image, bbox)
                if face_img is None:
                    continue

                # Compute embedding
                if face_processor is not None:
                    # Use the provided processor
                    preprocessed = face_processor.preprocess_face(face_img)
                    face_embedding = face_processor.compute_embedding(preprocessed)
                else:
                    # Assume face_detector can compute embeddings directly
                    face_embedding = face_detector.compute_embedding(face_img)

                # Match against database
                match_result = self.match_face(face_embedding)

                if match_result:
                    results.append(
                        {
                            "bbox": bbox,
                            "name": match_result["name"],
                            "confidence": match_result["similarity"],
                            "match_id": match_result["id"],
                        }
                    )

        except Exception as e:
            print(f"Error identifying faces: {str(e)}")

        return results

    def load_embeddings_from_files(self, contestants_dir: Union[str, Path], contestant_info):
        """
        Load embeddings from .npy files and add to ChromaDB.

        Args:
            contestants_dir: Directory with contestant photos
            contestant_info: DataFrame with contestant information
        """
        if isinstance(contestants_dir, str):
            contestants_dir = Path(contestants_dir)

        count = 0
        embeddings_dict = {}

        for _, contestant in contestant_info.iterrows():
            nickname = contestant["暱稱"]
            embedding_path = contestants_dir / f"{nickname}_embedding.npy"

            if embedding_path.exists():
                try:
                    embedding = np.load(str(embedding_path), allow_pickle=True)

                    # Handle different embedding formats
                    if isinstance(embedding, list) or (
                        isinstance(embedding, np.ndarray) and embedding.ndim > 1
                    ):
                        # Multiple embeddings
                        embeddings_dict[nickname] = embedding
                    else:
                        # Single embedding
                        embeddings_dict[nickname] = [embedding]

                    count += 1
                except Exception as e:
                    print(f"Error loading embedding for {nickname}: {str(e)}")

        # Add all embeddings in batch
        if embeddings_dict:
            self.add_embeddings_batch(embeddings_dict)

        print(f"Loaded {count} contestant embeddings into ChromaDB")

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        avg_query_time = 0
        if self.query_count > 0:
            avg_query_time = self.query_time / self.query_count

        return {
            "total_embeddings": self.collection.count()
            if self.collection
            else len(getattr(self, "_fallback_embeddings", {})),
            "queries": self.query_count,
            "avg_query_time_ms": avg_query_time * 1000,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }

    @staticmethod
    def _compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score (0-1 range)
        """
        # Ensure embeddings are properly formatted
        if embedding1.ndim > 1:
            embedding1 = embedding1.flatten()
        if embedding2.ndim > 1:
            embedding2 = embedding2.flatten()

        # Compute cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.sqrt(np.sum(embedding1 * embedding1))
        norm2 = np.sqrt(np.sum(embedding2 * embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
