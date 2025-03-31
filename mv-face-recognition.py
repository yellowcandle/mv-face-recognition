import os
import shutil
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import argparse
import torch

# Configure environment before importing FaceAnalysis
os.environ['ONNXRT_ENABLE_COREML'] = '0'  # Disable CoreML for ONNX runtime
os.environ['INSIGHTFACE_DISABLE_COREML'] = '1'  # Disable CoreML for InsightFace

from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.progress import track

console = Console()

# Define constants with defaults that can be overridden
DISTANCE_THRESHOLD = 0.4  # Default threshold
FRAME_SKIP = 5            # Default frame skip

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Test mode configuration
TEST_IMAGE_PATH = os.path.join(project_root, "source", "images", "test", "test_image.jpeg")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', 
                       help='Run in test mode with test_image.jpeg')
    return parser.parse_args()

# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")

# Initialize FaceAnalysis with CPU-only detection
app = FaceAnalysis(
    providers=[
        "CPUExecutionProvider"  # Force CPU for detection model
    ],
    allowed_modules=['detection', 'recognition'],
    use_onnx=True
)
app.prepare(ctx_id=0, det_size=(640, 640))  # Use standard detection size

# Configure GPU optimizations
if torch.backends.mps.is_available():
    # Enable Metal Performance Shaders for PyTorch operations
    torch.mps.set_per_process_memory_fraction(0.75)
    torch.set_flush_denormal(True)
    # Use GPU-accelerated image processing
    os.environ['OPENCV_OPENCL_DEVICE'] = 'Apple:GPU'


def get_image_paths(contestant_path):
    """Retrieve image paths for a contestant."""
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith((".jpg", ".png"))
    ]


def compute_embeddings(image_paths):
    """Compute embeddings for a list of image paths."""
    embeddings = []
    for img_path in track(image_paths, description="Processing images..."):
        console.print(f"[green]Processed:[/green] {os.path.basename(img_path)}")
        try:
            img = cv2.imread(img_path)
            faces = app.get(img)
            embeddings.extend([face.normed_embedding for face in faces])
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
    return embeddings


def get_known_faces_embeddings(contestants_dir, selected_contestants, contestant_info):
    collection = get_contestant_collection()
    return {
        item['metadata']['name']: item['embedding']
        for item in collection.get()
        if item['metadata']['name'] in selected_contestants
    }
    """Load and compute embeddings for selected contestants."""
    known_embeddings = {}
    for contestant_name in selected_contestants:
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
    return known_embeddings


def match_face(face_embedding, known_embeddings, threshold=0.4):
    """Compare a face embedding against known embeddings using ChromaDB."""
    collection = get_contestant_collection()
    results = collection.query(
        query_embeddings=[face_embedding.tolist()],
        n_results=3
    )
    
    # Add comprehensive safety checks
    if not results or not results.get('distances') or not results.get('metadatas'):
        return "Unknown", 0.0
    
    try:
        best_distance = results['distances'][0][0]
        best_name = results['metadatas'][0][0].get('name', 'Unknown')
    except (IndexError, KeyError):
        return "Unknown", 0.0
    
    if best_distance < threshold:
        return best_name, 1 - best_distance
    
    return "Unknown", 0.0


def process_frame(frame, known_embeddings):
    """Detect faces in a frame and recognize known faces."""
    matches = []
    try:
        # Preprocessing optimizations
        frame = cv2.resize(frame, (0,0), fx=0.67, fy=0.67)  # Reduce resolution
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Use half precision for Apple GPU
        if torch.backends.mps.is_available():
            rgb_frame = (rgb_frame.astype('float32') / 255.0).astype('float16')
        
        faces = app.get(rgb_frame)
        for face in faces:
            face_embedding = face.normed_embedding
            matched_name, confidence = match_face(face_embedding, known_embeddings)
            if matched_name != "Unknown":
                matches.append((face, matched_name))
    except Exception as e:
        print(f"Error processing frame: {str(e)[:100]}")  # Truncate long errors
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


def draw_boxes_and_labels(frame, matches, timestamp):
    """Draw boxes, labels, and timestamp on the frame using Pillow."""
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
    """Create a GIF from a list of frame paths."""
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


def recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings, test_mode=False):
    """Recognize faces in selected videos and prepare frames for GIF creation."""
    results = []
    console.print("[bold yellow]\nStarting video processing...[/bold yellow]")
    for video_file in track(selected_videos, description="Processing videos"):
        console.print(f"\n[bold]Processing video:[/bold] [cyan]{video_file}[/cyan]")
        video_path = os.path.join(videos_dir, video_file)
        if not os.path.isfile(video_path):
            print(f"Video file {video_file} not found.")
            continue

        print(f"\nProcessing {'test image' if test_mode else 'video'}: {video_file}")
        
        if test_mode:
            # For test image, just read it directly
            frame = cv2.imread(video_path)
            if frame is None:
                print(f"Could not read test image {video_path}")
                continue
                
            matches = process_frame(frame, known_embeddings)
            if matches:
                frame_with_boxes = draw_boxes_and_labels(frame, matches, "00:00")
                output_path = os.path.join(project_root, "output_frames", "test_result.jpg")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                cv2.imwrite(output_path, frame_with_boxes)
                print(f"\nTest result saved to {output_path}")
                
                for _, matched_name in matches:
                    print(f"Found {matched_name} in test image")
                    results.append({
                        "Video": "test_image.jpeg",
                        "Frame": 0,
                        "Name": matched_name
                    })
            else:
                print("No matches found in test image")
            continue
                
        # Normal video processing
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
                        timestamp_formatted = "{:02}:{:02}".format(int(timestamp_seconds // 60), int(timestamp_seconds % 60))
                        frame_with_boxes = draw_boxes_and_labels(frame, matches, timestamp_formatted)
                        output_frame_path = os.path.join(
                            output_dir, f"frame_{frame_count}.jpg"
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
    """Save recognition results to a CSV file."""
    if results:
        df = pd.DataFrame(results)
        output_csv = os.path.join(project_root, "video_recognition_results.csv")
        df.to_csv(output_csv, index=False)
        print(f"\nResults saved to {output_csv}")
    else:
        print("No faces recognized in videos.")

def select_items(options, item_type):
    """Allow user to select items from a list."""
    console.print(f"\n[bold yellow]Available {item_type}:[/bold yellow]")
    for idx, name in enumerate(options, 1):
        console.print(f"[cyan]{idx}.[/cyan] [green]{name}[/green]")
    console.print(f"[cyan]{len(options) + 1}.[/cyan] [green]Select all[/green]")

    indices = console.input(
        f"\n[bold]Enter the numbers of the {item_type} you want to select, separated by commas (e.g., 1,3,5), or '{len(options) + 1}' to select all: [/bold]"
    )

    if indices.strip() == str(len(options) + 1):
        return options

    selected_indices = [
        int(i.strip()) - 1 for i in indices.split(",") if i.strip().isdigit()
    ]
    selected_items = [options[i] for i in selected_indices if 0 <= i < len(options)]
    return selected_items


def get_contestant_image(contestants_dir, contestant, contestant_info):
    """Retrieve the image path for a contestant."""
    contestant_number = contestant_info.loc[
        contestant_info["暱稱"] == contestant, "編號"
    ].values[0]
    contestant_path = os.path.join(contestants_dir, str(contestant_number))
    image_paths = get_image_paths(contestant_path)
    if image_paths:
        return image_paths[0]
    return None


from chroma_db import get_contestant_collection

def compute_face_embedding(image_path):
    # Existing face detection logic
    img = cv2.imread(image_path)
    faces = app.get(img)
    if not faces:
        return None
        
    face = faces[0]
    embedding = face.normed_embedding.tolist()
    
    # Store in ChromaDB
    collection = get_contestant_collection()
    contestant_id = os.path.basename(os.path.dirname(image_path))
    contestant_name = os.path.basename(image_path).split('-')[0]
    
    collection.add(
        embeddings=[embedding],
        metadatas=[{"name": contestant_name}],
        ids=[contestant_id]
    )
    
    return embedding
    """Compute the face embedding for a given image."""
    img = cv2.imread(image_path)
    faces = app.get(img)
    if len(faces) > 0:
        return faces[0].normed_embedding
    return None


def main():
    # Add hardware acceleration
    cv2.setUseOptimized(True)
    cv2.ocl.setUseOpenCL(True)
    
    if torch.backends.mps.is_available():
        print("🚀 Using Apple Silicon GPU acceleration")
        os.environ['INSIGHTFACE_ENABLE_MPS'] = '1'
    else:
        print("⚠️ Running on CPU only")

    console.print("[bold green]\nMV Face Recognition System[/bold green]")
    console.print("[bold magenta]=======================[/bold magenta]\n")
    
    args = parse_args()
    TEST_MODE = args.test
    
    if TEST_MODE:
        if not os.path.exists(TEST_IMAGE_PATH):
            print(f"\nError: Test image not found at {TEST_IMAGE_PATH}")
            print("Please place your test image at that location or run without --test flag")
            return
        print("\nRunning in test mode")
        
    # Load contestant data
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info["暱稱"].tolist()

    if TEST_MODE:
        # In test mode, use all contestants and just the test image
        selected_contestants = all_contestants
        test_video = "test_image.jpeg"
        selected_videos = [test_video]
        
        # Copy test image to videos dir temporarily
        shutil.copy(TEST_IMAGE_PATH, os.path.join(videos_dir, test_video))
    else:
        # Normal mode - user selects contestants and videos
        selected_contestants = select_items(all_contestants, "contestants")
        all_videos = sorted(
            [f for f in os.listdir(videos_dir) if os.path.isfile(os.path.join(videos_dir, f))]
        )
        selected_videos = select_items(all_videos, "videos")

    # Load embeddings
    known_embeddings = {}
    for contestant in selected_contestants:
        embedding_file = os.path.join(contestants_dir, f"{contestant}_embedding.npy")
        if os.path.exists(embedding_file):
            embedding = np.load(embedding_file, allow_pickle=True)
            known_embeddings[contestant] = [
                embedding
            ]  # Ensure embeddings are stored as a list
        else:
            print(f"Computing embedding for {contestant}...")
            contestant_image = get_contestant_image(
                contestants_dir, contestant, contestant_info
            )
            if contestant_image is not None:
                embedding = compute_face_embedding(contestant_image)
                if embedding is not None:
                    known_embeddings[contestant] = [
                        embedding
                    ]  # Store embedding in a list
                    np.save(
                        embedding_file, [embedding]
                    )  # Save as a list to maintain consistency
                else:
                    print(f"Could not compute embedding for {contestant}")
            else:
                print(f"Could not find image for {contestant}")
    print(f"Loaded/computed embeddings for {len(known_embeddings)} contestants.")

    # Process videos
    recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings, TEST_MODE)


if __name__ == "__main__":
    main()
