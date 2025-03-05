import os
import cv2
import numpy as np
import pandas as pd
from src.detection.face_detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer
import glob

def find_contestant_photo(contestants_dir, contestant_id):
    """Find contestant's photo in numbered directories"""
    for dir_path in glob.glob(os.path.join(contestants_dir, "*")):
        if os.path.isdir(dir_path):
            # Look for contestant's first photo (ID-1.jpg)
            photo_path = os.path.join(dir_path, f"{contestant_id}-1.jpg")
            if os.path.exists(photo_path):
                return photo_path
    return None

def main():
    # Initialize paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    contestants_dir = os.path.join(project_root, "source", "photo", "contestants")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")

    # Load contestant information
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info['編號'] = contestant_info['編號'].astype(str)

    # Initialize components
    face_detector = FaceDetector(confidence_threshold=0.3)
    face_recognizer = FaceRecognizer(
        recognition_model_path=os.path.join(project_root, "models", "arcface_r50.onnx"),
        face_detector=face_detector,
        similarity_threshold=0.6
    )

    # Process each contestant
    for _, contestant in contestant_info.iterrows():
        nickname = contestant['暱稱']
        contestant_id = contestant['編號']
        
        # Find photo in numbered directories
        photo_path = find_contestant_photo(contestants_dir, contestant_id)
        
        if not photo_path:
            print(f"Photo not found for {nickname} (ID: {contestant_id})")
            continue
            
        try:
            # Load and process image
            image = cv2.imread(photo_path)
            if image is None:
                print(f"Failed to load image for {nickname}")
                continue
                
            # Get face embedding
            faces = face_recognizer.detect_and_embed(image)
            if not faces:
                print(f"No face detected for {nickname}")
                continue
                
            # Save embedding
            embedding = faces[0][0]  # First face's embedding
            embedding_path = os.path.join(contestants_dir, f"{nickname}_embedding.npy")
            np.save(embedding_path, embedding)
            print(f"Generated embedding for {nickname}")
            
        except Exception as e:
            print(f"Error processing {nickname}: {str(e)}")

if __name__ == "__main__":
    main()
