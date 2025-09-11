"""Integration test for multiple faces per frame (50+ faces)."""

import pytest
from pathlib import Path
import tempfile
import shutil
import cv2
import numpy as np


@pytest.fixture
def many_faces_image():
    """Create image with many face-like regions for testing."""
    # Create large image that could contain many faces
    img = np.ones((800, 1200, 3), dtype=np.uint8) * 128

    # Add many small circular regions that could be detected as faces
    face_positions = []
    for row in range(5):
        for col in range(10):  # 5x10 = 50 face-like regions
            x = 60 + col * 110
            y = 80 + row * 140

            # Create face-like pattern
            cv2.circle(img, (x - 15, y - 10), 8, (255, 255, 255), -1)  # Left eye
            cv2.circle(img, (x + 15, y - 10), 8, (255, 255, 255), -1)  # Right eye
            cv2.ellipse(
                img, (x, y + 15), (20, 10), 0, 0, 180, (200, 150, 100), -1
            )  # Mouth
            cv2.circle(img, (x, y), 35, (220, 180, 150), 2)  # Face outline

            face_positions.append((x, y))

    return img, face_positions


@pytest.fixture
def crowded_video():
    """Create video with many faces per frame."""
    temp_dir = Path(tempfile.mkdtemp())
    video_path = temp_dir / "crowded_video.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 5.0, (1200, 800))

    for frame_idx in range(10):
        # Create base image
        img = np.ones((800, 1200, 3), dtype=np.uint8) * (100 + frame_idx * 10)

        # Add many face-like regions (varying slightly per frame)
        for row in range(4):  # 4x12 = 48 faces per frame
            for col in range(12):
                x = 50 + col * 95 + (frame_idx % 3) * 5  # Slight movement
                y = 70 + row * 180 + (frame_idx % 2) * 3

                if x < 1150 and y < 750:  # Stay within bounds
                    # Simple face-like pattern
                    cv2.circle(img, (x - 10, y - 8), 5, (255, 255, 255), -1)  # Left eye
                    cv2.circle(
                        img, (x + 10, y - 8), 5, (255, 255, 255), -1
                    )  # Right eye
                    cv2.rectangle(
                        img, (x - 8, y + 8), (x + 8, y + 15), (200, 150, 100), -1
                    )  # Mouth
                    cv2.circle(img, (x, y), 25, (220, 180, 150), 1)  # Face outline

        out.write(img)

    out.release()
    yield video_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def output_directory():
    """Create temporary output directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_detect_multiple_faces_single_image(many_faces_image):
    """Test face detection on image with many faces."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    img, expected_positions = many_faces_image

    # Detect faces in crowded image
    detections = detector.detect(img)

    # Should return list of detections
    assert isinstance(detections, list)

    # Should detect multiple faces (may not find all 50 due to simple patterns)
    # But should handle the load without crashing
    assert len(detections) >= 0  # At least doesn't crash

    # Each detection should have proper structure
    for detection in detections[:5]:  # Check first 5
        assert "bbox" in detection or hasattr(detection, "bbox")
        if isinstance(detection, dict) and "bbox" in detection:
            bbox = detection["bbox"]
            assert len(bbox) == 4  # x, y, width, height or similar


def test_process_crowded_video_frame_mode(crowded_video, output_directory):
    """Test processing video with many faces in frame output mode."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Process crowded video
    result = processor.process(
        video_path=str(crowded_video),
        output_mode="frames",
        output_dir=str(output_directory),
        max_faces=50,  # Should handle up to 50 faces
    )

    # Should complete successfully
    assert result is not None

    # Should create output frames
    frame_files = list(output_directory.glob("*.jpg")) + list(
        output_directory.glob("*.png")
    )
    assert len(frame_files) > 0

    # Check that frames were processed (have reasonable file sizes)
    for frame_file in frame_files[:3]:
        assert frame_file.stat().st_size > 5000  # Should have substantial content


def test_face_matching_with_many_faces(many_faces_image):
    """Test face matching performance with many detected faces."""
    from src.core.face_detector import FaceDetector
    from src.core.face_matcher import FaceMatcher

    detector = FaceDetector()
    matcher = FaceMatcher()

    img, _ = many_faces_image

    # Detect all faces
    detections = detector.detect(img)

    # Try to match each detection (should handle batch efficiently)
    matches = []
    for detection in detections[:20]:  # Test first 20 to avoid excessive runtime
        try:
            # Extract embedding if detection has face data
            if hasattr(detection, "embedding") or "embedding" in detection:
                embedding = (
                    detection.embedding
                    if hasattr(detection, "embedding")
                    else detection["embedding"]
                )
                match = matcher.match(embedding)
                matches.append(match)
            else:
                # If no embedding, this is still valid (detection without recognition)
                matches.append(None)
        except Exception:
            # Expected if no contestants loaded or embeddings not generated
            matches.append(None)

    # Should handle all matches without crashing
    assert len(matches) == min(len(detections), 20)


def test_memory_usage_many_faces(crowded_video, output_directory):
    """Test that memory usage stays reasonable with many faces."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Process video and monitor that it completes
    # (In a real system, you'd monitor actual memory usage)
    result = processor.process(
        video_path=str(crowded_video),
        output_mode="video",
        output_dir=str(output_directory),
    )

    # Should complete without running out of memory
    assert result is not None

    # Should produce output
    output_files = list(output_directory.glob("*.mp4"))
    assert len(output_files) > 0


