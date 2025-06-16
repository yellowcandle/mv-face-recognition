import os

os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"  # Suppress albumentations update warning
import shutil
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import argparse
import sys
import torch
import logging
from rich.logging import RichHandler

logger = logging.getLogger(__name__)

# Check if ChromaDB is available
CHROMA_AVAILABLE = False
try:
    from chroma_db import get_contestant_collection

    CHROMA_AVAILABLE = True
except ImportError as e:
    print(f"Warning: ChromaDB import failed: {e}")
    print("Face matching will use direct comparison only.")

# Configure environment before importing FaceAnalysis
os.environ["ONNXRT_ENABLE_COREML"] = "0"  # Disable CoreML for ONNX runtime
os.environ["INSIGHTFACE_DISABLE_COREML"] = "0"  # Disable CoreML for InsightFace

from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.progress import track

console = Console()


def setup_logging(level):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler()],
    )


# Define constants with defaults that can be overridden
DISTANCE_THRESHOLD = 0.3  # Default threshold
FRAME_SKIP = 60  # Default frame skip

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Global font cache
FONT_PATH = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")
_font_cache = {}


def get_font(font_size):
    return _font_cache.setdefault(font_size, ImageFont.truetype(FONT_PATH, font_size))


# Test mode configuration
TEST_IMAGE_PATH = os.path.join(
    project_root, "source", "images", "test", "test_image.jpeg"
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test", action="store_true", help="Run in test mode with test_image.jpeg"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Similarity threshold (0.0-1.0), default: 0.5",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set log level",
    )
    args = parser.parse_args()

    # Validate threshold
    if not 0.0 <= args.threshold <= 1.0:
        print(
            f"Error: Threshold {args.threshold} is invalid. Must be between 0.0 and 1.0"
        )
        sys.exit(1)

    if args.threshold < 0.6:
        print(
            f"Warning: Low threshold ({args.threshold}) may produce false positives. Recommended minimum is 0.6"
        )

    return args


# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")

# Initialize FaceAnalysis with CPU-only detection
app = FaceAnalysis(
    providers=[
        "CUDAExecutionProvider" if torch.cuda.is_available() else "CPUExecutionProvider"
    ],
    allowed_modules=["detection", "recognition"],
    use_onnx=True,
    det_thresh=0.3,  # Lower detection threshold
    det_size=(800, 800),  # Larger detection size
)
app.prepare(ctx_id=0, det_size=(800, 800))

# Configure GPU optimizations
if torch.backends.mps.is_available():
    # Enable Metal Performance Shaders for PyTorch operations
    torch.mps.set_per_process_memory_fraction(0.75)
    torch.set_flush_denormal(True)
    # Use GPU-accelerated image processing
    os.environ["OPENCV_OPENCL_DEVICE"] = "Apple:GPU"


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
    images = []
    for img_path in image_paths:
        img = cv2.imread(img_path)
        if img is None:
            print(f"Failed to read {img_path}")
            continue
        images.append(img)
        console.print(f"[green]Loaded:[/green] {os.path.basename(img_path)}")
    if images:
        try:
            batch_results = app.get(images)
            for faces in batch_results:
                for face in faces:
                    embeddings.append(face.normed_embedding.flatten())
        except Exception as e:
            print(f"Error processing batch embeddings: {e}")
    return embeddings


def get_known_faces_embeddings(contestants_dir, selected_contestants, contestant_info):
    """Load and compute embeddings for selected contestants."""
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
                    f"Directory not found for contestant {contestant_name}: {contestant_path}"
                )
        except Exception as e:
            print(f"Error processing contestant {contestant_name}: {e}")
            import traceback

            print(traceback.format_exc())

    return known_embeddings


def debug_embedding(name, embedding):
    """Print debug info about an embedding"""
    print(
        f"Embedding for {name}: shape={embedding.shape}, type={type(embedding)}, min={np.min(embedding)}, max={np.max(embedding)}"
    )
    if isinstance(embedding, np.ndarray) and embedding.size > 0:
        print(f"First 5 values: {embedding.flatten()[:5]}")
    else:
        print("Empty or invalid embedding")


