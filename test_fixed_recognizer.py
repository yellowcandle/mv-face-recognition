import os

import cv2
import matplotlib.pyplot as plt
import numpy as np

from src.core.detector import FaceDetector
from src.recognition.fixed_face_recognizer import FixedFaceRecognizer


def load_gallery_embeddings(embedding_dir="source/photo/contestants/embeddings"):
    """Load embeddings from the gallery directory."""
    print(f"Loading embeddings from: {os.path.abspath(embedding_dir)}")

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
                    embedding_dimensions = arr.shape[0]
                    print(f"Using embedding dimension: {embedding_dimensions}")

                # For this test, we'll keep the original embeddings unchanged
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

    return gallery_embeddings, gallery_nicknames


def get_top_matches(face_embedding, gallery_embeddings, gallery_nicknames, top_n=5, threshold=0.6):
    """Find the top matches for a face embedding from the gallery."""
    face_emb_norm = np.linalg.norm(face_embedding)
    if face_emb_norm == 0:  # Avoid division by zero for detected embedding
        return []

    norm_face_embedding = face_embedding / face_emb_norm

    similarities = []
    for i, gallery_emb in enumerate(gallery_embeddings):
        # Ensure compatible dimensions
        if len(gallery_emb) != len(norm_face_embedding):
            if len(gallery_emb) > len(norm_face_embedding):
                # Truncate gallery embedding
                comp_embedding = gallery_emb[: len(norm_face_embedding)]
            else:
                # Pad with zeros
                comp_embedding = np.zeros(len(norm_face_embedding), dtype=np.float32)
                comp_embedding[: len(gallery_emb)] = gallery_emb
        else:
            comp_embedding = gallery_emb

        # Ensure normalized
        gallery_norm = np.linalg.norm(comp_embedding)
        if gallery_norm > 1e-10:
            comp_embedding = comp_embedding / gallery_norm

        # Compute similarity
        similarity = np.dot(norm_face_embedding, comp_embedding)
        similarities.append((gallery_nicknames[i], similarity, i))

    # Sort by similarity (descending)
    sorted_similarities = sorted(similarities, key=lambda x: x[1], reverse=True)

    # Filter by threshold
    filtered_matches = [
        (name, sim, idx) for name, sim, idx in sorted_similarities[:top_n] if sim >= threshold
    ]
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
    # Initialize the detector
    core_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto"
    )

    # Test different configurations
    test_configs = [
        {"use_arcface": True, "similarity_threshold": 0.6, "norm_values": "SFace [0.5, 0.5, 0.5]"},
        {"use_arcface": True, "similarity_threshold": 0.7, "norm_values": "SFace [0.5, 0.5, 0.5]"},
        {"use_arcface": False, "similarity_threshold": 0.6, "norm_values": "OpenCV DNN"},
    ]

    # Load gallery embeddings
    gallery_embeddings, gallery_nicknames = load_gallery_embeddings()

    # Load the test image
    test_image_path = "source/images/test/original.jpeg"
    image = cv2.imread(test_image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Detect faces (do this once)
    faces = core_detector.detect_faces(image_rgb)
    print(f"Detected {len(faces)} faces")

    for idx, config in enumerate(test_configs):
        print(f"\nTesting configuration {idx + 1}:")
        print(f"  - use_arcface: {config['use_arcface']}")
        print(f"  - threshold: {config['similarity_threshold']}")
        print(f"  - normalization: {config['norm_values']}")

        # Initialize recognizer with this configuration
        face_recognizer = FixedFaceRecognizer(
            face_detector=core_detector,
            similarity_threshold=config["similarity_threshold"],
            use_arcface=config["use_arcface"],
        )

        # For each face, get embeddings and matches
        matches_list = []
        for i, face in enumerate(faces):
            face_img = core_detector.extract_face(image_rgb, face.bbox.astype(int), padding=0.1)
            if face_img is not None:
                embedding = face_recognizer._get_embedding(face_img)
                top_matches = get_top_matches(
                    embedding,
                    gallery_embeddings,
                    gallery_nicknames,
                    top_n=3,
                    threshold=config["similarity_threshold"],
                )
                matches_list.append(top_matches)
                print(f"Face {i + 1} matches: {top_matches}")
            else:
                print(f"Could not extract face {i + 1}")
                matches_list.append([])

        # Draw faces with labels
        labeled_image = draw_faces_with_labels(image_rgb, faces, matches_list)

        # Create configuration description for filename
        config_desc = f"fixed_{idx + 1}_arcface_{config['use_arcface']}_thresh_{config['similarity_threshold']}"

        # Save the result
        result_path = f"source/images/test/result_{config_desc}.jpeg"
        plt.figure(figsize=(12, 8))
        plt.imshow(labeled_image)
        plt.title(f"Face Recognition with Fixed Recognizer (Config {idx + 1})")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(result_path)
        print(f"Saved result to {result_path}")


if __name__ == "__main__":
    main()
