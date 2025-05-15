import os
import cv2
import numpy as np
import onnxruntime
from typing import List, Dict
from src.core.detector import FaceDetector  # Corrected import path


class FaceRecognizer:
    def __init__(
        self,
        face_detector: FaceDetector,
        similarity_threshold: float = 0.35,  # Lower from 0.6 to start
        use_arcface: bool = True,
    ):
        self.use_arcface = use_arcface
        if self.use_arcface:
            # Initialize SFace ONNX model as a primary option (since ArcFace download failed)
            model_path = os.path.join("models", "face_recognition_sface.onnx")
            if not os.path.exists(model_path):
                # Fallback to trying arcface_r50 if sface is also not found for some reason
                model_path = os.path.join("models", "arcface_r50.onnx")
                if not os.path.exists(model_path):
                    raise FileNotFoundError(
                        f"Neither SFace nor ArcFace model found at {model_path} or models/face_recognition_sface.onnx. Please download them first."
                    )
                else:
                    print("Using arcface_r50.onnx as SFace was not found.")
            else:
                print(f"Using SFace model: {model_path}")

            if not os.path.exists(model_path):  # Double check after potential fallback
                raise FileNotFoundError(
                    f"Face recognition model not found at {model_path}. Please download it first."
                )

            self.session = onnxruntime.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Determine embedding size from model's output shape
            # Output shape is typically [None, dim] or [batch_size, dim]
            # We need the second dimension.
            model_output_shape = self.session.get_outputs()[0].shape
            if len(model_output_shape) == 2 and isinstance(model_output_shape[1], int):
                self.embedding_size = model_output_shape[1]
            else:
                # Fallback or raise error if shape is unexpected
                # For SFace (128) or ArcFace (512)
                print(f"Warning: Could not reliably determine embedding size from model output shape {model_output_shape}. Defaulting to 512. Check model compatibility if issues arise.")
                self.embedding_size = 512 # Default, but SFace is likely 128. This might need adjustment based on which model is primary.
                if "sface" in model_path.lower(): # A simple check based on common model name
                    self.embedding_size = 128
                    print(f"Adjusted embedding size to 128 based on SFace model name.")


            # Mean and std for normalization, ensure float32
            self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        else:
            # Fallback to OpenCV DNN (typically 128-dim)
            self.embedding_size = 128 # OpenFace models used by OpenCV DNN are often 128-dim
            recognition_model_path = os.path.join(
                "models", "face_recognition.caffemodel"
            )
            prototxt_path = recognition_model_path.replace(".caffemodel", ".prototxt")
            if not os.path.exists(recognition_model_path) or not os.path.exists(
                prototxt_path
            ):
                raise FileNotFoundError("OpenCV face recognition model files not found")
            self.model = cv2.dnn.readNetFromCaffe(prototxt_path, recognition_model_path)

        self.face_detector = face_detector
        self.similarity_threshold = similarity_threshold
        self.face_database = {}

    def add_face(self, image: np.ndarray, person_id: str):
        detected_faces_data = self.face_detector.detect_faces(image)
        if not detected_faces_data:
            raise ValueError("No face detected in the image")

        # Ensure the bbox passed to extract_face is a list/tuple
        first_face_data = detected_faces_data[0]
        if hasattr(first_face_data, 'bbox'): # InsightFaceObject
            bbox_to_extract = first_face_data.bbox.astype(int).tolist()
        elif isinstance(first_face_data, list): # Bbox list
            bbox_to_extract = first_face_data
        else:
            raise TypeError(f"Unexpected face data type from detector: {type(first_face_data)}")

        face_crop = self.face_detector.extract_face(image, bbox_to_extract)
        if face_crop is None:
            # This can happen if extraction fails post-detection (e.g. bbox is at edge and padding makes it invalid)
            raise ValueError("Failed to extract face crop from detected face.")
            
        face_embedding = self._get_embedding(face_crop)
        self.face_database[person_id] = face_embedding

    def identify_face(self, image: np.ndarray) -> List[Dict]:
        detected_faces_data = self.face_detector.detect_faces(image)
        results = []

        for face_data_item in detected_faces_data:
            # Ensure the bbox passed to extract_face is a list/tuple
            if hasattr(face_data_item, 'bbox'): # InsightFaceObject
                bbox_to_extract = face_data_item.bbox.astype(int).tolist()
                original_bbox_for_results = face_data_item.bbox # Keep original for reporting if needed, or use list
            elif isinstance(face_data_item, list): # Bbox list
                bbox_to_extract = face_data_item
                original_bbox_for_results = face_data_item
            else:
                print(f"Skipping unexpected face data type in identify_face: {type(face_data_item)}")
                continue

            face_crop = self.face_detector.extract_face(image, bbox_to_extract)
            if face_crop is None:
                # If extraction fails for a specific detected face, skip it or handle as unknown
                print(f"Warning: Failed to extract face for bbox {bbox_to_extract}, skipping this face in identification.")
                # Optionally, append a result indicating failure for this bbox
                # results.append({"bbox": original_bbox_for_results, "person_id": None, "confidence": -1, "error": "Extraction failed"})
                continue
                
            embedding = self._get_embedding(face_crop)

            # Find best match
            best_match = None
            best_similarity = -1

            for person_id, stored_embedding in self.face_database.items():
                similarity = self._compute_similarity(embedding, stored_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = person_id

            results.append(
                {
                    "bbox": original_bbox_for_results, # Report the bbox that was initially detected
                    "person_id": best_match
                    if best_similarity > self.similarity_threshold
                    else None,
                    "confidence": best_similarity,
                }
            )

        return results

    def _get_embedding(self, face_image: np.ndarray) -> np.ndarray:
        try:
            # Preprocess face image
            if face_image.ndim == 2:
                face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)  # pylint: disable=no-member

            # Resize to model's expected size
            face_image = cv2.resize(face_image, (112, 112))  # pylint: disable=no-member

            # Convert to RGB and normalize
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)  # pylint: disable=no-member
            face_image = face_image.astype(np.float32) / 255.0

            if self.use_arcface:
                # Standardize using ArcFace normalization
                face_image = (face_image - self.mean) / self.std

                # HWC to NCHW format
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)

                # Get embedding using ONNX model
                outputs = self.session.run(
                    [self.output_name], {self.input_name: face_image}
                )
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
                rng = np.random.RandomState(42)  # pylint: disable=no-member # Fixed seed for consistency
                embedding = rng.randn(self.embedding_size)  # Use dynamic embedding size
                embedding = embedding / np.linalg.norm(embedding)
                return embedding

            embedding = embedding / norm
            return embedding

        except Exception as e:
            print(f"Error in _get_embedding: {str(e)}")
            # Return random unit vector on error
            rng = np.random.RandomState(42)  # pylint: disable=no-member
            embedding = rng.randn(self.embedding_size)  # Use dynamic embedding size
            return embedding / np.linalg.norm(embedding)

    def _compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
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
                "source",
                "photo",
                "contestants",
                f"{nickname}_embedding.npy",
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
