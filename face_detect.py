import os
from deepface import DeepFace
import pandas as pd
import tqdm

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.join(os.path.dirname(os.path.dirname(current_script_path)), "mv-face-recognition")
base_dir = os.path.join(project_root, "source", "photo", "contestants")

# Function to verify faces in a folder
def verify_faces_in_folder(folder_path):
    img1_path_jpg = os.path.join(folder_path, f"{os.path.basename(folder_path)}-1.jpg")
    img2_path_jpg = os.path.join(folder_path, f"{os.path.basename(folder_path)}-2.jpg")
    img1_path_png = os.path.join(folder_path, f"{os.path.basename(folder_path)}-1.png")
    img2_path_png = os.path.join(folder_path, f"{os.path.basename(folder_path)}-2.png")
    
    img1_path = img1_path_jpg if os.path.exists(img1_path_jpg) else img1_path_png
    img2_path = img2_path_jpg if os.path.exists(img2_path_jpg) else img2_path_png
    
    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        return None, False if not os.path.exists(img1_path) else None, False if not os.path.exists(img2_path) else None, f"Expected 2 images, found {int(os.path.exists(img1_path)) + int(os.path.exists(img2_path))}"
    
    try:
        result = DeepFace.verify(img1_path=img1_path, img2_path=img2_path, enforce_detection=False)
        face1_exists = result["verified"]
        face2_exists = result["verified"]
        print(f"Verification result for folder {folder_path}: {result['verified']}, Face 1 Exists: {face1_exists}, Face 2 Exists: {face2_exists}")
        return result["verified"], face1_exists, face2_exists, None
    except KeyError as e:
        import traceback
        error_message = f"Error processing images: '{e}'\n{traceback.format_exc()}"
        print(error_message)
        return None, None, None, error_message
    except ValueError as e:
        if "Face could not be detected" in str(e):
            if "img1_path" in str(e):
                error_message = f"Error processing images: {str(e)}"
                print(error_message)
                return None, False, None, error_message
            elif "img2_path" in str(e):
                error_message = f"Error processing images: {str(e)}"
                print(error_message)
                return None, None, False, error_message
        import traceback
        error_message = f"Error processing images: {str(e)}\n{traceback.format_exc()}"
        print(error_message)
        return None, None, None, error_message
    except Exception as e:
        import traceback
        error_message = f"Error processing images: {str(e)}\n{traceback.format_exc()}"
        print(error_message)
        return None, None, None, error_message

# Prepare results dataframe
results = []

# Iterate through all 96 folders
for i in tqdm.tqdm(range(1, 97), desc="Verifying faces", unit="folder"):
    folder_path = os.path.join(base_dir, str(i))
    if not os.path.exists(folder_path):
        tqdm.tqdm.write(f"Folder {i} not found")
        continue
    
    is_same_person, face1_exists, face2_exists, error = verify_faces_in_folder(folder_path)
    
    results.append({
        "Folder": i,
        "Is Same Person": is_same_person,
        "Face 1 Exists": face1_exists,
        "Face 2 Exists": face2_exists,
        "Error": error
    })

# Convert results to DataFrame
df_results = pd.DataFrame(results)

# Print summary
print(df_results)

# Optional: Save results to CSV
results_csv_path = os.path.join(project_root, "face_verification_results.csv")
df_results.to_csv(results_csv_path, index=False)

print(f"Face verification complete. Results saved to {results_csv_path}")