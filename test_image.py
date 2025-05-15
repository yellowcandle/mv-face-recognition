# pylint: disable=no-member
from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer
import os
import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Optional, Tuple

def main():
    # Debug settings
    DEBUG = True
    SHOW_ALL_SIMILARITIES = True
    SHOW_TIMING = True
    
    # Initialize paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    test_image_path = os.path.join(project_root, "source", "images", "test", "original.jpeg")
    result_path = os.path.join(project_root, "source", "images", "test", "result.jpeg")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")
    font_path = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")

    if DEBUG:
        print("\n=== DEBUG MODE ENABLED ===")
        print(f"Current working directory: {project_root}")
        print(f"Test image path: {test_image_path}")

    # Load contestant information
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info["編號"] = contestant_info["編號"].astype(str)

    # Initialize detector with InsightFace backend
    face_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE,
        model_size=(640, 640),
        device="auto",
        confidence_threshold=0.3
    )

    # Initialize recognizer
    face_recognizer = FaceRecognizer(
        face_detector=face_detector,
        similarity_threshold=0.30, # Lowered threshold
        use_arcface=True
    )

    if DEBUG:
        print("\n=== CURRENT PARAMETERS ===")
        print(f"Detection confidence threshold: {face_detector.confidence_threshold}")
        print(f"Recognition similarity threshold: {face_recognizer.similarity_threshold}")
        print(f"Model size: {face_detector.model_size}")
        print(f"Using ArcFace: {face_recognizer.use_arcface}")

    # Focus on specific contestants
    target_contestants = ["Mei Mei", "Sinnie", "Yanny", "阿蛋", "Elka", "Tania", "阿妹", "阿 Yo"]
    target_ids = contestant_info[contestant_info["暱稱"].isin(target_contestants)]["編號"].tolist()

    # Load embeddings for target contestants
    known_embeddings = {}
    embeddings_dir = os.path.join(project_root, "source", "photo", "contestants", "embeddings")
    
    if DEBUG:
        print("\n=== LOADING EMBEDDINGS ===")
    
    for contestant in target_contestants:
        embedding_path = os.path.join(embeddings_dir, f"{contestant}_embedding.npy")
        if os.path.exists(embedding_path):
            embedding = np.load(embedding_path)
            known_embeddings[contestant] = [embedding]
            if DEBUG:
                print(f"Loaded embedding for {contestant}:")
                print(f"  Shape: {embedding.shape}")
                print(f"  Norm: {np.linalg.norm(embedding):.4f}")
                print(f"  Min/Max: {np.min(embedding):.4f}/{np.max(embedding):.4f}")
        else:
            print(f"Embedding not found for {contestant} at {embedding_path}")
    
    if DEBUG:
        print(f"\nSuccessfully loaded {len(known_embeddings)}/{len(target_contestants)} embeddings")

    # Add known embeddings to the recognizer's database
    for person_id, embeddings_list in known_embeddings.items():
        if embeddings_list: # Ensure there's at least one embedding
            # Use the new add_known_embedding method
            face_recognizer.add_known_embedding(person_id, embeddings_list[0])
            if DEBUG:
                print(f"Added {person_id} to face_recognizer via add_known_embedding")

    # Load test image
    image = cv2.imread(test_image_path)  # pylint: disable=no-member
    if image is None:
        print(f"Failed to load test image at {test_image_path}")
        return

    # Detect and recognize faces
    import time
    start_time = time.time()
    
    if DEBUG:
        print("\n=== FACE DETECTION ===")
    
    # Get both embeddings and recognition results
    face_data = face_recognizer.detect_and_embed(image)
    # Pass face_data (pre-computed embeddings for detected faces) to identify_face
    results = face_recognizer.identify_face(image, detected_face_embeddings=face_data)
    
    if DEBUG:
        detection_time = time.time() - start_time
        print(f"Detected {len(results)} faces in {detection_time:.2f} seconds")
        for i, (face_embedding, result) in enumerate(zip(face_data, results)):
            print(f"\nFace {i+1}:")
            
            # Handle different bbox formats
            bbox = result['bbox']
            if hasattr(bbox, 'tolist'):  # If it's a numpy array
                bbox = bbox.tolist()
            elif isinstance(bbox, list) and len(bbox) >= 4:  # If it's already a list
                bbox = bbox[:4]  # Take first 4 elements
            else:
                print(f"  Warning: Unexpected bbox format: {bbox}")
                continue
                
            print(f"  Bounding box: {bbox}")
            print(f"  Confidence: {result['confidence']:.4f}")
            if result['person_id']:
                print(f"  Recognized as: {result['person_id']}")
                if SHOW_ALL_SIMILARITIES:
                    print("  Similarity scores:")
                    for contestant, embeddings_list in known_embeddings.items():
                        for known_emb in embeddings_list: # known_emb is an np.ndarray
                            # face_embedding is already a single np.ndarray for the current detected face
                            similarity = face_recognizer._compute_similarity(
                                face_embedding, known_emb
                            )
                            print(f"    {contestant}: {similarity:.4f}")
            else:
                print("  No match found")
                if SHOW_ALL_SIMILARITIES:
                    print("  Similarity scores:")
                    for contestant, embeddings_list in known_embeddings.items():
                        for known_emb in embeddings_list: # known_emb is an np.ndarray
                            # face_embedding is already a single np.ndarray for the current detected face
                            similarity = face_recognizer._compute_similarity(
                                face_embedding, known_emb
                            )
                            print(f"    {contestant}: {similarity:.4f}")
    
    # Convert to PIL for better text rendering
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))  # pylint: disable=no-member
    draw = ImageDraw.Draw(pil_img)
    font = ImageFont.truetype(font_path, 24)

    # Draw results
    for result in results:
        bbox = result["bbox"]
        person_id = result["person_id"]
        confidence = result["confidence"]

        # Draw bounding box
        x1, y1, x2, y2 = map(int, bbox)
        draw.rectangle([x1, y1, x2, y2], outline="green", width=2)

        # Draw label
        if person_id:
            label = f"{person_id} ({confidence:.2f})"
            draw.text((x1, y1 - 30), label, font=font, fill="white")

    # Save result
    pil_img.save(result_path)
    print(f"Results saved to {result_path}")

if __name__ == "__main__":
    main()
