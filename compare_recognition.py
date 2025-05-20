import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

# Load the sample data image (expected results)
expected_results_path = "source/images/test/sample_data.png"
expected_img = np.array(Image.open(expected_results_path))

# Load the test results from our script
threshold_values = [0.3, 0.35, 0.4, 0.45, 0.5]
test_result_images = []

for threshold in threshold_values:
    result_path = f"source/images/test/result_threshold_{threshold:.2f}.jpeg"
    if os.path.exists(result_path):
        test_img = np.array(Image.open(result_path))
        test_result_images.append((threshold, test_img))

# Display the expected results and our test results side by side
plt.figure(figsize=(20, 12))

# First, display the expected results (sample_data.png)
plt.subplot(1, len(test_result_images) + 1, 1)
plt.imshow(expected_img)
plt.title("Expected Results (sample_data.png)")
plt.axis('off')

# Display each of our test results
for i, (threshold, img) in enumerate(test_result_images):
    plt.subplot(1, len(test_result_images) + 1, i + 2)
    plt.imshow(img)
    plt.title(f"Our Results (threshold = {threshold:.2f})")
    plt.axis('off')

plt.tight_layout()
plt.savefig("source/images/test/comparison.png", dpi=150)
print("Comparison image saved to source/images/test/comparison.png")

# Now create a script that will correct the issue based on what we've observed
with open("fix_face_recognition.py", "w") as f:
    f.write("""
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
    print("\\nFace Recognizer Configuration:")
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
    print("\\nPossible solutions to improve recognition:")
    print("1. Check contestant embedding quality - they might need recomputation")
    print("2. Try a different model (ArcFace vs SFace)")
    print("3. Adjust preprocessing parameters (mean, std)")
    print("4. Refine the threshold value")
    print("5. Check embedding normalization")
    
if __name__ == "__main__":
    main()
""")
print("Created fix_face_recognition.py script with potential solutions")
