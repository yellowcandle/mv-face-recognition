import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import insightface
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont

# Define constants
DISTANCE_THRESHOLD = 0.4
FRAME_SKIP = 10  # Process every nth frame

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")

# Initialize InsightFace
app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

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
            img = cv2.imread(img_path)
            faces = app.get(img)
            embeddings.extend([face.normed_embedding for face in faces])
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
    return embeddings

def get_known_faces_embeddings(contestants_dir, selected_contestants, contestant_info):
    """Load and compute embeddings for selected contestants."""
    known_embeddings = {}
    for contestant_name in selected_contestants:
        contestant_number = contestant_info.loc[contestant_info['暱稱'] == contestant_name, '編號'].values[0]
        contestant_path = os.path.join(contestants_dir, str(contestant_number))
        if os.path.isdir(contestant_path):
            image_paths = get_image_paths(contestant_path)
            embeddings = compute_embeddings(image_paths)
            if embeddings:
                known_embeddings[contestant_name] = embeddings
        else:
            print(f"Directory for contestant '{contestant_name}' not found: {contestant_path}")
    return known_embeddings

def match_face(face_embedding, known_embeddings):
    """Compare a face embedding against known embeddings."""
    for name, embeddings_list in known_embeddings.items():
        for known_embedding in embeddings_list:
            known_embedding = known_embedding.flatten()  # {{ Ensure known_embedding is 1D }}
            distance = np.dot(face_embedding, known_embedding)
            if isinstance(distance, np.ndarray):
                if distance.size == 1:
                    distance = distance.item()  # Convert single-element array to scalar
                else:
                    print(f"Unexpected distance array size for {name}: {distance.size}")
                    distance = distance.mean()  # Handle multi-element arrays appropriately
            if distance > DISTANCE_THRESHOLD:
                return name
    return None

def process_frame(frame, known_embeddings):
    """Detect faces in a frame and recognize known faces."""
    matches = []
    try:
        faces = app.get(frame)
        for face in faces:
            face_embedding = face.normed_embedding
            matched_name = match_face(face_embedding, known_embeddings)
            if matched_name:
                matches.append((face, matched_name))
    except Exception as e:
        print(f"Error processing frame: {e}")
    return matches

def draw_utf8_text(img, text, pos, font_size, color):
    """Draw UTF-8 text on the image using Pillow."""
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

def draw_boxes_and_labels(frame, matches):
    """Draw boxes and labels on the frame using Pillow."""
    try:
        # Convert OpenCV image (BGR) to PIL image (RGB)
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        # Load the font
        font_path = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")
        font = ImageFont.truetype(font_path, 30)
        
        for face, name in matches:
            bbox = face.bbox.astype(int)
            # Increase rectangle size
            padding = 10
            bbox_enlarged = [bbox[0]-padding, bbox[1]-padding, bbox[2]+padding, bbox[3]+padding]
            # Draw enlarged rectangle
            draw.rectangle(bbox_enlarged, outline="green", width=3)
            # Increase font size
            larger_font = ImageFont.truetype(font_path, 40)
            # Draw text with increased size
            text_bbox = draw.textbbox((bbox_enlarged[0], bbox_enlarged[1] - 45), name, font=larger_font)
            draw.rectangle(text_bbox, fill="green")
            draw.text((bbox_enlarged[0], bbox_enlarged[1] - 45), name, font=larger_font, fill="white")
        
        # Convert back to OpenCV image (BGR)
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return frame
    except Exception as e:
        print(f"Error drawing boxes and labels: {e}")
        return frame  # Ensure frame is returned even if an error occurs

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

        output_dir = os.path.join(project_root, 'output_frames', video_file)
        os.makedirs(output_dir, exist_ok=True)

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
                        frame_with_boxes = draw_boxes_and_labels(frame, matches)
                        output_frame_path = os.path.join(output_dir, f"frame_{frame_count}.jpg")
                        cv2.imwrite(output_frame_path, frame_with_boxes)  # Updated to use frame_with_boxes
                        for _, matched_name in matches:
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

def get_contestant_image(contestants_dir, contestant, contestant_info):
    """Retrieve the image path for a contestant."""
    contestant_number = contestant_info.loc[contestant_info['暱稱'] == contestant, '編號'].values[0]
    contestant_path = os.path.join(contestants_dir, str(contestant_number))
    image_paths = get_image_paths(contestant_path)
    if image_paths:
        return image_paths[0]
    return None

def compute_face_embedding(image_path):
    """Compute the face embedding for a given image."""
    img = cv2.imread(image_path)
    faces = app.get(img)
    if len(faces) > 0:
        return faces[0].normed_embedding
    return None

def main():
    print("Face Recognition Script - Processing Videos")

    # Load contestant data
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info['暱稱'].tolist()

    # Select contestants
    selected_contestants = select_items(all_contestants, "contestants")

    # Select videos
    all_videos = sorted([
        f for f in os.listdir(videos_dir)
        if os.path.isfile(os.path.join(videos_dir, f))
    ])
    selected_videos = select_items(all_videos, "videos")

    # Load embeddings
    known_embeddings = {}
    for contestant in selected_contestants:
        embedding_file = os.path.join(contestants_dir, f"{contestant}_embedding.npy")
        if os.path.exists(embedding_file):
            embedding = np.load(embedding_file, allow_pickle=True)
            known_embeddings[contestant] = [embedding]  # Ensure embeddings are stored as a list
        else:
            print(f"Computing embedding for {contestant}...")
            contestant_image = get_contestant_image(contestants_dir, contestant, contestant_info)
            if contestant_image is not None:
                embedding = compute_face_embedding(contestant_image)
                if embedding is not None:
                    known_embeddings[contestant] = [embedding]  # Store embedding in a list
                    np.save(embedding_file, [embedding])  # Save as a list to maintain consistency
                else:
                    print(f"Could not compute embedding for {contestant}")
            else:
                print(f"Could not find image for {contestant}")
    print(f"Loaded/computed embeddings for {len(known_embeddings)} contestants.")

    # Process videos
    recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings)

if __name__ == '__main__':
    main()