import os
import cv2
import numpy as np
import pandas as pd
import tqdm
import warnings

# from insightface.app import FaceAnalysis # Will be replaced by core_detector
from src.core.detector import FaceDetector  # Import the centralized detector


# Suppress the specific FutureWarning from numpy.linalg.lstsq
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="insightface.utils.transform"
)

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.join(
    os.path.dirname(os.path.dirname(current_script_path)), "mv-face-recognition"
)
base_dir = os.path.join(project_root, "source", "photo", "contestants")

# Initialize Centralized FaceDetector
core_detector = FaceDetector(
    backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto"
)
# Note: The FaceAnalysis object 'app' is no longer needed globally.


# Function to detect face in an image (can be removed if verify_faces_in_folder is self-sufficient)
# For now, let's keep it and adapt it, or it can be removed later if not used.
def face_exists(img_path):
    try:
        img = cv2.imread(img_path)
        if img is None:
            print(f"Warning: Could not read image {img_path}")
            return False

        raw_detected_faces = core_detector.detect_faces(img)
        # Filter faces by detection score
        DETECTION_SCORE_THRESHOLD = 0.5
        detected_faces = [
            face
            for face in raw_detected_faces
            if hasattr(face, "det_score")
            and face.det_score >= DETECTION_SCORE_THRESHOLD
        ]
        return len(detected_faces) > 0
    except Exception as e:
        # InsightFace's app.get() might not raise "Face could not be detected"
        # The core_detector.detect_faces() should return an empty list if no faces.
        # So, specific error string check might not be needed.
        print(f"Error in face_exists for {img_path}: {e}")
        # Depending on desired behavior, either return False or re-raise
        return False


# Function to verify faces in a folder
def verify_faces_in_folder(folder_path):
    img1_path_jpg = os.path.join(folder_path, f"{os.path.basename(folder_path)}-1.jpg")
    img2_path_jpg = os.path.join(folder_path, f"{os.path.basename(folder_path)}-2.jpg")
    img1_path_png = os.path.join(folder_path, f"{os.path.basename(folder_path)}-1.png")
    img2_path_png = os.path.join(folder_path, f"{os.path.basename(folder_path)}-2.png")

    img1_path = img1_path_jpg if os.path.exists(img1_path_jpg) else img1_path_png
    img2_path = img2_path_jpg if os.path.exists(img2_path_jpg) else img2_path_png

    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        error_message = f"Expected 2 images, found {int(os.path.exists(img1_path)) + int(os.path.exists(img2_path))}"
        print(error_message)
        return (
            None,
            False if not os.path.exists(img1_path) else None,
            False if not os.path.exists(img2_path) else None,
            error_message,
        )

    # Load images once and perform detection
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)

    if img1 is None:
        error_message = f"Could not read image {img1_path}."
        print(error_message)
        return None, False, None, error_message
    if img2 is None:
        error_message = f"Could not read image {img2_path}."
        print(error_message)
        return None, True, False, error_message  # img1 exists, img2 doesn't

    try:
        raw_detected_faces1 = core_detector.detect_faces(img1)
        raw_detected_faces2 = core_detector.detect_faces(img2)

        DETECTION_SCORE_THRESHOLD = 0.5  # Ensure consistency

        detected_faces1 = [
            face
            for face in raw_detected_faces1
            if hasattr(face, "det_score")
            and face.det_score >= DETECTION_SCORE_THRESHOLD
        ]
        detected_faces2 = [
            face
            for face in raw_detected_faces2
            if hasattr(face, "det_score")
            and face.det_score >= DETECTION_SCORE_THRESHOLD
        ]

        face1_exists = len(detected_faces1) > 0
        face2_exists = len(detected_faces2) > 0

        if not face1_exists or not face2_exists:
            error_message = "Face could not be detected (or did not meet score threshold) in one or both images during verification."
            print(error_message)
            return None, face1_exists, face2_exists, error_message

        # Use the first detected face (that passed threshold) for verification
        face_obj1 = detected_faces1[0]
        face_obj2 = detected_faces2[0]

        # Extract embeddings
        embedding1 = face_obj1.normed_embedding
        embedding2 = face_obj2.normed_embedding

        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2)
        is_same_person = similarity > 0.5  # You can adjust the threshold as needed

        print(
            f"Verification result for folder {folder_path}: {is_same_person}, Face 1 Exists: {face1_exists}, Face 2 Exists: {face2_exists}"
        )
        return is_same_person, face1_exists, face2_exists, None
    except Exception as e:
        import traceback

        error_message = f"Error processing images: {str(e)}\n{traceback.format_exc()}"
        print(error_message)
        return None, None, None, error_message


def main():
    # Replace Streamlit UI elements with batch processing logic
    print("Face Verification Script - Batch Processing")

    results = []

    # Loop over folder numbers from 1 to 96 with tqdm progress bar
    for folder_num in tqdm.tqdm(range(1, 97), desc="Processing folders"):
        folder_path = os.path.join(base_dir, str(folder_num))
        if os.path.exists(folder_path):
            is_same_person, face1_exists, face2_exists, error = verify_faces_in_folder(
                folder_path
            )

            if error:
                print(f"Folder {folder_num}: Error - {error}")
                results.append(
                    {
                        "Folder": folder_num,
                        "Is Same Person": None,
                        "Face 1 Exists": face1_exists,
                        "Face 2 Exists": face2_exists,
                        "Error": error,
                    }
                )
            else:
                print(f"Folder {folder_num}:")
                print(f"  Is Same Person: {is_same_person}")
                print(f"  Face 1 Exists: {face1_exists}")
                print(f"  Face 2 Exists: {face2_exists}")
                results.append(
                    {
                        "Folder": folder_num,
                        "Is Same Person": is_same_person,
                        "Face 1 Exists": face1_exists,
                        "Face 2 Exists": face2_exists,
                        "Error": None,
                    }
                )
        else:
            print(f"Folder {folder_num} not found.")
            results.append(
                {
                    "Folder": folder_num,
                    "Is Same Person": None,
                    "Face 1 Exists": None,
                    "Face 2 Exists": None,
                    "Error": "Folder not found.",
                }
            )

    # Save results to 'face_verification_results.csv'
    output_csv = os.path.join(project_root, "face_verification_results.csv")
    df = pd.DataFrame(results)
    df.to_csv(output_csv, index=False)
    print(f"\nResults saved to {output_csv}")


if __name__ == "__main__":
    main()
