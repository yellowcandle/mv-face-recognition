"""
Face detection module using InsightFace.
"""

import json
import logging
from typing import List, Optional
import cv2
import numpy as np
from insightface.app import FaceAnalysis
from src.core.hardware_acceleration import get_hardware_accelerator

logger = logging.getLogger(__name__)


class FaceDetector:
    """Face detection using InsightFace models."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize face detector with configuration."""
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.detection_threshold = self.config["face_detection"]["detection_threshold"]
        self.input_size = tuple(self.config["face_detection"]["input_size"])
        self.model_name = self.config["face_detection"]["model_name"]

        # Initialize hardware acceleration
        self.accelerator = get_hardware_accelerator()
        self.accelerator.optimize_opencv_threads()

        # Initialize InsightFace
        self.app = None
        self.initialize_model()

    def initialize_model(self):
        """Initialize the InsightFace model with hardware acceleration."""
        try:
            # Get optimal providers and context
            providers = self.accelerator.get_insightface_providers()
            ctx_id = self.accelerator.get_optimal_ctx_id()
            
            logger.info(f"Initializing {self.model_name} with providers: {providers}")
            
            self.app = FaceAnalysis(
                name=self.model_name,
                providers=providers
            )
            
            self.app.prepare(ctx_id=ctx_id, det_size=self.input_size)
            
            # Log hardware acceleration status
            active_provider = providers[0] if providers else "Unknown"
            if "CUDA" in active_provider:
                logger.info(f"🚀 Face detection model loaded with CUDA acceleration")
            elif "CoreML" in active_provider:
                logger.info(f"🍎 Face detection model loaded with Apple Silicon acceleration")
            else:
                logger.info(f"💻 Face detection model loaded with CPU processing")
                
        except Exception as e:
            logger.error(f"Failed to initialize face detection model: {e}")
            # Fallback to CPU only
            try:
                logger.warning("Falling back to CPU-only processing")
                self.app = FaceAnalysis(
                    name=self.model_name,
                    providers=["CPUExecutionProvider"]
                )
                self.app.prepare(ctx_id=-1, det_size=self.input_size)
                logger.info("✅ Face detection model loaded with CPU fallback")
            except Exception as e2:
                logger.error(f"CPU fallback also failed: {e2}")
                raise

    def detect_faces(self, image: np.ndarray) -> List[dict]:
        """
        Detect faces in an image.

        Args:
            image: Input image as numpy array (BGR format)

        Returns:
            List of face dictionaries with bbox, landmarks, and embedding
        """
        if self.app is None:
            logger.error("Face detection model not initialized")
            return []

        try:
            # Detect faces
            faces = self.app.get(image)

            # Filter by detection threshold
            filtered_faces = []
            for face in faces:
                if face.det_score >= self.detection_threshold:
                    # Normalize embedding to unit vector for consistent similarity calculation
                    embedding = face.embedding if hasattr(face, "embedding") else None
                    if embedding is not None:
                        # Normalize to unit vector (L2 normalization)
                        embedding_norm = np.linalg.norm(embedding)
                        if embedding_norm > 0:
                            embedding = embedding / embedding_norm
                    
                    face_dict = {
                        "bbox": face.bbox.astype(int).tolist(),  # [x1, y1, x2, y2]
                        "confidence": float(face.det_score),
                        "landmarks": face.kps.astype(int).tolist()
                        if hasattr(face, "kps")
                        else None,
                        "embedding": embedding,
                    }
                    filtered_faces.append(face_dict)

            logger.debug(
                f"Detected {len(filtered_faces)} faces (from {len(faces)} total)"
            )
            return filtered_faces

        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []

    def extract_face_region(
        self, image: np.ndarray, bbox: List[int], margin: float = 0.2
    ) -> np.ndarray:
        """
        Extract face region from image with optional margin.

        Args:
            image: Input image
            bbox: Face bounding box [x1, y1, x2, y2]
            margin: Margin to add around face (as fraction of face size)

        Returns:
            Cropped face image
        """
        h, w = image.shape[:2]
        x1, y1, x2, y2 = bbox

        # Calculate face dimensions
        face_w = x2 - x1
        face_h = y2 - y1

        # Add margin
        margin_w = int(face_w * margin)
        margin_h = int(face_h * margin)

        # Calculate new coordinates with margin
        new_x1 = max(0, x1 - margin_w)
        new_y1 = max(0, y1 - margin_h)
        new_x2 = min(w, x2 + margin_w)
        new_y2 = min(h, y2 + margin_h)

        # Extract face region
        face_region = image[new_y1:new_y2, new_x1:new_x2]

        return face_region

    def get_face_embedding(
        self, image: np.ndarray, bbox: List[int] = None
    ) -> Optional[np.ndarray]:
        """
        Get face embedding for a specific face or the whole image.

        Args:
            image: Input image
            bbox: Optional face bounding box. If None, detect faces first.

        Returns:
            Face embedding as numpy array, or None if no face found
        """
        if bbox is None:
            # Detect faces first
            faces = self.detect_faces(image)
            if not faces:
                return None
            # Use the first face
            face = faces[0]
            return face["embedding"]
        else:
            # Use provided bounding box to extract face
            face_region = self.extract_face_region(image, bbox)
            faces = self.detect_faces(face_region)
            if faces:
                return faces[0]["embedding"]
            return None

    def draw_face_annotations(
        self,
        image: np.ndarray,
        faces: List[dict],
        names: List[str] = None,
        confidences: List[float] = None,
    ) -> np.ndarray:
        """
        Draw face annotations on image.

        Args:
            image: Input image
            faces: List of face dictionaries from detect_faces()
            names: Optional list of names for each face
            confidences: Optional list of recognition confidences

        Returns:
            Annotated image
        """
        annotated = image.copy()

        for i, face in enumerate(faces):
            bbox = face["bbox"]
            x1, y1, x2, y2 = bbox

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw detection confidence
            det_conf = face["confidence"]
            conf_text = f"Det: {det_conf:.2f}"
            cv2.putText(
                annotated,
                conf_text,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )

            # Draw name and recognition confidence if provided
            if names and i < len(names):
                name = names[i]
                rec_conf = (
                    confidences[i] if confidences and i < len(confidences) else 0.0
                )

                name_text = f"{name} ({rec_conf:.2f})"
                text_size = cv2.getTextSize(
                    name_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                )[0]

                # Draw background for text
                cv2.rectangle(
                    annotated,
                    (x1, y2),
                    (x1 + text_size[0], y2 + text_size[1] + 10),
                    (0, 255, 0),
                    -1,
                )

                # Draw text
                cv2.putText(
                    annotated,
                    name_text,
                    (x1, y2 + text_size[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 0),
                    2,
                )

            # Draw landmarks if available
            if face.get("landmarks"):
                landmarks = np.array(face["landmarks"])
                for point in landmarks:
                    cv2.circle(annotated, tuple(point), 2, (255, 0, 0), -1)

        return annotated

    def detect_faces_batch(self, images: List[np.ndarray]) -> List[List[dict]]:
        """
        Detect faces in multiple images with optimized batching.

        Args:
            images: List of input images as numpy arrays

        Returns:
            List of face detection results for each image
        """
        if not images:
            return []

        batch_size = self.accelerator.get_optimal_batch_size()
        results = []

        # Process in optimal batches
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            batch_results = []

            for image in batch:
                faces = self.detect_faces(image)
                batch_results.append(faces)

            results.extend(batch_results)

        return results

    def get_hardware_info(self) -> dict:
        """Get hardware acceleration information."""
        return {
            'providers': self.accelerator.get_insightface_providers(),
            'batch_size': self.accelerator.get_optimal_batch_size(),
            'ctx_id': self.accelerator.get_optimal_ctx_id(),
            'system_info': self.accelerator.system_info,
            'apple_silicon': self.accelerator._is_apple_silicon(),
            'cuda_available': self.accelerator._is_cuda_available()
        }

    def print_hardware_info(self):
        """Print hardware acceleration information."""
        self.accelerator.print_hardware_info()


def test_face_detector():
    """Test the face detector with a sample image."""
    import os

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Initialize detector
    detector = FaceDetector()
    
    # Print hardware info
    detector.print_hardware_info()

    # Test with a sample image from contestants
    test_image_path = "source/photo/contestants/1/1-1.jpg"

    if os.path.exists(test_image_path):
        # Load image
        image = cv2.imread(test_image_path)

        if image is not None:
            # Detect faces
            faces = detector.detect_faces(image)
            print(f"Detected {len(faces)} faces")

            for i, face in enumerate(faces):
                print(
                    f"Face {i + 1}: bbox={face['bbox']}, confidence={face['confidence']:.3f}"
                )
                if face["embedding"] is not None:
                    print(f"  Embedding shape: {face['embedding'].shape}")

            # Draw annotations and save result
            annotated = detector.draw_face_annotations(image, faces)
            cv2.imwrite("test_detection_result.jpg", annotated)
            print("Test result saved as test_detection_result.jpg")
        else:
            print(f"Could not load image: {test_image_path}")
    else:
        print(f"Test image not found: {test_image_path}")


if __name__ == "__main__":
    test_face_detector()
