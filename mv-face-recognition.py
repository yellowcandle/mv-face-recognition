import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont
import mediapipe as mp
import sys
import logging

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

# Initialize MediaPipe pose estimation
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=True,
    model_complexity=2,
    min_detection_confidence=0.5
)

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
    """Extract pose landmarks from an image.
    
    Args:
        img: Input image in BGR format
        
    Returns:
        numpy.ndarray: Normalized pose landmarks or None if no pose detected
    """
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = pose.process(img_rgb)
    
    if results.pose_landmarks:
        landmarks = [[lm.x, lm.y, lm.z] for lm in results.pose_landmarks.landmark]
        return np.array(landmarks)
    return None


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
            
            # Get pose embeddings
            pose_embedding = get_pose_features(img)
            if pose_embedding is not None:
                pose_embeddings.append(pose_embedding)
                
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            
    return face_embeddings, pose_embeddings


def get_known_faces_embeddings(contestants_dir, selected_contestants, contestant_info):
    """Retrieve known face embeddings for selected contestants.

    Args:
        contestants_dir (str): Directory containing contestant images.
        selected_contestants (list): List of selected contestant names.
        contestant_info (DataFrame): DataFrame containing contestant information.

    Returns:
        dict: Dictionary of known embeddings.
    """
    known_embeddings = {}
    for contestant_name in selected_contestants:
        try:
            contestant_number = contestant_info.loc[
                contestant_info["暱稱"] == contestant_name, "編號"
            ].values[0]
            contestant_path = os.path.join(contestants_dir, str(contestant_number))
            if os.path.isdir(contestant_path):
                image_paths = get_image_paths(contestant_path)
                embeddings = compute_embeddings(image_paths)
                if embeddings:
                    known_embeddings[contestant_name] = embeddings
            else:
                print(
                    f"Directory for contestant '{contestant_name}' not found: {contestant_path}"
                )
        except Exception as e:
            print(f"Error retrieving embeddings for {contestant_name}: {e}")
    return known_embeddings


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
                    pose_similarity = max(pose_similarity, 
                        np.dot(pose_embedding.flatten(), known_pose_emb.flatten()) / 
                        (np.linalg.norm(pose_embedding) * np.linalg.norm(known_pose_emb)))
            
            # Combine similarities with weights
            combined_score = 0.7 * face_similarity + 0.3 * pose_similarity
            
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


def draw_utf8_text(img, text, pos, font_size, color):
    """Draw UTF-8 text on an image.

    Args:
        img (ndarray): Image to draw on.
        text (str): Text to draw.
        pos (tuple): Position to draw the text.
        font_size (int): Font size.
        color (str): Color of the text.
    """
    try:
        # Convert OpenCV image (BGR) to PIL image (RGB)
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # Load the font
        font_path = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")
        font = ImageFont.truetype(font_path, font_size)

        # Draw the text
        draw.text(pos, text, font=font, fill=color)

        # Convert back to OpenCV image (BGR)
        img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"Error drawing text: {e}")


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
            # Increase font size even more
            larger_font = ImageFont.truetype(font_path, 60)  # Increased from 40 to 60
            # Draw text with increased size
            text_bbox = draw.textbbox(
                (bbox_enlarged[0], bbox_enlarged[1] - 65), name, font=larger_font
            )  # Adjusted y-coordinate
            draw.rectangle(text_bbox, fill="green")
            draw.text(
                (bbox_enlarged[0], bbox_enlarged[1] - 65),
                name,
                font=larger_font,
                fill="white",
            )  # Adjusted y-coordinate

        # Define font size and color for timestamp
        timestamp_font = ImageFont.truetype(font_path, 40)
        timestamp_color = "yellow"

        # Get image dimensions
        img_width, img_height = pil_img.size

        # Calculate position for timestamp (10 pixels from the bottom-right corner)
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
        return frame  # Ensure frame is returned even if an error occurs


def create_gif_from_frames(frame_paths, output_gif_path, duration=0.5):
    """Create a GIF from a list of frame paths.

    Args:
        frame_paths (list): List of frame file paths.
        output_gif_path (str): Path to save the output GIF.
        duration (int, optional): Duration for each frame in seconds. Defaults to 0.5.
    """
    images = []
    for frame_path in frame_paths:
        img = Image.open(frame_path)
        images.append(img)

    # Save the frames as an animated GIF
    images[0].save(
        output_gif_path,
        save_all=True,
        append_images=images[1:],
        duration=duration * 1000,
        loop=0,
    )
    print(f"GIF saved to {output_gif_path}")


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

        labeled_frames = []  # List to store paths of frames with labels

        with tqdm(
            total=total_frames, desc=f"Frames in {video_file}", leave=False
        ) as pbar:
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


def get_contestant_image(contestants_dir, contestant, contestant_info):
    """Retrieve the image path for a contestant.

    Args:
        contestants_dir (str): Directory containing contestant images.
        contestant (str): Contestant name.
        contestant_info (DataFrame): DataFrame with contestant information.

    Returns:
        str: Path to the contestant's image or None if not found.
    """
    contestant_number = contestant_info.loc[
        contestant_info["暱稱"] == contestant, "編號"
    ].values[0]
    contestant_path = os.path.join(contestants_dir, str(contestant_number))
    image_paths = get_image_paths(contestant_path)
    if image_paths:
        return image_paths[0]
    return None


def compute_face_embedding(image_path):
    """Compute the face embedding for a given image.

    Args:
        image_path (str): Path to the image.

    Returns:
        ndarray: Face embedding or None if no face detected.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error reading image {image_path}.")
        return None
    
    faces = app.get(img)
    if len(faces) > 0:
        return faces[0].normed_embedding
    return None


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
