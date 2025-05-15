import os
import cv2  # pylint: disable=import-error
import numpy as np
import onnxruntime
from typing import List, Dict, Optional # Added Optional
from src.core.detector import FaceDetector


class FaceRecognizer:
    def __init__(
        self,
        face_detector: FaceDetector,
        similarity_threshold: float = 0.35,
        use_arcface: bool = True,
    ):
        self.use_arcface = use_arcface
        if self.use_arcface:
            # Initialize SFace ONNX model as primary option
            model_path = os.path.join("models", "face_recognition_sface.onnx")
            if not os.path.exists(model_path):
                # Fallback to arcface_r50
                model_path = os.path.join("models", "arcface_r50.onnx")
                if not os.path.exists(model_path):
                    raise FileNotFoundError(
                        "Neither SFace nor ArcFace model found. Please download them first."
                    )
                else:
                    print("Using arcface_r50.onnx as SFace was not found.") # This case implies R50 is used
            else:
                print(f"Using SFace model: {model_path}") # This case implies SFace is used

            # Attempt to load the selected model_path
            try:
                self.session = onnxruntime.InferenceSession(model_path)
                print(f"Successfully loaded model: {model_path}")
            except Exception as e:
                # If the chosen model (e.g. SFace) fails to load, try the other one if not already tried.
                if "sface" in model_path.lower() and os.path.exists(os.path.join("models", "arcface_r50.onnx")):
                    print(f"Failed to load {model_path} due to {e}. Attempting to load arcface_r50.onnx.")
                    model_path = os.path.join("models", "arcface_r50.onnx")
                    try:
                        self.session = onnxruntime.InferenceSession(model_path)
                        print(f"Successfully loaded model: {model_path}")
                    except Exception as e2:
                        raise FileNotFoundError(f"Failed to load both SFace and ArcFace R50 models. Last error: {e2}")
                elif "arcface_r50" in model_path.lower() and os.path.exists(os.path.join("models", "face_recognition_sface.onnx")):
                     print(f"Failed to load {model_path} due to {e}. Attempting to load face_recognition_sface.onnx.")
                     model_path = os.path.join("models", "face_recognition_sface.onnx")
                     try:
                        self.session = onnxruntime.InferenceSession(model_path)
                        print(f"Successfully loaded model: {model_path}")
                     except Exception as e2:
                        raise FileNotFoundError(f"Failed to load both ArcFace R50 and SFace models. Last error: {e2}")
                else:
                    raise e # Re-raise original error if no alternative or alternative also failed
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Determine embedding size from model's output shape
            model_output_shape = self.session.get_outputs()[0].shape
            if len(model_output_shape) == 2 and isinstance(model_output_shape[1], int):
                self.embedding_size = model_output_shape[1]
            else:
                self.embedding_size = 512  # Default for ArcFace
                if "sface" in model_path.lower(): # Check if 'sface' is in the model_path string
                    self.embedding_size = 128
                    print("Adjusted embedding size to 128 based on SFace model name.")

            # Mean and std for normalization
            self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        else:
            # Fallback to OpenCV DNN
            self.embedding_size = 128 # Default embedding size for OpenCV DNN
            recognition_model_path = os.path.join(
                "models", "face_recognition_resnet.caffemodel" # Corrected model name
            )
            prototxt_path = recognition_model_path.replace(".caffemodel", ".prototxt")
            if not os.path.exists(recognition_model_path) or not os.path.exists(
                prototxt_path
            ):
                # Try another common model name as a fallback
                recognition_model_path = os.path.join(
                    "models", "face_recognition.caffemodel"
                )
                prototxt_path = recognition_model_path.replace(".caffemodel", ".prototxt")
                if not os.path.exists(recognition_model_path) or not os.path.exists(
                    prototxt_path
                ):
                    raise FileNotFoundError("OpenCV face recognition model files not found. Searched for resnet and generic versions.")
            self.model = cv2.dnn.readNetFromCaffe(prototxt_path, recognition_model_path)

        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.face_database = {} # Initialize an empty dictionary for storing known faces

    # Add a method to directly add pre-computed embeddings to the database
    def add_known_embedding(self, person_id: str, embedding: np.ndarray):
        """Adds a pre-computed embedding to the face database."""
        if embedding is not None and embedding.size > 0:
            # Ensure it's normalized, though known embeddings should already be
            norm = np.linalg.norm(embedding)
            if norm > 1e-10:
                self.face_database[person_id] = embedding / norm
            else: # Should not happen for pre-generated known embeddings
                self.face_database[person_id] = embedding 
            # print(f"Added pre-computed embedding for {person_id} to database. Shape: {self.face_database[person_id].shape}")
        else:
            print(f"Warning: Attempted to add invalid pre-computed embedding for {person_id}")


    def add_face(self, image: np.ndarray, person_id: str):
        """Detects a face in the image, computes its embedding, and stores it."""
        detected_faces_data = self.face_detector.detect_faces(image)
        if not detected_faces_data:
            # It's better to log or print a warning than raise an error if no face is found,
            # as this might be expected in some scenarios.
            print(f"Warning: No face detected in the image provided for person_id: {person_id}")
            return # Or handle as per application requirements

        # Assuming we take the first detected face if multiple are present
        first_face_data = detected_faces_data[0]
        
        # Standardize bbox extraction
        if hasattr(first_face_data, 'bbox') and first_face_data.bbox is not None:
            # InsightFaceObject often has bbox as a numpy array
            bbox_to_extract = first_face_data.bbox.astype(int).tolist()
        elif isinstance(first_face_data, (list, np.ndarray)) and len(first_face_data) >= 4:
            # Standard list [x1, y1, x2, y2] or similar numpy array
            bbox_to_extract = np.array(first_face_data[:4]).astype(int).tolist()
        else:
            print(f"Warning: Unexpected face data type or format for person_id {person_id}: {type(first_face_data)}")
            return

        face_crop = self.face_detector.extract_face(image, bbox_to_extract)
        if face_crop is None:
            print(f"Warning: Failed to extract face crop for person_id {person_id} using bbox {bbox_to_extract}")
            return
            
        face_embedding = self._get_embedding(face_crop)
        if face_embedding is None or np.all(face_embedding == 0): # Check if embedding is valid
            print(f"Warning: Failed to compute a valid embedding for person_id {person_id}")
            return
            
        self.face_database[person_id] = face_embedding
        print(f"Successfully added face for {person_id} to database.")

    def identify_face(self, image: np.ndarray, detected_face_embeddings: Optional[List[np.ndarray]] = None) -> List[Dict]:
        """
        Identifies known faces in an image.
        If detected_face_embeddings are provided, uses them. Otherwise, detects faces and computes embeddings.
        """
        results = []
        
        detected_faces_data = self.face_detector.detect_faces(image) # Still need bboxes

        if not detected_faces_data:
            return results

        if detected_face_embeddings is not None and len(detected_face_embeddings) != len(detected_faces_data):
            print("Warning: Mismatch between number of detected_faces_data and provided detected_face_embeddings. Re-computing embeddings.")
            detected_face_embeddings = None # Force re-computation

        if not self.face_database:
            print("Warning: Face database is empty. Cannot identify faces.")
            # Return empty results or results with no person_id for each detected face
            for face_data_item in detected_faces_data:
                original_bbox = None
                if hasattr(face_data_item, 'bbox') and face_data_item.bbox is not None:
                    original_bbox = face_data_item.bbox
                elif isinstance(face_data_item, (list, np.ndarray)) and len(face_data_item) >= 4:
                    original_bbox = face_data_item[:4]
                
                if original_bbox is not None:
                    results.append({
                        "bbox": original_bbox,
                        "person_id": None,
                        "confidence": 0.0,
                    })
            return results

        for idx, face_data_item in enumerate(detected_faces_data): # Added enumerate here
            original_bbox = None
            bbox_to_extract = None

            if hasattr(face_data_item, 'bbox') and face_data_item.bbox is not None:
                bbox_to_extract = face_data_item.bbox.astype(int).tolist()
                original_bbox = face_data_item.bbox
            elif isinstance(face_data_item, (list, np.ndarray)) and len(face_data_item) >= 4:
                bbox_to_extract = np.array(face_data_item[:4]).astype(int).tolist()
                original_bbox = face_data_item[:4]
            else:
                print(f"Skipping unexpected face data type during identification: {type(face_data_item)}")
                continue
            
            embedding_to_use = None
            if detected_face_embeddings is not None:
                embedding_to_use = detected_face_embeddings[idx]
            else:
                face_crop = self.face_detector.extract_face(image, bbox_to_extract)
                if face_crop is None:
                    print(f"Failed to extract face for bbox {bbox_to_extract} during identification (re-computation)")
                    results.append({"bbox": original_bbox, "person_id": None, "confidence": 0.0})
                    continue
                embedding_to_use = self._get_embedding(face_crop)

            if embedding_to_use is None or np.all(embedding_to_use == 0):
                print(f"Failed to compute/use a valid embedding for bbox {bbox_to_extract} during identification")
                results.append({"bbox": original_bbox,
                    "person_id": None,
                    "confidence": 0.0,
                })
                continue

            best_match = None
            best_similarity = -1.0

            for person_id, stored_embedding in self.face_database.items():
                similarity = self._compute_similarity(embedding_to_use, stored_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = person_id
            
            current_result = {
                "bbox": original_bbox,
                "person_id": best_match if best_similarity >= self.similarity_threshold else None,
                "confidence": float(best_similarity), # Ensure confidence is float
            }
            results.append(current_result)

        return results

    def _get_embedding(self, face_image: np.ndarray) -> np.ndarray:
        # print(f"Debug: ENTERING _get_embedding. Initial face_image shape: {face_image.shape if face_image is not None else 'None'}, dtype: {face_image.dtype if face_image is not None else 'None'}")
        try:
            if face_image is None or face_image.size == 0:
                # print("Debug: _get_embedding - face_image is None or empty at start.")
                return np.zeros(self.embedding_size, dtype=np.float32)

            if face_image.ndim == 2: # Grayscale image
                face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)
            
            # Ensure correct number of channels if not grayscale
            if face_image.ndim != 3 or face_image.shape[2] != 3:
                # print(f"Debug: _get_embedding - Invalid image shape {face_image.shape} for embedding. Expected 3 channels.")
                return np.zeros(self.embedding_size, dtype=np.float32)

            # Debug: Print info about the face_image before processing
            # print(f"Debug: _get_embedding - face_image received (before resize) - shape: {face_image.shape}, dtype: {face_image.dtype}, min: {np.min(face_image):.2f}, max: {np.max(face_image):.2f}")

            face_image = cv2.resize(face_image, (112, 112))
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB) # Model expects RGB
            face_image = face_image.astype(np.float32) / 255.0

            if self.use_arcface:
                # Normalize using class mean and std for ArcFace
                face_image = (face_image - self.mean) / self.std
                face_image = np.transpose(face_image, (2, 0, 1)) # HWC to CHW
                face_image = np.expand_dims(face_image, axis=0) # Add batch dimension CHW to NCHW

                outputs = self.session.run(
                    [self.output_name], {self.input_name: face_image}
                )
                embedding = outputs[0][0] # Output is usually [[embedding_vector]]
                # print(f"Debug: _get_embedding - Raw ONNX output embedding - shape: {embedding.shape}, min: {np.min(embedding):.4f}, max: {np.max(embedding):.4f}, norm: {np.linalg.norm(embedding):.4f}")
            else:
                # Fallback to OpenCV DNN
                # Define mean and std for OpenCV DNN if not already class members, or use specific ones
                mean_cv = np.array([0.485, 0.456, 0.406], dtype=np.float32) 
                std_cv = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                face_image = (face_image - mean_cv) / std_cv
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)

                self.model.setInput(face_image)
                embedding = self.model.forward().flatten()
                # print(f"Debug: _get_embedding - Raw OpenCV DNN output embedding - shape: {embedding.shape}, min: {np.min(embedding):.4f}, max: {np.max(embedding):.4f}, norm: {np.linalg.norm(embedding):.4f}")

            norm = np.linalg.norm(embedding)
            # print(f"Debug: _get_embedding - Calculated norm of raw embedding: {norm:.4f}")
            if norm < 1e-10: # Check for zero norm to avoid division by zero
                # print(f"Debug: _get_embedding - Embedding norm is close to zero ({norm:.4e}). Returning zero vector.")
                return np.zeros(self.embedding_size, dtype=np.float32) # Return zero vector

            normalized_embedding = embedding / norm
            # print(f"Debug: _get_embedding - Normalized embedding norm: {np.linalg.norm(normalized_embedding):.4f}")
            return normalized_embedding

        except Exception as e:
            print(f"Error in _get_embedding: {e}. Returning zero embedding.")
            return np.zeros(self.embedding_size, dtype=np.float32)

    def _compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        # Ensure embeddings are 1D numpy arrays
        if not isinstance(embedding1, np.ndarray) or not isinstance(embedding2, np.ndarray):
            # print("Warning: Non-numpy array passed to _compute_similarity.")
            return 0.0
            
        embedding1 = embedding1.flatten()
        embedding2 = embedding2.flatten()

        if embedding1.shape != embedding2.shape:
            # print(f"Warning: Embedding shapes mismatch: {embedding1.shape} vs {embedding2.shape}")
            return 0.0

        # Compute cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 < 1e-10 or norm2 < 1e-10: # Check for zero norms
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        # Clip similarity to [0, 1] range as sometimes it can be slightly outside due to precision
        return float(np.clip(similarity, 0.0, 1.0))

    def detect_and_embed(self, image: np.ndarray) -> List[np.ndarray]:
        """Detect faces and compute embeddings for each."""
        detected_faces_data = self.face_detector.detect_faces(image)
        embeddings = []

        if not detected_faces_data:
            # print("No faces detected in detect_and_embed.")
            return embeddings # Return empty list if no faces detected

        for face_data_item in detected_faces_data:
            bbox_to_extract = None
            if hasattr(face_data_item, 'bbox') and face_data_item.bbox is not None:
                bbox_to_extract = face_data_item.bbox.astype(int).tolist()
            elif isinstance(face_data_item, (list, np.ndarray)) and len(face_data_item) >= 4:
                bbox_to_extract = np.array(face_data_item[:4]).astype(int).tolist()
            else:
                # print(f"Skipping unexpected face data type for embedding: {type(face_data_item)}")
                embeddings.append(np.zeros(self.embedding_size, dtype=np.float32)) # Add placeholder
                continue
            
            # Add padding to the extracted face crop
            face_crop = self.face_detector.extract_face(image, bbox_to_extract, padding=0.1)
            
            current_embedding_to_add = None
            if face_crop is None:
                # print(f"Debug: detect_and_embed - face_crop is None for bbox {bbox_to_extract}.")
                current_embedding_to_add = np.zeros(self.embedding_size, dtype=np.float32)
            else:
                # print(f"Debug: detect_and_embed - face_crop shape: {face_crop.shape}, dtype: {face_crop.dtype}. Passing to _get_embedding.")
                current_embedding_to_add = self._get_embedding(face_crop)
            
            embeddings.append(current_embedding_to_add)
            
        return embeddings
