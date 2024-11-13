import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont
import sys
import logging
from pose_recognition import PoseRecognition

logging.basicConfig(level=logging.DEBUG)

# Define constants
# User input for distance threshold and frame skip
try:
    DISTANCE_THRESHOLD = float(input("Enter the distance threshold (e.g., 0.4): "))
    FRAME_SKIP = int(input("Enter the frame skip value (e.g., 5): "))
except ValueError as e:
    print(f"Invalid input: {e}. Please enter numeric values.")
    sys.exit(1)

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")

# Initialize InsightFace
print("Initializing InsightFace...")
try:
    print("Creating FaceAnalysis instance...")
    app = FaceAnalysis(name='buffalo_l')
    print("Preparing FaceAnalysis...")
    app.prepare(ctx_id=-1, det_size=(640, 640), download=True, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    print("InsightFace initialized successfully.")
except Exception as e:
    print(f"Unexpected error during InsightFace initialization: {type(e)}: {str(e)}")
    sys.exit(1)

# Initialize PoseRecognition
pose_recognizer = PoseRecognition()

# Initialize progress bar for script setup
setup_steps = ["Loading modules", "Setting up directories", "Initializing InsightFace"]
with tqdm(total=len(setup_steps), desc="Initializing script") as pbar:
    for step in setup_steps:
        pbar.set_description(f"Initializing script: {step}")
        pbar.update(1)

print("Script initialization complete.")


def get_image_paths(contestant_path):
    """Retrieve image paths from a contestant directory.

    Args:
        contestant_path (str): Path to the contestant's directory.

    Returns:
        list: List of image file paths.
    """
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith((".jpg", ".png"))
    ]


def get_pose_features(img):
    """Extract pose features from an image using enhanced pose recognition.
    
    Args:
        img: Input image in BGR format
        
    Returns:
        numpy.ndarray: Enhanced pose features or None if no face detected
    """
    return pose_recognizer.get_pose_features(img)


def compute_embeddings(image_paths):
    """Compute face and pose embeddings for given images.
    
    Args:
        image_paths (list): List of image file paths
        
    Returns:
        tuple: Lists of face and pose embeddings
    """
    face_embeddings = []
    pose_embeddings = []
    
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is None:
                print(f"Error reading image {img_path}. Skipping.")
                continue
            
            # Get face embeddings
            faces = app.get(img)
            face_embeddings.extend([face.normed_embedding for face in faces])
            
            # Get enhanced pose embeddings
            pose_embedding = get_pose_features(img)
            if pose_embedding is not None:
                pose_embeddings.append(pose_embedding)
                
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            
    return face_embeddings, pose_embeddings


def match_face(face_embedding, pose_embedding, known_embeddings):
    """Match face and pose embeddings against known embeddings.
    
    Args:
        face_embedding: Face embedding to match
        pose_embedding: Pose embedding to match
        known_embeddings: Dictionary of known embeddings
        
    Returns:
        str: Matched name or None
    """
    best_match = None
    best_score = -1
    
    for name, (known_face_embeddings, known_pose_embeddings) in known_embeddings.items():
        for known_face_emb in known_face_embeddings:
            # Calculate face similarity
            face_similarity = np.dot(face_embedding, known_face_emb)
            
            # Calculate pose similarity if available
            pose_similarity = 0.0
            if pose_embedding is not None and known_pose_embeddings:
                for known_pose_emb in known_pose_embeddings:
                    # Calculate similarity using enhanced pose features
                    pose_similarity = max(pose_similarity, 
                        np.dot(pose_embedding, known_pose_emb) / 
                        (np.linalg.norm(pose_embedding) * np.linalg.norm(known_pose_emb)))
            
            # Combine similarities with adjusted weights
            # Increased weight for pose similarity since it's more reliable now
            combined_score = 0.6 * face_similarity + 0.4 * pose_similarity
            
            if combined_score > best_score and combined_score > DISTANCE_THRESHOLD:
                best_score = combined_score
                best_match = name
                
    return best_match