def verify_borderline_match(face_embedding, candidate_embedding, threshold):
    """Additional verification for matches between threshold and threshold+0.1"""
    # Convert to float32 if needed
    face_emb = face_embedding.astype(np.float32)
    cand_emb = candidate_embedding.astype(np.float32)

    # Normalize
    face_emb /= np.linalg.norm(face_emb)
    cand_emb /= np.linalg.norm(cand_emb)

    # Calculate multiple similarity metrics
    cosine_sim = np.dot(face_emb, cand_emb)
    euclidean_dist = np.linalg.norm(face_emb - cand_emb)
    pearson_corr = np.corrcoef(face_emb, cand_emb)[0, 1]

    # More lenient weights favoring cosine similarity
    combined_score = (
        (0.7 * cosine_sim) + (0.2 * (1 - euclidean_dist)) + (0.1 * pearson_corr)
    )

    print(
        f"Verification - Cosine: {cosine_sim:.3f}, Euclidean: {euclidean_dist:.3f}, Pearson: {pearson_corr:.3f}, Combined: {combined_score:.3f}"
    )

    # More permissive verification threshold
    return combined_score >= (
        threshold * 0.90
    )  # Allow 10% lower threshold for verification


def match_face(face_embedding, known_embeddings, threshold=0.5):
    """Compare a face embedding against known embeddings using vectorized cosine similarity."""
    logger.debug(
        f"match_face called: threshold={threshold:.2f}, CHROMA_AVAILABLE={CHROMA_AVAILABLE}"
    )
    try:
        face_emb = face_embedding.flatten().astype(np.float32)
        face_emb /= np.linalg.norm(face_emb) + 1e-10
        # ANN lookup with ChromaDB
        if CHROMA_AVAILABLE:
            logger.debug("CHROMA_AVAILABLE: performing ANN lookup")
            try:
                coll = get_contestant_collection()
                results = coll.query(query_embeddings=[face_emb.tolist()], n_results=1)
                if results and results.get("distances") and results.get("metadatas"):
                    if (
                        len(results["distances"][0]) > 0
                        and len(results["metadatas"][0]) > 0
                    ):
                        best_distance = results["distances"][0][0]
                        best_name = results["metadatas"][0][0].get("name", "Unknown")
                        similarity = 1 - best_distance
                        logger.debug(
                            f"CHROMA branch result: {best_name}, similarity={similarity:.3f}"
                        )
                        return best_name, similarity
            except Exception as e:
                logger.error(f"ChromaDB query error: {e}")
                logger.debug("Falling back to vectorized matching")
        # Fallback: vectorized cosine similarity
        logger.debug("Using vectorized fallback matching")
        best_match = "Unknown"
        best_score = 0.0
        for name, emb_mat in known_embeddings.items():
            sims = emb_mat @ face_emb  # vectorized cosine similarities
            max_sim = float(np.max(sims))
            if max_sim > best_score:
                best_score = max_sim
                best_match = name
                logger.debug(
                    f"Best fallback match so far: {best_match}, score={best_score:.3f}"
                )
        return best_match, best_score
    except Exception as e:
        print(f"Error in match_face: {e}")
        return "Unknown", 0.0


def detect_faces(frame):
    """Detect faces in a frame using InsightFace."""
    try:
        # Check if frame is valid
        if frame is None or frame.size == 0:
            print("Warning: Empty or invalid frame received")
            return []

        # Convert to RGB for consistent processing
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Get faces from InsightFace
        faces = app.get(rgb_frame)
        if faces:
            print(f"InsightFace found {len(faces)} faces in frame")
            return faces
        return []
    except Exception as e:
        print(f"Error detecting faces: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return []


def process_frame(frame, known_embeddings, threshold):
    """Process a frame to identify known faces."""
    matches = []
    try:
        # Detect faces
        faces = detect_faces(frame)
        logger.debug(f"Detected {len(faces)} faces in frame; threshold={threshold:.2f}")

        # Match each face against known embeddings
        for face in faces:
            face_embedding = face.normed_embedding
            matched_name, confidence = match_face(
                face_embedding, known_embeddings, threshold
            )
            logger.debug(
                f"Best match for face: {matched_name} (confidence: {confidence:.3f})"
            )
            if confidence >= threshold and matched_name != "Unknown":
                matches.append((face, matched_name))
    except Exception as e:
        print(f"Error processing frame: {str(e)}")
        import traceback

        print(traceback.format_exc())
    return matches


def draw_utf8_text(img, text, pos, font_size, color):
    """Draw UTF-8 text on the image using Pillow."""
    try:
        # Convert OpenCV image (BGR) to PIL image (RGB)
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # Load font from cache
        font = get_font(font_size)

        # Draw the text
        draw.text(pos, text, font=font, fill=color)

        # Convert back to OpenCV image (BGR)
        img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"Error drawing text: {e}")


