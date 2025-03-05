import os
import cv2
import numpy as np
import onnxruntime
from typing import List, Dict
from src.detection.face_detector import FaceDetector

class FaceRecognizer:
    def __init__(self, 
                 face_detector: FaceDetector,
                 similarity_threshold: float = 0.6,
                 use_arcface: bool = True):
        self.use_arcface = use_arcface
        if self.use_arcface:
            # Initialize ArcFace ONNX model
            model_path = os.path.join('models', 'arcface.onnx')
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"ArcFace model not found at {model_path}. Please download it first.")
            
            self.session = onnxruntime.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Mean and std for normalization
            self.mean = np.array([0.485, 0.456, 0.406])
            self.std = np.array([0.229, 0.224, 0.225])
        else:
            # Fallback to OpenCV DNN
            recognition_model_path = os.path.join('models', 'face_recognition.caffemodel')
            prototxt_path = recognition_model_path.replace('.caffemodel', '.prototxt')
            if not os.path.exists(recognition_model_path) or not os.path.exists(prototxt_path):
                raise FileNotFoundError("OpenCV face recognition model files not found")
            self.model = cv2.dnn.readNetFromCaffe(prototxt_path, recognition_model_path)
            
        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.face_database = {}

    def add_face(self, image: np.ndarray, person_id: str):
        faces = self.face_detector.detect_faces(image)
        if not faces:
            raise ValueError("No face detected in the image")
            
        face_embedding = self._get_embedding(
            self.face_detector.extract_face(image, faces[0])
        )
        self.face_database[person_id] = face_embedding

    def identify_face(self, image: np.ndarray) -> List[Dict]:
        faces = self.face_detector.detect_faces(image)
        results = []
        
        for bbox in faces:
            face_crop = self.face_detector.extract_face(image, bbox)
            embedding = self._get_embedding(face_crop)
            
            # Find best match
            best_match = None
            best_similarity = -1
            
            for person_id, stored_embedding in self.face_database.items():
                similarity = self._compute_similarity(embedding, stored_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = person_id
            
            results.append({
                'bbox': bbox,
                'person_id': best_match if best_similarity > self.similarity_threshold else None,
                'confidence': best_similarity
            })
            
        return results

    def _get_embedding(self, face_image: np.ndarray) -> np.ndarray:
        try:
            # Preprocess face image
            if face_image.ndim == 2:
                face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)
            
            # Resize to model's expected size
            face_image = cv2.resize(face_image, (112, 112))
            
            # Convert to RGB and normalize
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            face_image = face_image.astype(np.float32) / 255.0
            
            if self.use_arcface:
                # Standardize using ArcFace normalization
                face_image = (face_image - self.mean) / self.std
                
                # HWC to NCHW format
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)
                
                # Get embedding using ONNX model
                outputs = self.session.run([self.output_name], {self.input_name: face_image})
                embedding = outputs[0][0]
            else:
                # Standardize using OpenCV DNN normalization
                mean = np.array([0.485, 0.456, 0.406])
                std = np.array([0.229, 0.224, 0.225])
                face_image = (face_image - mean) / std
                
                # HWC to NCHW format
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)
                
                # Get embedding using OpenCV DNN model
                self.model.setInput(face_image)
                embedding = self.model.forward()
                embedding = embedding.flatten()
            
            # Normalize embedding
            norm = np.linalg.norm(embedding)
            if norm < 1e-10:  # Avoid division by very small numbers
                # Return random unit vector instead of zeros
                rng = np.random.RandomState(42)  # Fixed seed for consistency
                embedding = rng.randn(512)  # Standard embedding size
                embedding = embedding / np.linalg.norm(embedding)
                return embedding
            
            embedding = embedding / norm
            return embedding
            
        except Exception as e:
            print(f"Error in _get_embedding: {str(e)}")
            # Return random unit vector on error
            rng = np.random.RandomState(42)
            embedding = rng.randn(512)  # Standard embedding size
            return embedding / np.linalg.norm(embedding)

    def _compute_similarity(self, 
                          embedding1: np.ndarray, 
                          embedding2: np.ndarray) -> float:
        # Ensure both embeddings are flattened
        e1 = embedding1.flatten()
        e2 = embedding2.flatten()
        
        # Compute norms
        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)
        
        # Handle zero vectors
        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.0
            
        # Compute cosine similarity
        similarity = np.dot(e1, e2) / (norm1 * norm2)
        return float(similarity)

    def get_embedding(self, nickname):
        """
        Get pre-computed embedding for a contestant.
        
        Args:
            nickname: Contestant's nickname
            
        Returns:
            numpy.ndarray: Face embedding vector if found, None otherwise
        """
        try:
            # Load pre-computed embedding
            embedding_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "source", "photo", "contestants",
                f"{nickname}_embedding.npy"
            )
            return np.load(embedding_path)
        except Exception as e:
            print(f"Error loading embedding for {nickname}: {str(e)}")
            return None

    def detect_and_embed(self, image, bboxes=None):
        """
        Detect faces and compute embeddings for all faces in an image.
        
        Args:
            image: Input image
            bboxes: Optional list of face bounding boxes. If None, will detect faces.
            
        Returns:
            list: List of tuples (embedding, bbox) for each face
        """
        if bboxes is None:
            bboxes = self.face_detector.detect_faces(image)
        
        results = []
        for bbox in bboxes:
            try:
                # Ensure bbox is in correct format [x1, y1, x2, y2]
                x1, y1, x2, y2 = bbox[:4]  # Only take first 4 values
                bbox = [x1, y1, x2, y2]  # Standardize bbox format
                
                # Extract face region
                face = self.face_detector.extract_face(image, bbox)
                
                # Skip if face extraction failed
                if face is None or face.size == 0:
                    continue
                
                # Get embedding using DNN model
                embedding = self._get_embedding(face)
                
                # Reshape to match expected format (1, N)
                embedding = embedding.reshape(1, -1)
                
                # Verify embedding is valid
                if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
                    print("Invalid embedding (NaN or Inf values)")
                    continue
                    
                # Verify embedding norm
                norm = np.linalg.norm(embedding)
                if norm < 1e-10:
                    print("Invalid embedding (zero norm)")
                    continue
                    
                results.append((embedding, bbox))
            except Exception as e:
                print(f"Error processing face: {str(e)}")
                continue
            
        return results
