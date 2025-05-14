from src.config.config import (
    Config,
    DetectionConfig,
    SegmentationConfig,
    RecognitionConfig,
)
from src.detection.face_detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer
import os
import cv2
import pandas as pd


def main():
    # Initialize paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    test_image_path = os.path.join(
        project_root, "source", "images", "test", "original.jpeg"
    )
    result_path = os.path.join(project_root, "source", "images", "test", "result.jpeg")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")

    # Load contestant information
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info["編號"] = contestant_info["編號"].astype(str)

    # Initialize configuration
    config = Config(
        detection=DetectionConfig(
            model_path=os.path.join(project_root, "models", "face_detection_yunet.onnx")
        ),
        segmentation=SegmentationConfig(model_path=""),
        recognition=RecognitionConfig(
            model_path=os.path.join(
                project_root, "models", "face_recognition_mobilenet.caffemodel"
            )
        ),
    )

    # Initialize components
    face_detector = FaceDetector(
        confidence_threshold=config.detection.confidence_threshold
    )

    face_recognizer = FaceRecognizer(
        recognition_model_path=os.path.join(
            project_root, "models", "face_recognition_mobilenet.caffemodel"
        ),
        face_detector=face_detector,
        similarity_threshold=0.45,  # Threshold for strong matches
    )

    # Load pre-computed contestant embeddings
    known_embeddings = {}
    for _, contestant in contestant_info.iterrows():
        nickname = contestant["暱稱"]
        embedding = face_recognizer.get_embedding(nickname)
        if embedding is not None:
            known_embeddings[nickname] = [embedding]

    print(f"Successfully loaded embeddings for {len(known_embeddings)} contestants")

    # Load and process test image
    image = cv2.imread(test_image_path)
    if image is None:
        print(f"Failed to load image: {test_image_path}")
        return

    # Get face embeddings
    faces = face_recognizer.detect_and_embed(image)

    # Create copy for annotation
    annotated_image = image.copy()

    # Process each detected face
    for face_embedding, bbox in faces:
        best_match = None
        best_confidence = -1

        # Compare with known embeddings
        for nickname, known_embs in known_embeddings.items():
            for known_emb in known_embs:
                confidence = face_recognizer._compute_similarity(
                    face_embedding, known_emb
                )
                print(f"Similarity with {nickname}: {confidence:.4f}")
                if confidence > config.recognition.similarity_threshold:
                    if confidence > best_confidence:
                        best_match = nickname
                        best_confidence = confidence

        # Draw bounding box and label
        x1, y1, x2, y2 = bbox
        cv2.rectangle(
            annotated_image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2
        )
        label = f"{best_match} ({best_confidence:.2f})" if best_match else "Unknown"
        cv2.putText(
            annotated_image,
            label,
            (int(x1), int(y1) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
        )

        print(
            f"Detected {label} at coordinates ({int(x1)}, {int(y1)}, {int(x2)}, {int(y2)})"
        )

    # Save result
    cv2.imwrite(result_path, annotated_image)
    print(f"Saved annotated image to: {result_path}")


if __name__ == "__main__":
    main()
