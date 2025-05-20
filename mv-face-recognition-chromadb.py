import argparse
import os
import sys
import time

import cv2
import numpy as np
import pandas as pd
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

# Try to import ChromaDB
try:
    import chromadb

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(
        description="Face Recognition for Videos with ChromaDB support"
    )

    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.18,
        help="Distance threshold for face matching (default: 0.18)",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=5,
        help="Number of frames to skip between processing (default: 5)",
    )
    parser.add_argument(
        "--use-chromadb",
        action="store_true",
        help="Use ChromaDB for faster face matching",
    )
    parser.add_argument(
        "--in-memory-db",
        action="store_true",
        help="Use in-memory ChromaDB (faster but not persistent)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--augmentation", action="store_true", help="Use image augmentation")
    parser.add_argument(
        "--quality-check",
        action="store_true",
        help="Enable face quality checking (may filter out too many faces)",
    )
    parser.add_argument(
        "--specific-contestants",
        type=str,
        help="Comma-separated list of contestant names to include",
    )
    parser.add_argument(
        "--specific-videos",
        type=str,
        help="Comma-separated list of video filenames to process",
    )

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


# Preprocessing functions
def preprocess_face_image(face_img):
    """Apply preprocessing to improve face recognition."""
    try:
        # Resize to a consistent size if needed
        if face_img.shape[0] > 300 or face_img.shape[1] > 300:
            scale = 300 / max(face_img.shape[0], face_img.shape[1])
            face_img = cv2.resize(face_img, None, fx=scale, fy=scale)

        # Convert to grayscale and back to enhance features
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)

        # Convert back to color for the model
        if len(face_img.shape) == 3:
            enhanced = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)

            # Blend with original for better features
            enhanced = cv2.addWeighted(face_img, 0.5, enhanced, 0.5, 0)
        else:
            enhanced = enhanced_gray

        return enhanced
    except Exception as e:
        print(f"Error in preprocessing: {e}")
        return face_img  # Return original if preprocessing fails


def is_quality_face(face, frame, min_size=30, blur_threshold=25):
    """Check if a face is of good quality for recognition."""
    try:
        # Check face size
        bbox = face.bbox.astype(np.int32)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]

        if width < min_size or height < min_size:
            return False

        # Check for blurriness using Laplacian variance
        face_roi = frame[
            max(0, bbox[1]) : min(frame.shape[0], bbox[3]),
            max(0, bbox[0]) : min(frame.shape[1], bbox[2]),
        ]

        if face_roi.size == 0:  # Empty ROI
            return False

        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        blur_value = cv2.Laplacian(gray, cv2.CV_64F).var()

        if blur_value < blur_threshold:
            return False

        return True
    except Exception as e:
        print(f"Error checking face quality: {e}")
        return True  # Be more permissive on error


def compute_embeddings_with_augmentation(image_paths, angles=[-10, -5, 0, 5, 10]):
    """Compute face embeddings with augmentation for better matching."""
    embeddings = []
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is None:
                continue

            # Process original image
            original_faces = app.get(img)
            if len(original_faces) > 0:
                face = original_faces[0]
                embeddings.append(face.normed_embedding)

                # Try preprocessing
                preprocessed = preprocess_face_image(img)
                preprocessed_faces = app.get(preprocessed)
                if len(preprocessed_faces) > 0:
                    face = preprocessed_faces[0]
                    embeddings.append(face.normed_embedding)

            # Add augmented versions
            for angle in angles:
                if angle == 0:  # Skip 0 as we already processed the original
                    continue

                # Rotate image
                h, w = img.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

                # Process rotated image
                rot_faces = app.get(rotated)
                if len(rot_faces) > 0:
                    face = rot_faces[0]
                    embeddings.append(face.normed_embedding)

        except Exception as e:
            print(f"Error processing {img_path} with augmentation: {e}")

    return embeddings


# Replace the original compute_embeddings function
def compute_embeddings(image_paths, use_augmentation=True):
    """Compute face embeddings for a list of images."""
    if use_augmentation:
        return compute_embeddings_with_augmentation(image_paths)

    embeddings = []
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is None:
                continue

            # Try with preprocessing
            preprocessed = preprocess_face_image(img)
            faces = app.get(preprocessed)

            if len(faces) > 0:
                face = faces[0]
                embedding = face.normed_embedding
                embeddings.append(embedding)
            else:
                # Try with original if preprocessing didn't work
                faces = app.get(img)
                if len(faces) > 0:
                    face = faces[0]
                    embedding = face.normed_embedding
                    embeddings.append(embedding)
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
    return embeddings


