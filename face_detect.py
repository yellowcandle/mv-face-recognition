import os
import cv2
import numpy as np
import pandas as pd
import tqdm
from insightface.app import FaceAnalysis

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.join(
    os.path.dirname(os.path.dirname(current_script_path)), "mv-face-recognition"
)
base_dir = os.path.join(project_root, "source", "photo", "contestants")

# Initialize InsightFace
app = FaceAnalysis(providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))


# Function to detect face in an image
def face_exists(img_path):
    """_summary_

    Args:
        img_path (_type_): _description_

    Raises:
        e: _description_

    Returns:
        _type_: _description_
    """
    try:
        img = cv2.imread(img_path)
        faces = app.get(img)
        return len(faces) > 0
    except Exception as e:
        if "Face could not be detected" in str(e):
            return False
        else:
            raise e


# Function to verify faces in a folder
def verify_faces_in_folder(folder_path):
    """_summary_

    Args:
        folder_path (_type_): _description_

    Returns:
        _type_: _description_
    """
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

    face1_exists = face_exists(img1_path)
    face2_exists = face_exists(img2_path)

    if not face1_exists or not face2_exists:
        error_message = "Face could not be detected in one or both images."
        print(error_message)
        return None, face1_exists, face2_exists, error_message

    try:
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        faces1 = app.get(img1)
        faces2 = app.get(img2)

        if len(faces1) == 0 or len(faces2) == 0:
            error_message = (
                "Face could not be detected in one or both images during verification."
            )
            print(error_message)
            return None, face1_exists, face2_exists, error_message

        # Use the first detected face for verification
        face1 = faces1[0]
        face2 = faces2[0]

        # Extract embeddings
        embedding1 = face1.normed_embedding
        embedding2 = face2.normed_embedding

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
