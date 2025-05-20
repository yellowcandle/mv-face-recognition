"""
Visualization utilities for the Gradio interface.

This module provides functions for creating visualizations and plots
specific to the Gradio interface for face recognition.
"""

import os
import logging
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import List, Dict, Any, Tuple, Optional, Union
import cv2
from sklearn.decomposition import PCA
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import visualization utilities from the main project
from src.utils.visualization import draw_bbox, draw_multiple_boxes

def plot_bar(matches: List[Tuple[str, float]], max_items: int = 10) -> Figure:
    """
    Create a bar chart visualization of face recognition matches.

    Args:
        matches: List of (name, confidence) tuples
        max_items: Maximum number of items to show

    Returns:
        Matplotlib figure object
    """
    try:
        plt.close('all')  # Close any existing plots to prevent memory leaks
        
        # Create a new figure
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        # Check if there are any matches
        if not matches:
            ax.text(0.5, 0.5, "No matches found", 
                   horizontalalignment='center',
                   verticalalignment='center',
                   transform=ax.transAxes, 
                   fontsize=14)
            ax.set_title("Recognition Results")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig
        
        # Limit to max_items
        if len(matches) > max_items:
            matches = matches[:max_items]
        
        # Extract names and scores
        names = [m[0] for m in matches]
        scores = [m[1] for m in matches]
        
        # Create horizontal bar chart
        bars = ax.barh(names, scores, color='skyblue')
        
        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(max(width + 0.01, 0.05), 
                   bar.get_y() + bar.get_height()/2, 
                   f'{width:.2f}', 
                   va='center')
        
        # Set title and labels
        ax.set_title("Recognition Results")
        ax.set_xlabel("Confidence Score")
        
        # Set limits
        ax.set_xlim(0, 1.0)
        
        # Add a threshold line at 0.6 (typical threshold)
        ax.axvline(x=0.6, color='red', linestyle='--', alpha=0.7)
        ax.text(0.6, ax.get_ylim()[1] * 0.02, "Threshold", 
               horizontalalignment='center', 
               color='red')
        
        fig.tight_layout()
        return fig
    except Exception as e:
        logger.error(f"Error creating bar plot: {str(e)}")
        # Create a fallback figure
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"Error creating visualization:\n{str(e)}", 
               horizontalalignment='center',
               verticalalignment='center',
               transform=ax.transAxes, 
               fontsize=12,
               color='red')
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