# ChromaDB wrapper class
class ChromaDBFaceDB:
    def __init__(self, distance_threshold=0.18, persistent=True):
        """Initialize ChromaDB face database."""
        if not HAS_CHROMADB:
            raise ImportError(
                "ChromaDB is not installed. Install with: pip install chromadb>=0.4.18"
            )

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

        # Get the embedding dimension from InsightFace's model
        # InsightFace embeddings are typically 512-dimensional
        self.embedding_dimension = 512

        # Create the collection with the specific embedding function
        self.collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
            embedding_function=None,  # We'll provide pre-computed embeddings
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
            # Convert to list for ChromaDB and ensure correct dimension
            if isinstance(embedding, np.ndarray):
                embedding = embedding.flatten()

                # Verify embedding dimension
                if len(embedding) != self.embedding_dimension:
                    print(
                        f"Warning: Expected embedding dimension {self.embedding_dimension}, got {len(embedding)}. Skipping..."
                    )
                    continue

                embedding = embedding.tolist()

            # Create unique ID for this embedding
            embedding_id = f"{contestant_name}_{i}"

            # Add to collection
            try:
                self.collection.add(
                    ids=[embedding_id],
                    embeddings=[embedding],
                    metadatas=[{"name": contestant_name}],
                )
            except Exception as e:
                print(f"Error adding embedding for {contestant_name}: {e}")

    def match_face(self, face_embedding, n_results=1):
        """Match a face embedding against the database."""
        self.query_count += 1

        # Convert embedding to list if needed
        if isinstance(face_embedding, np.ndarray):
            face_embedding = face_embedding.flatten()

            # Verify embedding dimension
            if len(face_embedding) != self.embedding_dimension:
                print(
                    f"Warning: Query embedding dimension mismatch. Expected {self.embedding_dimension}, got {len(face_embedding)}"
                )
                return None

            face_embedding = face_embedding.tolist()

        try:
            # Query the collection
            results = self.collection.query(query_embeddings=[face_embedding], n_results=n_results)

            # Return the best match if found
            if results["distances"][0] and results["metadatas"][0]:
                # Check if distance meets threshold (converts cosine similarity to distance)
                similarity = 1 - results["distances"][0][0]  # First result, first distance
                if similarity > self.distance_threshold:
                    self.match_count += 1
                    return results["metadatas"][0][0][
                        "name"
                    ]  # First result, first metadata, name field

            return None
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
            return None


def get_image_paths(contestant_path):
    """Retrieve image paths for a contestant."""
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith((".jpg", ".png"))
    ]


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
            embeddings = compute_embeddings(image_paths, use_augmentation=parse_args().augmentation)
            if embeddings:
                known_embeddings[contestant_name] = embeddings
        else:
            print(f"Directory for contestant '{contestant_name}' not found: {contestant_path}")
    return known_embeddings


def standard_match_face(face_embedding, known_embeddings, distance_threshold):
    """Compare a face embedding against known embeddings using standard approach."""
    best_similarity = 0
    best_name = None

    for name, embeddings_list in known_embeddings.items():
        for known_embedding in embeddings_list:
            # Ensure both embeddings are flattened and the same dimension
            face_embedding_flat = face_embedding.flatten()
            known_embedding_flat = known_embedding.flatten()

            # Check if dimensions match
            if len(face_embedding_flat) != len(known_embedding_flat):
                # Skip if dimensions don't match
                continue

            # Calculate cosine similarity (dot product of normalized vectors)
            similarity = np.dot(face_embedding_flat, known_embedding_flat)

            # Handle if similarity is an array (shouldn't happen with properly flattened vectors)
            if isinstance(similarity, np.ndarray):
                if similarity.size == 1:
                    similarity = similarity.item()  # Convert single-element array to scalar
                else:
                    similarity = similarity.mean()  # Handle multi-element arrays by taking the mean

            # Update best match
            if similarity > best_similarity:
                best_similarity = similarity
                best_name = name

    # Only return name if it meets the threshold
    if best_similarity > distance_threshold:
        return best_name
    return None


