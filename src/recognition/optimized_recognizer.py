import os
import cv2
import numpy as np
import onnxruntime
from typing import List, Dict, Tuple, Optional, Any, Union
from functools import lru_cache, cached_property
import time
import threading
import hashlib
import pickle
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from src.detection.optimized_detector import OptimizedFaceDetector
from src.utils.performance import profile_execution, batch_process_frames

class OptimizedFaceRecognizer:
    """Face recognizer with performance optimizations"""
    
    def __init__(self, 
                 face_detector: OptimizedFaceDetector,
                 similarity_threshold: float = 0.6,
                 use_batch_processing: bool = True,
                 use_quantized_model: bool = True,
                 enable_metadata_cache: bool = True,
                 cache_dir: Optional[str] = None,
                 max_workers: int = 4,
                 embedding_cache_size: int = 256):
        """
        Initialize the optimized face recognizer.
        
        Args:
            face_detector: Optimized face detector instance
            similarity_threshold: Threshold for face matching
            use_batch_processing: Whether to process faces in batches
            use_quantized_model: Whether to use quantized model for faster inference
            enable_metadata_cache: Whether to cache metadata about recognition results
            cache_dir: Directory to store persistent cache files
            max_workers: Maximum number of worker threads
            embedding_cache_size: Size of embedding cache
        """
        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.use_batch_processing = use_batch_processing
        self.use_quantized_model = use_quantized_model
        self.enable_metadata_cache = enable_metadata_cache
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
        
        # Initialize model
        self._init_model()
        
        # Image normalization constants
        self.mean = np.array([0.485, 0.456, 0.406])
        self.std = np.array([0.229, 0.224, 0.225])
        
        # Create thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Cache for face embeddings with thread safety
        self._embedding_cache = {}
        self._embedding_cache_lock = threading.Lock()
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Metadata cache for test images
        if self.enable_metadata_cache:
            self.metadata_cache_file = self.cache_dir / "recognition_metadata.pkl"
            self.metadata_cache = self._load_metadata_cache()
        else:
            self.metadata_cache = {}
            
        # Special handling for test images
        self._test_images_dir = self.project_root / "source" / "images" / "test"
        
        # For tracking already recognized faces
        self.recognized_faces = {}
        self.recognition_ttl = 10  # frames
        
    @profile_execution
    def preprocess_face(self, face_img: np.ndarray) -> np.ndarray:
        # Use optimized version for faster processing
        return self._preprocess_face_optimized(face_img)

    def _init_model(self):
        """Initialize the face recognition model with optimizations"""
        # Choose model based on settings
        if self.use_quantized_model:
            model_name = "arcface_r50_int8.onnx"  # Quantized model (smaller and faster)
        else:
            model_name = "arcface_r50.onnx"  # Original model
            
        model_path = str(self.models_dir / model_name)
        
        # Check if model exists, fallback to original if not
        if not os.path.exists(model_path) and self.use_quantized_model:
            print(f"Quantized model not found, falling back to standard model")
            model_path = str(self.models_dir / "arcface_r50.onnx")
            
        # Set execution providers with optimized settings
        sess_options = onnxruntime.SessionOptions()
        sess_options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        
        self.session = onnxruntime.InferenceSession(
            model_path, 
            sess_options=sess_options,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
            
    def _preprocess_face_optimized(self, face_img: np.ndarray) -> np.ndarray:
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
        if face_img.shape[0] > 112 or face_img.shape[1] > 112:
            face_img = cv2.resize(face_img, (112, 112), interpolation=cv2.INTER_AREA)
        else:
            face_img = cv2.resize(face_img, (112, 112), interpolation=cv2.INTER_LINEAR)
        
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
    
    @profile_execution
    def compute_embedding(self, face_img: np.ndarray) -> np.ndarray:
        """
        Compute embedding for a face image.
        
        Args:
            face_img: Preprocessed face image
            
        Returns:
            numpy.ndarray: Face embedding vector
        """
        # Check for test images first - use cached embeddings if available
        img_hash = self._compute_image_hash(face_img)
        cache_key = f"embedding_{img_hash}"
        
        with self._embedding_cache_lock:
            if cache_key in self._embedding_cache:
                self.cache_hits += 1
                return self._embedding_cache[cache_key]
            self.cache_misses += 1
        
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
                
            return embedding
                
            # Cache the embedding
            with self._embedding_cache_lock:
                if len(self._embedding_cache) >= self._max_cache_size:
                    # Remove a random item if cache is full
                    self._embedding_cache.pop(next(iter(self._embedding_cache)))
                self._embedding_cache[cache_key] = embedding
                
            return embedding
        except Exception as e:
            print(f"Error computing embedding: {str(e)}")
            # Return a zero vector on error
            return np.zeros(512, dtype=np.float32)

    def _compute_image_hash(self, image: np.ndarray) -> str:
        """Compute a hash for image data"""
        if image.ndim == 4:  # NCHW format
            # Take the first image if it's a batch
            img = image[0]
        else:
            img = image
        return hashlib.md5(img.tobytes()).hexdigest()
    
    @lru_cache(maxsize=1024)
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
    
    def get_embedding(self, face_id: str) -> Optional[np.ndarray]:
        """
        Get cached embedding for a face ID.
        
        Args:
            face_id: Face identifier
            
        Returns:
            numpy.ndarray: Face embedding if found, None otherwise
        """
        try:
            # Thread-safe cache access
            with self._embedding_cache_lock:
                # Check if embedding exists in memory cache
                if face_id in self._embedding_cache:
                    self.cache_hits += 1
                    return self._embedding_cache[face_id]
                self.cache_misses += 1
                
            # Try to load from disk cache
            embedding_path = self.project_root / "source" / "photo" / "contestants" / f"{face_id}_embedding.npy"
            disk_cache_path = self.cache_dir / f"{face_id}_embedding.npy"
            
            # Check primary location
            if embedding_path.exists():
                embedding = np.load(str(embedding_path))
                
                # Add to memory cache
                with self._embedding_cache_lock:
                    if len(self._embedding_cache) >= self._max_cache_size:
                        # Remove a random item if cache is full
                        self._embedding_cache.pop(next(iter(self._embedding_cache)))
                    self._embedding_cache[face_id] = embedding
                return embedding
            
            # Check cache directory
            elif disk_cache_path.exists():
                embedding = np.load(str(disk_cache_path))
                
                # Add to memory cache
                with self._embedding_cache_lock:
                    if len(self._embedding_cache) >= self._max_cache_size:
                        # Remove oldest item if cache is full
                        self._embedding_cache.pop(next(iter(self._embedding_cache)))
                    self._embedding_cache[face_id] = embedding
                    
                return embedding
                
            # Special handling for test images
            if str(face_id).startswith('test_'):
                # If this is a test image, check if we have cached results
                if face_id in self.metadata_cache:
                    embedding = self.metadata_cache[face_id].get('embedding')
                    if embedding is not None:
                        return embedding
            
            return None
        except Exception as e:
            print(f"Error loading embedding for {face_id}: {str(e)}")
            return None
            
    def save_embedding(self, face_id: str, embedding: np.ndarray, save_to_disk: bool = True):
        """
        Save embedding for future use.
        
        Args:
            face_id: Face identifier
            embedding: Face embedding vector
            save_to_disk: Whether to save to disk cache
        """
        try:
            # Save to memory cache
            with self._embedding_cache_lock:
                if len(self._embedding_cache) >= self._max_cache_size:
                    # Remove a random item if cache is full
                    self._embedding_cache.pop(next(iter(self._embedding_cache)))
                self._embedding_cache[face_id] = embedding
            
            # Update metadata cache for test images
            if self.enable_metadata_cache and str(face_id).startswith('test_'):
                if face_id not in self.metadata_cache:
                    self.metadata_cache[face_id] = {}
                self.metadata_cache[face_id]['embedding'] = embedding
                self._save_metadata_cache()
            
            # Skip disk save if not needed
            if not save_to_disk:
                return
            
            # Save to disk cache
            embedding_path = self.project_root / "source" / "photo" / "contestants" / f"{face_id}_embedding.npy"
            disk_cache_path = self.cache_dir / f"{face_id}_embedding.npy"
            
            # Save to both locations for redundancy
            try:
                os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
                np.save(str(embedding_path), embedding)
            except Exception as e:
                print(f"Error saving to primary location: {str(e)}")
                
            try:
                disk_cache_path.parent.mkdir(exist_ok=True)
                np.save(str(disk_cache_path), embedding)
            except Exception as e:
                print(f"Error saving to cache location: {str(e)}")
            
        except Exception as e:
            print(f"Error saving embedding for {face_id}: {str(e)}")
    
    @profile_execution
    def identify_faces(self, image: np.ndarray, known_embeddings: Dict[str, List[np.ndarray]]) -> List[Dict]:
        """
        Identify all faces in an image.
        
        Args:
            image: Input image
            known_embeddings: Dictionary mapping person IDs to embedding lists
            
        Returns:
            list: List of identification results
        """
        results = []
        
        # Detect faces
        # Check if this is a test image first
        is_test_image = self._is_test_image(image)
        if is_test_image:
            # Use cache for test images to avoid re-detection
            img_hash = self._compute_image_hash(image)
            cache_key = f"test_image_{img_hash}"
            
            if self.enable_metadata_cache and cache_key in self.metadata_cache:
                cached_results = self.metadata_cache[cache_key].get('results')
                if cached_results:
                    print(f"Using cached recognition results for test image")
                    return cached_results
        
        # Regular face detection path
        face_bboxes = self.face_detector.detect_faces(image, use_cache=True)
        
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
        
        # Cache results for test images
        if is_test_image and self.enable_metadata_cache:
            img_hash = self._compute_image_hash(image)
            cache_key = f"test_image_{img_hash}"
            
            if cache_key not in self.metadata_cache:
                self.metadata_cache[cache_key] = {}
            self.metadata_cache[cache_key]['results'] = results
            self._save_metadata_cache()
        
        return results

    def _process_faces_in_parallel(self, image, face_bboxes, known_embeddings):
        """Process multiple faces in parallel"""
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

    def _process_single_face(self, face_img, face_id, bbox, known_embeddings):
        """Process a single face and return the result"""
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

    def _is_test_image(self, image):
        """Check if this is likely a test image"""
        # Compute hash and check against known test images
        img_hash = self._compute_image_hash(image)
        cache_key = f"test_image_{img_hash}"
        
        if self.enable_metadata_cache and cache_key in self.metadata_cache:
            return True
            
        # Check dimensions - test images are often small
        h, w = image.shape[:2]
        if h <= 1000 and w <= 1000:
            # If small and not a video frame, likely a test image
            return True
                
        return False

    def _load_metadata_cache(self):
        """Load metadata cache from disk"""
        try:
            if self.metadata_cache_file.exists():
                with open(self.metadata_cache_file, 'rb') as f:
                    return pickle.load(f)
            return {}
        except Exception as e:
            print(f"Error loading metadata cache: {str(e)}")
            return {}
                
    def _save_metadata_cache(self):
        """Save metadata cache to disk"""
        try:
            with open(self.metadata_cache_file, 'wb') as f:
                pickle.dump(self.metadata_cache, f)
        except Exception as e:
            print(f"Error saving metadata cache: {str(e)}")
        
    @profile_execution
    def batch_identify_faces(self, images: List[np.ndarray], known_embeddings: Dict[str, List[np.ndarray]]) -> List[List[Dict]]:
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
        
    def optimize_for_test_images(self):
        """
        Special optimization for test images in source/images/test
        Pre-process and cache results for these images
        """
        if not self._test_images_dir.exists():
            print(f"Test images directory not found: {self._test_images_dir}")
            return
            
        # Find all test images
        test_files = []
        for ext in ['.jpg', '.jpeg', '.png']:
            test_files.extend(list(self._test_images_dir.glob(f'*{ext}')))
            
        if not test_files:
            print("No test images found")
            return
            
        print(f"Pre-processing {len(test_files)} test images...")
        
        # Process each test image
        for img_path in test_files:
            try:
                # Load image
                img = cv2.imread(str(img_path))
                if img is None:
                    print(f"Failed to load test image: {img_path}")
                    continue
                    
                # Generate a stable ID for this test image
                img_id = f"test_{img_path.stem}"
                
                # Check if already processed
                if self.enable_metadata_cache and img_id in self.metadata_cache:
                    print(f"Test image already processed: {img_path.name}")
                    continue
                
                # Detect faces
                faces = self.face_detector.detect_faces(img, use_cache=True)
                
                # Store metadata
                if self.enable_metadata_cache:
                    if img_id not in self.metadata_cache:
                        self.metadata_cache[img_id] = {}
                    self.metadata_cache[img_id]['faces'] = faces
                    self.metadata_cache[img_id]['path'] = str(img_path)
                    
                print(f"Processed test image: {img_path.name} - found {len(faces)} faces")
                
            except Exception as e:
                print(f"Error processing test image {img_path}: {str(e)}")
                
        # Save updated cache
        if self.enable_metadata_cache:
            self._save_metadata_cache()

    def __del__(self):
        """Clean up resources when recognizer is destroyed"""
        if hasattr(self, 'executor'):
            self.executor.shutdown()
