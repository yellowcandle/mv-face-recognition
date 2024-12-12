import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
from insightface.app import FaceAnalysis
from PIL import Image, ImageFont, ImageDraw
import sys
import logging
from pose_recognition import PoseRecognition
import torch
from segment_anything import sam_model_registry, SamPredictor
from dataclasses import dataclass
from typing import Dict, List, Tuple
import threading
from moviepy.editor import VideoFileClip

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
    app.prepare(ctx_id=-1, det_size=(640, 640))
    print("InsightFace initialized successfully.")
except Exception as e:
    print(f"Unexpected error during InsightFace initialization: {type(e)}: {str(e)}")
    sys.exit(1)

# Initialize PoseRecognition
pose_recognizer = PoseRecognition()

# Initialize SAM model
print("Initializing SAM model...")
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
MODEL_TYPE = "vit_h"
CHECKPOINT_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
CHECKPOINT_PATH = os.path.join(project_root, "sam_vit_h_4b8939.pth")

# Download checkpoint if not exists
if not os.path.exists(CHECKPOINT_PATH):
    print(f"Downloading SAM checkpoint from {CHECKPOINT_URL}...")
    import urllib.request
    urllib.request.urlretrieve(CHECKPOINT_URL, CHECKPOINT_PATH)
    print("Download complete!")

sam = sam_model_registry[MODEL_TYPE](checkpoint=CHECKPOINT_PATH)
sam.to(device=DEVICE)
predictor = SamPredictor(sam)

# Initialize progress bar for script setup
setup_steps = ["Loading modules", "Setting up directories", "Initializing InsightFace", "Initializing SAM model"]
with tqdm(total=len(setup_steps), desc="Initializing script") as pbar:
    for step in setup_steps:
        pbar.set_description(f"Initializing script: {step}")
        pbar.update(1)

print("Script initialization complete.")

@dataclass
class TrackedObject:
    id: int
    label: str
    bbox: np.ndarray
    mask: np.ndarray
    embedding: np.ndarray
    last_seen: int

class ContestantTracker:
    def __init__(self):
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_id = 0
        self.max_frames_missing = 30
        self.lock = threading.Lock()

    def update(self, frame_idx: int, detections: List[Tuple[str, np.ndarray, np.ndarray, np.ndarray]]):
        with self.lock:
            # Update existing tracks
            current_ids = set()
            for label, bbox, mask, embedding in detections:
                best_id = None
                best_score = float('inf')
                
                for obj_id, tracked in self.tracked_objects.items():
                    if tracked.last_seen < frame_idx - self.max_frames_missing:
                        continue
                    
                    # Compute similarity score (combine embedding and IoU)
                    emb_dist = np.linalg.norm(embedding - tracked.embedding)
                    iou = self._compute_iou(mask, tracked.mask)
                    score = emb_dist - 0.5 * iou  # Weight IoU more heavily
                    
                    if score < best_score and score < 0.7:  # Threshold for matching
                        best_score = score
                        best_id = obj_id

                if best_id is not None:
                    # Update existing track
                    self.tracked_objects[best_id] = TrackedObject(
                        best_id, label, bbox, mask, embedding, frame_idx
                    )
                    current_ids.add(best_id)
                else:
                    # Create new track
                    new_id = self.next_id
                    self.next_id += 1
                    self.tracked_objects[new_id] = TrackedObject(
                        new_id, label, bbox, mask, embedding, frame_idx
                    )
                    current_ids.add(new_id)

            # Remove old tracks
            self.tracked_objects = {
                k: v for k, v in self.tracked_objects.items()
                if v.last_seen >= frame_idx - self.max_frames_missing
            }

    def get_active_tracks(self, frame_idx: int) -> List[TrackedObject]:
        with self.lock:
            return [
                obj for obj in self.tracked_objects.values()
                if obj.last_seen >= frame_idx - self.max_frames_missing
            ]

    @staticmethod
    def _compute_iou(mask1: np.ndarray, mask2: np.ndarray) -> float:
        intersection = np.logical_and(mask1, mask2).sum()
        union = np.logical_or(mask1, mask2).sum()
        return intersection / union if union > 0 else 0.0

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
            face_embedding = face.embedding
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


