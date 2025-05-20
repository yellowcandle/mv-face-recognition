import os
import cv2
import numpy as np
import onnxruntime
from typing import List, Dict, Optional, Tuple
from src.core.detector import FaceDetector
import sys


class FixedFaceRecognizer:
    def __init__(
        self,
        face_detector: FaceDetector,
        similarity_threshold: float = 0.6,  # Increased threshold for higher precision
        use_arcface: bool = False,  # Try using OpenCV DNN first
        model_override: str = None,  # Allow explicitly setting model path
    ):
        self.use_arcface = use_arcface
        self.model_path = model_override
        
        # Model paths
        self.sface_path = os.path.join("models", "face_recognition_sface.onnx")
        self.arcface_path = os.path.join("models", "arcface_r50.onnx")
        self.opencv_model_path = os.path.join("models", "face_recognition_resnet.caffemodel")
        self.opencv_prototxt_path = self.opencv_model_path.replace(".caffemodel", ".prototxt")
        
        if self.use_arcface:
            self._init_onnx_model()
        else:
            self._init_opencv_model()

        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.face_database = {}  # Initialize an empty dictionary for storing known faces

    def _init_onnx_model(self):
        """Initialize ONNX model (SFace or ArcFace)"""
        # If model_override is specified, use it directly
        if self.model_path:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Specified model not found: {self.model_path}")
        else:
            # Try SFace first, fallback to ArcFace
            if os.path.exists(self.sface_path):
                self.model_path = self.sface_path
                print(f"Using SFace model: {self.model_path}")
            elif os.path.exists(self.arcface_path):
                self.model_path = self.arcface_path
                print(f"Using ArcFace model: {self.model_path}")
            else:
                raise FileNotFoundError("Neither SFace nor ArcFace models found.")

        # Configure ONNX provider
        providers_config = ['CPUExecutionProvider']  # Use CPU as default
        
        # Setup ONNX inference session
        try:
            print(f"Loading model: {self.model_path} with providers: {providers_config}")
            self.session = onnxruntime.InferenceSession(self.model_path, providers=providers_config)
            print(f"Successfully loaded model with providers: {self.session.get_providers()}")
            
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Determine embedding size from model's output shape
            model_output_shape = self.session.get_outputs()[0].shape
            if len(model_output_shape) == 2 and isinstance(model_output_shape[1], int):
                self.embedding_size = model_output_shape[1]
            else:
                # Set default based on model type
                if "sface" in self.model_path.lower():
                    self.embedding_size = 128
                else:  # ArcFace
                    self.embedding_size = 512
            
            print(f"Using embedding size: {self.embedding_size}")
            
            # Mean and std for normalization
            # These values are critical for proper embedding calculation
            if "sface" in self.model_path.lower():
                # SFace specific normalization values
                self.mean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
                self.std = np.array([0.5, 0.5, 0.5], dtype=np.float32)
            else:
                # ArcFace values
                self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
                self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                
        except Exception as e:
            raise RuntimeError(f"Failed to load ONNX model: {e}")

    def _init_opencv_model(self):
        """Initialize OpenCV DNN model"""
        if not os.path.exists(self.opencv_model_path) or not os.path.exists(self.opencv_prototxt_path):
            # Try alternative filenames (without _resnet suffix)
            alt_model_path = os.path.join("models", "face_recognition.caffemodel")
            alt_prototxt_path = alt_model_path.replace(".caffemodel", ".prototxt")
            
            if os.path.exists(alt_model_path) and os.path.exists(alt_prototxt_path):
                self.opencv_model_path = alt_model_path
                self.opencv_prototxt_path = alt_prototxt_path
            else:
                raise FileNotFoundError(
                    "OpenCV face recognition model files not found. "
                    "Searched for resnet and generic versions."
                )
        
        print(f"Using OpenCV DNN model: {self.opencv_model_path}")
        self.model = cv2.dnn.readNetFromCaffe(self.opencv_prototxt_path, self.opencv_model_path)
        self.embedding_size = 128  # Standard for OpenCV DNN face recognition models
        
        # Mean and std for OpenCV normalization
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def add_known_embedding(self, person_id: str, embedding: np.ndarray):
        """Adds a pre-computed embedding to the face database."""
        if embedding is not None and embedding.size > 0:
            # Ensure it's normalized
            norm = np.linalg.norm(embedding)
            if norm > 1e-10:
                self.face_database[person_id] = embedding / norm
            else:
                self.face_database[person_id] = embedding
        else:
            print(f"Warning: Attempted to add invalid pre-computed embedding for {person_id}")

    def add_face(self, image: np.ndarray, person_id: str):
        """Detects a face in the image, computes its embedding, and stores it."""
        detected_faces_data = self.face_detector.detect_faces(image)
        if not detected_faces_data:
            print(f"Warning: No face detected for person_id: {person_id}")
            return

        # Take the first detected face
        first_face_data = detected_faces_data[0]
        
        # Extract bbox
        if hasattr(first_face_data, 'bbox') and first_face_data.bbox is not None:
            bbox_to_extract = first_face_data.bbox.astype(int).tolist()
        elif isinstance(first_face_data, (list, np.ndarray)) and len(first_face_data) >= 4:
            bbox_to_extract = np.array(first_face_data[:4]).astype(int).tolist()
        else:
            print(f"Warning: Unexpected face data type for person_id {person_id}")
            return

        # Extract face with padding
        face_crop = self.face_detector.extract_face(image, bbox_to_extract, padding=0.1)
        if face_crop is None:
            print(f"Warning: Failed to extract face for person_id {person_id}")
            return
            
        # Compute embedding
        face_embedding = self._get_embedding(face_crop)
        if face_embedding is None or np.all(face_embedding == 0):
            print(f"Warning: Failed to compute embedding for person_id {person_id}")
            return
            
        self.face_database[person_id] = face_embedding
        print(f"Added face for {person_id} to database.")

    def identify_face(
        self, image: np.ndarray, detected_face_embeddings: Optional[List[np.ndarray]] = None
    ) -> List[Dict]:
        """
        Identifies known faces in an image.
        If detected_face_embeddings are provided, uses them directly.
        """
        results = []
        
        detected_faces_data = self.face_detector.detect_faces(image)
        if not detected_faces_data:
            return results

        if detected_face_embeddings is not None and len(detected_face_embeddings) != len(detected_faces_data):
            print("Warning: Mismatch between detected_faces_data and detected_face_embeddings")
            detected_face_embeddings = None

        if not self.face_database:
            print("Warning: Face database is empty. Cannot identify faces.")
            return [{"bbox": f.bbox if hasattr(f, 'bbox') else f[:4], 
                    "person_id": None, "confidence": 0.0} 
                    for f in detected_faces_data]

        for idx, face_data_item in enumerate(detected_faces_data):
            # Get bbox
            if hasattr(face_data_item, 'bbox') and face_data_item.bbox is not None:
                bbox_to_extract = face_data_item.bbox.astype(int).tolist()
                original_bbox = face_data_item.bbox
            elif isinstance(face_data_item, (list, np.ndarray)) and len(face_data_item) >= 4:
                bbox_to_extract = np.array(face_data_item[:4]).astype(int).tolist()
                original_bbox = face_data_item[:4]
            else:
                print(f"Skipping unexpected face data type: {type(face_data_item)}")
                continue
            
            # Get embedding
            if detected_face_embeddings is not None:
                embedding_to_use = detected_face_embeddings[idx]
            else:
                face_crop = self.face_detector.extract_face(image, bbox_to_extract, padding=0.1)
                if face_crop is None:
                    results.append({"bbox": original_bbox, "person_id": None, "confidence": 0.0})
                    continue
                embedding_to_use = self._get_embedding(face_crop)

            if embedding_to_use is None or np.all(embedding_to_use == 0):
                results.append({"bbox": original_bbox, "person_id": None, "confidence": 0.0})
                continue

            # Find best match
            best_match, best_similarity = self._find_best_match(embedding_to_use)
            
            results.append({
                "bbox": original_bbox,
                "person_id": best_match if best_similarity >= self.similarity_threshold else None,
                "confidence": float(best_similarity),
            })

        return results

    def _find_best_match(self, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """Find the best match for an embedding in the face database."""
        best_match = None
        best_similarity = -1.0

        for person_id, stored_embedding in self.face_database.items():
            # Ensure embeddings have matching dimensions
            if stored_embedding.shape != embedding.shape:
                if len(stored_embedding) > len(embedding):
                    comp_embedding = stored_embedding[:len(embedding)]
                else:
                    # Pad with zeros if needed
                    comp_embedding = np.zeros(embedding.shape, dtype=np.float32)
                    comp_embedding[:len(stored_embedding)] = stored_embedding
            else:
                comp_embedding = stored_embedding
                
            similarity = self._compute_similarity(embedding, comp_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = person_id
        
        return best_match, best_similarity

    def _get_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """Get the embedding for a face image."""
        try:
            if face_image is None or face_image.size == 0:
                return np.zeros(self.embedding_size, dtype=np.float32)

            # Ensure BGR image with 3 channels
            if face_image.ndim == 2:  # Grayscale
                face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)
            elif face_image.ndim == 3 and face_image.shape[2] != 3:
                return np.zeros(self.embedding_size, dtype=np.float32)

            # Resize to 112x112 (standard for face recognition models)
            face_image = cv2.resize(face_image, (112, 112))
            
            # Convert to RGB (models typically expect RGB)
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            
            # Normalize to [0, 1]
            face_image = face_image.astype(np.float32) / 255.0

            if self.use_arcface:
                # Normalize with mean and std
                face_image = (face_image - self.mean) / self.std
                
                # Convert HWC to NCHW (batch, channels, height, width)
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)

                # Run inference
                outputs = self.session.run([self.output_name], {self.input_name: face_image})
                embedding = outputs[0][0]
            else:
                # OpenCV DNN path
                face_image = (face_image - self.mean) / self.std
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)

                self.model.setInput(face_image)
                embedding = self.model.forward().flatten()

            # Normalize the embedding
            norm = np.linalg.norm(embedding)
            if norm < 1e-10:
                return np.zeros(self.embedding_size, dtype=np.float32)

            return embedding / norm

        except Exception as e:
            print(f"Error in _get_embedding: {e}")
            return np.zeros(self.embedding_size, dtype=np.float32)

    def _compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        if not isinstance(embedding1, np.ndarray) or not isinstance(embedding2, np.ndarray):
            return 0.0
            
        embedding1 = embedding1.flatten()
        embedding2 = embedding2.flatten()

        if embedding1.shape != embedding2.shape:
            return 0.0

        # Both embeddings should already be normalized, but we'll normalize again for safety
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.0

        # Compute cosine similarity
        dot_product = np.dot(embedding1 / norm1, embedding2 / norm2)
        return float(np.clip(dot_product, 0.0, 1.0))

    def detect_and_embed(self, image: np.ndarray) -> List[np.ndarray]:
        """Detect faces and compute embeddings for each."""
        detected_faces_data = self.face_detector.detect_faces(image)
        embeddings = []

        if not detected_faces_data:
            return embeddings

        for face_data_item in detected_faces_data:
            # Get bbox
            if hasattr(face_data_item, 'bbox') and face_data_item.bbox is not None:
                bbox_to_extract = face_data_item.bbox.astype(int).tolist()
            elif isinstance(face_data_item, (list, np.ndarray)) and len(face_data_item) >= 4:
                bbox_to_extract = np.array(face_data_item[:4]).astype(int).tolist()
            else:
                embeddings.append(np.zeros(self.embedding_size, dtype=np.float32))
                continue
            
            # Extract face with padding
            face_crop = self.face_detector.extract_face(image, bbox_to_extract, padding=0.1)
            
            if face_crop is None:
                embeddings.append(np.zeros(self.embedding_size, dtype=np.float32))
            else:
                embedding = self._get_embedding(face_crop)
                embeddings.append(embedding)
            
        return embeddings
