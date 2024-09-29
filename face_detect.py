import os
from deepface import DeepFace
import pandas as pd
import tqdm

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.join(os.path.dirname(os.path.dirname(current_script_path)), "mv-face-recognition")
base_dir = os.path.join(project_root, "source", "photo", "contestants")

# Function to detect face in an image
def face_exists(img_path):
    try:
        # Use extract_faces to detect faces
        faces = DeepFace.extract_faces(img_path=img_path, enforce_detection=False)
        return len(faces) > 0
    except ValueError as e:
        if "Face could not be detected" in str(e):
            return False
        else:
            raise e

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
        return None, False if not os.path.exists(img1_path) else None, False if not os.path.exists(img2_path) else None, error_message
    
    face1_exists = face_exists(img1_path)
    face2_exists = face_exists(img2_path)
    
    if not face1_exists or not face2_exists:
        error_message = "Face could not be detected in one or both images."
        print(error_message)
        return None, face1_exists, face2_exists, error_message
    
    try:
        result = DeepFace.verify(img1_path=img1_path, img2_path=img2_path, enforce_detection=True)
        print(f"Verification result for folder {folder_path}: {result['verified']}, Face 1 Exists: {face1_exists}, Face 2 Exists: {face2_exists}")
        return result["verified"], face1_exists, face2_exists, None
    except ValueError as e:
        if "Face could not be detected" in str(e) or "Exception while processing" in str(e):
            error_message = "Face could not be detected in one or both images during verification."
            print(error_message)
            return None, face1_exists, face2_exists, error_message
        else:
            error_message = f"Error processing images: {str(e)}"
            print(error_message)
            return None, None, None, error_message
    except Exception as e:
        import traceback
        error_message = f"Error processing images: {str(e)}\n{traceback.format_exc()}"
        print(error_message)
        return None, None, None, error_message

def main():
    # Replace Streamlit UI elements with batch processing logic
    print("Face Verification Script - Batch Processing")

    results = []

    # Loop over folder numbers from 1 to 96
    for folder_num in range(1, 97):
        folder_path = os.path.join(base_dir, str(folder_num))
        if os.path.exists(folder_path):
            is_same_person, face1_exists, face2_exists, error = verify_faces_in_folder(folder_path)
            
            if error:
                print(f"Folder {folder_num}: Error - {error}")
                results.append({
                    'Folder': folder_num,
                    'Is Same Person': None,
                    'Face 1 Exists': face1_exists,
                    'Face 2 Exists': face2_exists,
                    'Error': error
                })
            else:
                print(f"Folder {folder_num}:")
                print(f"  Is Same Person: {is_same_person}")
                print(f"  Face 1 Exists: {face1_exists}")
                print(f"  Face 2 Exists: {face2_exists}")
                results.append({
                    'Folder': folder_num,
                    'Is Same Person': is_same_person,
                    'Face 1 Exists': face1_exists,
                    'Face 2 Exists': face2_exists,
                    'Error': None
                })
        else:
            print(f"Folder {folder_num} not found.")
            results.append({
                'Folder': folder_num,
                'Is Same Person': None,
                'Face 1 Exists': None,
                'Face 2 Exists': None,
                'Error': 'Folder not found.'
            })

    # Save results to 'face_verification_results.csv'
    output_csv = os.path.join(project_root, 'face_verification_results.csv')
    df = pd.DataFrame(results)
    df.to_csv(output_csv, index=False)
    print(f"\nResults saved to {output_csv}")

if __name__ == '__main__':
    main()