def create_pil_image(frame):
    """Convert OpenCV frame to PIL Image."""
    try:
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    except Exception as e:
        print(f"Error converting frame to PIL image: {e}")
        return None


def load_font(font_size):
    """Load font for drawing text."""
    font_path = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")
    if not os.path.exists(font_path):
        print(f"Warning: Font file not found at {font_path}")
        return None
    try:
        return ImageFont.truetype(font_path, font_size)
    except Exception as e:
        print(f"Error loading font: {e}")
        return None


def draw_face_box(draw, face, font, color="green"):
    """Draw bounding box around a face."""
    try:
        bbox = face.bbox.astype(int)
        # Increase rectangle size
        padding = 10
        bbox_enlarged = [
            max(0, bbox[0] - padding),
            max(0, bbox[1] - padding),
            bbox[2] + padding,
            bbox[3] + padding,
        ]
        # Draw enlarged rectangle
        draw.rectangle(bbox_enlarged, outline=color, width=3)
        return bbox_enlarged
    except Exception as e:
        print(f"Error drawing face box: {e}")
        return None


def draw_name_label(draw, name, bbox, font, bg_color="green", text_color="white"):
    """Draw name label above the face box."""
    try:
        if font:
            text_bbox = draw.textbbox((bbox[0], bbox[1] - 65), name, font=font)
            draw.rectangle(text_bbox, fill=bg_color)
            draw.text(
                (bbox[0], bbox[1] - 65),
                name,
                font=font,
                fill=text_color,
            )
    except Exception as e:
        print(f"Error drawing name label: {e}")


