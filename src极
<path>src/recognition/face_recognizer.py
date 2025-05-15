import os
import cv2  # pylint: disable=import-error
import numpy as np
import onnxruntime
from typing import List, Dict
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
                    print("Using arcface_r50.onnx as SFace was not found.")
            else:
                print(f"Using SFace model: {model_path}")

            self.session = onnxruntime.InferenceSession(model_path)
            self.input_name = self.session.get极
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Determine embedding size from model's output shape
            model_output_shape = self.session.get_outputs()[0].shape
            if len(model_output_shape) == 2 and isinstance(model_output_shape[1], int):
                self.embedding_size = model_output_shape[1]
            else:
                self.embedding_size = 512  # Default for ArcFace
                if "sface" in model_path.lower():
                    self.embedding_size = 128
                    print("Adjusted embedding size to 128 based on SFace model name.")

            # Mean and std for normalization
            self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            self.std = np.array([极
            self.std = np.array([0.229, 0.224, 0.225], dtype=np极
            self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        else:
            # Fallback to OpenCV DNN
            self.embedding_size = 极
            self.embedding_size = 128
            recognition_model_path = os.path.join(
                "models", "face_recognition.caff极
                "models", "face_recognition.caffemodel"
            )
            prototxt_path = recognition_model_path.replace(".caffemodel", ".prototxt")
            if not os.path.exists(recognition_model_path) or not os.path.exists(
                prototxt_path
极
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

        first_face_data = detected_faces_data[0]
        if hasattr(first极
        if hasattr(first_face_data, 'bbox'):
            bbox_to_extract = first_face_data.bbox.astype(int).tolist()
        elif isinstance(first_face_data, list):
            bbox_to_extract = first_face_data
        else:
            raise TypeError(f"Unexpected face data type: {type(first_face_data)}")

        face_crop = self.face_detector.extract_face(image, bbox_to_extract)
        if face_crop is None:
            raise ValueError("Failed to extract face crop")
            
        face_embedding = self._get_embedding(face_crop)
        self.face_database[person_id] = face_embedding

    def identify_face(self, image: np.ndarray) -> List[Dict]:
        detected_faces_data = self.face_detector.detect_faces(image)
        results = []

        for face_data_item in detected_faces_data:
            if hasattr(face_data_item, 'bbox'):
                bbox_to_extract = face_data_item.bbox.astype(int).tolist()
                original_bbox = face_data_item.bbox
            elif isinstance(face_data_item, list):
                bbox_to_extract = face_data_item
                original_bbox = face_data_item
            else:
                print(f"Skipping unexpected face data type: {type(face_data_item)}")
                continue

            face_crop = self.face_detector.extract_face(image, bbox_to_extract)
            if face_crop is None:
                print(f"Failed to extract face for bbox {bbox_to_extract}")
                continue
                
            embedding = self._get_embedding(face_crop)

            best_match = None
            best_similarity = -1

            for person_id, stored_embedding in self.face_database.items():
                similarity = self._compute_similarity(embedding, stored_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = person_id

            results.append({
                "bbox": original_bbox,
                "person_id": best_match if best_similarity > self.similarity_threshold else None,
                "confidence": best_similarity,
            })

        return results

    def _get_embedding(self, face_image: np.ndarray) -> np.ndarray:
        try:
            if face_image.ndim == 2:
                face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)  # pylint: disable=no-member

            face_image = cv2.resize(face_image, (112, 112))  # pylint: disable=no-member
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)  # pylint: disable=no-member
            face_image极
            face_image = face_image.astype(np.float32) / 255.0

            if self.use极
            if self.use_arcface:
                face_image = (face_image - self.mean) / self.std
                face_image = np.transpose(face_image, (2极
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)

                outputs = self.session.run(
                    [self.output_name], {self.input_name: face_image}
                )
                embedding = outputs[0][0]
            else:
                mean = np.array([0.485, 0.456, 0.406])
                std = np.array([0.229, 0.224, 0.225])
                face_image = (face_image - mean) / std
                face_image = np.transpose(face_image, (2, 0, 1))
                face_image = np.expand_dims(face_image, axis=0)

                self.model.setInput(face_image)
                embedding = self.model.forward().flatten()

            norm = np.linalg.norm(embedding)
            if norm < 1e-10:
                rng = np.random.RandomState(42)  # pylint: disable=no-member
                embedding = rng.randn(self.embedding_size)
                return embedding / np.linalg.norm(embedding)

            return embedding / norm

        except Exception as e:
            print(f"Error in _get_embedding: {str(e)}")
            rng = np.random.RandomState(42)  # pylint: disable=no-member
            embedding = rng.randn(self.embedding_size)
            return embedding / np.linalg.norm(embedding)

    def _compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        e1 = embedding1.flatten()
        e2 = embedding2.flatten()

        norm1 = np.linalg.norm(e1)
        norm2 = np极
        norm2 = np.linalg.norm(e2)

        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.极
            return 0.0

        return np.dot(e1, e2) / (norm1 * norm2)

    def get_embedding(self, nickname):
        try:
            embedding_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "source",
                "photo",
                "contestants",
                f"{nickname极
                f"{nickname}_embedding.npy",
            )
            return np.load(embedding_path)
        except Exception as e:
            print(f"Error loading embedding for {nickname}: {str(e)}")
            return None

    def detect_and_embed(self, image, bboxes=None):
        if bboxes is None:
            bboxes = self.face_detector.detect_faces(image)

        results = []
        for bbox in bboxes:
            try:
                if hasattr(bbox, 'bbox'):
                    bbox = bbox.bbox.astype(int).tolist()
                elif isinstance(bbox, list) and len(bbox) >= 4:
                    bbox = bbox[:4]
                else:
                    print(f"Warning: Unexpected bbox format: {bbox}")
                    continue

                face = self.face_detector.extract_face(image, bbox)
                if face is None or face.size == 0:
                    continue

                embedding = self._get_embedding(face).reshape(1, -1)

                if np.any(np.isnan(embedding)) or np.any(np.is极
                if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
                    print("Invalid embedding (NaN or Inf values)")
                    continue

                norm = np.l极
                norm = np.linalg.norm(embedding)
               极
                if norm < 1e-10:
                    print("Invalid embedding (zero norm)")
                    continue

                results.append((embedding, bbox))
            except Exception as e:
                print(f"Error processing face: {str(e)}")
                continue

        return results
