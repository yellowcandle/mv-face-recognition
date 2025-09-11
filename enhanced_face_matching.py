"""
Enhanced face matching logic with embedding-based similarity and improved tracking.
This module contains the optimized functions for face similarity calculation and persistent label management.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


def calculate_enhanced_face_similarity(
    bbox1, bbox2, embedding1=None, embedding2=None, embedding_weight=0.6
):
    """
    Calculate enhanced similarity between two faces using both bbox and embedding information.

    Args:
        bbox1, bbox2: Face bounding boxes
        embedding1, embedding2: Optional face embeddings for identity matching
        embedding_weight: Weight for embedding similarity (0.6 = 60% embedding, 40% bbox)

    Returns:
        Combined similarity score (higher = more similar, for consistency with embedding similarity)
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2

    # Calculate bbox similarity components
    center1 = ((x1_1 + x2_1) / 2, (y1_1 + y2_1) / 2)
    center2 = ((x1_2 + x2_2) / 2, (y1_2 + y2_2) / 2)

    # Calculate distance between centers
    distance = np.sqrt((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2)

    # Calculate size similarity
    size1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    size2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    size_ratio = min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 0

    # Calculate IoU (Intersection over Union)
    x_overlap = max(0, min(x2_1, x2_2) - max(x1_1, x1_2))
    y_overlap = max(0, min(y2_1, y2_2) - max(y1_1, y1_2))
    intersection = x_overlap * y_overlap
    union = size1 + size2 - intersection
    iou = intersection / union if union > 0 else 0

    # Normalize distance by face size
    face_size = max(x2_1 - x1_1, y2_1 - y1_1, 50)
    normalized_distance = distance / face_size

    # Calculate bbox similarity (higher = more similar)
    bbox_similarity = (
        0.4 * max(0, 1 - normalized_distance)  # Distance similarity
        + 0.3 * size_ratio  # Size similarity
        + 0.3 * iou  # Overlap similarity
    )

    # Calculate embedding similarity if available
    embedding_similarity = 0.0
    if embedding1 is not None and embedding2 is not None:
        try:
            # Ensure embeddings are normalized
            emb1_norm = embedding1 / (np.linalg.norm(embedding1) + 1e-8)
            emb2_norm = embedding2 / (np.linalg.norm(embedding2) + 1e-8)

            # Cosine similarity
            embedding_similarity = np.dot(emb1_norm, emb2_norm)
            embedding_similarity = max(0.0, embedding_similarity)  # Clamp to [0, 1]
        except Exception as e:
            logger.debug(f"Error calculating embedding similarity: {e}")
            embedding_similarity = 0.0

    # Combine similarities based on availability
    if embedding1 is not None and embedding2 is not None:
        # Use weighted combination of bbox and embedding
        combined_similarity = (
            1 - embedding_weight
        ) * bbox_similarity + embedding_weight * embedding_similarity
    else:
        # Fall back to bbox similarity only
        combined_similarity = bbox_similarity

    return combined_similarity


def update_enhanced_persistent_labels(
    matches, label_cache, current_frame, persistence_duration=300
):
    """
    Enhanced persistent label cache with improved tracking and longer persistence.

    Args:
        matches: List of (face, name) tuples from current frame
        label_cache: Dictionary of persistent face labels
        current_frame: Current frame number
        persistence_duration: How long to keep labels (default 300 frames = 10 seconds at 30fps)

    Returns:
        Updated label cache with enhanced tracking
    """
    # Clean up expired labels
    expired_keys = [
        key for key, data in label_cache.items() if data["expire_frame"] < current_frame
    ]
    for key in expired_keys:
        del label_cache[key]

    # Process new matches with enhanced similarity calculation
    for face, name in matches:
        if name == "Unknown":
            continue

        bbox = face.bbox.astype(int)

        # Extract embedding if available
        embedding = None
        if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
            embedding = face.normed_embedding
        elif hasattr(face, "embedding") and face.embedding is not None:
            embedding = face.embedding

        face_key = None
        best_similarity = 0.0  # Changed to 0.0 since we now use higher = better

        # Try to match with existing faces using enhanced similarity
        for existing_key, existing_data in label_cache.items():
            # Get existing embedding if available
            existing_embedding = existing_data.get("embedding", None)

            # Calculate enhanced similarity including embeddings
            similarity = calculate_enhanced_face_similarity(
                bbox,
                existing_data["bbox"],
                embedding,
                existing_embedding,
                embedding_weight=0.6,
            )

            # Use higher threshold for better matching (0.5 instead of 0.2)
            if similarity > 0.5 and similarity > best_similarity:
                best_similarity = similarity
                face_key = existing_key

        # Create new face key if no match found
        if face_key is None:
            face_key = f"face_{current_frame}_{len(label_cache)}"

        # Enhanced bbox smoothing for existing faces
        if face_key in label_cache:
            old_bbox = label_cache[face_key]["bbox"]

            # Adaptive smoothing based on similarity confidence
            # Higher similarity = more aggressive smoothing
            base_smooth_factor = 0.7
            confidence_boost = min(0.2, best_similarity * 0.3)
            smooth_factor = base_smooth_factor + confidence_boost

            # Exponential moving average for smoother transitions
            smoothed_bbox = [
                int(old_bbox[0] * smooth_factor + bbox[0] * (1 - smooth_factor)),
                int(old_bbox[1] * smooth_factor + bbox[1] * (1 - smooth_factor)),
                int(old_bbox[2] * smooth_factor + bbox[2] * (1 - smooth_factor)),
                int(old_bbox[3] * smooth_factor + bbox[3] * (1 - smooth_factor)),
            ]
            bbox = smoothed_bbox

            # Update trajectory confidence
            trajectory_confidence = label_cache[face_key].get(
                "trajectory_confidence", 0.5
            )
            # Boost confidence for consistent detections
            trajectory_confidence = min(1.0, trajectory_confidence + 0.05)
        else:
            # New trajectory starts with base confidence
            trajectory_confidence = 0.6

        # Enhanced cache entry with more tracking information
        label_cache[face_key] = {
            "name": name,
            "bbox": bbox,
            "embedding": embedding,  # Store embedding for future comparisons
            "expire_frame": current_frame + persistence_duration,
            "last_seen": current_frame,
            "first_seen": label_cache[face_key].get("first_seen", current_frame)
            if face_key in label_cache
            else current_frame,
            "confidence": getattr(face, "det_score", 1.0)
            if hasattr(face, "det_score")
            else 1.0,
            "trajectory_confidence": trajectory_confidence,
            "similarity_score": best_similarity,
            "detection_count": label_cache[face_key].get("detection_count", 0) + 1
            if face_key in label_cache
            else 1,
        }

    return label_cache


def get_trajectory_stability_metrics(label_cache, current_frame):
    """
    Calculate stability metrics for all active trajectories.

    Args:
        label_cache: Dictionary of persistent face labels
        current_frame: Current frame number

    Returns:
        Dictionary with stability metrics for each trajectory
    """
    stability_metrics = {}

    for face_key, data in label_cache.items():
        # Calculate trajectory duration
        duration = current_frame - data.get("first_seen", current_frame)

        # Calculate detection consistency
        detection_count = data.get("detection_count", 1)
        expected_detections = max(1, duration // 5)  # Expect detection every 5 frames
        consistency_ratio = min(1.0, detection_count / expected_detections)

        # Calculate overall stability
        trajectory_confidence = data.get("trajectory_confidence", 0.5)
        similarity_score = data.get("similarity_score", 0.5)

        overall_stability = (
            0.4 * trajectory_confidence
            + 0.3 * consistency_ratio
            + 0.3 * similarity_score
        )

        stability_metrics[face_key] = {
            "duration": duration,
            "detection_count": detection_count,
            "consistency_ratio": consistency_ratio,
            "trajectory_confidence": trajectory_confidence,
            "similarity_score": similarity_score,
            "overall_stability": overall_stability,
            "is_stable": overall_stability > 0.7
            and duration > 30,  # Stable if good metrics and >1 second
        }

    return stability_metrics
