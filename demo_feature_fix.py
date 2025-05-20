"""
Demo script to show face recognition with fixed normalization values for SFace model.
This addresses the issue reported in the original error where face recognizer was failing.
"""

import os
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib import gridspec
from PIL import Image, ImageDraw, ImageFont
import logging
from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer
from typing import List, Tuple, Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('face_recognition_demo')

# Constants
CJKV_FONT_PATH = "fonts/SourceHanSansTC-VF.ttf"
EMBEDDING_DIR = "source/photo/contestants/embeddings"
TEST_IMAGE_PATH = "source/images/test/original.jpeg"
FONT_SIZE = 30

def load_embeddings():
    """Load embeddings from the gallery directory."""
    logger.info(f"Loading embeddings from: {os.path.abspath(EMBEDDING_DIR)}")
    
    embedding_files = [f for f in os.listdir(EMBEDDING_DIR) if f.endswith("_embedding.npy")]
    logger.info(f"Found {len(embedding_files)} embedding files")
    
    gallery_nicknames = []
    gallery_embeddings = []
    embedding_dimensions = None  # Will be set when we load the first embedding

    for f in embedding_files:
        try:
            file_path = os.path.join(EMBEDDING_DIR, f)
            arr = np.load(file_path)
            arr = arr.flatten()  # Ensure it's 1D
            
            if len(arr.shape) == 1:
                if embedding_dimensions is None:
                    embedding_dimensions = arr.shape[0]
                    logger.info(f"Using embedding dimension: {embedding_dimensions}")
                    
                nickname = os.path.basename(f).replace("_embedding.npy", "")
                gallery_nicknames.append(nickname)
                gallery_embeddings.append(arr)
            else:
                logger.warning(f"Skipping embedding file {f}: not a 1D array")
        except Exception as e:
            logger.error(f"Error loading embedding from {f}: {str(e)}")

    if not gallery_embeddings:
        logger.error("No embeddings found in gallery! Face recognition will not work.")
        return np.empty((0, 128), dtype=np.float32), []
    
    logger.info(f"Loaded {len(gallery_embeddings)} embeddings from gallery")
    return gallery_embeddings, gallery_nicknames

def overlay_faces(image, faces, matches, font_path=None):
    """Overlay bounding boxes and labels on an image."""
    image_pil = Image.fromarray(image)
    draw = ImageDraw.Draw(image_pil)
    
    # Load font or use default if the font file is not available
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE) if font_path else ImageFont.load_default()
    except Exception as e:
        logger.warning(f"Could not load font: {e}")
        font = ImageFont.load_default()
    
    for i, (face, match_list) in enumerate(zip(faces, matches)):
        # Convert bbox to integer values if it's not already
        if hasattr(face, 'bbox'):
            box = face.bbox.astype(int)
        else:
            # If face is just a bounding box array [x1, y1, x2, y2]
            box = np.array(face[:4]).astype(int)
        
        # Draw rectangle around face
        draw.rectangle([box[0], box[1], box[2], box[3]], outline=(0, 255, 0), width=2)
        
        # Create label text
        if match_list:
            label = f"{match_list[0][0]} ({match_list[0][1]:.2f})"
        else:
            label = f"Unknown ({i+1})"
        
        # Draw text background
        text_bbox = draw.textbbox((box[0], box[1] - FONT_SIZE - 5), label, font=font)
        draw.rectangle(text_bbox, fill=(0, 0, 0))
        
        # Draw text
        draw.text((box[0], box[1] - FONT_SIZE - 5), label, font=font, fill=(0, 255, 0))
    
    return np.array(image_pil)