def draw_timestamp(draw, timestamp, img_size, font, text_color="yellow"):
    """Draw timestamp on the image."""
    try:
        if font:
            img_width, img_height = img_size
            text_bbox = draw.textbbox((0, 0), timestamp, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            position = (img_width - text_width - 10, img_height - text_height - 10)
            draw.text(position, timestamp, font=font, fill=text_color)
    except Exception as e:
        print(f"Error drawing timestamp: {e}")


def draw_boxes_and_labels(frame, matches, timestamp):
    """Draw boxes, labels, and timestamp on the frame."""
    try:
        # Check if frame is valid
        if frame is None or frame.size == 0:
            print("Warning: Empty or invalid frame in draw_boxes_and_labels")
            return frame

        # Convert to PIL image
        pil_img = create_pil_image(frame)
        if pil_img is None:
            return frame

        draw = ImageDraw.Draw(pil_img)

        # Load fonts
        larger_font = load_font(60)
        timestamp_font = load_font(40)

        # Draw boxes and labels
        for face, name in matches:
            bbox = draw_face_box(draw, face, larger_font)
            if bbox:
                draw_name_label(draw, name, bbox, larger_font)

        # Draw timestamp
        draw_timestamp(draw, timestamp, pil_img.size, timestamp_font)

        # Convert back to OpenCV image
        try:
            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"Error converting PIL image back to OpenCV: {e}")

        return frame
    except Exception as e:
        print(f"Error in draw_boxes_and_labels: {e}")
        import traceback

        print(traceback.format_exc())
        return frame  # Return original frame if any error occurs


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
    videos_dir, selected_videos, known_embeddings, threshold=0.5, test_mode=False
):
    """Recognize faces in selected videos and prepare frames for GIF creation."""
    results = []
    logger.info("Starting video processing...")
    for video_file in track(selected_videos, description="Processing videos"):
        logger.info(f"Processing video: {video_file}")
        video_path = os.path.join(videos_dir, video_file)
        if not os.path.isfile(video_path):
            print(f"Video file {video_file} not found.")
            continue

        print(f"\nProcessing {'test image' if test_mode else 'video'}: {video_file}")

        if test_mode:
            # For test image, validate and preprocess
            frame = cv2.imread(video_path)
            if frame is None:
                print(f"Could not read test image {video_path}")
                continue

            # Check resolution
            if frame.shape[0] < 512 or frame.shape[1] < 512:
                print("Test image resolution too low (min 512x512 required)")
                continue

            # Convert to 3 channels if needed
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            # Apply sharpening
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            frame = cv2.filter2D(frame, -1, kernel)

            matches = process_frame(frame, known_embeddings, threshold)
            if matches:
                frame_with_boxes = draw_boxes_and_labels(frame, matches, "00:00")
                output_path = os.path.join(
                    project_root, "output_frames", "test_result.jpg"
                )
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                cv2.imwrite(output_path, frame_with_boxes)
                print(f"\nTest result saved to {output_path}")

                for _, matched_name in matches:
                    print(f"Found {matched_name} in test image")
                    results.append(
                        {"Video": "test_image.jpeg", "Frame": 0, "Name": matched_name}
                    )
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
        skip_frames = 0
        # Parallel inference setup
        from concurrent.futures import ThreadPoolExecutor

        executor = ThreadPoolExecutor(max_workers=4)
        pending = []  # List of (future, frame, frame_no)

        with tqdm(
            total=total_frames, desc=f"Frames in {video_file}", leave=False
        ) as pbar:
            while True:
                # Drop skipped frames without random seek
                if skip_frames > 0:
                    for _ in range(skip_frames):
                        ret_drop, _ = cap.read()
                        if not ret_drop:
                            break
                        frame_count += 1
                        pbar.update(1)
                    skip_frames = 0
                # Read next frame
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                pbar.update(1)
                # Submit inference
                future = executor.submit(
                    process_frame, frame, known_embeddings, threshold
                )
                pending.append((future, frame, frame_count))
                # Handle completed tasks
                new_pending = []
                for fut, fr, cnt in pending:
                    if fut.done():
                        matches = fut.result()
                        if matches:
                            skip_frames = 2
                            ts = cnt / fps
                            ts_fmt = f"{int(ts // 60):02}:{int(ts % 60):02}"
                            img_out = draw_boxes_and_labels(fr, matches, ts_fmt)
                            out_path = os.path.join(output_dir, f"frame_{cnt}.jpg")
                            cv2.imwrite(out_path, img_out)
                            labeled_frames.append(out_path)
                            for _, name in matches:
                                results.append(
                                    {"Video": video_file, "Frame": cnt, "Name": name}
                                )
                        else:
                            skip_frames = 10
                        # Finished this task
                    else:
                        new_pending.append((fut, fr, cnt))
                pending = new_pending
        # Wait for any remaining inference tasks
        executor.shutdown(wait=True)
        cap.release()

    save_results(results, project_root)


def save_results(results, project_root):
    """Save recognition results to a CSV file."""
    if results:
        df = pd.DataFrame(results)
        output_csv = os.path.join(project_root, "video_recognition_results.csv")
        df.to_csv(output_csv, index=False)
        logger.info(f"Results saved to {output_csv}")
    else:
        logger.warning("No faces recognized in videos.")


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


# ChromaDB import is now handled at the top of the file


