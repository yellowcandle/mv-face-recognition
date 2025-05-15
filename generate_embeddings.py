import os
import cv2
import numpy as np
import pandas as pd
from src.core.detector import FaceDetector  # Corrected import path
from src.recognition.face_recognizer import FaceRecognizer
import glob


def find_contestant_photos(contestants_dir, contestant_id):
    """Find all photos for a contestant"""
    photos = []
    # Search for photos like <contestant_id>-1.jpg, <contestant_id>-2.jpg, etc.
    # within any subdirectory of contestants_dir
    for dir_path in glob.glob(os.path.join(contestants_dir, "*")): # Iterate through numbered directories like "1", "2", ...
        if os.path.isdir(dir_path):
            # Look for photos matching the pattern <contestant_id>-*.jpg
            # For example, if contestant_id is "1", it looks for "1-1.jpg", "1-2.jpg", etc.
            # This assumes photos are named like <ID>-<index>.jpg
            photo_pattern = os.path.join(dir_path, f"{contestant_id}-*.jpg")
            found_photos = glob.glob(photo_pattern)
            if found_photos:
                photos.extend(found_photos)
    if not photos: # Fallback: if no photos found with <ID>-<index>.jpg, try <ID>.jpg directly in subdirs
        for dir_path in glob.glob(os.path.join(contestants_dir, "*")):
            if os.path.isdir(dir_path):
                photo_path = os.path.join(dir_path, f"{contestant_id}.jpg")
                if os.path.exists(photo_path):
                    photos.append(photo_path)
                    break # Assuming only one such photo if this fallback is used
    return photos


def main():
    # Initialize paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    contestants_dir = os.path.join(project_root, "source", "photo", "contestants")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")

    # Load contestant information
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info["編號"] = contestant_info["編號"].astype(str)

    # Initialize components
    face_detector = FaceDetector(confidence_threshold=0.3)
    face_recognizer = FaceRecognizer(  # Removed model_path argument
        face_detector=face_detector,
        similarity_threshold=0.6,
        use_arcface=True,  # Explicitly use ArcFace, which is the default
    )

    # Process each contestant
    for _, contestant in contestant_info.iterrows():
        nickname = contestant["暱稱"]
        contestant_id = contestant["編號"]

        # Find all photos for this contestant
        photo_paths = find_contestant_photos(contestants_dir, contestant_id)

        if not photo_paths:
            print(f"Photos not found for {nickname} (ID: {contestant_id})")
            continue

        embeddings = []
        # Determine the directory for saving the averaged embedding.
        # Use the directory of the first photo found for this contestant.
        # This assumes all photos for a contestant are in the same parent numbered directory.
        if photo_paths:
            contestant_photo_parent_dir = os.path.dirname(photo_paths[0])
            generated_dir = os.path.join(contestant_photo_parent_dir, "generated")
            os.makedirs(generated_dir, exist_ok=True)
        else: # Should not happen due to check above, but as a safeguard
            print(f"No photo paths found for {nickname}, cannot determine save directory.")
            continue


        for photo_path in photo_paths:
            try:
                # Load and process image
                image = cv2.imread(photo_path) # pylint: disable=no-member
                if image is None:
                    print(f"Failed to load image {photo_path} for {nickname}")
                    continue

                # Get face embedding
                detected_faces_bboxes = face_detector.detect_faces(image)
                if not detected_faces_bboxes:
                    print(f"No face detected for {nickname} in image {photo_path}")
                    continue

                first_face_data = detected_faces_bboxes[0]
                current_embedding = None

                if isinstance(first_face_data, list):  # Bbox list
                    bbox = first_face_data
                    face_img = face_detector.extract_face(image, bbox, padding=0.1)
                    if face_img is not None:
                        current_embedding = face_recognizer._get_embedding(face_img)
                    else:
                        print(f"Could not extract face for {nickname} from {photo_path}")
                elif hasattr(first_face_data, "bbox"):  # InsightFaceObject
                    if (
                        face_detector.backend == FaceDetector.BACKEND_INSIGHTFACE
                        and hasattr(first_face_data, "normed_embedding")
                        and first_face_data.normed_embedding is not None
                    ):
                        current_embedding = first_face_data.normed_embedding
                    else:
                        bbox = first_face_data.bbox.astype(int)
                        face_img = face_detector.extract_face(
                            image, bbox.tolist(), padding=0.1
                        )
                        if face_img is not None:
                            current_embedding = face_recognizer._get_embedding(face_img)
                        else:
                            print(f"Could not extract face for {nickname} from {photo_path} (InsightFace obj)")
                else:
                    print(f"Unknown face detection result type for {nickname} in {photo_path}")

                if current_embedding is not None and current_embedding.size > 0:
                    embeddings.append(current_embedding)
                else:
                    print(f"Failed to compute embedding for {nickname} from {photo_path}")

            except Exception as e:
                print(f"Error processing photo {photo_path} for {nickname}: {str(e)}")

        if not embeddings:
            print(f"Failed to generate any valid embeddings for {nickname}")
            continue

        # Average the embeddings
        avg_embedding = np.mean(embeddings, axis=0)
        # Normalize the averaged embedding
        norm = np.linalg.norm(avg_embedding)
        if norm > 1e-10: # Avoid division by zero or very small number
            avg_embedding = avg_embedding / norm
        else: # Handle case where average embedding is close to zero (e.g., if all inputs were problematic)
            print(f"Warning: Averaged embedding for {nickname} has near-zero norm. Using as is or consider fallback.")
            # Optionally, could set to a default non-zero vector or skip saving.
            # For now, save it as is, but it might cause issues in similarity computation.

        # Save the averaged embedding
        embedding_path = os.path.join(generated_dir, f"{nickname}_embedding.npy")
        np.save(embedding_path, avg_embedding)
        print(
            f"Generated and saved averaged embedding for {nickname} (ID: {contestant_id}) from {len(embeddings)} photos to {embedding_path}"
        )


if __name__ == "__main__":
    main()
