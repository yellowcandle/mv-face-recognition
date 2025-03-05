import os
import cv2
import numpy as np
import onnxruntime
from typing import List, Dict, Tuple, Optional
from functools import lru_cache
import time
from src.detection.optimized_detector import OptimizedFaceDetector
from src.utils.performance import profile_execution

class OptimizedFaceRecognizer:
    """Face recognizer with performance optimizations"""
    
    def __init__(self, 
                 face_detector: OptimizedFaceDetector,
                 similarity_threshold: float = 0.6,
                 use_batch_processing: bool = True,
                 embedding_cache_size: int = 256):
        """
        Initialize the optimized face recognizer.
        
        Args:
            face_detector: Optimized face detector instance
            similarity_threshold: Threshold for face matching
            use_batch_processing: Whether to process faces in batches
            embedding_cache_size: Size of embedding cache
        """
        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.use_batch_processing = use_batch_processing
        
        # Load ArcFace model
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models", 
            "arcface_r50.onnx"
        )
        self.session = onnxruntime.InferenceSession(
            model_path, 
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        
        # Image normalization constants
        self.mean = np.array([0.485, 0.456, 0.406])
        self.std = np.array([0.229, 0.224, 0.225])
        
        # Cache for face embeddings
        self._embedding_cache = {}
        self._max_cache_size = embedding_cache_size
        
        # For tracking already recognized faces
        self.recognized_faces = {}
        self.recognition_ttl = 10  # frames
        
    @profile_execution
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
        face_img = cv2.resize(face_img, (112, 112))
        
        # Ensure BGR to RGB conversion
        if face_img.ndim == 3 and face_img.shape[2] == 3:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            
        # Convert to float and normalize
        face_img = face_img.astype(np.float32) / 255.0
        face_img = (face_img - self.mean) / self.std
        
        # HWC to NCHW format for the model
        face_img = np.transpose(face_img, (2, 0, 1))
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
        try:
            # Use model to get embedding
            outputs = self.session.run([self.output_name], {self.input_name: face_img})
            embedding = outputs[0][0]
            
            # Normalize embedding
            norm = np.linalg.norm(embedding)
            if norm > 1e-10:
                embedding = embedding / norm
            else:
                # Handle zero vector gracefully
                embedding = np.zeros_like(embedding)
                
            return embedding
        except Exception as e:
            print(f"Error computing embedding: {str(e)}")
            # Return a zero vector on error
            return np.zeros(512)
    
    @lru_cache(maxsize=128)
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
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.0
            
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
            # Check if embedding exists in memory cache
            if face_id in self._embedding_cache:
                return self._embedding_cache[face_id]
                
            # Try to load from disk cache
            embedding_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "source", "photo", "contestants",
                f"{face_id}_embedding.npy"
            )
            
            if os.path.exists(embedding_path):
                embedding = np.load(embedding_path)
                
                # Add to memory cache
                if len(self._embedding_cache) >= self._max_cache_size:
                    # Remove a random item if cache is full
                    self._embedding_cache.pop(next(iter(self._embedding_cache)))
                    
                self._embedding_cache[face_id] = embedding
                return embedding
                
            return None
        except Exception as e:
            print(f"Error loading embedding for {face_id}: {str(e)}")
            return None
            
    def save_embedding(self, face_id: str, embedding: np.ndarray):
        """
        Save embedding for future use.
        
        Args:
            face_id: Face identifier
            embedding: Face embedding vector
        """
        try:
            # Save to memory cache
            if len(self._embedding_cache) >= self._max_cache_size:
                # Remove a random item if cache is full
                self._embedding_cache.pop(next(iter(self._embedding_cache)))
                
            self._embedding_cache[face_id] = embedding
            
            # Save to disk cache
            embedding_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "source", "photo", "contestants",
                f"{face_id}_embedding.npy"
            )
            
            os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
            np.save(embedding_path, embedding)
            
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
        face_bboxes = self.face_detector.detect_faces(image)
        
        # Process each detected face
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
                
            # Preprocess and compute embedding
            try:
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
                    
                results.append(result)
                
            except Exception as e:
                print(f"Error processing face: {str(e)}")
                continue
        
        return results
        
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
        if not self.use_batch_processing:
            return [self.identify_faces(img, known_embeddings) for img in images]
            
        # Process images in parallel (implementation depends on available hardware)
        # For now, we'll use a simple loop
        results = []
        for img in images:
            results.append(self.identify_faces(img, known_embeddings))
            
        return results