def process_frame(
    frame,
    known_embeddings,
    chroma_db=None,
    distance_threshold=0.18,
    debug=False,
    quality_check=False,
):
    """Detect faces in a frame and recognize known faces."""
    matches = []
    try:
        # Try with preprocessing first
        preprocessed = preprocess_face_image(frame.copy())
        faces = app.get(preprocessed)

        # If no faces found with preprocessing, try original
        if len(faces) == 0:
            faces = app.get(frame)

        if len(faces) > 0 and debug:
            print(f"Found {len(faces)} faces in frame")

        for face in faces:
            # Check if face is good quality (optional)
            if quality_check and not is_quality_face(face, frame):
                if debug:
                    print("Skipping low quality face")
                continue

            face_embedding = face.normed_embedding

            # Use ChromaDB if available, otherwise standard matching
            if chroma_db is not None:
                matched_name = chroma_db.match_face(face_embedding)
                if matched_name is None:
                    # If ChromaDB doesn't find a match, try standard matching as fallback
                    if debug:
                        print("ChromaDB match failed, trying standard matching...")
                    matched_name = standard_match_face(
                        face_embedding, known_embeddings, distance_threshold * 0.9
                    )  # Lower threshold for fallback
            else:
                matched_name = standard_match_face(
                    face_embedding, known_embeddings, distance_threshold
                )

            if matched_name:
                if debug:
                    print(f"Recognized face: {matched_name}")
                matches.append((face, matched_name))
            else:
                # Debug info - if no match, print the highest similarity found
                highest_similarity = 0
                best_name = None

                for name, embeddings_list in known_embeddings.items():
                    for known_embedding in embeddings_list:
                        # Ensure both embeddings are flattened and the same dimension
                        face_embedding_flat = face_embedding.flatten()
                        known_embedding_flat = known_embedding.flatten()

                        # Check if dimensions match
                        if len(face_embedding_flat) != len(known_embedding_flat):
                            continue

                        # Calculate cosine similarity
                        similarity = np.dot(face_embedding_flat, known_embedding_flat)
                        if isinstance(similarity, np.ndarray):
                            similarity = (
                                similarity.item() if similarity.size == 1 else similarity.mean()
                            )

                        if similarity > highest_similarity:
                            highest_similarity = similarity
                            best_name = name

                if best_name and debug:
                    print(
                        f"Best match (below threshold): {best_name} with similarity {highest_similarity:.4f} (threshold: {distance_threshold})"
                    )

                    # If very close to threshold, add it with a flag
                    if highest_similarity > distance_threshold * 0.9:
                        print(f"Close match added: {best_name} ({highest_similarity:.4f})")
                        matches.append((face, f"{best_name}?"))
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


def recognize_faces_in_videos(
    videos_dir,
    selected_videos,
    known_embeddings,
    chroma_db=None,
    frame_skip=5,
    debug=False,
    quality_check=False,
):
    """Recognize faces in selected videos and prepare frames for GIF creation."""
    results = []
    recognized_contestants = set()
    recognized_frames = []

    bar = tqdm(selected_videos)
    for video_name in bar:
        bar.set_description(f"Processing video: {video_name}")

        video_path = os.path.join(videos_dir, video_name)
        if not os.path.exists(video_path):
            print(f"Video not found: {video_path}")
            continue

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Could not open video: {video_path}")
            continue

        frame_count = 0
        processed_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Process every Nth frame
            if frame_count % frame_skip == 0:
                # Process frame for face recognition
                matches = process_frame(
                    frame,
                    known_embeddings,
                    chroma_db,
                    debug=debug,
                    quality_check=quality_check,
                )
                processed_count += 1

                if matches:
                    # Get timestamp
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    timestamp = frame_count / fps
                    minutes = int(timestamp // 60)
                    seconds = int(timestamp % 60)
                    timestamp_str = f"{minutes:02d}:{seconds:02d}"

                    # Draw boxes and labels on the frame
                    labeled_frame = draw_boxes_and_labels(frame.copy(), matches, timestamp_str)

                    # Add to recognized frames
                    recognized_frames.append(labeled_frame)

                    # Add contestants to the set of recognized contestants
                    for _, name in matches:
                        # Handle "close match" names (with '?' suffix)
                        clean_name = name.rstrip("?")
                        recognized_contestants.add(clean_name)

                    # Add to results
                    for _, name in matches:
                        clean_name = name.rstrip("?")
                        results.append((video_name, timestamp_str, clean_name))

            frame_count += 1

        cap.release()

    if results:
        print("\nRecognition Results:")
        for video_name, timestamp, contestant in results:
            print(f"{video_name} at {timestamp}: {contestant}")

        print("\nRecognized Contestants:")
        for contestant in sorted(recognized_contestants):
            print(f"- {contestant}")

        # Create a GIF if there are recognized frames
        if recognized_frames:
            output_gif_dir = "recognized_frames"
            os.makedirs(output_gif_dir, exist_ok=True)

            # Save recognized frames as images
            frame_paths = []
            for i, frame in enumerate(recognized_frames):
                frame_path = os.path.join(output_gif_dir, f"frame_{i:04d}.jpg")
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_path)

            # Create GIF from frames
            if frame_paths:
                output_gif_path = os.path.join(output_gif_dir, "recognized_faces.gif")
                create_gif_from_frames(frame_paths, output_gif_path)
    else:
        print("No faces recognized in videos.")


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

    selected_indices = [int(i.strip()) - 1 for i in indices.split(",") if i.strip().isdigit()]
    selected_items = [options[i] for i in selected_indices if 0 <= i < len(options)]
    return selected_items


