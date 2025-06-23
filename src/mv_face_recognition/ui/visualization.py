import logging
import os
import platform

# Set matplotlib backend before importing pyplot to avoid NSWindow threading issues on macOS
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import umap.umap_ as umap
from matplotlib.figure import Figure
from PIL import ImageFont

logger = logging.getLogger(__name__)


class VisualizationService:
    """
    Service for handling all visualization aspects of the face recognition system,
    including drawing annotations on frames, generating UMAP plots, and managing fonts.
    """

    def __init__(self, fonts_dir: str | None = None):
        self.fonts_dir = (
            fonts_dir
            if fonts_dir
            else os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts"
            )
        )
        self.label_font = None
        self.timestamp_font = None
        self._setup_matplotlib_fonts()
        self._load_fonts()

    def _setup_matplotlib_fonts(self):
        """Setup matplotlib fonts with proper CJKV support and fallbacks."""
        cjkv_fonts = []
        if platform.system() == "Darwin":
            cjkv_fonts.extend(
                [
                    "PingFang TC",
                    "Hiragino Sans GB",
                    "STHeiti",
                    "Apple LiGothic",
                    "SimHei",
                ]
            )
        elif platform.system() == "Windows":
            cjkv_fonts.extend(["Microsoft YaHei", "SimHei", "KaiTi", "FangSong"])
        else:
            cjkv_fonts.extend(
                [
                    "Noto Sans CJK TC",
                    "Noto Sans CJK SC",
                    "WenQuanYi Micro Hei",
                    "AR PL UMing CN",
                ]
            )

        available_fonts = []
        for font_name in cjkv_fonts:
            try:
                font_files = fm.findSystemFonts(fontpaths=None, fontext="ttf")
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

        font_list = available_fonts + [
            "DejaVu Sans",
            "Arial",
            "Helvetica",
            "sans-serif",
        ]

        plt.rcParams["font.sans-serif"] = font_list
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["font.size"] = 16
        plt.rcParams["text.color"] = "black"
        plt.rcParams["axes.labelcolor"] = "black"
        plt.rcParams["xtick.color"] = "black"
        plt.rcParams["ytick.color"] = "black"
        plt.rcParams["figure.facecolor"] = "white"
        plt.rcParams["savefig.facecolor"] = "white"
        plt.rcParams["savefig.dpi"] = 150

        logger.info(f"Configured matplotlib fonts: {font_list[:3]}...")

    def _load_fonts(self):
        """Loads fonts for PIL ImageDraw with multiple fallback paths."""
        # Debug: Log current working directory and font directory
        logger.info("Current working directory: %s", os.getcwd())
        logger.info("Font directory setting: %s", self.fonts_dir)

        # Try multiple possible font locations
        font_locations = [
            os.path.join(self.fonts_dir, "SourceHanSansTC-VF.ttf"),  # Relative to project
            os.path.join("fonts", "SourceHanSansTC-VF.ttf"),  # Direct relative path
            "./fonts/SourceHanSansTC-VF.ttf",  # Current directory relative
            "fonts/SourceHanSansTC-VF.ttf",  # No leading ./
        ]

        font_path = None
        for location in font_locations:
            if os.path.exists(location):
                font_path = location
                break

        if not font_path:
            logger.warning(
                "Font file not found in any of these locations: %s. Using default PIL font.",
                font_locations
            )
            self.label_font = ImageFont.load_default()
            self.timestamp_font = ImageFont.load_default()
        else:
            try:
                self.label_font = ImageFont.truetype(font_path, 60)
                self.timestamp_font = ImageFont.truetype(font_path, 40)
                logger.info("Successfully loaded font from: %s", font_path)
            except Exception as e:
                logger.error(
                    "Error loading font from %s: %s. Using default PIL font.",
                    font_path,
                    e,
                )
                self.label_font = ImageFont.load_default()
                self.timestamp_font = ImageFont.load_default()

    def generate_umap_plot(
        self,
        detected_embeddings: list[np.ndarray],
        gallery_embeddings: dict[str, list[np.ndarray]],
        gallery_names: dict[str, str],
        detected_labels: list[str],
        show_current_only: bool = False,
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
        # Define consistent color palette for contestants (matching timeline colors)
        color_palette = [
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#96CEB4",
            "#FFEAA7",
            "#DDA0DD",
            "#98D8C8",
            "#F7DC6F",
            "#BB8FCE",
            "#85C1E9",
            "#F8C471",
            "#82E0AA",
            "#F1948A",
            "#85929E",
            "#D2B4DE",
            "#F39C12",
            "#E74C3C",
            "#9B59B6",
            "#3498DB",
            "#1ABC9C",
            "#2ECC71",
            "#F1C40F",
            "#E67E22",
            "#E91E63",
            "#9C27B0",
        ]

        # Get all unique contestants and create color mapping
        all_contestant_names = set()
        for label in detected_labels:
            # Extract contestant name (remove confidence scores if present)
            clean_name = label.split("(")[0].strip() if "(" in label else label.strip()
            if clean_name != "Unknown":
                all_contestant_names.add(clean_name)

        for name in gallery_names.values():
            all_contestant_names.add(name)

        # Also add any names from the internal gallery keys
        for name in gallery_embeddings.keys():
            all_contestant_names.add(name)

        contestants_list = sorted(all_contestant_names)

        # Ensure we have enough colors, repeat the palette if needed
        extended_palette = color_palette * (
            (len(contestants_list) // len(color_palette)) + 1
        )
        contestant_color_map = dict(
            zip(contestants_list, extended_palette[: len(contestants_list)], strict=False)
        )

        # Debug logging
        logger.info(
            f"UMAP Color Mapping: Found {len(contestants_list)} contestants: {contestants_list}"
        )
        logger.info(f"Color map keys: {list(contestant_color_map.keys())}")

        # Prepare data structures
        all_embeddings = []
        all_labels = []
        all_types = []  # 'current', 'gallery_matched', 'gallery_other'
        all_colors = []  # Store color for each point
        gallery_indices = {}  # Map gallery names to their indices in all_embeddings

        # Add gallery embeddings first
        for name, emb_list in gallery_embeddings.items():
            display_name = gallery_names.get(name, name)
            gallery_indices[name] = []

            # Ensure we have a color for this contestant
            if display_name not in contestant_color_map:
                # Add missing contestant to color map
                next_color_index = len(contestant_color_map) % len(extended_palette)
                contestant_color_map[display_name] = extended_palette[next_color_index]
                logger.warning(
                    f"Added missing gallery contestant '{display_name}' to color map with color {extended_palette[next_color_index]}"
                )

            contestant_color = contestant_color_map.get(display_name, "#888888")

            for emb in emb_list:
                all_embeddings.append(emb)
                all_labels.append(display_name)
                all_types.append("gallery_other")  # Will update later if matched
                all_colors.append(contestant_color)
                gallery_indices[name].append(len(all_embeddings) - 1)

        # Add current detected embeddings
        current_start_idx = len(all_embeddings)
        all_embeddings.extend(detected_embeddings)

        # Process detected labels and assign colors
        for label in detected_labels:
            clean_name = label.split("(")[0].strip() if "(" in label else label.strip()

            # Ensure we have a color for this contestant
            if clean_name not in contestant_color_map and clean_name != "Unknown":
                # Add missing contestant to color map
                next_color_index = len(contestant_color_map) % len(extended_palette)
                contestant_color_map[clean_name] = extended_palette[next_color_index]
                logger.warning(
                    f"Added missing contestant '{clean_name}' to color map with color {extended_palette[next_color_index]}"
                )

            contestant_color = contestant_color_map.get(
                clean_name, "#FF0000"
            )  # Red for Unknown/unmatched

            all_labels.append(label)
            all_types.append("current")
            all_colors.append(contestant_color)

        if not all_embeddings:
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(
                0.5,
                0.5,
                "No embeddings to visualize",
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            return fig

        # Check if we have enough embeddings for UMAP
        if len(all_embeddings) < 2:  # UMAP needs at least 2 samples
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(
                0.5,
                0.5,
                f"Not enough embeddings for UMAP visualization\n(found {len(all_embeddings)}, need at least 2)",
                ha="center",
                va="center",
                wrap=True,
                fontsize=12,
            )
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
                            similarity = np.dot(curr_emb_flat, gallery_emb) / (
                                norm_curr * norm_gallery
                            )
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
                        all_types[idx] = "gallery_matched"

        # Perform UMAP
        n_neighbors = min(15, len(all_embeddings) - 1)
        reducer = umap.UMAP(n_neighbors=n_neighbors, min_dist=0.1, random_state=42)
        embeddings_2d_raw = reducer.fit_transform(np.array(all_embeddings))
        if isinstance(embeddings_2d_raw, tuple):
            embeddings_2d = embeddings_2d_raw[0]
        else:
            embeddings_2d = embeddings_2d_raw

        if not isinstance(embeddings_2d, np.ndarray | np.generic):
            embeddings_2d = embeddings_2d.toarray()

        # Create enhanced scatter plot
        fig, ax = plt.subplots(figsize=(16, 12))

        # Plot gallery embeddings (non-matched) - use lighter versions of contestant colors
        gallery_other_mask = np.array([t == "gallery_other" for t in all_types])
        if np.any(gallery_other_mask):
            gallery_other_colors = [
                all_colors[i] for i, mask in enumerate(gallery_other_mask) if mask
            ]
            ax.scatter(
                embeddings_2d[gallery_other_mask, 0],
                embeddings_2d[gallery_other_mask, 1],
                c=gallery_other_colors,
                s=60,
                alpha=0.4,
                marker="o",
                label="Gallery (unmatched)",
                edgecolors="white",
                linewidth=1,
            )

        # Plot gallery embeddings (matched) - use full contestant colors
        gallery_matched_mask = np.array([t == "gallery_matched" for t in all_types])
        if np.any(gallery_matched_mask):
            # Group by person for consistent coloring
            matched_indices = [i for i, mask in enumerate(gallery_matched_mask) if mask]
            matched_labels = [all_labels[i] for i in matched_indices]
            [all_colors[i] for i in matched_indices]
            matched_positions = embeddings_2d[gallery_matched_mask]

            unique_matched = list(set(matched_labels))

            for person in unique_matched:
                person_indices = [
                    i for i, label in enumerate(matched_labels) if label == person
                ]
                person_positions = matched_positions[person_indices]
                person_color = contestant_color_map.get(person, "#888888")

                ax.scatter(
                    person_positions[:, 0],
                    person_positions[:, 1],
                    c=person_color,
                    s=120,
                    alpha=0.8,
                    marker="s",
                    label=f"{person} (gallery)",
                    edgecolors="black",
                    linewidth=1.5,
                )

                # Add label for matched gallery points
                if len(person_positions) > 0:
                    # Find the centroid of the cluster for labeling
                    centroid_x = np.mean(person_positions[:, 0])
                    centroid_y = np.mean(person_positions[:, 1])
                    ax.annotate(
                        person,
                        (centroid_x, centroid_y),
                        xytext=(0, 15),
                        textcoords="offset points",
                        fontsize=10,
                        ha="center",
                        va="bottom",
                        bbox={
                            "boxstyle": "round,pad=0.3",
                            "fc": "white",
                            "alpha": 0.8,
                            "edgecolor": person_color,
                        },
                        fontweight="bold",
                    )

        # Plot current detected faces - use contestant colors or red for unknown
        current_mask = np.array([t == "current" for t in all_types])
        if np.any(current_mask):
            current_indices = [i for i, mask in enumerate(current_mask) if mask]
            current_labels = [all_labels[i] for i in current_indices]
            current_colors = [all_colors[i] for i in current_indices]
            current_positions = embeddings_2d[current_mask]

            # Group current detections by contestant
            unique_current = {}
            for i, label in enumerate(current_labels):
                clean_name = (
                    label.split("(")[0].strip() if "(" in label else label.strip()
                )
                if clean_name not in unique_current:
                    unique_current[clean_name] = []
                unique_current[clean_name].append(
                    (current_positions[i], current_colors[i], label)
                )

            for contestant_name, detections in unique_current.items():
                positions = np.array([det[0] for det in detections])
                [det[1] for det in detections]
                labels = [det[2] for det in detections]

                # Use the same color for all detections of this contestant
                contestant_color = contestant_color_map.get(contestant_name, "#FF0000")

                ax.scatter(
                    positions[:, 0],
                    positions[:, 1],
                    c=contestant_color,
                    s=200,
                    alpha=1.0,
                    marker="*",
                    label=f"{contestant_name} (detected)",
                    edgecolors="white",
                    linewidth=2,
                    zorder=3,
                )

                # Add labels for current detections
                for pos, label in zip(positions, labels, strict=False):
                    ax.annotate(
                        label,
                        pos,
                        xytext=(8, 8),
                        textcoords="offset points",
                        fontsize=9,
                        fontweight="bold",
                        bbox={
                            "boxstyle": "round,pad=0.3",
                            "facecolor": contestant_color,
                            "alpha": 0.8,
                            "edgecolor": "white",
                        },
                        color="white",
                        zorder=4,
                    )

        # Draw connection lines between current detections and their matches
        for curr_idx, top_matches in matches_info:
            curr_x, curr_y = embeddings_2d[curr_idx]
            curr_color = all_colors[curr_idx]

            for match_idx, _match_name, similarity in top_matches:
                if similarity > 0.5:  # Only show significant matches
                    match_x, match_y = embeddings_2d[match_idx]

                    # Line properties based on similarity
                    alpha = min(similarity, 0.8)
                    linewidth = 1 + (similarity * 2)

                    # Draw arrow using contestant color
                    ax.annotate(
                        "",
                        xy=(match_x, match_y),
                        xytext=(curr_x, curr_y),
                        arrowprops={
                            "facecolor": curr_color,
                            "edgecolor": curr_color,
                            "arrowstyle": "->",
                            "linewidth": linewidth,
                            "alpha": alpha,
                            "shrinkA": 8,
                            "shrinkB": 8,
                        },
                        zorder=2,
                    )

                    # Add similarity score at midpoint
                    mid_x, mid_y = (curr_x + match_x) / 2, (curr_y + match_y) / 2
                    ax.annotate(
                        f"{similarity:.2f}",
                        (mid_x, mid_y),
                        fontsize=8,
                        ha="center",
                        va="center",
                        bbox={
                            "boxstyle": "round,pad=0.2",
                            "facecolor": "white",
                            "alpha": 0.9,
                            "edgecolor": curr_color,
                        },
                        zorder=5,
                    )

        # Customize plot
        ax.set_title(
            "Face Embedding Relationships (UMAP) - Color-Coded by Contestant",
            fontsize=18,
            fontweight="bold",
            pad=20,
        )
        ax.set_xlabel("UMAP Dimension 1", fontsize=14)
        ax.set_ylabel("UMAP Dimension 2", fontsize=14)

        # Create custom legend with contestant colors
        legend_elements = []

        # Get actual detected contestant names for safer processing
        detected_contestant_names = set()
        for label in detected_labels:
            clean_name = label.split("(")[0].strip() if "(" in label else label.strip()
            if clean_name != "Unknown":
                detected_contestant_names.add(clean_name)

        # Add detected contestants
        for contestant in detected_contestant_names:
            if contestant in contestant_color_map:
                legend_elements.append(
                    plt.scatter(
                        [],
                        [],
                        c=contestant_color_map[contestant],
                        s=100,
                        marker="*",
                        label=f"🎯 {contestant} (detected)",
                        edgecolors="white",
                        linewidth=1,
                    )
                )

        # Add gallery contestants (only those present in our data)
        gallery_contestant_names = set()
        for name in gallery_names.values():
            gallery_contestant_names.add(name)
        for name in gallery_embeddings.keys():
            gallery_contestant_names.add(name)

        for contestant in gallery_contestant_names:
            if contestant in contestant_color_map:
                legend_elements.append(
                    plt.scatter(
                        [],
                        [],
                        c=contestant_color_map[contestant],
                        s=80,
                        marker="s",
                        label=f"📚 {contestant} (gallery)",
                        edgecolors="black",
                        linewidth=1,
                        alpha=0.8,
                    )
                )

        # Add unknown detections if any
        if any("Unknown" in label for label in detected_labels):
            legend_elements.append(
                plt.scatter(
                    [],
                    [],
                    c="#FF0000",
                    s=100,
                    marker="*",
                    label="❓ Unknown",
                    edgecolors="white",
                    linewidth=1,
                )
            )

        # Position legend
        ax.legend(
            handles=legend_elements,
            bbox_to_anchor=(1.05, 1),
            loc="upper left",
            fontsize=10,
            framealpha=0.95,
            title="Contestants",
            title_fontsize=12,
        )

        # Add grid for better readability
        ax.grid(True, alpha=0.3, linestyle="--")

        # Add enhanced similarity scale reference
        ax.text(
            0.02,
            0.98,
            "🎨 Color-coded by contestant\n📏 Line thickness = similarity strength\n➡️ Arrows show matches > 0.5\n⭐ Stars = detected faces\n⬜ Squares = gallery faces",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox={
                "boxstyle": "round,pad=0.5", "facecolor": "white", "alpha": 0.9, "edgecolor": "gray"
            },
        )

        plt.tight_layout()
        return fig

    def create_similarity_plot(
        self,
        frame_similarities: list[dict],
        frame_number: int = None,
        max_faces: int = 5,
    ) -> Figure:
        """
        Create a real-time similarity plot showing top 5 most similar faces for current frame.

        Args:
            frame_similarities: List of similarity dictionaries from frame processing
            frame_number: Current frame number for display
            max_faces: Maximum number of top similar faces to show

        Returns:
            matplotlib.figure.Figure: The generated similarity plot
        """
        if not frame_similarities:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(
                0.5,
                0.5,
                "No face similarities to display",
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_title("Face Similarity Scores")
            return fig

        # Group similarities by detected face and get top matches
        face_groups = {}
        for sim_data in frame_similarities:
            face_id = sim_data.get("face_id", "Face_1")
            if face_id not in face_groups:
                face_groups[face_id] = []
            face_groups[face_id].append(sim_data)

        # Create subplot for each detected face (up to max_faces)
        n_faces = min(len(face_groups), max_faces)
        if n_faces == 0:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(
                0.5,
                0.5,
                "No faces detected in current frame",
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.set_title("Face Similarity Scores")
            return fig

        fig, axes = plt.subplots(n_faces, 1, figsize=(12, 3 * n_faces))
        if n_faces == 1:
            axes = [axes]

        frame_title = f" - Frame {frame_number}" if frame_number is not None else ""
        fig.suptitle(
            f"Top 5 Most Similar Faces{frame_title}", fontsize=16, fontweight="bold"
        )

        for i, (face_id, similarities) in enumerate(
            list(face_groups.items())[:n_faces]
        ):
            ax = axes[i]

            # Sort by similarity score and take top 5
            similarities.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            top_similarities = similarities[:5]

            if not top_similarities:
                ax.text(
                    0.5, 0.5, f"No similarities for {face_id}", ha="center", va="center"
                )
                ax.set_title(f"{face_id}")
                continue

            # Prepare data for plotting
            names = []
            scores = []
            colors = []

            for sim_data in top_similarities:
                name = sim_data.get("name", "Unknown")
                similarity = sim_data.get("similarity", 0.0)

                # Truncate long names
                if len(name) > 15:
                    name = name[:12] + "..."

                names.append(name)
                scores.append(similarity)

                # Color coding based on similarity threshold
                if similarity >= 0.7:
                    colors.append("#2E8B57")  # Sea Green - High confidence
                elif similarity >= 0.5:
                    colors.append("#FF8C00")  # Dark Orange - Medium confidence
                elif similarity >= 0.3:
                    colors.append("#FFD700")  # Gold - Low confidence
                else:
                    colors.append("#DC143C")  # Crimson - Very low confidence

            # Create horizontal bar chart
            y_pos = np.arange(len(names))
            bars = ax.barh(
                y_pos, scores, color=colors, alpha=0.8, edgecolor="black", linewidth=0.5
            )

            # Customize the plot
            ax.set_yticks(y_pos)
            ax.set_yticklabels(names, fontsize=10)
            ax.set_xlabel("Similarity Score", fontsize=11)
            ax.set_title(f"{face_id} - Top Matches", fontsize=12, fontweight="bold")
            ax.set_xlim(0, 1.0)

            # Add value labels on bars
            for _j, (bar, score) in enumerate(zip(bars, scores, strict=False)):
                width = bar.get_width()
                label_x = width + 0.01 if width < 0.8 else width - 0.01
                ha = "left" if width < 0.8 else "right"
                color = "black" if width < 0.8 else "white"
                ax.text(
                    label_x,
                    bar.get_y() + bar.get_height() / 2,
                    f"{score:.3f}",
                    ha=ha,
                    va="center",
                    fontweight="bold",
                    fontsize=9,
                    color=color,
                )

            # Add threshold lines
            ax.axvline(x=0.7, color="green", linestyle="--", alpha=0.7, linewidth=1)
            ax.axvline(x=0.5, color="orange", linestyle="--", alpha=0.7, linewidth=1)
            ax.axvline(x=0.3, color="gold", linestyle="--", alpha=0.7, linewidth=1)

            # Add grid
            ax.grid(True, axis="x", alpha=0.3, linestyle="-", linewidth=0.5)
            ax.set_axisbelow(True)

            # Invert y-axis to show highest similarity at top
            ax.invert_yaxis()

        # Add legend
        legend_elements = [
            plt.Rectangle((0, 0), 1, 1, fc="#2E8B57", alpha=0.8, label="High (≥0.7)"),
            plt.Rectangle(
                (0, 0), 1, 1, fc="#FF8C00", alpha=0.8, label="Medium (0.5-0.7)"
            ),
            plt.Rectangle((0, 0), 1, 1, fc="#FFD700", alpha=0.8, label="Low (0.3-0.5)"),
            plt.Rectangle(
                (0, 0), 1, 1, fc="#DC143C", alpha=0.8, label="Very Low (<0.3)"
            ),
        ]
        fig.legend(
            handles=legend_elements,
            loc="upper right",
            bbox_to_anchor=(0.98, 0.98),
            fontsize=10,
        )

        plt.tight_layout()
        plt.subplots_adjust(top=0.93, right=0.85)
        return fig

    def create_frame_timeline_plot(
        self,
        timeline_data: list[dict],
        current_frame: int = None,
        window_size: int = 100,
    ) -> Figure:
        """
        Create a timeline plot showing similarity scores across frames.

        Args:
            timeline_data: List of frame data with similarities
            current_frame: Current frame number to highlight
            window_size: Number of frames to show around current frame

        Returns:
            matplotlib.figure.Figure: The generated timeline plot
        """
        if not timeline_data:
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.text(
                0.5,
                0.5,
                "No timeline data available",
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.set_title("Similarity Timeline")
            return fig

        # Extract frame numbers and similarity data
        frames = []
        max_similarities = []
        avg_similarities = []
        face_counts = []

        for frame_data in timeline_data:
            frame_num = frame_data.get("frame", 0)
            similarities = frame_data.get("similarities", [])

            frames.append(frame_num)
            face_counts.append(len(similarities))

            if similarities:
                scores = [s.get("similarity", 0) for s in similarities]
                max_similarities.append(max(scores))
                avg_similarities.append(np.mean(scores))
            else:
                max_similarities.append(0)
                avg_similarities.append(0)

        if not frames:
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.text(
                0.5,
                0.5,
                "No frame data to display",
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.set_title("Similarity Timeline")
            return fig

        # Filter data around current frame if specified
        if current_frame is not None and window_size > 0:
            start_frame = max(0, current_frame - window_size // 2)
            end_frame = current_frame + window_size // 2

            # Find indices within the window
            window_indices = [
                i for i, f in enumerate(frames) if start_frame <= f <= end_frame
            ]

            if window_indices:
                frames = [frames[i] for i in window_indices]
                max_similarities = [max_similarities[i] for i in window_indices]
                avg_similarities = [avg_similarities[i] for i in window_indices]
                face_counts = [face_counts[i] for i in window_indices]

        # Create the plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # Plot 1: Similarity scores
        ax1.plot(
            frames,
            max_similarities,
            "r-",
            linewidth=2,
            label="Max Similarity",
            alpha=0.8,
        )
        ax1.plot(
            frames,
            avg_similarities,
            "b-",
            linewidth=2,
            label="Avg Similarity",
            alpha=0.8,
        )
        ax1.fill_between(frames, max_similarities, alpha=0.3, color="red")
        ax1.fill_between(frames, avg_similarities, alpha=0.3, color="blue")

        # Highlight current frame
        if current_frame is not None and current_frame in frames:
            curr_idx = frames.index(current_frame)
            ax1.axvline(
                x=current_frame,
                color="green",
                linestyle="--",
                linewidth=3,
                label=f"Current Frame ({current_frame})",
            )
            ax1.scatter(
                [current_frame],
                [max_similarities[curr_idx]],
                color="green",
                s=100,
                zorder=5,
                marker="o",
            )

        ax1.set_ylabel("Similarity Score", fontsize=12)
        ax1.set_title(
            "Face Recognition Similarity Timeline", fontsize=14, fontweight="bold"
        )
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 1.0)

        # Add threshold lines
        ax1.axhline(
            y=0.7, color="green", linestyle=":", alpha=0.7, label="High Threshold"
        )
        ax1.axhline(
            y=0.5, color="orange", linestyle=":", alpha=0.7, label="Medium Threshold"
        )

        # Plot 2: Face count
        ax2.bar(frames, face_counts, alpha=0.7, color="purple", width=0.8)
        ax2.set_xlabel("Frame Number", fontsize=12)
        ax2.set_ylabel("Faces Detected", fontsize=12)
        ax2.set_title("Number of Faces Detected per Frame", fontsize=12)
        ax2.grid(True, alpha=0.3, axis="y")

        # Highlight current frame
        if current_frame is not None and current_frame in frames:
            curr_idx = frames.index(current_frame)
            ax2.bar(
                [current_frame],
                [face_counts[curr_idx]],
                color="green",
                alpha=0.8,
                width=0.8,
            )

        plt.tight_layout()
        return fig