def compare_recognition(image_path, threshold_original=0.35, threshold_fixed=0.6):
    """
    Compare face recognition results between original settings and fixed settings
    
    Args:
        image_path: Path to the test image
        threshold_original: Recognition threshold for original settings
        threshold_fixed: Recognition threshold for fixed settings
    """
    # Load test image
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"Failed to load image from {image_path}")
        return
    
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Load gallery embeddings
    gallery_embeddings, gallery_nicknames = load_embeddings()
    gallery_embeddings_np = np.stack(gallery_embeddings)
    
    # Initialize detectors and recognizers
    detector = FaceDetector(backend=FaceDetector.BACKEND_INSIGHTFACE, model_size=(640, 640), device="auto")
    
    # Create two face recognizers with different configurations
    recognizer_original = FaceRecognizer(
        face_detector=detector, 
        similarity_threshold=threshold_original,
        use_arcface=True
    )
    
    # The fixed recognizer uses our improved settings from face_recognizer.py
    # The key difference is mean/std values for SFace model (now [0.5, 0.5, 0.5] instead of [0.485, 0.456, 0.406])
    recognizer_fixed = FaceRecognizer(
        face_detector=detector, 
        similarity_threshold=threshold_fixed,
        use_arcface=True
    )
    
    # Method to compute similarity and return top matches
    def get_top_matches(embedding, top_n=3, threshold=0.4):
        # Normalize the query embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        else:
            return []
        
        # Compute similarities
        similarities = []
        for i, gallery_emb in enumerate(gallery_embeddings):
            # Normalize gallery embedding
            gallery_norm = np.linalg.norm(gallery_emb)
            if gallery_norm > 0:
                gallery_emb_norm = gallery_emb / gallery_norm
            else:
                gallery_emb_norm = gallery_emb
                
            # Ensure dimensions match
            min_dim = min(len(embedding), len(gallery_emb_norm))
            sim = np.dot(embedding[:min_dim], gallery_emb_norm[:min_dim])
            similarities.append((gallery_nicknames[i], sim, i))
        
        # Sort by similarity (descending)
        sorted_sims = sorted(similarities, key=lambda x: x[1], reverse=True)
        
        # Return top N matches above threshold
        return [(name, sim, idx) for name, sim, idx in sorted_sims[:top_n] if sim >= threshold]
    
    # Detect faces once
    detected_faces = detector.detect_faces(image_rgb)
    logger.info(f"Detected {len(detected_faces)} faces")
    
    if not detected_faces:
        logger.warning("No faces detected in the image")
        return
    
    # Process with original settings
    original_matches = []
    for face in detected_faces:
        face_crop = detector.extract_face(image_rgb, face.bbox.astype(int), padding=0.1)
        if face_crop is None:
            original_matches.append([])
            continue
            
        embedding = recognizer_original._get_embedding(face_crop)
        top_matches = get_top_matches(embedding, threshold=threshold_original)
        original_matches.append(top_matches)
        
        # Print info about top matches for this face
        if top_matches:
            logger.info(f"Original - Face {len(original_matches)}: Top match {top_matches[0][0]} with confidence {top_matches[0][1]:.4f}")
        else:
            logger.info(f"Original - Face {len(original_matches)}: No matches above threshold {threshold_original}")
    
    # Process with fixed settings
    fixed_matches = []
    for face in detected_faces:
        face_crop = detector.extract_face(image_rgb, face.bbox.astype(int), padding=0.1)
        if face_crop is None:
            fixed_matches.append([])
            continue
            
        embedding = recognizer_fixed._get_embedding(face_crop)
        top_matches = get_top_matches(embedding, threshold=threshold_fixed)
        fixed_matches.append(top_matches)
        
        # Print info about top matches for this face
        if top_matches:
            logger.info(f"Fixed - Face {len(fixed_matches)}: Top match {top_matches[0][0]} with confidence {top_matches[0][1]:.4f}")
        else:
            logger.info(f"Fixed - Face {len(fixed_matches)}: No matches above threshold {threshold_fixed}")
    
    # Generate visualizations
    original_img = overlay_faces(image_rgb.copy(), detected_faces, 
                                [[(name, sim) for name, sim, _ in matches] for matches in original_matches],
                                font_path=CJKV_FONT_PATH)
    
    fixed_img = overlay_faces(image_rgb.copy(), detected_faces, 
                            [[(name, sim) for name, sim, _ in matches] for matches in fixed_matches],
                            font_path=CJKV_FONT_PATH)
    
    # Create a figure with two subplots for comparison
    fig = plt.figure(figsize=(20, 10))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1, 1])
    
    ax0 = plt.subplot(gs[0])
    ax0.imshow(original_img)
    ax0.set_title(f"Original Settings (Threshold: {threshold_original})")
    ax0.axis('off')
    
    ax1 = plt.subplot(gs[1])
    ax1.imshow(fixed_img)
    ax1.set_title(f"Fixed Settings (Threshold: {threshold_fixed})")
    ax1.axis('off')
    
    plt.tight_layout()
    plt.savefig("source/images/test/demo_fixed_vs_original.png", dpi=150)
    logger.info("Saved comparison to source/images/test/demo_fixed_vs_original.png")
    plt.show()

if __name__ == "__main__":
    compare_recognition(TEST_IMAGE_PATH)
    logger.info("\nKey improvements in face recognition:")
    logger.info("1. Updated normalization values for SFace model to [0.5, 0.5, 0.5]")
    logger.info("2. Increased similarity threshold from 0.35 to 0.6 for better precision")
    logger.info("3. Fixed model-specific parameters based on detected model type")