def compute_face_embedding(image_path):
    """Compute the face embedding for a given image."""
    try:
        print(f"Reading image from {image_path}")
        img = cv2.imread(image_path)

        if img is None:
            print(f"Failed to read image: {image_path}")
            return None

        print(f"Image shape: {img.shape}, detecting faces...")
        rgb_img = cv2.cvtColor(
            img, cv2.COLOR_BGR2RGB
        )  # Convert to RGB for better face detection
        # Try detection with different sizes with debug info
        print("Attempting face detection with InsightFace...")
        for det_size in [(800, 800), (640, 640), (1024, 1024)]:
            print(f"Trying detection size {det_size}")
            app.det_size = det_size
            faces = app.get(rgb_img)
            if faces:
                break

        print(f"Found {len(faces)} faces in {image_path}")

        if len(faces) > 0:
            face = faces[0]
            embedding = face.normed_embedding

            # Get contestant name from path
            path_parts = image_path.split("/")
            contestant_id = path_parts[-2]  # Folder name (number)

            # Look up contestant name from contestant_info
            try:
                contestant_info = pd.read_csv(contestant_info_path)
                contestant_row = contestant_info[
                    contestant_info["編號"].astype(str) == contestant_id
                ]
                if not contestant_row.empty:
                    contestant_name = contestant_row["暱稱"].iloc[0]
                else:
                    # Use filename as fallback
                    contestant_name = os.path.basename(image_path).split("-")[0]
            except Exception as e:
                print(f"Error looking up contestant name: {e}")
                contestant_name = os.path.basename(image_path).split("-")[0]

            # Store in ChromaDB if available
            if CHROMA_AVAILABLE:
                try:
                    collection = get_contestant_collection()

                    collection.add(
                        embeddings=[embedding.tolist()],
                        metadatas=[{"name": contestant_name}],
                        ids=[f"{contestant_id}-{os.path.basename(image_path)}"],
                    )
                    print(f"Stored embedding for {contestant_name} in ChromaDB")
                except Exception as e:
                    print(f"Error storing in ChromaDB: {e}")
                    print("Continuing without ChromaDB storage")

            return embedding
        else:
            print(f"No faces detected in {image_path}")
            return None
    except Exception as e:
        print(f"Error computing embedding for {image_path}: {e}")
        import traceback

        print(traceback.format_exc())
        return None


