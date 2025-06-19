import os
import cv2
import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Optional

from src.core.face_detector import FaceDetector

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for managing face embeddings, including computation, caching, and loading.
    """

    def __init__(self, detector: FaceDetector, contestants_dir: str, contestant_info_path: str):
        """
        Initialize the EmbeddingService.

        Args:
            detector: An instance of FaceDetector.
            contestants_dir: Path to the directory containing contestant photos.
            contestant_info_path: Path to the CSV file with contestant information.
        """
        self.detector = detector
        self.contestants_dir = contestants_dir
        self.contestant_info_path = contestant_info_path
        self.known_embeddings: Dict[str, List[np.ndarray]] = {}
        
        if not os.path.exists(self.contestants_dir):
            raise FileNotFoundError(f"Contestants directory not found: {self.contestants_dir}")
        
        try:
            self.contestant_info = pd.read_csv(self.contestant_info_path)
        except FileNotFoundError:
            logger.error(f"Contestant info file not found: {self.contestant_info_path}")
            raise

    def get_image_paths_for_contestant(self, contestant_number: str) -> List[str]:
        """Retrieve image paths for a specific contestant by their number."""
        contestant_path = os.path.join(self.contestants_dir, str(contestant_number))
        if not os.path.isdir(contestant_path):
            return []
        return [
            os.path.join(contestant_path, f)
            for f in os.listdir(contestant_path)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

    def compute_and_cache_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Compute face embedding for a single image and cache it.
        This is a simplified version for single image processing.
        """
        logger.debug(f"Computing embedding for {image_path}")
        img = cv2.imread(image_path)
        if img is None:
            logger.warning(f"Failed to read image: {image_path}")
            return None

        embedding = self.detector.extract_face_embedding(img)

        if embedding is not None:
            # Caching logic: save as .npy file next to the image
            cache_path = os.path.splitext(image_path)[0] + "_embedding.npy"
            try:
                np.save(cache_path, embedding)
                logger.info(f"Cached embedding for {os.path.basename(image_path)} to {cache_path}")
            except Exception as e:
                logger.error(f"Failed to cache embedding to {cache_path}: {e}")
        else:
            logger.warning(f"No face detected in {image_path}, cannot compute embedding.")

        return embedding

    def load_embeddings_for_contestants(self, selected_contestants: List[str]):
        """
        Load embeddings for a list of selected contestants, computing and caching if necessary.
        """
        logger.info(f"Loading embeddings for {len(selected_contestants)} contestants...")
        self.known_embeddings = {}

        for name in selected_contestants:
            contestant_row = self.contestant_info[self.contestant_info["暱稱"] == name]
            if contestant_row.empty:
                logger.warning(f"No info found for contestant: {name}")
                continue

            contestant_number = contestant_row["編號"].values[0]
            contestant_path = os.path.join(self.contestants_dir, str(contestant_number))
            
            # Check for a pre-computed aggregate embedding file for the contestant
            # This is a convention from the original mv-face-recognition.py
            aggregate_embedding_file = os.path.join(self.contestants_dir, f"{name}_embedding.npy")

            if os.path.exists(aggregate_embedding_file):
                try:
                    embedding = np.load(aggregate_embedding_file, allow_pickle=True).flatten()
                    self.known_embeddings[name] = [embedding]
                    logger.debug(f"Loaded aggregate embedding for {name} from file.")
                    continue
                except Exception as e:
                    logger.warning(f"Could not load aggregate embedding for {name}: {e}. Will recompute.")

            # If no aggregate, compute from individual images
            image_paths = self.get_image_paths_for_contestant(str(contestant_number))
            if not image_paths:
                logger.warning(f"No images found for contestant {name} in {contestant_path}")
                continue

            embeddings_for_contestant = []
            for img_path in image_paths:
                # Load the image before extracting embedding
                img = cv2.imread(img_path)
                if img is None:
                    logger.warning(f"Failed to read image: {img_path}")
                    continue
                    
                embedding = self.detector.extract_face_embedding(img)
                if embedding is not None:
                    embeddings_for_contestant.append(embedding)
            
            if embeddings_for_contestant:
                self.known_embeddings[name] = embeddings_for_contestant
                logger.debug(f"Computed and loaded {len(embeddings_for_contestant)} embeddings for {name}.")
            else:
                logger.warning(f"Could not compute any embeddings for {name}.")

        logger.info(f"Finished loading embeddings for {len(self.known_embeddings)} contestants.")
        return self.known_embeddings

    def get_known_embeddings(self, normalize: bool = True) -> Dict[str, np.ndarray]:
        """
        Returns the loaded embeddings as a dictionary of names to numpy matrices.
        Each matrix has shape (n_embeddings, 512).
        """
        processed_embeddings = {}
        for name, embs_list in self.known_embeddings.items():
            if not embs_list:
                continue
            
            emb_mat = np.vstack(embs_list).astype(np.float32)
            if normalize:
                emb_mat /= np.linalg.norm(emb_mat, axis=1, keepdims=True) + 1e-10
            
            processed_embeddings[name] = emb_mat
            
        return processed_embeddings
