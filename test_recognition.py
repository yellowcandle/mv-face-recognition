import os
import cv2
import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image, ImageDraw, ImageFont


def draw_arrow(img, start_point, end_point, color, thickness=3, arrow_size=20):
    """Draw an arrow from start_point to end_point."""
    # Calculate direction vector
    dx = end_point[0] - start_point[0]
    dy = end_point[1] - start_point[1]

    # Normalize direction vector
    length = np.sqrt(dx * dx + dy * dy)
    if length == 0:
        return img

    dx = dx / length
    dy = dy / length

    # Shorten the arrow to not touch the face or label
    margin = 20  # Increased margin for better spacing
    new_start = (int(start_point[0] + dx * margin), int(start_point[1] + dy * margin))
    new_end = (int(end_point[0] - dx * margin), int(end_point[1] - dy * margin))

    # Draw the main line
    cv2.line(img, new_start, new_end, color, thickness)

    # Calculate arrow head points
    arrow_angle = np.pi / 6  # 30 degrees
    angle = np.arctan2(dy, dx)

    p1 = (
        int(new_end[0] - arrow_size * np.cos(angle - arrow_angle)),
        int(new_end[1] - arrow_size * np.sin(angle - arrow_angle)),
    )
    p2 = (
        int(new_end[0] - arrow_size * np.cos(angle + arrow_angle)),
        int(new_end[1] - arrow_size * np.sin(angle + arrow_angle)),
    )

    # Draw arrow head
    cv2.line(img, new_end, p1, color, thickness)
    cv2.line(img, new_end, p2, color, thickness)

    return img


