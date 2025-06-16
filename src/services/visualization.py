import logging
import os
import platform
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
import traceback

# Set matplotlib backend before importing pyplot to avoid NSWindow threading issues on macOS
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.figure import Figure
import umap.umap_ as umap
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

class VisualizationService:
    """
    Service for handling all visualization aspects of the face recognition system,
    including drawing annotations on frames, generating UMAP plots, and managing fonts.
    """

    def __init__(self, fonts_dir: Optional[str] = None):
        self.fonts_dir = fonts_dir if fonts_dir else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts")
        self.label_font = None
        self.timestamp_font = None
        self._setup_matplotlib_fonts()
        self._load_fonts()

    def _setup_matplotlib_fonts(self):
        """Setup matplotlib fonts with proper CJKV support and fallbacks."""
        cjkv_fonts = []
        if platform.system() == 'Darwin':
            cjkv_fonts.extend(['PingFang TC', 'Hiragino Sans GB', 'STHeiti', 'Apple LiGothic', 'SimHei'])
        elif platform.system() == 'Windows':
            cjkv_fonts.extend(['Microsoft YaHei', 'SimHei', 'KaiTi', 'FangSong'])
        else:
            cjkv_fonts.extend(['Noto Sans CJK TC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'AR PL UMing CN'])
        
        available_fonts = []
        for font_name in cjkv_fonts:
            try:
                font_files = fm.findSystemFonts(fontpaths=None, fontext='ttf')
                for font_file in font_files:
                    try:
                        font_prop = fm.FontProperties(fname=font_file)
                        if font_prop.get_name() == font_name:
                            available_fonts.append(font_name)
                            break
                    except Exception:
                        continue
            except Exception:
                continue
        
        font_list = available_fonts + ['DejaVu Sans', 'Arial', 'Helvetica', 'sans-serif']
        
        plt.rcParams['font.sans-serif'] = font_list
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = 16
        plt.rcParams['text.color'] = 'black'
        plt.rcParams['axes.labelcolor'] = 'black'
        plt.rcParams['xtick.color'] = 'black'
        plt.rcParams['ytick.color'] = 'black'
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['savefig.facecolor'] = 'white'
        plt.rcParams['savefig.dpi'] = 150
        
        logger.info(f"Configured matplotlib fonts: {font_list[:3]}...")

    def _load_fonts(self):
        """Loads fonts for PIL ImageDraw."""
        font_path = os.path.join(self.fonts_dir, "SourceHanSansTC-VF.ttf")
        if not os.path.exists(font_path):
            logger.warning("Font file not found: %s. Using default PIL font.", font_path)
            self.label_font = ImageFont.load_default()
            self.timestamp_font = ImageFont.load_default()
        else:
            try:
                self.label_font = ImageFont.truetype(font_path, 60)
                self.timestamp_font = ImageFont.truetype(font_path, 40)
            except Exception as e:
                logger.error("Error loading font from %s: %s. Using default PIL font.", font_path, e)
                self.label_font = ImageFont.load_default()
                self.timestamp_font = ImageFont.load_default()

    def generate_umap_plot(
        self,
        detected_embeddings: List[np.ndarray],
        gallery_embeddings: Dict[str, List[np.ndarray]],
        gallery_names: Dict[str, str],
        detected_labels: List[str],
        show_current_only: bool = False
    ) -> Figure:
        """
        Generate enhanced UMAP plot showing relationships between detected faces and gallery embeddings.

        Args:
            detected_embeddings: List of embeddings from the current frame.
            gallery_embeddings: Dictionary of known embeddings from the gallery.
            gallery_names: Dictionary mapping internal gallery names to display names.
            detected_labels: Labels corresponding to detected_embeddings (e.g., "Unknown", "Name (score)").
            show_current_only: If True, only show embeddings from the current frame and their matches.

        Returns:
            matplotlib.figure.Figure: The generated UMAP plot.
        """
        # Prepare data structures
        all_embeddings = []
        all_labels = []
        all_types = []  # 'current', 'gallery_matched', 'gallery_other'
        gallery_indices = {}  # Map gallery names to their indices in all_embeddings
        
        # Add gallery embeddings first
        for name, emb_list in gallery_embeddings.items():
            display_name = gallery_names.get(name, name)
            gallery_indices[name] = []
            for emb in emb_list:
                all_embeddings.append(emb)
                all_labels.append(display_name)
                all_types.append('gallery_other')  # Will update later if matched
                gallery_indices[name].append(len(all_embeddings) - 1)
        
        # Add current detected embeddings
        current_start_idx = len(all_embeddings)
        all_embeddings.extend(detected_embeddings)
        all_labels.extend(detected_labels)
        all_types.extend(['current'] * len(detected_embeddings))
        
        if not all_embeddings:
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(0.5, 0.5, "No embeddings to visualize", ha='center', va='center', fontsize=14)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            return fig
        
        # Check if we have enough embeddings for UMAP
        if len(all_embeddings) < 2: # UMAP needs at least 2 samples
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(0.5, 0.5, f"Not enough embeddings for UMAP visualization\n(found {len(all_embeddings)}, need at least 2)", 
                    ha='center', va='center', wrap=True, fontsize=12)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            return fig
        
        # Calculate similarities between current detections and gallery
        matches_info = []
        if detected_embeddings:
            for i, curr_emb in enumerate(detected_embeddings):
                curr_emb_flat = curr_emb.flatten().astype(np.float32)
                best_matches = []
                
                for name, indices in gallery_indices.items():
                    for idx in indices:
                        gallery_emb = all_embeddings[idx].flatten().astype(np.float32)
                        
                        # Calculate cosine similarity
                        norm_curr = np.linalg.norm(curr_emb_flat)
                        norm_gallery = np.linalg.norm(gallery_emb)
                        if norm_curr > 1e-10 and norm_gallery > 1e-10:
                            similarity = np.dot(curr_emb_flat, gallery_emb) / (norm_curr * norm_gallery)
                        else:
                            similarity = 0.0
                        
                        best_matches.append((idx, name, similarity))
                
                # Sort by similarity and keep top 5
                best_matches.sort(key=lambda x: x[2], reverse=True)
                top_matches = best_matches[:5]
                matches_info.append((current_start_idx + i, top_matches))
                
                # Mark matched gallery embeddings
                for idx, name, sim in top_matches:
                    if sim > 0.5:  # Threshold for considering it a match
                        all_types[idx] = 'gallery_matched'
        
        # Perform UMAP
        n_neighbors = min(15, len(all_embeddings) - 1)
        reducer = umap.UMAP(n_neighbors=n_neighbors, min_dist=0.1)
        embeddings_2d_raw = reducer.fit_transform(np.array(all_embeddings))
        if isinstance(embeddings_2d_raw, tuple):
            embeddings_2d = embeddings_2d_raw[0]
        else:
            embeddings_2d = embeddings_2d_raw

        if not isinstance(embeddings_2d, (np.ndarray, np.generic)):
            embeddings_2d = embeddings_2d.toarray()
        
        # Create enhanced scatter plot
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Plot gallery embeddings (non-matched)
        gallery_other_mask = np.array([t == 'gallery_other' for t in all_types])
        if np.any(gallery_other_mask):
            ax.scatter(embeddings_2d[gallery_other_mask, 0], 
                      embeddings_2d[gallery_other_mask, 1],
                      c='lightgray', s=50, alpha=0.3, marker='o',
                      label='Gallery (unmatched)', edgecolors='none')
        
        # Plot gallery embeddings (matched)
        gallery_matched_mask = np.array([t == 'gallery_matched' for t in all_types])
        if np.any(gallery_matched_mask):
            # Group by person for coloring
            matched_labels = [all_labels[i] for i, matched in enumerate(gallery_matched_mask) if matched]
            unique_matched = list(set(matched_labels))
            # Use a colormap for matched gallery embeddings
            colors = plt.get_cmap('tab20')(np.linspace(0, 1, len(unique_matched)))
            
            for i, person in enumerate(unique_matched):
                person_mask = np.array([t == 'gallery_matched' and all_labels[j] == person 
                                       for j, t in enumerate(all_types)])
                ax.scatter(embeddings_2d[person_mask, 0], 
                          embeddings_2d[person_mask, 1],
                          c=[colors[i]], s=150, alpha=0.8, marker='s',
                          label=f'{person} (matched)', edgecolors='black', linewidth=1)
                
                # Add label for matched gallery points
                if np.any(person_mask):
                    # Find the centroid of the cluster for labeling
                    centroid_x = np.mean(embeddings_2d[person_mask, 0])
                    centroid_y = np.mean(embeddings_2d[person_mask, 1])
                    ax.annotate(person, (centroid_x, centroid_y), 
                               xytext=(0, 10), textcoords='offset points',
                               fontsize=9, ha='center', va='bottom',
                               bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7))

        # Plot current detected faces
        current_mask = np.array([t == 'current' for t in all_types])
        if np.any(current_mask):
            current_points = embeddings_2d[current_mask]
            ax.scatter(current_points[:, 0], current_points[:, 1],
                      c='red', s=300, alpha=1.0, marker='*',
                      label='Current Detection', edgecolors='darkred', linewidth=2, zorder=3)
            
            # Add labels for current detections with recognized names
            for i, (x, y) in enumerate(current_points):
                label_text = all_labels[current_start_idx + i] # Get the actual label (e.g., "Unknown" or "Name (score)")
                ax.annotate(label_text, (x, y), 
                           xytext=(5, 5), textcoords='offset points',
                           fontsize=10, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                           zorder=4)
        
        # Draw connection lines between current detections and their matches
        for curr_idx, top_matches in matches_info:
            curr_x, curr_y = embeddings_2d[curr_idx]
            
            for match_idx, match_name, similarity in top_matches:
                if similarity > 0.5:  # Only show significant matches
                    match_x, match_y = embeddings_2d[match_idx]
                    
                    # Line properties based on similarity
                    alpha = min(similarity, 0.8)
                    linewidth = 1 + (similarity * 2)
                    
                    # Draw arrow
                    ax.annotate('', xy=(match_x, match_y), xytext=(curr_x, curr_y),
                                arrowprops=dict(facecolor='green', edgecolor='green', 
                                                arrowstyle='->', linewidth=linewidth, 
                                                alpha=alpha, shrinkA=5, shrinkB=5),
                                zorder=2)
                    
                    # Add similarity score at midpoint
                    mid_x, mid_y = (curr_x + match_x) / 2, (curr_y + match_y) / 2
                    ax.annotate(f'{similarity:.2f}', (mid_x, mid_y),
                               fontsize=8, ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8),
                               zorder=5)
        
        # Customize plot
        ax.set_title("Face Embedding Relationships (UMAP)", fontsize=16, fontweight='bold')
        ax.set_xlabel("UMAP Dimension 1", fontsize=12)
        ax.set_ylabel("UMAP Dimension 2", fontsize=12)
        
        # Add legend with custom positioning
        legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', 
                          fontsize=10, framealpha=0.9)
        
        # Add grid for better readability
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Add similarity scale reference
        ax.text(0.02, 0.98, 'Line thickness = similarity strength\nGreen arrows show matches > 0.5',
                transform=ax.transAxes, fontsize=9, verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        return fig