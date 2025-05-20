import hashlib
import os
from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np

from .performance import compute_image_hash, image_cache


def load_image(image_path: Union[str, Path], use_cache: bool = True) -> Optional[np.ndarray]:
    """
    Load an image with optimized caching for test images.

    Args:
        image_path: Path to the image
        use_cache: Whether to use image cache

    Returns:
        numpy.ndarray: Loaded image or None if failed
    """
    # Convert path to string if it's a Path object
    if isinstance(image_path, Path):
        image_path = str(image_path)

    # Check if image exists
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return None

    # For test images, check cache first
    if use_cache and is_test_image(image_path):
        # Compute hash without loading full image first
        img_hash = get_image_file_hash(image_path)

        # Check cache
        cached_img = image_cache.get(img_hash)
        if cached_img is not None:
            return cached_img

    # Regular image loading
    try:
        image = cv2.imread(image_path)

        # Cache test images for future use
        if use_cache and image is not None and is_test_image(image_path):
            img_hash = compute_image_hash(image)
            image_cache.set(img_hash, image)

        return image
    except Exception as e:
        print(f"Error loading image {image_path}: {str(e)}")
        return None


def save_image(image: np.ndarray, output_path: Union[str, Path], quality: int = 95) -> bool:
    """
    Save an image with optimized parameters.

    Args:
        image: Image to save
        output_path: Path to save the image
        quality: JPEG quality (0-100)

    Returns:
        bool: True if successful, False otherwise
    """
    # Convert path to string if it's a Path object
    if isinstance(output_path, Path):
        output_path = str(output_path)

    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Determine file format
        _, ext = os.path.splitext(output_path)
        ext = ext.lower()

        if ext in [".jpg", ".jpeg"]:
            # JPEG with optimized parameters
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        elif ext == ".png":
            # PNG with compression
            params = [cv2.IMWRITE_PNG_COMPRESSION, 9]  # Max compression
        else:
            # Default parameters
            params = []

        # Save the image
        result = cv2.imwrite(output_path, image, params)

        # Update cache for test images
        if result and is_test_image(output_path):
            img_hash = compute_image_hash(image)
            image_cache.set(img_hash, image)

        return result
    except Exception as e:
        print(f"Error saving image {output_path}: {str(e)}")
        return False


def is_test_image(image_path: Union[str, Path]) -> bool:
    """
    Check if an image is in the test directory.

    Args:
        image_path: Path to the image

    Returns:
        bool: True if it's a test image, False otherwise
    """
    # Convert to Path for easier path manipulation
    if isinstance(image_path, str):
        image_path = Path(image_path)

    # Check if the image is in the test directory
    test_dir = Path(__file__).parents[2] / "source" / "images" / "test"

    try:
        # Check if the image is in the test directory
        return image_path.is_relative_to(test_dir)
    except Exception:
        # Fallback for Python versions without is_relative_to
        return str(test_dir) in str(image_path.absolute())


def get_image_file_hash(image_path: Union[str, Path]) -> str:
    """
    Compute a hash of an image file without loading the full image.

    Args:
        image_path: Path to the image

    Returns:
        str: Hash string
    """
    # Convert path to string if it's a Path object
    if isinstance(image_path, Path):
        image_path = str(image_path)

    try:
        # Use file size and modification time for faster hashing
        file_stat = os.stat(image_path)
        file_data = f"{image_path}:{file_stat.st_size}:{file_stat.st_mtime}"
        return hashlib.md5(file_data.encode()).hexdigest()
    except Exception as e:
        print(f"Error computing file hash: {str(e)}")
        # Fallback to path-only hash
        return hashlib.md5(str(image_path).encode()).hexdigest()