def process_frame_with_segmentation(frame, known_embeddings, predictor, tracker, frame_idx):
    """Process a video frame with segmentation and tracking.
    
    Args:
        frame: Video frame
        known_embeddings: Dictionary of known embeddings
        predictor: SAM predictor instance
        tracker: ContestantTracker instance
        frame_idx: Current frame index
        
    Returns:
        tuple: Processed frame and list of tracked objects
    """
    # Detect faces and get embeddings
    faces = app.get(frame)
    
    if len(faces) > 0:
        # Prepare image for SAM
        predictor.set_image(frame)
        
        detections = []
        for face in faces:
            # Get face embedding and match
            face_embedding = face.embedding
            pose_embedding = get_pose_features(frame)
            
            name = match_face(face_embedding, pose_embedding, known_embeddings)
            if name is None:
                continue
                
            # Get segmentation mask using face bbox as prompt
            bbox = face.bbox.astype(int)
            input_box = np.array([bbox[0], bbox[1], bbox[2], bbox[3]])
            masks, _, _ = predictor.predict(
                point_coords=None,
                point_labels=None,
                box=input_box[None, :],
                multimask_output=False,
            )
            mask = masks[0]
            
            # Expand mask to include full body using pose information
            if pose_embedding is not None:
                # Use pose keypoints to expand mask downward
                pose_bbox = pose_recognizer.get_pose_bbox(frame)
                if pose_bbox is not None:
                    expanded_box = np.array([
                        min(bbox[0], pose_bbox[0]),
                        min(bbox[1], pose_bbox[1]),
                        max(bbox[2], pose_bbox[2]),
                        max(bbox[3], pose_bbox[3])
                    ])
                    masks, _, _ = predictor.predict(
                        point_coords=None,
                        point_labels=None,
                        box=expanded_box[None, :],
                        multimask_output=False,
                    )
                    mask = np.logical_or(mask, masks[0])
            
            detections.append((name, bbox, mask, face_embedding))
        
        # Update tracker
        tracker.update(frame_idx, detections)
        tracked_objects = tracker.get_active_tracks(frame_idx)
        
        # Apply segmentation masks and draw labels
        result_frame = frame.copy()
        for obj in tracked_objects:
            # Apply segmentation mask
            result_frame[~obj.mask] = result_frame[~obj.mask] * 0.3  # Dim background
            
            # Calculate label position (above head)
            label_y = max(0, int(obj.bbox[1] - 30))
            label_x = int((obj.bbox[0] + obj.bbox[2]) / 2)
            
            # Draw label with tracking ID
            label_text = f"{obj.label} (ID: {obj.id})"
            cv2.putText(
                result_frame,
                label_text,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,  # Larger font size
                (255, 255, 255),  # White color
                3,    # Thicker outline
                cv2.LINE_AA
            )
            cv2.putText(
                result_frame,
                label_text,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 0, 0),  # Black color
                1,
                cv2.LINE_AA
            )
        
        return result_frame, tracked_objects
    
    return frame, []


def recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings):
    """Enhanced version with segmentation and tracking"""
    tracker = ContestantTracker()
    
    for video_file in selected_videos:
        video_path = os.path.join(videos_dir, video_file)
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Extract audio using moviepy
        video_clip = VideoFileClip(video_path)
        audio = video_clip.audio
        
        # Setup output video
        output_path = os.path.join(videos_dir, f"processed_{video_file}")
        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
        
        frame_idx = 0
        with tqdm(total=total_frames, desc=f"Processing {video_file}") as pbar:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % FRAME_SKIP == 0:
                    # Process frame with segmentation and tracking
                    processed_frame, _ = process_frame_with_segmentation(
                        frame, known_embeddings, predictor, tracker, frame_idx
                    )
                else:
                    processed_frame = frame
                
                out.write(processed_frame)
                frame_idx += 1
                pbar.update(1)
        
        # Clean up video capture and writer
        cap.release()
        out.release()
        
        # Add audio back to the processed video
        processed_video = VideoFileClip(output_path)
        final_video = processed_video.set_audio(audio)
        final_output_path = os.path.join(videos_dir, f"final_processed_{video_file}")
        final_video.write_videofile(final_output_path, codec='libx264', audio_codec='aac')
        
        # Clean up temporary files
        os.remove(output_path)
        processed_video.close()
        video_clip.close()


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