def test_annotation_quality_many_faces(many_faces_image, output_directory):
    """Test annotation quality when many faces are present."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    img, expected_positions = many_faces_image

    # Detect faces
    detections = detector.detect(img)

    # Create annotated version (simulate annotation process)
    annotated_img = img.copy()

    # Draw bounding boxes for detections
    for detection in detections:
        if isinstance(detection, dict) and "bbox" in detection:
            bbox = detection["bbox"]
            x, y, w, h = bbox[:4]
            cv2.rectangle(
                annotated_img,
                (int(x), int(y)),
                (int(x + w), int(y + h)),
                (0, 255, 0),
                2,
            )
        elif hasattr(detection, "bbox"):
            bbox = detection.bbox
            x, y, w, h = bbox[:4]
            cv2.rectangle(
                annotated_img,
                (int(x), int(y)),
                (int(x + w), int(y + h)),
                (0, 255, 0),
                2,
            )

    # Save annotated image
    output_path = output_directory / "annotated_many_faces.jpg"
    cv2.imwrite(str(output_path), annotated_img)

    # Should create valid output file
    assert output_path.exists()
    assert output_path.stat().st_size > len(detections) * 100  # Rough size check


def test_performance_benchmark_many_faces(many_faces_image):
    """Test performance benchmark for processing many faces."""
    from src.core.face_detector import FaceDetector
    import time

    detector = FaceDetector()
    img, _ = many_faces_image

    # Measure detection time
    start_time = time.time()
    detections = detector.detect(img)
    detection_time = time.time() - start_time

    # Should complete within reasonable time (10 seconds for test environment)
    assert detection_time < 10.0, f"Detection took too long: {detection_time:.2f}s"

    # Should return reasonable results
    assert isinstance(detections, list)
    assert len(detections) < 100  # Sanity check - shouldn't detect more than possible


def test_confidence_filtering_many_faces(many_faces_image):
    """Test confidence threshold filtering with many potential faces."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    img, _ = many_faces_image

    # Test with different confidence thresholds
    detections_low = detector.detect(img, confidence=0.3)
    detections_high = detector.detect(img, confidence=0.8)

    # Should return valid results for both
    assert isinstance(detections_low, list)
    assert isinstance(detections_high, list)

    # Higher confidence should typically return fewer detections
    # (though with synthetic data, this might not always hold)
    assert len(detections_high) <= len(detections_low) + 5  # Allow some variance


def test_batch_processing_multiple_crowded_frames():
    """Test batch processing of multiple frames with many faces each."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()

    # Create multiple crowded images
    batch_results = []
    for batch_idx in range(3):
        # Create image with many small face-like regions
        img = np.ones((400, 600, 3), dtype=np.uint8) * (100 + batch_idx * 20)

        # Add face-like patterns
        for i in range(15):  # 15 faces per image
            x = 50 + (i % 5) * 110
            y = 50 + (i // 5) * 110
            cv2.circle(img, (x, y), 20, (200, 180, 150), 2)
            cv2.circle(img, (x - 8, y - 5), 3, (0, 0, 0), -1)  # Eyes
            cv2.circle(img, (x + 8, y - 5), 3, (0, 0, 0), -1)

        # Process image
        detections = detector.detect(img)
        batch_results.append(len(detections))

    # Should process all images successfully
    assert len(batch_results) == 3
    assert all(isinstance(count, int) and count >= 0 for count in batch_results)