def enhance_test_image(image: np.ndarray) -> np.ndarray:
    """
    Enhance a test image for better recognition.

    Args:
        image: Input image

    Returns:
        numpy.ndarray: Enhanced image
    """
    if image.size == 0:
        return image

    try:
        # Convert to grayscale if color
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Keep original color image
            enhanced = image.copy()
            # Convert to grayscale for processing
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            enhanced = image.copy()
            gray = image.copy()

        # Apply histogram equalization to improve contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Apply slight Gaussian blur to reduce noise
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # If original was color, replace the luminance channel
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Convert to LAB color space
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            # Replace L channel with enhanced grayscale
            lab[:, :, 0] = gray
            # Convert back to BGR
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            enhanced = gray

        return enhanced
    except Exception as e:
        print(f"Error enhancing image: {str(e)}")
        return image


def compare_test_images(original_path: Union[str, Path], result_path: Union[str, Path]) -> float:
    """
    Compare original and result test images to calculate similarity.

    Args:
        original_path: Path to original image
        result_path: Path to result image

    Returns:
        float: Similarity score between 0 and 1
    """
    # Load images
    original = load_image(original_path)
    result = load_image(result_path)

    if original is None or result is None:
        return 0.0

    try:
        # Resize to same dimensions if needed
        if original.shape != result.shape:
            result = cv2.resize(result, (original.shape[1], original.shape[0]))

        # Convert to grayscale for comparison
        if len(original.shape) == 3 and original.shape[2] == 3:
            original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        else:
            original_gray = original

        if len(result.shape) == 3 and result.shape[2] == 3:
            result_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        else:
            result_gray = result

        # Calculate structural similarity
        score, _ = cv2.compareHist(
            cv2.calcHist([original_gray], [0], None, [256], [0, 256]),
            cv2.calcHist([result_gray], [0], None, [256], [0, 256]),
            cv2.HISTCMP_CORREL,
        )

        # Normalize score to 0-1 range
        if score < 0:
            score = 0.0

        return float(score)
    except Exception as e:
        print(f"Error comparing images: {str(e)}")
        return 0.0


def create_composite_image(
    original_path: Union[str, Path],
    result_path: Union[str, Path],
    output_path: Union[str, Path],
) -> bool:
    """
    Create a side-by-side composite of original and result test images.

    Args:
        original_path: Path to original image
        result_path: Path to result image
        output_path: Path to save composite image

    Returns:
        bool: True if successful, False otherwise
    """
    # Load images
    original = load_image(original_path)
    result = load_image(result_path)

    if original is None or result is None:
        return False

    try:
        # Resize to same height if different
        if original.shape[0] != result.shape[0]:
            aspect_ratio = original.shape[1] / original.shape[0]
            width = int(result.shape[0] * aspect_ratio)
            original = cv2.resize(original, (width, result.shape[0]))

        # Create side-by-side composite
        composite = np.hstack((original, result))

        # Add labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(composite, "Original", (10, 30), font, 1, (0, 255, 0), 2)
        cv2.putText(composite, "Result", (original.shape[1] + 10, 30), font, 1, (0, 255, 0), 2)

        # Add similarity score
        similarity = compare_test_images(original_path, result_path)
        cv2.putText(
            composite,
            f"Similarity: {similarity:.2f}",
            (10, composite.shape[0] - 20),
            font,
            0.7,
            (0, 255, 0),
            2,
        )

        # Save composite image
        return save_image(composite, output_path)
    except Exception as e:
        print(f"Error creating composite image: {str(e)}")
        return False


def get_all_test_images() -> List[Path]:
    """
    Get a list of all test images.

    Returns:
        list: List of paths to test images
    """
    test_dir = Path(__file__).parents[2] / "source" / "images" / "test"

    if not test_dir.exists():
        return []

    test_files = []
    for ext in [".jpg", ".jpeg", ".png"]:
        test_files.extend(list(test_dir.glob(f"*{ext}")))

    return test_files


def preload_test_images() -> int:
    """
    Preload all test images into cache for faster processing.

    Returns:
        int: Number of images preloaded
    """
    test_files = get_all_test_images()
    count = 0

    for image_path in test_files:
        img = load_image(image_path)
        if img is not None:
            count += 1

    return count
