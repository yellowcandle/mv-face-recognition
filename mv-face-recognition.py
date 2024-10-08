import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont

# Define constants
# User input for distance threshold and frame skip
DISTANCE_THRESHOLD = float(input("Enter the distance threshold (e.g., 0.4): "))
FRAME_SKIP = int(input("Enter the frame skip value (e.g., 5): "))

# Get the absolute path of the current script
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(current_script_path)

# Directory paths
contestants_dir = os.path.join(project_root, "source/photo/contestants")
videos_dir = os.path.join(project_root, "source/videos")
contestant_info_path = os.path.join(project_root, "contestant_info.csv")

# Initialize InsightFace
print("Initializing InsightFace...")
app = FaceAnalysis(providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))
print("InsightFace initialized successfully.")

# Initialize progress bar for script setup
setup_steps = ["Loading modules", "Setting up directories", "Initializing InsightFace"]
with tqdm(total=len(setup_steps), desc="Initializing script") as pbar:
    for step in setup_steps:
        pbar.set_description(f"Initializing script: {step}")
        pbar.update(1)

print("Script initialization complete.")


def get_image_paths(contestant_path):
    """_summary_

    Args:
        contestant_path (_type_): _description_

    Returns:
        _type_: _description_
    """
    return [
        os.path.join(contestant_path, f)
        for f in os.listdir(contestant_path)
        if f.lower().endswith((".jpg", ".png"))
    ]


def compute_embeddings(image_paths):
    """_summary_

    Args:
        image_paths (_type_): _description_

    Returns:
        _type_: _description_
    """
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
    """_summary_

    Args:
        contestants_dir (_type_): _description_
        selected_contestants (_type_): _description_
        contestant_info (_type_): _description_

    Returns:
        _type_: _description_
    """
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


def match_face(face_embedding, known_embeddings):
    """_summary_

    Args:
        face_embedding (_type_): _description_
        known_embeddings (_type_): _description_

    Returns:
        _type_: _description_
    """
    for name, embeddings_list in known_embeddings.items():
        for known_embedding in embeddings_list:
            known_embedding = (
                known_embedding.flatten()
            )  # {{ Ensure known_embedding is 1D }}
            distance = np.dot(face_embedding, known_embedding)
            if isinstance(distance, np.ndarray):
                if distance.size == 1:
                    distance = distance.item()  # Convert single-element array to scalar
                else:
                    print(f"Unexpected distance array size for {name}: {distance.size}")
                    distance = (
                        distance.mean()
                    )  # Handle multi-element arrays appropriately
            if distance > DISTANCE_THRESHOLD:
                return name
    return None


def process_frame(frame, known_embeddings):
    """_summary_

    Args:
        frame (_type_): _description_
        known_embeddings (_type_): _description_

    Returns:
        _type_: _description_
    """
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
    """_summary_

    Args:
        img (_type_): _description_
        text (_type_): _description_
        pos (_type_): _description_
        font_size (_type_): _description_
        color (_type_): _description_
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
    """_summary_

    Args:
        frame (_type_): _description_
        matches (_type_): _description_
        timestamp (_type_): _description_
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
    """_summary_

    Args:
        frame_paths (_type_): _description_
        output_gif_path (_type_): _description_
        duration (int, optional): _description_. Defaults to 0.5.
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
        videos_dir (_type_): _description_
        selected_videos (_type_): _description_
        known_embeddings (_type_): _description_
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
        results (_type_): _description_
        project_root (_type_): _description_
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
        options (_type_): _description_
        item_type (_type_): _description_

    Returns:
        _type_: _description_
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
        contestants_dir (_type_): _description_
        contestant (_type_): _description_
        contestant_info (_type_): _description_

    Returns:
        _type_: _description_
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
        image_path (_type_): _description_

    Returns:
        _type_: _description_
    """
    img = cv2.imread(image_path)
    faces = app.get(img)
    if len(faces) > 0:
        return faces[0].normed_embedding
    return None


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
    recognize_faces_in_videos(videos_dir, selected_videos, known_embeddings)


if __name__ == "__main__":
    main()