def get_contestant_image(contestants_dir, contestant, contestant_info):
    """Retrieve the image path for a contestant."""
    contestant_number = contestant_info.loc[contestant_info["暱稱"] == contestant, "編號"].values[0]
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

    print("Face Recognition Script - Processing Videos")
    print(f"Distance threshold: {args.distance_threshold}")
    print(f"Frame skip: {args.frame_skip}")
    print(f"Using augmentation: {args.augmentation}")
    print(f"Quality check enabled: {args.quality_check}")
    print()

    # Check if ChromaDB is requested but not available
    if args.use_chromadb and not HAS_CHROMADB:
        print("ERROR: ChromaDB is not installed. Use --use-chromadb only if ChromaDB is installed.")
        sys.exit(1)

    # Initialize ChromaDB if requested
    chroma_db = None
    if args.use_chromadb:
        print("Using ChromaDB for faster face matching")
        chroma_db = ChromaDBFaceDB(
            distance_threshold=args.distance_threshold, persistent=not args.in_memory_db
        )

    # Load contestant data
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info["暱稱"].tolist()

    # Select contestants
    if args.specific_contestants:
        selected_contestants = args.specific_contestants.split(",")
    else:
        selected_contestants = select_items(all_contestants, "contestants")

    # Select videos
    all_videos = sorted(
        [f for f in os.listdir(videos_dir) if os.path.isfile(os.path.join(videos_dir, f))]
    )
    if args.specific_videos:
        selected_videos = args.specific_videos.split(",")
    else:
        selected_videos = select_items(all_videos, "videos")

    # Load embeddings (we'll need the standard dictionary in either case)
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
                embeddings = compute_embeddings(
                    [contestant_image], use_augmentation=args.augmentation
                )
                if embeddings:
                    known_embeddings[contestant] = embeddings
                    np.save(embedding_file, embeddings)  # Save as a list to maintain consistency
                else:
                    print(f"Could not compute embedding for {contestant}")
    print(f"Loaded/computed embeddings for {len(known_embeddings)} contestants.")

    # If using ChromaDB, load embeddings into it
    if chroma_db is not None:
        print("Adding embeddings to ChromaDB...")
        for contestant, embeddings in known_embeddings.items():
            chroma_db.add_contestant(contestant, embeddings)
        print(f"Added {len(known_embeddings)} contestants to ChromaDB")

    # Process videos
    start_time = time.time()
    recognize_faces_in_videos(
        videos_dir,
        selected_videos,
        known_embeddings,
        chroma_db,
        args.frame_skip,
        debug=args.debug,
        quality_check=args.quality_check,
    )
    processing_time = time.time() - start_time

    # Print performance stats
    print(f"\nTotal processing time: {processing_time:.2f} seconds")
    if chroma_db is not None:
        print(f"ChromaDB queries: {chroma_db.query_count}")
        print(f"ChromaDB matches: {chroma_db.match_count}")


if __name__ == "__main__":
    main()