def main():
    # Add hardware acceleration
    cv2.setUseOptimized(True)
    cv2.ocl.setUseOpenCL(True)

    if torch.backends.mps.is_available():
        print("🚀 Using Apple Silicon GPU acceleration")
        os.environ["INSIGHTFACE_ENABLE_MPS"] = "1"
    else:
        print("⚠️ Running on CPU only")

    args = parse_args()
    TEST_MODE = args.test
    SIMILARITY_THRESHOLD = args.threshold  # Get threshold from arguments

    if TEST_MODE:
        if not os.path.exists(TEST_IMAGE_PATH):
            print(f"\nError: Test image not found at {TEST_IMAGE_PATH}")
            print(
                "Please place your test image at that location or run without --test flag"
            )
            return
        print("\nRunning in test mode")

    # Initialize logging
    log_level = logging.INFO
    if args.log_level:
        log_level = getattr(logging, args.log_level)
    elif args.verbose:
        log_level = logging.DEBUG
    setup_logging(log_level)

    logger.info("MV Face Recognition System")
    logger.info("=======================")

    # Load contestant data
    contestant_info = pd.read_csv(contestant_info_path)
    all_contestants = contestant_info["暱稱"].tolist()

    if TEST_MODE:
        # In test mode, use all contestants and just the test image
        selected_contestants = all_contestants
        test_video = "test_image.jpeg"
        selected_videos = [test_video]

        # Check if test image exists
        if not os.path.exists(TEST_IMAGE_PATH):
            print(f"Test image not found at {TEST_IMAGE_PATH}")
            return

        # Print test image info
        test_img = cv2.imread(TEST_IMAGE_PATH)
        if test_img is None:
            print(f"Failed to read test image: {TEST_IMAGE_PATH}")
            return

        print(f"Test image dimensions: {test_img.shape}")

        # Copy test image to videos dir temporarily
        shutil.copy(TEST_IMAGE_PATH, os.path.join(videos_dir, test_video))
        print(f"Copied test image to {os.path.join(videos_dir, test_video)}")
    else:
        # Normal mode - user selects contestants and videos
        selected_contestants = select_items(all_contestants, "contestants")
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
    logger.info("Loading contestant embeddings...")
    for contestant in selected_contestants:
        # Try to find contestant in contestant_info
        contestant_row = contestant_info[contestant_info["暱稱"] == contestant]
        if contestant_row.empty:
            print(f"Could not find contestant info for {contestant}")
            continue

        contestant_number = contestant_row["編號"].values[0]
        contestant_path = os.path.join(contestants_dir, str(contestant_number))

        # Check if we have embedding file
        embedding_file = os.path.join(contestants_dir, f"{contestant}_embedding.npy")
        if os.path.exists(embedding_file):
            try:
                embedding = np.load(
                    embedding_file, allow_pickle=True
                ).flatten()  # Ensure 1D array
                print(f"Loaded embedding for {contestant} from file: {embedding_file}")

                # Debug the loaded embedding
                if isinstance(embedding, np.ndarray):
                    print(f"  Shape: {embedding.shape}, Type: {type(embedding)}")
                    if len(embedding.shape) > 1:
                        embedding = embedding.flatten()
                        print(f"  Flattened to shape: {embedding.shape}")
                elif isinstance(embedding, list):
                    print(f"  List of {len(embedding)} embeddings")
                else:
                    print(f"  Unexpected type: {type(embedding)}")

                # Ensure embeddings are in a list and have consistent shape
                if isinstance(embedding, list):
                    # Make sure each embedding is a 1D array
                    processed_embeddings = []
                    for e in embedding:
                        if e is not None:
                            processed_embeddings.append(e.flatten())
                    known_embeddings[contestant] = processed_embeddings
                else:
                    # Single embedding, make sure it's a 1D array
                    known_embeddings[contestant] = [embedding.flatten()]
            except Exception as e:
                print(f"Error loading embedding for {contestant}: {e}")
                import traceback

                print(traceback.format_exc())

        # If no embedding file or loading failed, try to compute from images
        if contestant not in known_embeddings or not known_embeddings[contestant]:
            print(f"Computing embedding for {contestant}...")
            if os.path.isdir(contestant_path):
                image_paths = get_image_paths(contestant_path)
                if image_paths:
                    embedding = compute_face_embedding(image_paths[0])
                    if embedding is not None:
                        # Ensure embedding is a 1D array
                        known_embeddings[contestant] = [embedding.flatten()]
                        # Save for future use
                        np.save(embedding_file, embedding)
                        print(f"Computed and saved embedding for {contestant}")
                    else:
                        print(f"Could not compute embedding for {contestant}")
                else:
                    print(f"No images found for {contestant} in {contestant_path}")
            else:
                print(
                    f"Directory not found for contestant {contestant}: {contestant_path}"
                )

    logger.info(f"Loaded/computed embeddings for {len(known_embeddings)} contestants.")
    logger.info(f"Contestant names with embeddings: {list(known_embeddings.keys())}")

    # Verify embeddings are valid
    valid_embeddings = 0
    for name, embeddings in known_embeddings.items():
        if embeddings and all(
            e is not None and isinstance(e, np.ndarray) for e in embeddings
        ):
            valid_embeddings += 1
    logger.info(f"Valid embeddings: {valid_embeddings}/{len(known_embeddings)}")

    # Batch optimization: convert known embedding lists to normalized numpy matrices
    for name, embs in known_embeddings.items():
        emb_mat = np.vstack(embs).astype(np.float32)
        emb_mat /= np.linalg.norm(emb_mat, axis=1, keepdims=True) + 1e-10
        known_embeddings[name] = emb_mat

    # Ingest embeddings into ChromaDB for ANN indexing
    if CHROMA_AVAILABLE:
        coll = get_contestant_collection()
        try:
            existing = coll.get()
            if not existing.get("ids"):
                logger.info("Initializing ChromaDB index for embeddings...")
                for name, emb_mat in known_embeddings.items():
                    ids = [f"{name}_{i}" for i in range(emb_mat.shape[0])]
                    metadatas = [{"name": name} for _ in range(emb_mat.shape[0])]
                    coll.add(ids=ids, embeddings=emb_mat.tolist(), metadatas=metadatas)
                logger.info("ChromaDB index initialization complete.")
            else:
                logger.info("ChromaDB index found, skipping initialization.")
        except Exception as e:
            logger.error(f"ChromaDB indexing error: {e}")

    # Process videos
    recognize_faces_in_videos(
        videos_dir,
        selected_videos,
        known_embeddings,
        threshold=SIMILARITY_THRESHOLD,
        test_mode=TEST_MODE,
    )


if __name__ == "__main__":
    main()