def draw_utf8_text(img, text, pos, font_size, color):
    """Draw UTF-8 text on the image using OpenCV."""
    try:
        # Create a copy of the image
        img_copy = img.copy()

        # Convert OpenCV image to PIL
        pil_img = Image.fromarray(cv2.cvtColor(img_copy, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # Try to find a suitable system font for CJK characters
        font = None
        try:
            # Use the Source Han Sans font from our fonts directory
            font_path = "fonts/SourceHanSansTC-VF.ttf"
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    print(
                        f"Successfully loaded font: {font_path} with size {font_size}"
                    )
                except Exception as e:
                    print(f"Failed to load Source Han Sans font: {e}")
        except Exception as e:
            print(f"Error during font search: {e}")

        if font is None:
            # If no system font works, try to create a default font
            try:
                # On Unix systems, this typically uses a bitmap font
                font = ImageFont.load_default()
                print("Warning: Using default font - text size may be limited")
            except Exception as e:
                print(f"Error loading default font: {e}")
                return img

        # Get text size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Create semi-transparent background
        bg_color = (0, 0, 0)
        padding = 15  # Slightly reduced padding for cleaner look
        bg_left = pos[0]
        bg_top = pos[1]
        bg_right = pos[0] + text_width + padding * 2
        bg_bottom = pos[1] + text_height + padding * 2

        # Create a new RGBA image for the background
        bg_img = Image.new(
            "RGBA", (bg_right - bg_left, bg_bottom - bg_top), (0, 0, 0, 0)
        )
        bg_draw = ImageDraw.Draw(bg_img)
        bg_draw.rectangle(
            [(0, 0), (bg_right - bg_left, bg_bottom - bg_top)],
            fill=(0, 0, 0, int(255 * LABEL_ALPHA)),
        )

        # Convert main image to RGBA
        pil_img = pil_img.convert("RGBA")
        # Paste background with alpha
        pil_img.paste(bg_img, (bg_left, bg_top), bg_img)

        # Draw text with padding and improved color
        draw = ImageDraw.Draw(pil_img)
        draw.text(
            (pos[0] + padding, pos[1] + padding),
            text,
            font=font,
            fill=(color[2], color[1], color[0], 255),  # Full opacity for text
        )

        # Convert back to OpenCV format
        result_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)

        # Copy the affected region back to the original image
        img_copy[bg_top:bg_bottom, bg_left:bg_right] = result_img[
            bg_top:bg_bottom, bg_left:bg_right
        ]

        return img_copy

    except Exception as e:
        print(f"Error in draw_utf8_text: {e}")
        return img


def get_label_dimensions(text, font_size):
    """Get the dimensions a label would occupy with given text and font size."""
    font_path = "fonts/SourceHanSansTC-VF.ttf"
    font = ImageFont.truetype(font_path, font_size)
    # Create a temporary image to measure text
    img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    return (
        bbox[2] - bbox[0] + LABEL_PADDING * 2,
        bbox[3] - bbox[1] + LABEL_PADDING * 2,
    )


def find_label_position(
    img, label_width, label_height, face_bbox, existing_labels, seg_mask
):
    """Find a suitable position for a new label that doesn't overlap with existing ones or important content."""
    face_center_x = (face_bbox[0] + face_bbox[2]) // 2
    face_center_y = (face_bbox[1] + face_bbox[3]) // 2
    img_height, img_width = img.shape[:2]

    # Define search areas (prioritize sides over top)
    search_areas = [
        # Right side (wider range, preferred)
        {
            "x_range": range(
                min(img_width - label_width, face_bbox[2]),
                min(img_width - label_width, face_bbox[2] + 400),
                10,
            ),
            "y_range": range(
                max(0, face_center_y - 100),
                min(img_height - label_height, face_center_y + 100),
                10,
            ),
            "base_cost": 0,  # Preferred position
        },
        # Left side (wider range)
        {
            "x_range": range(
                max(0, face_bbox[0] - 400), max(0, face_bbox[0] - label_width), 10
            ),
            "y_range": range(
                max(0, face_center_y - 100),
                min(img_height - label_height, face_center_y + 100),
                10,
            ),
            "base_cost": 50,  # Slightly less preferred
        },
        # Top (last resort)
        {
            "x_range": range(
                max(0, face_center_x - 200),
                min(img_width - label_width, face_center_x + 200),
                10,
            ),
            "y_range": range(
                max(0, face_bbox[1] - 200), max(0, face_bbox[1] - label_height), 10
            ),
            "base_cost": 100,  # Least preferred
        },
    ]

    best_pos = None
    min_cost = float("inf")

    for area in search_areas:
        for test_x in area["x_range"]:
            for test_y in area["y_range"]:
                current_cost = 0

                # Region for the potential label
                label_region = (
                    slice(test_y, test_y + label_height),
                    slice(test_x, test_x + label_width),
                )

                # Cost from segmentation mask (avoid placing on faces/people)
                if (
                    label_region[0].stop <= seg_mask.shape[0]
                    and label_region[1].stop <= seg_mask.shape[1]
                ):
                    mask_region = seg_mask[label_region]
                    seg_overlap = np.mean(mask_region > 0)
                    current_cost += seg_overlap * 1000

                # Cost from existing labels
                for ex_x, ex_y, ex_w, ex_h in existing_labels:
                    if (
                        test_x < ex_x + ex_w
                        and test_x + label_width > ex_x
                        and test_y < ex_y + ex_h
                        and test_y + label_height > ex_y
                    ):
                        overlap_area = (
                            min(test_x + label_width, ex_x + ex_w) - max(test_x, ex_x)
                        ) * (
                            min(test_y + label_height, ex_y + ex_h) - max(test_y, ex_y)
                        )
                        current_cost += overlap_area * 2

                # Add base cost for search area
                current_cost += area.get("base_cost", 0)

                # Distance cost (adjusted weights)
                dx = test_x + label_width / 2 - face_center_x
                dy = test_y + label_height / 2 - face_center_y
                distance = np.sqrt(dx * dx + dy * dy)

                # Penalize vertical distance more than horizontal
                current_cost += abs(dx) * 0.03 + abs(dy) * 0.1

                # Additional cost for being too close or too far
                if distance < 100:
                    current_cost += 100 - distance
                elif distance > 400:
                    current_cost += (distance - 400) * 0.5

                if current_cost < min_cost:
                    min_cost = current_cost
                    best_pos = (test_x, test_y)

                if current_cost < 1:
                    return test_x, test_y

    return (
        best_pos
        if best_pos is not None
        else (face_bbox[0], max(0, face_bbox[1] - label_height))
    )


# Function to check if face is likely masked
def is_masked(face):
    # Get nose keypoint confidence
    kps = face.kps
    if kps is not None and len(kps) > 2:  # Check if nose keypoint exists
        nose_confidence = kps[2][1]  # Y coordinate of nose keypoint
        return nose_confidence < 0.5
    return False


# Load the models
app = FaceAnalysis(
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    allowed_modules=["detection", "recognition", "landmark_3d_68"],
)
app.prepare(ctx_id=0, det_size=(640, 640))


def get_segmentation_mask(image):
    """Get segmentation mask for the image using facial landmarks and estimated body regions."""
    # Convert to grayscale for simpler processing
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Get face landmarks for all detected faces
    faces = app.get(image)
    mask = np.zeros_like(gray)

    for face in faces:
        # Get facial landmarks
        lmk = face.landmark_3d_68
        bbox = face.bbox.astype(int)

        if lmk is not None:
            # Create head region using landmarks
            points = lmk[:, :2].astype(np.int32)
            hull = cv2.convexHull(points)

            # Draw filled convex hull (head region)
            cv2.fillConvexPoly(mask, hull, 255)

            # Estimate head region (expanded hull)
            head_kernel = np.ones((30, 30), np.uint8)
            cv2.dilate(mask, head_kernel, iterations=1, dst=mask)

            # Estimate body region based on face position and size
            face_width = bbox[2] - bbox[0]
            face_height = bbox[3] - bbox[1]

            # Body region estimation
            body_top = bbox[3]  # Start from bottom of face
            body_height = int(face_height * 3)  # Estimate body height
            body_width = int(face_width * 1.5)  # Estimate body width

            body_left = max(0, bbox[0] - face_width // 4)
            body_right = min(image.shape[1], bbox[2] + face_width // 4)
            body_bottom = min(image.shape[0], body_top + body_height)

            # Draw estimated body region
            cv2.rectangle(
                mask, (body_left, body_top), (body_right, body_bottom), 255, -1
            )  # -1 means filled

    # Final dilation to ensure coverage
    final_kernel = np.ones((10, 10), np.uint8)
    mask = cv2.dilate(mask, final_kernel, iterations=1)

    return mask


# load embeddings for all contestants
contestants_dir = "source/photo/contestants"
contestants_embeddings = {}
for embedding_file in os.listdir(contestants_dir):
    if embedding_file.endswith("_embedding.npy"):
        # Ensure proper UTF-8 decoding of contestant names
        contestant_name = embedding_file.replace("_embedding.npy", "")
        print(f"Loading embedding for contestant: {contestant_name!r}")

        embedding_path = os.path.join(contestants_dir, embedding_file)
        embedding = np.load(embedding_path)
        # Ensure embedding is a 1D array of 512 dimensions
        if embedding.size == 512:
            contestants_embeddings[contestant_name] = embedding.reshape(512)

# Load and process the test image
test_image_path = "source/images/test/test_image.jpeg"
test_image = cv2.imread(test_image_path)

# Get segmentation mask for better label positioning
seg_mask = get_segmentation_mask(test_image)

# Detect faces in the test image
faces = app.get(test_image)

# Define confidence thresholds as constants at the top
NORMAL_CONFIDENCE_THRESHOLD = 0.4
MASKED_CONFIDENCE_THRESHOLD = 0.95

# Define text display settings
LABEL_FONT_SIZE = 20  # Keep font size consistent
LABEL_PADDING = 10  # Padding around text
LABEL_ALPHA = 0.7  # Background transparency

# Keep track of label positions
existing_labels = []  # List of (x, y, width, height) tuples

# process each detected face
print("\n=== New Face Detection ===")
for face_idx, face in enumerate(faces):
    bbox = face.bbox.astype(int)
    embedding = face.embedding

    # find top 3 matches
    similarities = []
    embedding_norm = embedding / np.linalg.norm(embedding)

    for contestant_name, contestant_embedding in contestants_embeddings.items():
        contestant_embedding_norm = contestant_embedding / np.linalg.norm(
            contestant_embedding
        )
        similarity = np.dot(embedding_norm, contestant_embedding_norm)
        similarities.append((contestant_name, similarity))

    # Sort by similarity score
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_3 = similarities[:3]

    # Check if face is masked and set appropriate threshold
    masked = is_masked(face)
    confidence_threshold = (
        MASKED_CONFIDENCE_THRESHOLD if masked else NORMAL_CONFIDENCE_THRESHOLD
    )

    # Print all top 3 matches with their scores
    print(f"\nFace #{face_idx + 1}:")
    print(
        f"Confidence threshold: {confidence_threshold} {'(masked)' if masked else ''}"
    )
    for match_name, score in top_3:
        threshold_met = "✓" if score >= confidence_threshold else "✗"
        print(f"{threshold_met} {match_name} (confidence: {score:.3f})")

    # Draw enlarged rectangle with padding
    padding = 10
    bbox_enlarged = [
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(test_image.shape[1], bbox[2] + padding),
        min(test_image.shape[0], bbox[3] + padding),
    ]
    cv2.rectangle(
        test_image,
        (bbox_enlarged[0], bbox_enlarged[1]),
        (bbox_enlarged[2], bbox_enlarged[3]),
        (0, 255, 0),
        2,
    )

    # Draw top matches that meet threshold
    for i, (match_name, score) in enumerate(top_3):
        if score >= confidence_threshold:
            # Create label with score
            label = f"{match_name} ({score:.2f})"
            if masked:
                label += " [MASKED]"

            # Calculate label dimensions
            label_width, label_height = get_label_dimensions(label, LABEL_FONT_SIZE)

            # Calculate face center for arrow
            face_center = (
                (bbox_enlarged[0] + bbox_enlarged[2]) // 2,
                (bbox_enlarged[1] + bbox_enlarged[3]) // 2,
            )

            # Find position for label using segmentation mask
            x_pos, y_pos = find_label_position(
                test_image,
                label_width,
                label_height,
                bbox_enlarged,
                existing_labels,
                seg_mask,
            )

            # Add label position to existing labels
            existing_labels.append((x_pos, y_pos, label_width, label_height))

            # Calculate label center for arrow
            label_center = (x_pos + label_width // 2, y_pos + label_height // 2)

            # Draw arrow first (so it appears behind the label)
            color = (0, 255, 0) if score >= confidence_threshold else (0, 0, 255)
            test_image = draw_arrow(test_image, label_center, face_center, color)

            # Draw label
            test_image = draw_utf8_text(
                test_image,
                label,
                (x_pos, y_pos),
                font_size=LABEL_FONT_SIZE,
                color=color,
            )

# display the test image
cv2.imshow("Face Recognition Test", test_image)
cv2.waitKey(0)
cv2.destroyAllWindows()
