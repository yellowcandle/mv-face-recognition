
import os
import numpy as np
import sys
from src.recognition.face_recognizer import FaceRecognizer
from src.core.detector import FaceDetector

def main():
    # Initialize detector and recognizer
    core_detector = FaceDetector(backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto")
    # Using a lower similarity threshold which seems to provide better results
    face_recognizer = FaceRecognizer(face_detector=core_detector, similarity_threshold=0.35, use_arcface=True)
    
    # The problem might be related to the model loading or inference process.
    # Inspect the model details 
    print("\nFace Recognizer Configuration:")
    print(f"Embedding size: {face_recognizer.embedding_size}")
    print(f"Using ArcFace: {face_recognizer.use_arcface}")
    if hasattr(face_recognizer, "session"):
        model_inputs = face_recognizer.session.get_inputs()
        model_outputs = face_recognizer.session.get_outputs()
        print(f"Model input name: {face_recognizer.input_name}")
        print(f"Model input shape: {model_inputs[0].shape}")
        print(f"Model output name: {face_recognizer.output_name}")
        print(f"Model output shape: {model_outputs[0].shape}")
        print(f"Model providers: {face_recognizer.session.get_providers()}")
    
    # Possible solutions:
    print("\nPossible solutions to improve recognition:")
    print("1. Check contestant embedding quality - they might need recomputation")
    print("2. Try a different model (ArcFace vs SFace)")
    print("3. Adjust preprocessing parameters (mean, std)")
    print("4. Refine the threshold value")
    print("5. Check embedding normalization")
    
if __name__ == "__main__":
    main()
