import os
import cv2
import numpy as np
import time
from pathlib import Path
from typing import List, Dict, Optional, Union
import concurrent.futures

from src.detection.optimized_detector import OptimizedFaceDetector
from src.recognition.optimized_recognizer import OptimizedFaceRecognizer
from src.utils.image_utils import (
    load_image,
    save_image,
    enhance_test_image,
    create_composite_image,
    get_all_test_images,
)


class TestImageOptimizer:
    """
    Specialized class for optimizing test image processing
    using advanced caching and parallel processing.
    """

    def __init__(
        self,
        detector: OptimizedFaceDetector = None,
        recognizer: OptimizedFaceRecognizer = None,
        cache_dir: Optional[str] = None,
        max_workers: int = 4,
    ):
        """
        Initialize the test image optimizer.

        Args:
            detector: Face detector instance (created if None)
            recognizer: Face recognizer instance (created if None)
            cache_dir: Directory for caching (default is project_root/cache)
            max_workers: Maximum number of worker threads
        """
        self.project_root = Path(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        self.test_dir = self.project_root / "source" / "images" / "test"

        # Set up cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = self.project_root / "cache"
        self.cache_dir.mkdir(exist_ok=True, parents=True)

        # Create components if not provided
        if detector is None:
            self.detector = OptimizedFaceDetector(
                confidence_threshold=0.3,
                skip_frames=0,
                tracking_duration=0,
                model_size=(320, 320),
                max_workers=max_workers,
            )
        else:
            self.detector = detector

        if recognizer is None:
            self.recognizer = OptimizedFaceRecognizer(
                face_detector=self.detector,
                similarity_threshold=0.6,
                use_batch_processing=True,
                use_quantized_model=True,
                enable_metadata_cache=True,
                cache_dir=str(self.cache_dir),
                max_workers=max_workers,
            )
        else:
            self.recognizer = recognizer

        self.max_workers = max_workers

        # Statistics
        self.processed_images = 0
        self.processing_time = 0

    def preprocess_all_test_images(self) -> int:
        """
        Preprocess all test images for faster processing.

        Returns:
            int: Number of images preprocessed
        """
        start_time = time.time()

        # Get all test images
        test_files = get_all_test_images()
        if not test_files:
            print("No test images found")
            return 0

        print(f"Preprocessing {len(test_files)} test images...")

        # Process images in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            futures = [
                executor.submit(self._preprocess_single_image, img_path)
                for img_path in test_files
            ]

            # Wait for all to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                    self.processed_images += 1
                except Exception as e:
                    print(f"Error in preprocessing: {str(e)}")

        self.processing_time = time.time() - start_time
        print(
            f"Preprocessed {self.processed_images} test images in {self.processing_time:.2f} seconds"
        )

        # Also optimize the recognizer for test images
        self.recognizer.optimize_for_test_images()

        return self.processed_images

    def _preprocess_single_image(self, img_path: Path) -> bool:
        """Process a single test image"""
        try:
            # Load and enhance the image
            img = load_image(img_path)
            if img is None:
                print(f"Failed to load image: {img_path}")
                return False

            # Enhance the image
            enhanced = enhance_test_image(img)

            # Detect faces
            face_bboxes = self.detector.detect_faces(
                enhanced, force_detection=True, use_cache=True
            )

            # Cache the detection results
            img_id = f"test_{img_path.stem}"

            # Store in metadata cache
            if hasattr(self.recognizer, "metadata_cache"):
                if img_id not in self.recognizer.metadata_cache:
                    self.recognizer.metadata_cache[img_id] = {}
                self.recognizer.metadata_cache[img_id]["faces"] = face_bboxes
                self.recognizer.metadata_cache[img_id]["path"] = str(img_path)

                # If the image is original.jpeg, precompute embeddings
                if img_path.name == "original.jpeg":
                    # Extract face regions
                    for i, bbox in enumerate(face_bboxes):
                        face = self.detector.extract_face(enhanced, bbox, padding=0.1)
                        if face is not None:
                            # Compute embedding
                            preprocessed = self.recognizer.preprocess_face(face)
                            embedding = self.recognizer.compute_embedding(preprocessed)

                            # Save embedding
                            face_id = f"{img_id}_face_{i}"
                            self.recognizer.save_embedding(
                                face_id, embedding, save_to_disk=True
                            )

                # Save the updated cache
                if hasattr(self.recognizer, "_save_metadata_cache"):
                    self.recognizer._save_metadata_cache()

            print(
                f"Preprocessed test image: {img_path.name} - found {len(face_bboxes)} faces"
            )
            return True

        except Exception as e:
            print(f"Error preprocessing {img_path}: {str(e)}")
            return False

    def process_test_images(
        self, output_dir: Optional[Union[str, Path]] = None
    ) -> List[Dict]:
        """
        Process all test images with recognition.

        Args:
            output_dir: Optional directory to save annotated images

        Returns:
            list: List of recognition results per image
        """
        start_time = time.time()

        # Ensure output directory exists
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True, parents=True)

        # Get all test images
        test_files = get_all_test_images()
        if not test_files:
            print("No test images found")
            return []

        print(f"Processing {len(test_files)} test images...")

        # First prepare known embeddings
        known_embeddings = self._prepare_known_embeddings()

        # Process images
        all_results = []

        # Process images in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            futures = {
                executor.submit(
                    self._process_single_test_image,
                    img_path,
                    known_embeddings,
                    output_dir,
                ): img_path
                for img_path in test_files
            }

            # Wait for all to complete
            for future in concurrent.futures.as_completed(futures):
                img_path = futures[future]
                try:
                    result = future.result()
                    if result:
                        all_results.append({"path": str(img_path), "result": result})
                        self.processed_images += 1
                except Exception as e:
                    print(f"Error processing {img_path}: {str(e)}")

        self.processing_time = time.time() - start_time
        print(
            f"Processed {self.processed_images} test images in {self.processing_time:.2f} seconds"
        )

        return all_results

    def _process_single_test_image(
        self, img_path: Path, known_embeddings: Dict, output_dir: Optional[Path]
    ) -> List[Dict]:
        """Process a single test image with recognition"""
        try:
            # Load the image
            img = load_image(img_path)
            if img is None:
                return []

            # Identify faces
            results = self.recognizer.identify_faces(img, known_embeddings)

            # If output directory provided, save annotated image
            if output_dir and results:
                # Create annotated image
                annotated = self._create_annotated_image(img, results)

                # Save to output directory
                output_path = output_dir / f"{img_path.stem}_annotated{img_path.suffix}"
                save_image(annotated, output_path)

                # If this is result.jpeg, create a comparison with original
                if img_path.name == "result.jpeg":
                    original_path = img_path.parent / "original.jpeg"
                    if original_path.exists():
                        comparison_path = output_dir / f"comparison{img_path.suffix}"
                        create_composite_image(
                            original_path, output_path, comparison_path
                        )

            return results

        except Exception as e:
            print(f"Error processing {img_path}: {str(e)}")
            return []

    def _create_annotated_image(
        self, image: np.ndarray, results: List[Dict]
    ) -> np.ndarray:
        """Create an annotated image with face detection and recognition results"""
        annotated = image.copy()

        # Draw each face
        for result in results:
            bbox = result["bbox"]
            person_id = result["person_id"]
            confidence = result["confidence"]

            if person_id:
                x1, y1, x2, y2 = map(int, bbox)

                # Draw rectangle
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Prepare label text
                label = f"{person_id} ({confidence:.2f})"

                # Draw background rectangle for text
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

                cv2.rectangle(
                    annotated,
                    (x1, y1 - label_size[1] - 10),
                    (x1 + label_size[0], y1),
                    (0, 255, 0),
                    cv2.FILLED,
                )

                # Draw text
                cv2.putText(
                    annotated,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

        return annotated

    def _prepare_known_embeddings(self) -> Dict:
        """Prepare known embeddings from test images"""
        # For test images, we'll use the embeddings from original.jpeg as known embeddings
        known_embeddings = {}

        # Try to get from cache first
        if hasattr(self.recognizer, "metadata_cache"):
            original_img_id = "test_original"
            if original_img_id in self.recognizer.metadata_cache:
                # Check for precomputed embeddings
                for key, value in self.recognizer.metadata_cache.items():
                    if (
                        key.startswith(f"{original_img_id}_face_")
                        and "embedding" in value
                    ):
                        # Use as a known embedding with an arbitrary ID
                        person_id = f"Person_{key.split('_')[-1]}"
                        known_embeddings[person_id] = [value["embedding"]]

        # If we have no embeddings yet, compute them
        if not known_embeddings:
            original_path = self.test_dir / "original.jpeg"
            if original_path.exists():
                # Load the image
                img = load_image(original_path)
                if img is not None:
                    # Detect faces
                    face_bboxes = self.detector.detect_faces(
                        img, force_detection=True, use_cache=True
                    )

                    # Extract and compute embeddings for each face
                    for i, bbox in enumerate(face_bboxes):
                        face = self.detector.extract_face(img, bbox, padding=0.1)
                        if face is not None:
                            # Compute embedding
                            preprocessed = self.recognizer.preprocess_face(face)
                            embedding = self.recognizer.compute_embedding(preprocessed)

                            # Add to known embeddings
                            person_id = f"Person_{i}"
                            known_embeddings[person_id] = [embedding]

                            # Also save to cache
                            face_id = f"test_original_face_{i}"
                            self.recognizer.save_embedding(
                                face_id, embedding, save_to_disk=True
                            )

        return known_embeddings


def optimize_test_images_processing():
    """
    Main function to optimize test images processing.
    """
    # Get project root
    project_root = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    output_dir = project_root / "output" / "test_images"
    output_dir.mkdir(exist_ok=True, parents=True)

    print("Starting test image optimization...")

    # Initialize optimizer
    optimizer = TestImageOptimizer(cache_dir=str(project_root / "cache"), max_workers=4)

    # Preprocess all test images
    optimizer.preprocess_all_test_images()

    # Process test images
    results = optimizer.process_test_images(output_dir=output_dir)

    print(f"Test image optimization complete. Processed {len(results)} images.")
    print(f"Results saved to {output_dir}")

    return results


if __name__ == "__main__":
    optimize_test_images_processing()
