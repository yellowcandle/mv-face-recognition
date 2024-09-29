import os
import cv2
from deepface import DeepFace
# from deepface.commons import distance as dst
import pandas as pd
from tqdm import tqdm
from deepface.modules import verification

distance = verification.find_euclidean_distance(x, y)

# Define constants
MODEL_NAME = 'Facenet'
DETECTOR_BACKEND = 'opencv'
DISTANCE_THRESHOLD = 0.4
FRAME_SKIP = 30  # Process every nth frame

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")

def get_image_paths(contestant_path):
    """Retrieve image paths for a contestant."""
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith(('.jpg', '.png'))
    ]

def compute_embeddings(image_paths):
    """Compute embeddings for a list of image paths."""
    embeddings = []
    for img_path in image_paths:
        try:
            embedding_objs = DeepFace.represent(
                img_path=img_path,
                model_name=MODEL_NAME,
                enforce_detection=False
            )
            embeddings.extend([obj["embedding"] for obj in embedding_objs])
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
    return embeddings

def get_known_faces_embeddings(contestants_dir, selected_contestants):
    """Load and compute embeddings for selected contestants."""
    known_embeddings = {}
    for contestant_name in selected_contestants:
        contestant_path = os.path.join(contestants_dir, contestant_name)
        if os.path.isdir(contestant_path):
            image_paths = get_image_paths(contestant_path)
            embeddings = compute_embeddings(image_paths)
            if embeddings:
                known_embeddings[contestant_name] = embeddings
    return known_embeddings

def match_face(face_embedding, known_embeddings):
    """Compare a face embedding against known embeddings."""
    for name, embeddings_list in known_embeddings.items():
        for known_embedding in embeddings_list:
            distance = dst.findCosineDistance(face_embedding, known_embedding)
            if distance <= DISTANCE_THRESHOLD:
                return name
    return None

def process_frame(frame, known_embeddings):
    """Detect faces in a frame and recognize known faces."""
    matches = []
    try:
        faces = DeepFace.extract_faces(
            img_path=frame,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=False
        )
        for face in faces:
            face_img = face["face"]
            embedding_objs = DeepFace.represent(
                img_path=face_img,
                model_name=MODEL_NAME,
                enforce_detection=False
            )
            for obj in embedding_objs:
                face_embedding = obj["embedding"]
                matched_name = match_face(face_embedding, known_embeddings)
                if matched_name:
                    matches.append(matched_name)
    except Exception as e:
        print(f"Error processing frame: {e}")
    return matches

def recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings):
    """Recognize faces in selected videos."""
    results = []
    for video_file in tqdm(selected_videos, desc="Processing videos"):
        video_path = os.path.join(videos_dir, video_file)
        if not os.path.isfile(video_path):
            print(f"Video file {video_file} not found.")
            continue

        print(f"\nProcessing video: {video_file}")
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        with tqdm(total=total_frames, desc=f"Frames in {video_file}", leave=False) as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                pbar.update(1)
                if frame_count % FRAME_SKIP == 0:
                    matches = process_frame(frame, known_embeddings)
                    for matched_name in matches:
                        print(f"Found {matched_name} in {video_file} at frame {frame_count}")
                        results.append({
                            'Video': video_file,
                            'Frame': frame_count,
                            'Name': matched_name
                        })
        cap.release()
    save_results(results, project_root)

def save_results(results, project_root):
    """Save recognition results to a CSV file."""
    if results:
        df = pd.DataFrame(results)
        output_csv = os.path.join(project_root, 'video_recognition_results.csv')
        df.to_csv(output_csv, index=False)
        print(f"\nResults saved to {output_csv}")
    else:
        print("No faces recognized in videos.")

def select_items(options, item_type):
    """Allow user to select items from a list."""
    print(f"\nAvailable {item_type}:")
    for idx, name in enumerate(options, 1):
        print(f"{idx}. {name}")
    indices = input(f"\nEnter the numbers of the {item_type} you want to select, separated by commas (e.g., 1,3,5): ")
    selected_indices = [
        int(i.strip()) - 1
        for i in indices.split(",") if i.strip().isdigit()
    ]
    selected_items = [
        options[i]
        for i in selected_indices
        if 0 <= i < len(options)
    ]
    return selected_items

def main():
    print("Face Recognition Script - Processing Videos")

    # Select contestants
    all_contestants = sorted([
        name for name in os.listdir(contestants_dir)
        if os.path.isdir(os.path.join(contestants_dir, name))
    ])
    selected_contestants = select_items(all_contestants, "contestants")

    # Select videos
    all_videos = sorted([
        f for f in os.listdir(videos_dir)
        if os.path.isfile(os.path.join(videos_dir, f))
    ])
    selected_videos = select_items(all_videos, "videos")

    # Load embeddings
    known_embeddings = get_known_faces_embeddings(contestants_dir, selected_contestants)
    print(f"Loaded embeddings for {len(known_embeddings)} contestants.")

    # Process videos
    recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings)

if __name__ == '__main__':
    main()