def plot_embedding_scatter(
    detected_embeddings: List[np.ndarray],
    gallery_embeddings: Dict[str, List[np.ndarray]],
    gallery_names: Dict[str, str],
    matches: List[List[Tuple[str, float, int]]],
    dim_reduction: str = "pca"
) -> Figure:
    """
    Create a scatter plot visualization of face embeddings.

    Args:
        detected_embeddings: List of embeddings from detected faces
        gallery_embeddings: Dictionary of known embeddings
        gallery_names: Dictionary mapping IDs to display names
        matches: List of matches for each detected face
        dim_reduction: Dimension reduction method ('pca' or 'tsne')

    Returns:
        Matplotlib figure object
    """
    try:
        plt.close('all')  # Close any existing plots to prevent memory leaks
        
        # Create a new figure
        fig = Figure(figsize=(10, 8))
        ax = fig.add_subplot(111)
        
        # Check if there are any detected embeddings
        if not detected_embeddings or len(detected_embeddings) == 0:
            ax.text(0.5, 0.5, "No face embeddings detected", 
                   horizontalalignment='center',
                   verticalalignment='center',
                   transform=ax.transAxes, 
                   fontsize=14)
            ax.set_title("Embedding Visualization")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig
        
        # Prepare data for dimension reduction
        all_embeddings = []
        categories = []
        labels = []
        
        # Add detected faces
        for i, embedding in enumerate(detected_embeddings):
            if embedding is None or embedding.size == 0:
                continue
            all_embeddings.append(embedding)
            categories.append('detected')
            labels.append(f"Face {i+1}")
        
        # Add gallery faces that were matched
        matched_ids = set()
        for match_list in matches:
            for name, _, idx in match_list:
                matched_ids.add(name)
        
        # Add top matches from gallery
        for person_id, embeddings_list in gallery_embeddings.items():
            display_name = gallery_names.get(person_id, person_id)
            if person_id in matched_ids:
                # If this person was matched, include their embedding
                for idx, emb in enumerate(embeddings_list):
                    all_embeddings.append(emb)
                    categories.append('matched_gallery')
                    labels.append(f"{display_name} ({idx+1})")
            elif len(all_embeddings) < 100:  # Limit total points for performance
                # Include some non-matched gallery items for context
                for idx, emb in enumerate(embeddings_list[:1]):  # Just include first embedding
                    all_embeddings.append(emb)
                    categories.append('unmatched_gallery')
                    labels.append(f"{display_name}")
        
        # Convert to numpy array
        embeddings_array = np.array(all_embeddings)
        
        # Apply dimension reduction if we have enough samples
        if len(embeddings_array) > 1:
            # Use PCA for dimension reduction
            if embeddings_array.shape[0] >= 2:  # Need at least 2 samples for PCA
                pca = PCA(n_components=2)
                reduced_data = pca.fit_transform(embeddings_array)
                
                # Create a DataFrame for easier plotting
                df = pd.DataFrame({
                    'x': reduced_data[:, 0],
                    'y': reduced_data[:, 1],
                    'category': categories,
                    'label': labels
                })
                
                # Plot each category with different colors
                for category, color, marker in [
                    ('detected', 'red', 'o'),
                    ('matched_gallery', 'green', 's'),
                    ('unmatched_gallery', 'gray', 'x')
                ]:
                    subset = df[df['category'] == category]
                    if not subset.empty:
                        ax.scatter(
                            subset['x'], subset['y'], 
                            c=color, label=category, alpha=0.7,
                            marker=marker, s=100 if category == 'detected' else 70
                        )
                        
                        # Add labels for points
                        for _, row in subset.iterrows():
                            ax.annotate(
                                row['label'],
                                (row['x'], row['y']),
                                textcoords="offset points",
                                xytext=(0, 7),
                                ha='center',
                                fontsize=8,
                                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.6)
                            )
                
                # Calculate explained variance for axis labels
                variance_ratio = pca.explained_variance_ratio_
                ax.set_xlabel(f'PC1 ({variance_ratio[0]:.2%} variance)')
                ax.set_ylabel(f'PC2 ({variance_ratio[1]:.2%} variance)')
                
                # Add legend and title
                ax.legend(title="Categories")
                ax.set_title("Face Embedding Visualization (PCA)")
                
                # Add grid for better readability
                ax.grid(alpha=0.3)
                
                # Equal aspect ratio for better visual representation
                ax.set_aspect('equal', adjustable='box')
            else:
                ax.text(0.5, 0.5, "Not enough data for dimensionality reduction", 
                       horizontalalignment='center',
                       verticalalignment='center',
                       transform=ax.transAxes, 
                       fontsize=14)
        else:
            ax.text(0.5, 0.5, "No embeddings to visualize", 
                   horizontalalignment='center',
                   verticalalignment='center',
                   transform=ax.transAxes, 
                   fontsize=14)
        
        fig.tight_layout()
        return fig
    except Exception as e:
        logger.error(f"Error creating scatter plot: {str(e)}")
        # Create a fallback figure
        fig = Figure(figsize=(10, 8))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"Error creating visualization:\n{str(e)}", 
               horizontalalignment='center',
               verticalalignment='center',
               transform=ax.transAxes, 
               fontsize=12,
               color='red')
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

def draw_faces_with_labels(
    image: np.ndarray,
    faces: List[Dict[str, Any]],
    box_thickness: int = 2,
    font_scale: float = 0.7,
    include_score: bool = True,
) -> np.ndarray:
    """
    Draw faces with recognition labels on an image.

    Args:
        image: Input image
        faces: List of face dictionaries with bbox, name, confidence
        box_thickness: Line thickness for bounding boxes
        font_scale: Font scale for text
        include_score: Whether to include confidence score in label

    Returns:
        Image with drawn faces and labels
    """
    try:
        # Create a deep copy of the image to avoid modifying the original
        img_with_faces = image.copy()
        
        # Draw each face
        for face in faces:
            bbox = face.get('bbox')
            if bbox is None:
                continue
                
            name = face.get('name', 'Unknown')
            confidence = face.get('confidence', 0.0)
            
            # Determine color based on confidence (green for high, red for low)
            g = min(255, int(confidence * 255))
            r = min(255, int((1 - confidence) * 255))
            color = (0, g, r)  # BGR format for OpenCV
            
            # Create label
            if include_score and confidence > 0:
                label = f"{name} ({confidence:.2f})"
            else:
                label = name
                
            # Draw bounding box and label
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            cv2.rectangle(img_with_faces, (x1, y1), (x2, y2), color, box_thickness)
            
            # Add text background
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, box_thickness)[0]
            cv2.rectangle(
                img_with_faces,
                (x1, y1 - text_size[1] - 10),
                (x1 + text_size[0] + 10, y1),
                color,
                -1  # Fill rectangle
            )
            
            # Add text
            cv2.putText(
                img_with_faces,
                label,
                (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),  # White text
                box_thickness
            )
        
        return img_with_faces
    except Exception as e:
        logger.error(f"Error drawing faces: {str(e)}")
        # Return the original image if there's an error
        if image is not None:
            # Add error text to the image
            img_copy = image.copy()
            cv2.putText(
                img_copy,
                f"Error: {str(e)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),  # Red text
                2
            )
            return img_copy
        return np.zeros((300, 300, 3), dtype=np.uint8)  # Return a blank image as fallback

