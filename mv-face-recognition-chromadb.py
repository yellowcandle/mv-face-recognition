import os
import cv2
import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Try to import ChromaDB
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Face Recognition for Videos with ChromaDB support")
    
    parser.add_argument("--distance-threshold", type=float, default=0.4,
                       help="Distance threshold for face matching (default: 0.4)")
    parser.add_argument("--frame-skip", type=int, default=5,
                       help="Number of frames to skip between processing (default: 5)")
    parser.add_argument("--use-chromadb", action="store_true",
                       help="Use ChromaDB for faster face matching")
    parser.add_argument("--in-memory-db", action="store_true",
                       help="Use in-memory ChromaDB (faster but not persistent)")
    
    return parser.parse_args()

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")

# Initialize InsightFace
app = FaceAnalysis(providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))

# ChromaDB wrapper class
class ChromaDBFaceDB:
    def __init__(self, distance_threshold=0.4, persistent=True):
        """Initialize ChromaDB face database."""
        if not HAS_CHROMADB:
            raise ImportError("ChromaDB is not installed. Install with: pip install chromadb>=0.4.18")
            
        self.distance_threshold = distance_threshold
        self.persistent = persistent
        self.cache_dir = os.path.join(project_root, "cache", "chromadb")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize ChromaDB
        if persistent:
            self.client = chromadb.PersistentClient(path=self.cache_dir)
        else:
            self.client = chromadb.Client()
            
        # Create collection with unique name
        collection_name = f"face_embeddings_{int(np.random.rand() * 10000)}"
        self.collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        # Statistics
        self.query_count = 0
        self.match_count = 0
        
    def add_contestant(self, contestant_name, embeddings):
        """Add contestant embeddings to ChromaDB."""
        # Convert embeddings to list format if needed
        if isinstance(embeddings, np.ndarray):
            if embeddings.ndim == 1:
                # Single embedding vector
                embeddings = [embeddings]
            elif embeddings.ndim == 2:
                # Already a list of embeddings
                pass
            else:
                raise ValueError(f"Unexpected embedding shape: {embeddings.shape}")
                
        # Add each embedding to the collection with contestant metadata
        for i, embedding in enumerate(embeddings):
            # Convert to list for ChromaDB
            if isinstance(embedding, np.ndarray):
                embedding = embedding.flatten().tolist()
                
            # Create unique ID for this embedding
            embedding_id = f"{contestant_name}_{i}"
            
            # Add to collection
            self.collection.add(
                ids=[embedding_id],
                embeddings=[embedding],
                metadatas=[{"name": contestant_name}]
            )
            
    def match_face(self, face_embedding, n_results=1):
        """Match a face embedding against the database."""
        self.query_count += 1
        
        # Convert embedding to list if needed
        if isinstance(face_embedding, np.ndarray):
            face_embedding = face_embedding.flatten().tolist()
            
        # Query ChromaDB for similar faces
        results = self.collection.query(
            query_embeddings=[face_embedding],
            n_results=n_results,
            include=["metadatas", "distances"]
        )
        
        # Check if we have any matches
        if not results["ids"] or not results["ids"][0]:
            return None
            
        # ChromaDB returns distance (0-2 for cosine), convert to similarity (0-1)
        distance = results["distances"][0][0]
        similarity = 1.0 - (distance / 2.0)
        
        # Check against threshold
        if similarity >= self.distance_threshold:
            self.match_count += 1
            return results["metadatas"][0][0]["name"]
            
        return None

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


def standard_match_face(face_embedding, known_embeddings, distance_threshold):
    """Compare a face embedding against known embeddings using standard approach."""
    for name, embeddings_list in known_embeddings.items():
        for known_embedding in embeddings_list:
            known_embedding = (
                known_embedding.flatten()
            )  # Ensure known_embedding is 1D
            distance = np.dot(face_embedding, known_embedding)
            if isinstance(distance, np.ndarray):
                if distance.size == 1:
                    distance = distance.item()  # Convert single-element array to scalar
                else:
                    print(f"Unexpected distance array size for {name}: {distance.size}")
                    distance = (
                        distance.mean()
                    )  # Handle multi-element arrays appropriately
            if distance > distance_threshold:
                return name
    return None


def process_frame(frame, known_embeddings, chroma_db=None, distance_threshold=0.4):
    """Detect faces in a frame and recognize known faces."""
    matches = []
    try:
        faces = app.get(frame)
        for face in faces:
            face_embedding = face.normed_embedding
            
            # Use ChromaDB if available, otherwise standard matching
            if chroma_db is not None:
                matched_name = chroma_db.match_face(face_embedding)
            else:
                matched_name = standard_match_face(face_embedding, known_embeddings, distance_threshold)
                
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


def recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings, chroma_db=None, frame_skip=5):
    """Recognize faces in selected videos and prepare frames for GIF creation."""
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
                if frame_count % frame_skip == 0:
                    # Process frame with the appropriate matcher
                    matches = process_frame(frame, known_embeddings, chroma_db)
                    
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
    """Retrieve the image path for a contestant."""
    contestant_number = contestant_info.loc[
        contestant_info["暱稱"] == contestant, "編號"
    ].values[0]
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
    # Parse command line arguments
    args = parse_args()
    
    # Display settings
    print("Face Recognition Script - Processing Videos")
    print(f"Distance threshold: {args.distance_threshold}")
    print(f"Frame skip: {args.frame_skip}")
    
    # Check if ChromaDB is requested but not available
    if args.use_chromadb and not HAS_CHROMADB:
        print("WARNING: ChromaDB was requested but is not installed!")
        print("Install ChromaDB with: pip install chromadb>=0.4.18")
        print("Continuing with standard face matching...")
        args.use_chromadb = False

    # Initialize ChromaDB if requested
    chroma_db = None
    if args.use_chromadb and HAS_CHROMADB:
        print("Using ChromaDB for faster face matching")
        chroma_db = ChromaDBFaceDB(
            distance_threshold=args.distance_threshold,
            persistent=not args.in_memory_db
        )

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

    # Load embeddings (we'll need the standard dictionary in either case)
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
    
    # If using ChromaDB, load embeddings into it
    if chroma_db is not None:
        print("Adding embeddings to ChromaDB...")
        for contestant, embeddings in known_embeddings.items():
            chroma_db.add_contestant(contestant, embeddings)
        print(f"Added {len(known_embeddings)} contestants to ChromaDB")

    # Process videos
    start_time = time.time()
    recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings, chroma_db, args.frame_skip)
    processing_time = time.time() - start_time
    
    # Print performance stats
    print(f"\nTotal processing time: {processing_time:.2f} seconds")
    if chroma_db is not None:
        print(f"ChromaDB queries: {chroma_db.query_count}")
        print(f"ChromaDB matches: {chroma_db.match_count}")


if __name__ == "__main__":
    main()