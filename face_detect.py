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
    images = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png'))]
    if len(images) != 2:
        return None, f"Expected 2 images, found {len(images)}"
    
    img1_path = os.path.join(folder_path, images[0])
    img2_path = os.path.join(folder_path, images[1])
    
    try:
        result = DeepFace.verify(img1_path=img1_path, img2_path=img2_path)
        return result["verified"], None
    except Exception as e:
        return None, f"Error processing images: {str(e)}"

# Prepare results dataframe
results = []

# Iterate through all 96 folders
for i in tqdm.tqdm(range(1, 97), desc="Verifying faces", unit="folder"):
    folder_path = os.path.join(base_dir, str(i))
    if not os.path.exists(folder_path):
        tqdm.tqdm.write(f"Folder {i} not found")
        continue
    
    is_same_person, error = verify_faces_in_folder(folder_path)
    
    results.append({
        "Folder": i,
        "Is Same Person": is_same_person,
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