def process_frame(frame, known_embeddings):
    """Process a video frame to detect and recognize faces with pose.
    
    Args:
        frame: Video frame
        known_embeddings: Dictionary of known embeddings
        
    Returns:
        list: List of (face, name) tuples for matched faces
    """
    matches = []
    try:
        faces = app.get(frame)
        pose_embedding = get_pose_features(frame)
        
        for face in faces:
            face_embedding = face.normed_embedding
            matched_name = match_face(face_embedding, pose_embedding, known_embeddings)
            if matched_name:
                matches.append((face, matched_name))
    except Exception as e:
        print(f"Error processing frame: {e}")
    return matches


def draw_boxes_and_labels(frame, matches, timestamp):
    """Draw bounding boxes and labels on the frame.

    Args:
        frame (ndarray): Frame to draw on.
        matches (list): List of matches.
        timestamp (str): Timestamp to display.
    """
    try:
        # Convert OpenCV image (BGR) to PIL image (RGB)
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # Load the font
        font_path = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")

        for face, name in matches:
            bbox = face.bbox.astype(int)
            # Increase rectangle size
            padding = 10
            bbox_enlarged = [
                bbox[0] - padding,
                bbox[1] - padding,
                bbox[2] + padding,
                bbox[3] + padding,
            ]
            # Draw enlarged rectangle
            draw.rectangle(bbox_enlarged, outline="green", width=3)
            # Increase font size
            larger_font = ImageFont.truetype(font_path, 60)
            # Draw text with increased size
            text_bbox = draw.textbbox(
                (bbox_enlarged[0], bbox_enlarged[1] - 65), name, font=larger_font
            )
            draw.rectangle(text_bbox, fill="green")
            draw.text(
                (bbox_enlarged[0], bbox_enlarged[1] - 65),
                name,
                font=larger_font,
                fill="white",
            )

        # Define font size and color for timestamp
        timestamp_font = ImageFont.truetype(font_path, 40)
        timestamp_color = "yellow"

        # Get image dimensions
        img_width, img_height = pil_img.size

        # Calculate position for timestamp
        text_bbox = draw.textbbox((0, 0), timestamp, font=timestamp_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        position = (img_width - text_width - 10, img_height - text_height - 10)

        # Draw the timestamp
        draw.text(position, timestamp, font=timestamp_font, fill=timestamp_color)

        # Convert back to OpenCV image (BGR)
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return frame
    except Exception as e:
        print(f"Error drawing boxes and labels: {e}")
        return frame


def recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings):
    """Recognize faces in selected videos and prepare frames for GIF creation.

    Args:
        videos_dir (str): Directory containing video files.
        selected_videos (list): List of selected video file names.
        known_embeddings (dict): Dictionary of known embeddings.
    """
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
        fps = cap.get(cv2.CAP_PROP_FPS)

        output_dir = os.path.join(project_root, "output_frames", video_file)
        os.makedirs(output_dir, exist_ok=True)

        labeled_frames = []

        with tqdm(total=total_frames, desc=f"Frames in {video_file}", leave=False) as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                pbar.update(1)
                if frame_count % FRAME_SKIP == 0:
                    matches = process_frame(frame, known_embeddings)
                    if matches:
                        timestamp_seconds = frame_count / fps
                        timestamp_formatted = "{:02}:{:02}".format(
                            int(timestamp_seconds // 60), int(timestamp_seconds % 60)
                        )
                        frame_with_boxes = draw_boxes_and_labels(
                            frame, matches, timestamp_formatted
                        )
                        output_frame_path = os.path.join(
                            output_dir, f"frame_{frame_count:04d}.jpg"
                        )
                        cv2.imwrite(output_frame_path, frame_with_boxes)
                        labeled_frames.append(output_frame_path)
                        for _, matched_name in matches:
                            print(
                                f"Found {matched_name} in {video_file} at frame {frame_count}"
                            )
                            results.append(
                                {
                                    "Video": video_file,
                                    "Frame": frame_count,
                                    "Name": matched_name,
                                }
                            )
        cap.release()

    save_results(results, project_root)


def save_results(results, project_root):
    """Save recognition results to a CSV file.

    Args:
        results (list): List of recognition results.
        project_root (str): Project root directory.
    """
    if results:
        df = pd.DataFrame(results)
        output_csv = os.path.join(project_root, "video_recognition_results.csv")
        df.to_csv(output_csv, index=False)
        print(f"\nResults saved to {output_csv}")
    else:
        print("No faces recognized in videos.")


def select_items(options, item_type):
    """Allow user to select items from a list.

    Args:
        options (list): List of available options.
        item_type (str): Type of items (e.g., "contestants", "videos").

    Returns:
        list: List of selected items.
    """
    print(f"\nAvailable {item_type}:")
    for idx, name in enumerate(options, 1):
        print(f"{idx}. {name}")
    print(f"{len(options) + 1}. Select all")

    indices = input(
        f"\nEnter the numbers of the {item_type} you want to select, separated by commas (e.g., 1,3,5), or '{len(options) + 1}' to select all: "
    )

    if indices.strip() == str(len(options) + 1):
        return options

    selected_indices = [
        int(i.strip()) - 1 for i in indices.split(",") if i.strip().isdigit()
    ]
    selected_items = [options[i] for i in selected_indices if 0 <= i < len(options)]
    return selected_items


def get_contestant_embeddings(contestants_dir, contestant, contestant_info):
    """Get face and pose embeddings for a contestant.
    
    Args:
        contestants_dir (str): Directory containing contestant images.
        contestant (str): Contestant name.
        contestant_info (DataFrame): DataFrame with contestant information.
        
    Returns:
        tuple: Face and pose embeddings or (None, None) if not found.
    """
    contestant_number = contestant_info.loc[
        contestant_info["暱稱"] == contestant, "編號"
    ].values[0]
    contestant_path = os.path.join(contestants_dir, str(contestant_number))
    image_paths = get_image_paths(contestant_path)
    
    if image_paths:
        return compute_embeddings(image_paths)
    return None, None


def main():
    print("Face Recognition Script - Processing Videos")

    # Load contestant data
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info["暱稱"].tolist()

    # Select contestants
    selected_contestants = select_items(all_contestants, "contestants")

    # Select videos
    all_videos = sorted(
        [
            f
            for f in os.listdir(videos_dir)
            if os.path.isfile(os.path.join(videos_dir, f))
        ]
    )
    selected_videos = select_items(all_videos, "videos")

    # Load embeddings
    known_embeddings = {}
    for contestant in selected_contestants:
        face_embedding_file = os.path.join(contestants_dir, f"{contestant}_face_embedding.npy")
        pose_embedding_file = os.path.join(contestants_dir, f"{contestant}_pose_embedding.npy")
        
        if os.path.exists(face_embedding_file) and os.path.exists(pose_embedding_file):
            face_embeddings = np.load(face_embedding_file, allow_pickle=True)
            pose_embeddings = np.load(pose_embedding_file, allow_pickle=True)
            known_embeddings[contestant] = (face_embeddings, pose_embeddings)
        else:
            print(f"Computing embeddings for {contestant}...")
            face_embeddings, pose_embeddings = get_contestant_embeddings(
                contestants_dir, contestant, contestant_info
            )
            if face_embeddings is not None:
                known_embeddings[contestant] = (face_embeddings, pose_embeddings)
                np.save(face_embedding_file, face_embeddings)
                if pose_embeddings is not None:
                    np.save(pose_embedding_file, pose_embeddings)
            else:
                print(f"Could not compute embeddings for {contestant}")

    print(f"Loaded/computed embeddings for {len(known_embeddings)} contestants.")

    # Process videos
    recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings)


if __name__ == "__main__":
    main()
