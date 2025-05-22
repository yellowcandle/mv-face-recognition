import os

import cv2
import matplotlib.pyplot as plt
import numpy as np

from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer


def load_gallery_embeddings(embedding_dir="source/photo/contestants/embeddings"):
    """Load embeddings from the gallery directory."""
    print(f"Loading embeddings from: {os.path.abspath(embedding_dir)}")

    os.path.join(embedding_dir, "*_embedding.npy")
    embedding_files = [f for f in os.listdir(embedding_dir) if f.endswith("_embedding.npy")]
    print(f"Found {len(embedding_files)} embedding files")

    gallery_nicknames = []
    gallery_embeddings = []
    embedding_dimensions = None

    for f in embedding_files:
        try:
            file_path = os.path.join(embedding_dir, f)
            arr = np.load(file_path)
            arr = arr.flatten()

            # Accept any 1D embedding array
            if len(arr.shape) == 1:
                if embedding_dimensions is None:
                    # Set the first encountered dimension as our standard
                    embedding_dimensions = arr.shape[0]
                    print(f"Using embedding dimension: {embedding_dimensions}")

                # If dimensions don't match, resize the embedding
                if arr.shape[0] != embedding_dimensions:
                    print(
                        f"Embedding in {os.path.basename(f)} has dimension {arr.shape[0]}, "
                        f"resizing to {embedding_dimensions}"
                    )

                    # Resize strategy: either truncate or pad with zeros
                    if arr.shape[0] > embedding_dimensions:
                        # Truncate to the standard dimension
                        arr = arr[:embedding_dimensions]
                    else:
                        # Pad with zeros
                        padding = np.zeros(embedding_dimensions - arr.shape[0])
                        arr = np.concatenate([arr, padding])

                nickname = os.path.basename(f).replace("_embedding.npy", "")
                gallery_nicknames.append(nickname)
                gallery_embeddings.append(arr)
            else:
                print(
                    f"Skipping embedding file {os.path.abspath(f)}: not a 1D array, shape={arr.shape}"
                )
        except Exception as e:
            print(f"Error loading embedding from {f}: {str(e)}")

    if not gallery_embeddings:
        print("No embeddings found in gallery! Face recognition will not work.")
        return np.empty((0, 128), dtype=np.float32), []

    print(f"Loaded {len(gallery_embeddings)} embeddings from gallery")

    return np.stack(gallery_embeddings), gallery_nicknames


def get_top_matches(face_embedding, gallery_embeddings, gallery_nicknames, top_n=5, threshold=0.4):
    """Find the top matches for a face embedding from the gallery."""
    face_emb_norm = np.linalg.norm(face_embedding)
    if face_emb_norm == 0:  # Avoid division by zero for detected embedding
        return []

    norm_face_embedding = face_embedding / face_emb_norm

    if norm_face_embedding.shape[0] != gallery_embeddings.shape[1]:
        print(
            f"Face embedding dimension {norm_face_embedding.shape[0]} doesn't match gallery "
            f"dimension {gallery_embeddings.shape[1]}. Adjusting..."
        )
        if norm_face_embedding.shape[0] > gallery_embeddings.shape[1]:
            norm_face_embedding = norm_face_embedding[: gallery_embeddings.shape[1]]
        else:
            padding = np.zeros(gallery_embeddings.shape[1] - norm_face_embedding.shape[0])
            norm_face_embedding = np.concatenate([norm_face_embedding, padding])

    sims = np.dot(gallery_embeddings, norm_face_embedding)
    top_idx_all = np.argsort(sims)[::-1][:top_n]

    filtered_matches = []
    for i in top_idx_all:
        if sims[i] >= threshold:
            filtered_matches.append((gallery_nicknames[i], sims[i], i))

    return filtered_matches


def draw_faces_with_labels(image, faces, matches_list):
    """Draw faces with labels on the image."""
    img_copy = image.copy()

    for i, (face, matches) in enumerate(zip(faces, matches_list, strict=False)):
        box = face.bbox.astype(int)
        x1, y1, x2, y2 = box

        color = (0, 255, 0)
        thickness = 2
        cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, thickness)

        label = ""
        if matches:
            label = f"{matches[0][0]} ({matches[0][1]:.2f})"
        else:
            label = "Unknown (0.00)"

        cv2.putText(
            img_copy,
            f"{i + 1}: {label}",
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            thickness,
        )

    return img_copy


def main():
    # Initialize the detector and recognizer
    core_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto"
    )

    # Try different recognition thresholds
    thresholds = [0.3, 0.35, 0.4, 0.45, 0.5]

    for threshold in thresholds:
        print(f"\nTesting with recognition threshold: {threshold}")
        face_recognizer = FaceRecognizer(
            face_detector=core_detector, similarity_threshold=threshold, use_arcface=True
        )

        # Load gallery embeddings
        gallery_embeddings, gallery_nicknames = load_gallery_embeddings()

        # Load the test image
        test_image_path = "source/images/test/original.jpeg"
        image = cv2.imread(test_image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Detect faces
        faces = core_detector.detect_faces(image_rgb)
        print(f"Detected {len(faces)} faces")

        # For each face, get embeddings and matches
        matches_list = []
        for i, face in enumerate(faces):
            face_img = core_detector.extract_face(image_rgb, face.bbox.astype(int), padding=0.1)
            if face_img is not None:
                embedding = face_recognizer._get_embedding(face_img)
                top_matches = get_top_matches(
                    embedding, gallery_embeddings, gallery_nicknames, top_n=3, threshold=threshold
                )
                matches_list.append(top_matches)
                print(f"Face {i + 1} matches: {top_matches}")
            else:
                print(f"Could not extract face {i + 1}")
                matches_list.append([])

        # Draw faces with labels
        labeled_image = draw_faces_with_labels(image_rgb, faces, matches_list)

        # Save the result
        result_path = f"source/images/test/result_threshold_{threshold:.2f}.jpeg"
        plt.figure(figsize=(12, 8))
        plt.imshow(labeled_image)
        plt.title(f"Face Recognition Results (Threshold: {threshold})")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(result_path)
        print(f"Saved result to {result_path}")


if __name__ == "__main__":
    main()
