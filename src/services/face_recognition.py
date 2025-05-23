import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2 # Ensure cv2 is imported
import numpy as np
import pandas as pd

from src.config.config import Config, get_config
from src.core.detector import FaceDetector
from src.core.recognizer import FaceRecognizer # Keep for type hinting
from src.backends.standard_backend import StandardBackend
from src.backends.chromadb_backend import ChromaDBFaceRecognizer

logger = logging.getLogger(__name__)

class FaceRecognitionService:
    """
    Unified service for all face recognition operations, encapsulating
    detection, recognition, and embedding management.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config if config else get_config()
        self._init_components()
        self._load_contestant_info()
        self._load_gallery_embeddings()

    def _init_components(self):
        """Initializes detector and recognizer based on configuration."""
        # Initialize InsightFace detector
        self.detector = FaceDetector(
            backend=self.config.detection.backend.value,
            confidence_threshold=self.config.detection.confidence_threshold,
            model_size=self.config.detection.model_size,
            skip_frames=self.config.detection.skip_frames,
            cache_enabled=self.config.detection.cache_enabled,
            max_workers=self.config.detection.max_workers,
        )

        # Initialize standard recognizer
        from src.core.recognizer import StandardFaceRecognizer # Import here to avoid circular dependency if FaceRecognizer is also in core

        self.standard_recognizer = StandardFaceRecognizer(
            face_detector=self.detector,
            similarity_threshold=self.config.recognition.similarity_threshold,
            use_batch_processing=self.config.recognition.use_batch_processing,
            use_quantized_model=self.config.recognition.use_quantized_model,
            cache_dir=str(self.config.paths.cache_dir),
            max_workers=self.config.recognition.max_workers,
            embedding_cache_size=self.config.recognition.embedding_cache_size,
        )

        # Initialize backend based on configuration
        if self.config.recognition.backend.value == "chromadb": # Use .value for Enum comparison
            self.recognizer_backend = ChromaDBFaceRecognizer(
                face_detector=self.detector,
                standard_recognizer=self.standard_recognizer, # StandardFaceRecognizer is a subclass of FaceRecognizer
                similarity_threshold=self.config.recognition.similarity_threshold,
                persistent=self.config.recognition.chromadb_persistent,
                collection_name=self.config.recognition.chromadb_collection,
                cache_dir=self.config.paths.cache_dir / "chromadb",
            )
        else:
            self.recognizer_backend = StandardBackend(self.standard_recognizer)

        logger.info(f"Initialized FaceRecognitionService with {self.config.recognition.backend.value} backend.")

    def _load_contestant_info(self):
        """Loads contestant information from CSV."""
        try:
            self.contestant_info = pd.read_csv(self.config.paths.contestant_info_path)
            self.contestant_info["編號"] = self.contestant_info["編號"].astype(str)
            self.all_contestants = self.contestant_info["暱稱"].tolist()
            logger.info("Loaded contestant info from %s", self.config.paths.contestant_info_path)
        except FileNotFoundError:
            self.contestant_info = pd.DataFrame()
            self.all_contestants = []
            logger.error("Error: %s not found.", self.config.paths.contestant_info_path)
        except Exception as e:
            self.contestant_info = pd.DataFrame()
            self.all_contestants = []
            logger.error("Error reading contestant info CSV: %s", e)

    def _load_gallery_embeddings(self):
        """Loads or computes face embeddings for known contestants."""
        if self.contestant_info.empty:
            self.gallery_embeddings = {}
            self.gallery_names = {}
            logger.warning("Contestant info is empty. Cannot load gallery embeddings.")
            return

        selected_contestants = self.all_contestants # Load all for now, can be filtered later
        
        # Delegate to the appropriate backend for loading embeddings
        if isinstance(self.recognizer_backend, ChromaDBFaceRecognizer):
            # ChromaDB backend handles its own embedding loading/management
            # We need to provide it with the raw image paths to process
            embeddings_to_add = {}
            for contestant_name in selected_contestants:
                contestant_row = self.contestant_info.loc[self.contestant_info["暱稱"] == contestant_name]
                if contestant_row.empty:
                    continue
                contestant_number = contestant_row["編號"].values[0]
                contestant_path = self.config.paths.contestants_dir / str(contestant_number)
                
                if not contestant_path.is_dir():
                    logger.warning(f"Directory for contestant '{contestant_name}' not found: {contestant_path}. Skipping.")
                    continue
                
                image_paths = [
                    str(f) for f in contestant_path.iterdir()
                    if f.suffix.lower() in (".jpg", ".png", ".jpeg")
                ]

                # For ChromaDB, we need to compute embeddings first and then add them
                # This part might need to be optimized or moved if it's too slow
                current_embeddings = []
                for img_path in image_paths:
                    try:
                        img = cv2.imread(img_path)
                        if img is None:
                            logger.warning(f"Failed to read image: {img_path}")
                            continue
                        # Use the service's detector and standard recognizer to get embeddings
                        faces = self.detector.detect_faces(img)
                        for face_obj in faces: # Iterate over face objects (InsightFace) or bboxes (OpenCV/MediaPipe)
                            # Extract bbox from face_obj if it's an InsightFace object, otherwise assume it's a bbox
                            bbox = face_obj.bbox.astype(int) if hasattr(face_obj, 'bbox') else face_obj
                            face_img = self.detector.extract_face(img, bbox)
                            if face_img is not None:
                                preprocessed = self.standard_recognizer.preprocess_face(face_img)
                                embedding = self.standard_recognizer.compute_embedding(preprocessed)
                                current_embeddings.append(embedding)
                    except Exception as e:
                        logger.error(f"Error processing image {img_path} for embeddings: {e}")

                if current_embeddings:
                    embeddings_to_add[contestant_name] = current_embeddings

            if embeddings_to_add:
                self.recognizer_backend.load_embeddings_from_dict(embeddings_to_add)
                logger.info("Loaded gallery embeddings into ChromaDB.")

            # For ChromaDB, gallery_embeddings and gallery_names are not directly used for matching
            # but might be needed for visualization. We'll populate them with dummy data or
            # retrieve from ChromaDB if possible for UMAP.
            self.gallery_embeddings = {} # ChromaDB manages its own
            self.gallery_names = {name: name for name in selected_contestants} # For display

        else: # StandardBackend
            # StandardBackend's load_embeddings expects Path objects for contestant_dir
            self.gallery_embeddings = self.recognizer_backend.load_embeddings(
                contestant_dir=self.config.paths.contestants_dir,
                contestant_info=self.contestant_info,
                selected_contestants=selected_contestants,
            )
            self.gallery_names = {name: name for name in self.gallery_embeddings.keys()}
            logger.info("Loaded gallery embeddings for StandardBackend.")

    def process_image(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Processes a single image to detect and recognize faces.

        Args:
            image: The input image (BGR format).

        Returns:
            A list of dictionaries, each containing 'bbox', 'name', and 'confidence'
            for recognized faces.
        """
        results = []
        face_bboxes = self.detector.detect_faces(image)

        for bbox in face_bboxes:
            # Extract bbox from face_obj if it's an InsightFace object, otherwise assume it's a bbox
            if hasattr(bbox, 'bbox'):
                # InsightFace face object - extract bbox coordinates
                actual_bbox = bbox.bbox.astype(int).tolist()
            else:
                # Already a bbox list
                actual_bbox = bbox
                
            try:
                face_img = self.detector.extract_face(image, actual_bbox)
                if face_img is None:
                    logger.warning(f"Failed to extract face for bbox {actual_bbox}")
                    continue
            except Exception as e:
                logger.error(f"Error extracting face for bbox {actual_bbox}: {e}")
                continue

            preprocessed = self.standard_recognizer.preprocess_face(face_img)
            face_embedding = self.standard_recognizer.compute_embedding(preprocessed)

            # Use the appropriate backend for matching
            if isinstance(self.recognizer_backend, ChromaDBFaceRecognizer):
                match_result = self.recognizer_backend.match_face(face_embedding)
            else: # StandardBackend
                match_result = self.recognizer_backend.identify_face(face_embedding, self.gallery_embeddings)

            if match_result:
                results.append({
                    "bbox": bbox,
                    "name": match_result["name"],
                    "confidence": match_result["similarity"],
                    "match_id": match_result["id"],
                })
        return results

    def process_video_frame(self, frame: np.ndarray, det_threshold: float, rec_threshold: float) -> Tuple[List[Tuple[Any, str, float]], List[np.ndarray], List[str]]:
        """
        Processes a single video frame for face recognition, returning the annotated frame
        and detected embeddings/names for visualization.

        Args:
            frame: The input video frame (BGR format).
            det_threshold: Detection confidence threshold.
            rec_threshold: Recognition similarity threshold.

        Returns:
            Tuple of (annotated_frame, detected_embeddings, detected_names).
        """
        if self.detector is None or self.standard_recognizer is None:
            raise RuntimeError("Face recognition components not initialized.")

        # Temporarily override thresholds for this call
        original_det_threshold = self.detector.confidence_threshold
        original_rec_threshold = self.standard_recognizer.similarity_threshold
        
        self.detector.confidence_threshold = det_threshold
        self.standard_recognizer.similarity_threshold = rec_threshold
        if isinstance(self.recognizer_backend, ChromaDBFaceRecognizer):
            self.recognizer_backend.similarity_threshold = rec_threshold

        all_detected_objects = self.detector.detect_faces(frame)
        
        # Filter faces based on detection score if available, otherwise assume all are valid
        faces = []
        for obj in all_detected_objects:
            if hasattr(obj, 'det_score') and obj.det_score >= det_threshold:
                faces.append(obj)
            elif not hasattr(obj, 'det_score') and isinstance(obj, list) and len(obj) == 4: # Assume it's a bbox
                # If it's a bbox, we don't have a det_score, so we include it if it passes a default threshold or if no threshold is applied
                # For simplicity, if no det_score, we consider it detected.
                faces.append(obj)

        detected_embeddings = []
        detected_names = []
        matches_for_drawing = [] # (face_object, name, confidence)

        for face_bbox in faces:
            # Extract bbox from face_obj if it's an InsightFace object, otherwise assume it's a bbox
            if hasattr(face_bbox, 'bbox'):
                # InsightFace face object - extract bbox coordinates
                bbox = face_bbox.bbox.astype(int).tolist()
            else:
                # Already a bbox list
                bbox = face_bbox
                
            try:
                face_img = self.detector.extract_face(frame, bbox)
                if face_img is None:
                    logger.warning(f"Failed to extract face for bbox {bbox}")
                    continue
            except Exception as e:
                logger.error(f"Error extracting face for bbox {bbox}: {e}")
                continue

            preprocessed = self.standard_recognizer.preprocess_face(face_img)
            face_embedding = self.standard_recognizer.compute_embedding(preprocessed)
            
            # Use the appropriate backend for matching
            if isinstance(self.recognizer_backend, ChromaDBFaceRecognizer):
                match_result = self.recognizer_backend.match_face(face_embedding)
            else: # StandardBackend
                match_result = self.recognizer_backend.identify_face(face_embedding, self.gallery_embeddings)

            name = match_result["name"] if match_result else "Unknown"
            confidence = match_result["similarity"] if match_result else 0.0

            detected_embeddings.append(face_embedding)
            detected_names.append(f"{name} ({confidence:.2f})" if name != "Unknown" else "Unknown")
            matches_for_drawing.append((face_bbox, name, confidence)) # Pass original face object

        # Restore original thresholds
        self.detector.confidence_threshold = original_det_threshold
        self.standard_recognizer.similarity_threshold = original_rec_threshold
        if isinstance(self.recognizer_backend, ChromaDBFaceRecognizer):
            self.recognizer_backend.similarity_threshold = original_rec_threshold

        # Return matches for drawing, detected embeddings, and detected names
        return matches_for_drawing, detected_embeddings, detected_names

    def get_gallery_data_for_visualization(self) -> Tuple[Dict[str, List[np.ndarray]], Dict[str, str]]:
        """
        Returns gallery embeddings and names suitable for UMAP visualization.
        If using ChromaDB, this might involve querying the DB for all embeddings.
        """
        if isinstance(self.recognizer_backend, ChromaDBFaceRecognizer):
            # For ChromaDB, we need to retrieve all embeddings from the collection
            # This can be slow if the collection is very large.
            if self.recognizer_backend.collection is None: # Check if collection is None
                logger.warning("ChromaDB collection is not initialized. Cannot retrieve embeddings for visualization.")
                return {}, {}

            try:
                # Fetch all IDs first to avoid issues with large collections and direct .get()
                # Ensure the collection is not None before calling .get()
                chroma_get_result = self.recognizer_backend.collection.get()
                
                # Safely get "ids" key, default to empty list if chroma_get_result is None or "ids" is not found
                all_ids = chroma_get_result.get("ids", []) if chroma_get_result else []

                if not all_ids:
                    return {}, {} # No embeddings in collection

                all_chroma_embeddings = self.recognizer_backend.collection.get(
                    ids=all_ids,
                    include=["embeddings", "metadatas"]
                )
                
                gallery_embs = {}
                gallery_names = {}
                
                if all_chroma_embeddings and "ids" in all_chroma_embeddings:
                    for i, _id in enumerate(all_chroma_embeddings["ids"]):
                        name = all_chroma_embeddings["metadatas"][i].get("name", _id)
                        embedding = np.array(all_chroma_embeddings["embeddings"][i])
                        
                        if name not in gallery_embs:
                            gallery_embs[name] = []
                        gallery_embs[name].append(embedding)
                        gallery_names[name] = name # Simple mapping for now
                
                return gallery_embs, gallery_names
                
            except Exception as e:
                logger.error(f"Error retrieving embeddings from ChromaDB for visualization: {e}")
                return {}, {} # Return empty if error
        else:
            return self.gallery_embeddings, self.gallery_names
