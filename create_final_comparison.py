import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import os

# Paths to the images we want to compare
original_image_path = "source/images/test/sample_data.png"
original_results_path = "source/images/test/result_threshold_0.50.jpeg"
fixed_results_path = "source/images/test/result_fixed_1_arcface_True_thresh_0.6.jpeg"

# Load the images
expected_img = np.array(Image.open(original_image_path)) if os.path.exists(original_image_path) else None
original_result = np.array(Image.open(original_results_path)) if os.path.exists(original_results_path) else None
fixed_result = np.array(Image.open(fixed_results_path)) if os.path.exists(fixed_results_path) else None

# Create the comparison visualization
plt.figure(figsize=(18, 8))

# Display the expected results
plt.subplot(1, 3, 1)
if expected_img is not None:
    plt.imshow(expected_img)
    plt.title("Expected Results (sample_data.png)")
else:
    plt.text(0.5, 0.5, "Expected results image not found", ha="center", va="center")
plt.axis('off')

# Display the original results
plt.subplot(1, 3, 2)
if original_result is not None:
    plt.imshow(original_result)
    plt.title("Original Face Recognizer (threshold=0.50)")
else:
    plt.text(0.5, 0.5, "Original results image not found", ha="center", va="center")
plt.axis('off')

# Display the fixed results
plt.subplot(1, 3, 3)
if fixed_result is not None:
    plt.imshow(fixed_result)
    plt.title("Fixed Face Recognizer (SFace, threshold=0.60)")
else:
    plt.text(0.5, 0.5, "Fixed results image not found", ha="center", va="center")
plt.axis('off')

plt.tight_layout()
plt.savefig("source/images/test/final_comparison.png", dpi=150)
print("Final comparison image saved to source/images/test/final_comparison.png")

# Now let's summarize our findings and fix recommendations
print("\nSummary of Face Recognition Issues and Fixes:")
print("1. Issue: The original face recognizer was using incorrect normalization values for the SFace model")
print("   Fix: Updated mean and std values to [0.5, 0.5, 0.5] for SFace model")
print("\n2. Issue: Confidence threshold was too low, leading to false positives")
print("   Fix: Increased threshold to 0.6 for better precision")
print("\n3. Issue: Inconsistent handling of embedding dimensions")
print("   Fix: Improved dimension matching when comparing embeddings")
print("\n4. Issue: OpenCV DNN model has compatibility issues on this platform")
print("   Fix: Defaulted to using SFace ONNX model which works correctly")
print("\nTo improve face recognition for this application:")
print("1. Update the normalization values in FaceRecognizer._get_embedding() to use [0.5, 0.5, 0.5] for SFace")
print("2. Increase the similarity_threshold parameter to 0.6 when initializing FaceRecognizer")
print("3. Consider re-computing the embeddings for the contestant gallery with the corrected normalization")
