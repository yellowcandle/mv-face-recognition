"""
Unified face recognizer with multiple backend support.

This module provides a base recognizer interface and implementations
for different face recognition methods.
"""

import os
import cv2
import numpy as np
import time
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor
import pickle
import hashlib

from src.core.detector import FaceDetector
from src.utils.cache import EmbeddingCache


class FaceRecognizer(ABC):
    """
    Abstract base class for face recognition systems.
    
    This class defines the interface that all recognizer implementations
    must follow.
    """
    
    @abstractmethod
    def compute_embedding(self, face_img: np.ndarray) -> np.ndarray:
        """
        Compute embedding for a face image.
        
        Args:
            face_img: Preprocessed face image
            
        Returns:
            numpy.ndarray: Face embedding vector
        """
        pass
    
    @abstractmethod
    def preprocess_face(self, face_img: np.ndarray) -> np.ndarray:
        """
        Preprocess face image for the recognition model.
        
        Args:
            face_img: Face image
            
        Returns:
            numpy.ndarray: Preprocessed face image
        """
        pass
    
    @abstractmethod
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute similarity between two face embeddings.
        
        Args:
            embedding1: First face embedding
            embedding2: Second face embedding
            
        Returns:
            float: Similarity score (higher is more similar)
        """
        pass
    
    @abstractmethod
    def identify_faces(
        self, 
        image: np.ndarray, 
        known_embeddings: Dict[str, List[np.ndarray]]
    ) -> List[Dict[str, Any]]:
        """
        Identify all faces in an image against known embeddings.
        
        Args:
            image: Input image
            known_embeddings: Dictionary mapping person IDs to embedding lists
            
        Returns:
            list: List of identification results
        """
        pass


class StandardFaceRecognizer(FaceRecognizer):
    """
    Standard face recognizer implementation based on embedding similarity.
    
    This implementation uses an ONNX model to compute face embeddings and
    cosine similarity for matching.
    """
    
    def __init__(
        self,
        face_detector: FaceDetector,
        similarity_threshold: float = 0.6,
        model_path: Optional[str] = None,
        use_batch_processing: bool = True,
        use_quantized_model: bool = True,
        cache_dir: Optional[str] = None,
        max_workers: int = 4,
        embedding_cache_size: int = 256
    ):
        """
        Initialize the standard face recognizer.
        
        Args:
            face_detector: Face detector instance
            similarity_threshold: Threshold for face matching
            model_path: Path to face recognition model
            use_batch_processing: Whether to process faces in batches
            use_quantized_model: Whether to use quantized model for faster inference
            cache_dir: Directory to store persistent cache files
            max_workers: Maximum number of worker threads
            embedding_cache_size: Size of embedding cache
        """
        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.use_batch_processing = use_batch_processing
        self.use_quantized_model = use_quantized_model
        self.max_workers = max_workers
        self._max_cache_size = embedding_cache_size
        
        # Path setup
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.models_dir = self.project_root / "models"
        
        # Cache directory setup
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = self.project_root / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # Set default model path if not provided
        if model_path is None:
            # Define model fallback order
            model_candidates = [
                # First try the quantized model if requested
                "arcface_r50_int8.onnx" if use_quantized_model else None,
                # Then try standard models in order of preference
                "arcface_r50.onnx",
                "face_recognition_sface.onnx",
                # Additional fallbacks
                "sface_model.onnx",
                "arc_resnet50.onnx"
            ]
            
            # Try each model in order until we find one
            for candidate in model_candidates:
                if candidate is None:
                    continue
                
                candidate_path = self.models_dir / candidate
                if os.path.exists(candidate_path):
                    model_path = str(candidate_path)
                    print(f"Using model: {candidate}")
                    break
            
            # If no model found, default to arcface_r50.onnx (may not exist)
            if model_path is None:
                model_path = str(self.models_dir / "arcface_r50.onnx")
                print(f"Warning: No valid model found, defaulting to {model_path}")
        
        self.model_path = model_path
        
        # Initialize the model
        self._init_model()
        
        # Image normalization constants
        self.mean = np.array([0.485, 0.456, 0.406])
        self.std = np.array([0.229, 0.224, 0.225])
        
        # Create thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Initialize embedding cache
        self.embedding_cache = EmbeddingCache(
            cache_dir=self.cache_dir,
            memory_size=embedding_cache_size
        )
        
        # Statistics
        self.stats = {
            "embeddings_computed": 0,
            "faces_processed": 0,
            "matches_found": 0,
            "processing_time": 0.0,
        }
        
        # For tracking recognized faces
        self.recognized_faces = {}
        self.recognition_ttl = 10  # frames
    
    def _init_model(self):
        """Initialize the face recognition model."""
        try:
            import onnxruntime as ort
            
            # Use ModelFinder to locate or download the model
            try:
                from src.utils.model_finder import ModelFinder
                model_finder = ModelFinder(project_root=str(self.project_root), cache_dir=str(self.cache_dir))
                
                # Try to find the model from the specified path first
                if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 1000:
                    print(f"Using specified model: {self.model_path}")
                    model_found = True
                else:
                    # Extract model name from path
                    model_name = os.path.basename(self.model_path)
                    print(f"Looking for model: {model_name}")
                    
                    # Try to find or download the model
                    found_path = model_finder.find_model(model_name)
                    if found_path:
                        print(f"ModelFinder found model: {found_path}")
                        self.model_path = found_path
                        model_found = True
                    else:
                        # Try alternative recognition models if the specific one wasn't found
                        recognition_models = model_finder.find_models(["face_recognition"])
                        if recognition_models:
                            # Use the first recognition model found
                            first_model_name = next(iter(recognition_models.keys()))
                            self.model_path = recognition_models[first_model_name]
                            print(f"Using alternative model: {self.model_path}")
                            model_found = True
                        else:
                            model_found = False
                
                if not model_found:
                    raise FileNotFoundError(f"Could not find a suitable face recognition model")
            except ImportError:
                # ModelFinder not available, fall back to the old behavior
                if not os.path.exists(self.model_path):
                    raise FileNotFoundError(f"Model file not found: {self.model_path}")
                
                # Check model file size
                file_size = os.path.getsize(self.model_path)
                if file_size < 1000:  # Too small to be a valid model
                    raise ValueError(f"Model file too small ({file_size} bytes), likely corrupted")
            
            # Set execution providers with optimized settings
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = min(4, os.cpu_count() or 1)
            
            # Get available providers
            available_providers = ort.get_available_providers()
            print(f"Available providers: {available_providers}")
            
            # Select providers
            providers = []
            if self.face_detector.device == "cuda" and "CUDAExecutionProvider" in available_providers:
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")
            
            print(f"Applied providers: {providers}, with options: {{'CPUExecutionProvider': {{}}}}")
            
            # Try to load the model
            try:
                self.session = ort.InferenceSession(
                    self.model_path, 
                    sess_options=sess_options,
                    providers=providers
                )
            except Exception as model_error:
                # Try to use other recognition models as fallbacks
                fallback_models = [
                    "face_recognition_sface.onnx",
                    "arcface_r50.onnx",
                    "sface_model.onnx"
                ]
                
                model_loaded = False
                for model_name in fallback_models:
                    fallback_path = str(self.models_dir / model_name)
                    if os.path.exists(fallback_path) and os.path.isfile(fallback_path) and fallback_path != self.model_path:
                        print(f"Primary model failed, trying fallback model: {fallback_path}")
                        try:
                            self.model_path = fallback_path
                            self.session = ort.InferenceSession(
                                self.model_path, 
                                sess_options=sess_options,
                                providers=providers
                            )
                            model_loaded = True
                            break
                        except Exception as fallback_error:
                            print(f"Fallback model {model_name} also failed: {str(fallback_error)}")
                
                if not model_loaded:
                    # Try one more time to find and load a model using ModelFinder
                    try:
                        from src.utils.model_finder import ModelFinder
                        model_finder = ModelFinder(project_root=str(self.project_root), cache_dir=str(self.cache_dir))
                        recognition_models = model_finder.find_models(["face_recognition"])
                        
                        if recognition_models:
                            for model_name, model_path in recognition_models.items():
                                print(f"Trying model: {model_name} at {model_path}")
                                try:
                                    self.model_path = model_path
                                    self.session = ort.InferenceSession(
                                        self.model_path, 
                                        sess_options=sess_options,
                                        providers=providers
                                    )
                                    model_loaded = True
                                    break
                                except Exception as alt_error:
                                    print(f"Failed to load {model_name}: {str(alt_error)}")
                    except ImportError:
                        pass
                        
                    if not model_loaded:
                        # Re-raise if all fallbacks failed
                        raise model_error
                    
            # Get input/output names
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Get model input shape
            self.input_shape = self.session.get_inputs()[0].shape
            # Handle dynamic dimensions marked as 'None'
            self.input_height = 112  # Default
            self.input_width = 112   # Default
            
            if len(self.input_shape) >= 3:
                # Get height and width from the model input shape
                if self.input_shape[-2] is not None:  # Height
                    self.input_height = int(self.input_shape[-2])
                if self.input_shape[-1] is not None:  # Width
                    self.input_width = int(self.input_shape[-1])
            
            print(f"Initialized face recognition model: {self.model_path}")
            print(f"Model input shape: {self.input_shape}, using size: {self.input_width}x{self.input_height}")
            
        except ImportError as import_error:
            if "onnxruntime" in str(import_error):
                raise ImportError(
                    "ONNX Runtime is not installed. Install with: pip install onnxruntime>=1.16.0"
                )
            else:
                # Reraise other import errors
                raise import_error
        except Exception as e:
            # Try to download the model
            print(f"Error initializing face recognition model: {str(e)}")
            print("Attempting to download required models...")
            
            # First try using ModelFinder if available
            try:
                from src.utils.model_finder import ModelFinder
                print("Using ModelFinder to download models...")
                
                model_finder = ModelFinder(project_root=str(self.project_root), cache_dir=str(self.cache_dir))
                # Extract model name from path or use a default recognition model
                model_name = os.path.basename(self.model_path) if self.model_path else "arcface_r50.onnx"
                
                # Force re-download
                found_path = model_finder.find_model(model_name, download_if_missing=True)
                if found_path:
                    print(f"Downloaded model: {found_path}")
                    self.model_path = found_path
                    
                    # Try initialization again
                    print("Retrying model initialization after download...")
                    import onnxruntime as ort
                    sess_options = ort.SessionOptions()
                    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    
                    self.session = ort.InferenceSession(
                        self.model_path, 
                        sess_options=sess_options,
                        providers=["CPUExecutionProvider"]
                    )
                    
                    self.input_name = self.session.get_inputs()[0].name
                    self.output_name = self.session.get_outputs()[0].name
                    
                    print(f"Successfully initialized model after download: {self.model_path}")
                    return
            except ImportError:
                # ModelFinder not available, use download_models.py
                pass
            except Exception as model_finder_error:
                print(f"ModelFinder error: {str(model_finder_error)}")
            
            # Fall back to using download_models.py script
            try:
                import subprocess
                print("Using download_models.py script to download models...")
                
                subprocess.run(["python", str(self.project_root / "download_models.py"), "--force"], 
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Try initialization again
                print("Retrying model initialization after download...")
                import onnxruntime as ort
                sess_options = ort.SessionOptions()
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                
                self.session = ort.InferenceSession(
                    self.model_path, 
                    sess_options=sess_options,
                    providers=["CPUExecutionProvider"]
                )
                
                self.input_name = self.session.get_inputs()[0].name
                self.output_name = self.session.get_outputs()[0].name
                
                print(f"Successfully initialized model after download: {self.model_path}")
                
            except Exception as download_error:
                # If still failing, raise the original error
                raise RuntimeError(f"Error initializing face recognition model: {str(e)}\n"
                                   f"Download attempt also failed: {str(download_error)}")
    
    def preprocess_face(self, face_img: np.ndarray) -> np.ndarray:
        """
        Preprocess face image for the recognition model.
        
        Args:
            face_img: Face image
            
        Returns:
            numpy.ndarray: Preprocessed face image
        """
        # Check if face image is valid
        if face_img is None or face_img.size == 0:
            raise ValueError("Invalid face image")
            
        # Resize to model's input size
        # Use INTER_AREA for downsampling (better quality and speed)
        if face_img.shape[0] > self.input_height or face_img.shape[1] > self.input_width:
            face_img = cv2.resize(face_img, (self.input_width, self.input_height), 
                                  interpolation=cv2.INTER_AREA)
        else:
            face_img = cv2.resize(face_img, (self.input_width, self.input_height), 
                                  interpolation=cv2.INTER_LINEAR)
        
        # Ensure BGR to RGB conversion
        if face_img.ndim == 3 and face_img.shape[2] == 3:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            
        # Efficient array operations
        face_img = face_img.astype(np.float32) / 255.0  # Scale to [0,1]
        
        # Vectorized normalization (faster than element-wise)
        # Reshape for broadcasting
        mean = self.mean.reshape(1, 1, 3)
        std = self.std.reshape(1, 1, 3)
        face_img = (face_img - mean) / std
        
        # HWC to NCHW format for the model
        # This operation is performance-critical, use optimized version
        if face_img.flags.c_contiguous:
            face_img = np.ascontiguousarray(np.transpose(face_img, (2, 0, 1)))
        else:
            face_img = np.transpose(face_img, (2, 0, 1)).copy()
        face_img = np.expand_dims(face_img, axis=0)
        
        return face_img
    
    def compute_embedding(self, face_img: np.ndarray) -> np.ndarray:
        """
        Compute embedding for a face image.
        
        Args:
            face_img: Preprocessed face image
            
        Returns:
            numpy.ndarray: Face embedding vector
        """
        start_time = time.time()
        
        # Check for cached embeddings
        img_hash = self._compute_image_hash(face_img)
        cache_key = f"embedding_{img_hash}"
        
        cached_embedding = self.embedding_cache.get(cache_key)
        if cached_embedding is not None:
            return cached_embedding
        
        try:
            # Use model to get embedding
            # Ensure contiguous memory for optimal inference speed
            if not face_img.flags.c_contiguous:
                face_img = np.ascontiguousarray(face_img)
                
            outputs = self.session.run(
                [self.output_name], 
                {self.input_name: face_img}
            )
            embedding = outputs[0][0]
            
            # Normalize embedding
            # Use faster L2 normalization
            norm = np.sqrt(np.sum(embedding * embedding))
            
            # Only normalize if needed
            # Zero vectors are handled separately
            if norm > 1e-10:
                embedding = embedding / norm
            else:
                # Handle zero vector gracefully
                embedding = np.zeros_like(embedding)
                
            # Cache the embedding
            self.embedding_cache.set(cache_key, embedding)
            
            # Update statistics
            self.stats["embeddings_computed"] += 1
            self.stats["processing_time"] += time.time() - start_time
            
            return embedding
        except Exception as e:
            print(f"Error computing embedding: {str(e)}")
            # Return a zero vector on error
            return np.zeros(512, dtype=np.float32)
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute similarity between two face embeddings.
        
        Args:
            embedding1: First face embedding
            embedding2: Second face embedding
            
        Returns:
            float: Similarity score (cosine similarity)
        """
        # Convert to 1D if needed
        if embedding1.ndim > 1:
            embedding1 = embedding1.flatten()
        if embedding2.ndim > 1:
            embedding2 = embedding2.flatten()
            
        # Compute cosine similarity
        # Use faster implementations
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.sqrt(np.sum(embedding1 * embedding1))
        norm2 = np.sqrt(np.sum(embedding2 * embedding2))
        
        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.0
        
        # More numerically stable implementation
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        return float(similarity)
    
    def identify_faces(
        self, 
        image: np.ndarray, 
        known_embeddings: Dict[str, List[np.ndarray]]
    ) -> List[Dict[str, Any]]:
        """
        Identify all faces in an image against known embeddings.
        
        Args:
            image: Input image
            known_embeddings: Dictionary mapping person IDs to embedding lists
            
        Returns:
            list: List of identification results
        """
        start_time = time.time()
        results = []
        
        # Detect faces
        face_bboxes = self.face_detector.detect_faces(image)
        
        # Process each detected face
        if self.use_batch_processing and len(face_bboxes) > 1:
            # Parallel processing for multiple faces
            batch_results = self._process_faces_in_parallel(image, face_bboxes, known_embeddings)
            results.extend(batch_results)
        else:
            # Sequential processing for single face
            for i, bbox in enumerate(face_bboxes):
                face_id = f"face_{i}"
                
                # Check if face was recently recognized
                if face_id in self.recognized_faces:
                    self.recognized_faces[face_id]['ttl'] -= 1
                    if self.recognized_faces[face_id]['ttl'] > 0:
                        # Use previous recognition result
                        results.append(self.recognized_faces[face_id]['result'])
                        continue
                    else:
                        # Recognition expired, remove from tracking
                        del self.recognized_faces[face_id]
                
                # Extract face region
                face_img = self.face_detector.extract_face(image, bbox, padding=0.1)
                if face_img is None:
                    continue
                    
                # Process the face
                result = self._process_single_face(face_img, face_id, bbox, known_embeddings)
                if result:
                    results.append(result)
        
        # Update statistics
        self.stats["faces_processed"] += len(face_bboxes)
        self.stats["matches_found"] += len(results)
        self.stats["processing_time"] += time.time() - start_time
        
        return results
    
    def _process_faces_in_parallel(
        self, 
        image: np.ndarray, 
        face_bboxes: List[List[float]], 
        known_embeddings: Dict[str, List[np.ndarray]]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple faces in parallel.
        
        Args:
            image: Input image
            face_bboxes: List of face bounding boxes
            known_embeddings: Known embeddings dictionary
            
        Returns:
            list: List of recognition results
        """
        futures = []
        results = []
        
        # Submit processing tasks for each face
        for i, bbox in enumerate(face_bboxes):
            face_id = f"face_{i}"
            
            # Skip if we have a recent recognition
            if face_id in self.recognized_faces:
                self.recognized_faces[face_id]['ttl'] -= 1
                if self.recognized_faces[face_id]['ttl'] > 0:
                    # Use previous recognition result
                    results.append(self.recognized_faces[face_id]['result'])
                    continue
                else:
                    # Recognition expired, remove from tracking
                    del self.recognized_faces[face_id]
            
            # Extract face
            face_img = self.face_detector.extract_face(image, bbox, padding=0.1)
            if face_img is None:
                continue
                
            # Submit the task
            future = self.executor.submit(
                self._process_single_face, face_img, face_id, bbox, known_embeddings
            )
            futures.append(future)
        
        # Collect results
        for future in futures:
            result = future.result()
            if result:
                results.append(result)
                
        return results
    
    def _process_single_face(
        self, 
        face_img: np.ndarray, 
        face_id: str, 
        bbox: List[float], 
        known_embeddings: Dict[str, List[np.ndarray]]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single face and return the result.
        
        Args:
            face_img: Face image
            face_id: Face identifier
            bbox: Bounding box coordinates
            known_embeddings: Known embeddings dictionary
            
        Returns:
            dict: Recognition result or None on failure
        """
        try:
            # Preprocess and compute embedding
            preprocessed = self.preprocess_face(face_img)
            face_embedding = self.compute_embedding(preprocessed)
            
            # Match against known embeddings
            best_match = None
            best_score = -1
            
            for person_id, embeddings_list in known_embeddings.items():
                for known_embedding in embeddings_list:
                    # Convert to proper format if needed
                    if isinstance(known_embedding, np.ndarray) and known_embedding.size > 0:
                        similarity = self.compute_similarity(face_embedding, known_embedding)
                        if similarity > self.similarity_threshold and similarity > best_score:
                            best_match = person_id
                            best_score = similarity
            
            # Create result
            result = {
                'bbox': bbox,
                'person_id': best_match,
                'confidence': best_score if best_match else 0.0
            }
            
            # Store for future frames
            if best_match:
                self.recognized_faces[face_id] = {
                    'result': result,
                    'ttl': self.recognition_ttl
                }
                
            return result
            
        except Exception as e:
            print(f"Error processing face: {str(e)}")
            return None
    
    def get_embedding(self, face_id: str) -> Optional[np.ndarray]:
        """
        Get cached embedding for a face ID.
        
        Args:
            face_id: Face identifier
            
        Returns:
            numpy.ndarray: Face embedding if found, None otherwise
        """
        # Check primary locations
        # 1. Check from embedding cache
        embedding = self.embedding_cache.get_embedding(face_id)
        if embedding is not None:
            return embedding
            
        # 2. Check in contestant directory
        embedding_path = self.project_root / "source" / "photo" / "contestants" / f"{face_id}_embedding.npy"
        if embedding_path.exists():
            try:
                embedding = np.load(str(embedding_path), allow_pickle=True)
                
                # Add to cache for future use
                self.embedding_cache.add_embedding(face_id, embedding)
                return embedding
            except Exception as e:
                print(f"Error loading embedding from {embedding_path}: {str(e)}")
        
        # Not found
        return None
    
    def save_embedding(
        self, 
        face_id: str, 
        embedding: np.ndarray, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save embedding for future use.
        
        Args:
            face_id: Face identifier
            embedding: Face embedding vector
            metadata: Optional metadata
            
        Returns:
            bool: Success status
        """
        # Save to cache
        self.embedding_cache.add_embedding(face_id, embedding, metadata)
        
        # Save to contestant directory
        try:
            embedding_path = self.project_root / "source" / "photo" / "contestants" / f"{face_id}_embedding.npy"
            os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
            np.save(str(embedding_path), embedding)
            return True
        except Exception as e:
            print(f"Error saving embedding to {embedding_path}: {str(e)}")
            return False
    
    def batch_identify_faces(
        self, 
        images: List[np.ndarray], 
        known_embeddings: Dict[str, List[np.ndarray]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch identify faces in multiple images.
        
        Args:
            images: List of input images
            known_embeddings: Dictionary mapping person IDs to embedding lists
            
        Returns:
            list: List of identification results per image
        """
        if not self.use_batch_processing or len(images) <= 1:
            return [self.identify_faces(img, known_embeddings) for img in images]
            
        # Process images in parallel using thread pool
        futures = []
        for img in images:
            future = self.executor.submit(self.identify_faces, img, known_embeddings)
            futures.append(future)
            
        # Wait for all results
        results = [future.result() for future in futures]
            
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get recognition statistics."""
        stats = self.stats.copy()
        
        # Add detector stats
        detector_stats = self.face_detector.get_stats()
        for key, value in detector_stats.items():
            stats[f"detector_{key}"] = value
        
        # Add cache stats
        cache_stats = self.embedding_cache.get_stats()
        for key, value in cache_stats.items():
            stats[f"cache_{key}"] = value
        
        # Calculate average processing time
        if stats["faces_processed"] > 0:
            stats["avg_processing_time"] = stats["processing_time"] / stats["faces_processed"]
        else:
            stats["avg_processing_time"] = 0.0
            
        # Calculate recognition rate
        if stats["faces_processed"] > 0:
            stats["recognition_rate"] = stats["matches_found"] / stats["faces_processed"]
        else:
            stats["recognition_rate"] = 0.0
            
        return stats
    
    @staticmethod
    def _compute_image_hash(image: np.ndarray) -> str:
        """Compute a hash for image data"""
        if image.ndim == 4:  # NCHW format
            # Take the first image if it's a batch
            img = image[0]
        else:
            img = image
        return hashlib.md5(img.tobytes()).hexdigest()
    
    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown()
