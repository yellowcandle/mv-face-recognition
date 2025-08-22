#!/usr/bin/env python3
"""
Embedding Analyzer - Consolidated Embedding Analysis System
==========================================================

This module provides comprehensive analysis and validation of face embeddings,
consolidating functionality from analyze_embeddings.py and adding advanced
analysis capabilities for the unified embedding system.

Key Features:
- Embedding quality analysis and validation
- Distance distribution analysis
- Outlier detection and quality scoring
- Cross-backend compatibility analysis
- Performance profiling and benchmarking
- Detailed reporting with visualization support
"""

import numpy as np
from pathlib import Path
import pandas as pd
import logging
import json
from typing import Dict, List, Any
from datetime import datetime

# Optional visualization dependencies
try:
    import matplotlib.pyplot as plt

    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False

try:
    from sklearn.manifold import TSNE
    from sklearn.decomposition import PCA

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import click

    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False

# Import local modules
from embedding_path_manager import EmbeddingPathManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingAnalyzer:
    """Comprehensive embedding analysis and validation system"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.path_manager = EmbeddingPathManager(config)
        self.contestants_info = self._load_contestant_info()
        self.embeddings_cache = {}

    def _load_contestant_info(self) -> Dict[str, Dict[str, Any]]:
        """Load contestant information"""
        try:
            contestant_csv = Path("../source/contestant_info.csv")
            if not contestant_csv.exists():
                contestant_csv = Path("../../source/contestant_info.csv")

            df = pd.read_csv(contestant_csv)
            contestants = {}

            for _, row in df.iterrows():
                contestant_id = str(row["編號"])
                contestants[contestant_id] = {
                    "id": contestant_id,
                    "name": row["姓名"],
                    "nickname": row["暱稱"],
                    "age": row.get("年齡", "Unknown"),
                }

            logger.info(f"Loaded {len(contestants)} contestants")
            return contestants

        except Exception as e:
            logger.error(f"Failed to load contestant info: {e}")
            return {}

    def load_all_embeddings(self, force_reload: bool = False) -> Dict[str, np.ndarray]:
        """Load all available embeddings"""

        if self.embeddings_cache and not force_reload:
            return self.embeddings_cache

        embeddings = {}

        for contestant_id, info in self.contestants_info.items():
            nickname = info["nickname"]

            # Try multiple embedding formats
            embedding_paths = [
                # New unified format
                self.path_manager.get_embedding_path(int(contestant_id)),
                # Legacy formats
                Path(f"../source/photo/contestants/{nickname}_embedding.npy"),
                Path(f"../../source/photo/contestants/{nickname}_embedding.npy"),
                Path(
                    f"../source/photo/contestants/contestant_{contestant_id}_unified_embedding.npy"
                ),
                Path(
                    f"../../source/photo/contestants/contestant_{contestant_id}_unified_embedding.npy"
                ),
            ]

            for embedding_path in embedding_paths:
                try:
                    if embedding_path.exists():
                        embedding = np.load(embedding_path)
                        embeddings[nickname] = embedding
                        logger.debug(
                            f"Loaded {nickname}: shape {embedding.shape}, norm {np.linalg.norm(embedding):.3f}"
                        )
                        break
                except Exception as e:
                    logger.debug(f"Failed to load {embedding_path}: {e}")
                    continue
            else:
                logger.warning(
                    f"No embedding found for {nickname} (ID: {contestant_id})"
                )

        self.embeddings_cache = embeddings
        logger.info(f"Loaded {len(embeddings)} embeddings")
        return embeddings

    def analyze_distance_distribution(
        self, embeddings: Dict[str, np.ndarray] = None
    ) -> Dict[str, Any]:
        """Analyze the distribution of distances between embeddings"""

        if embeddings is None:
            embeddings = self.load_all_embeddings()

        if len(embeddings) < 2:
            return {"error": "Need at least 2 embeddings for distance analysis"}

        # Calculate all pairwise distances
        names = list(embeddings.keys())
        embedding_matrix = np.array(list(embeddings.values()))

        # Different distance metrics
        distances = {"euclidean": [], "cosine": [], "manhattan": []}

        pairs = []

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                emb1, emb2 = embedding_matrix[i], embedding_matrix[j]

                # Euclidean distance
                euclidean_dist = np.linalg.norm(emb1 - emb2)
                distances["euclidean"].append(euclidean_dist)

                # Cosine distance (1 - cosine similarity)
                cosine_sim = np.dot(emb1, emb2) / (
                    np.linalg.norm(emb1) * np.linalg.norm(emb2)
                )
                cosine_dist = 1 - cosine_sim
                distances["cosine"].append(cosine_dist)

                # Manhattan distance
                manhattan_dist = np.sum(np.abs(emb1 - emb2))
                distances["manhattan"].append(manhattan_dist)

                pairs.append((names[i], names[j]))

        # Calculate statistics
        analysis = {"total_pairs": len(pairs), "distance_metrics": {}}

        for metric, dist_list in distances.items():
            dist_array = np.array(dist_list)
            analysis["distance_metrics"][metric] = {
                "min": float(np.min(dist_array)),
                "max": float(np.max(dist_array)),
                "mean": float(np.mean(dist_array)),
                "std": float(np.std(dist_array)),
                "median": float(np.median(dist_array)),
                "percentiles": {
                    "25": float(np.percentile(dist_array, 25)),
                    "75": float(np.percentile(dist_array, 75)),
                    "90": float(np.percentile(dist_array, 90)),
                    "95": float(np.percentile(dist_array, 95)),
                },
            }

            # Identify extreme pairs
            sorted_indices = np.argsort(dist_array)
            analysis["distance_metrics"][metric]["closest_pairs"] = [
                {"pair": pairs[idx], "distance": float(dist_array[idx])}
                for idx in sorted_indices[:3]
            ]
            analysis["distance_metrics"][metric]["furthest_pairs"] = [
                {"pair": pairs[idx], "distance": float(dist_array[idx])}
                for idx in sorted_indices[-3:]
            ]

        return analysis

    def analyze_embedding_quality(
        self, embeddings: Dict[str, np.ndarray] = None
    ) -> Dict[str, Any]:
        """Analyze overall embedding quality"""

        if embeddings is None:
            embeddings = self.load_all_embeddings()

        if not embeddings:
            return {"error": "No embeddings found"}

        quality_analysis = {
            "total_embeddings": len(embeddings),
            "dimension_analysis": {},
            "norm_analysis": {},
            "validity_analysis": {},
            "outlier_analysis": {},
        }

        # Dimension analysis
        dimensions = [emb.shape[0] for emb in embeddings.values()]
        quality_analysis["dimension_analysis"] = {
            "unique_dimensions": list(set(dimensions)),
            "most_common_dimension": max(set(dimensions), key=dimensions.count),
            "dimension_consistency": len(set(dimensions)) == 1,
        }

        # Norm analysis
        norms = [np.linalg.norm(emb) for emb in embeddings.values()]
        norm_array = np.array(norms)
        quality_analysis["norm_analysis"] = {
            "min_norm": float(np.min(norm_array)),
            "max_norm": float(np.max(norm_array)),
            "mean_norm": float(np.mean(norm_array)),
            "std_norm": float(np.std(norm_array)),
            "normalized_embeddings": sum(1 for norm in norms if abs(norm - 1.0) < 1e-3),
        }

        # Validity analysis
        validity_issues = []
        for name, embedding in embeddings.items():
            issues = []

            # Check for NaN or infinite values
            if np.any(np.isnan(embedding)):
                issues.append("Contains NaN values")
            if np.any(np.isinf(embedding)):
                issues.append("Contains infinite values")

            # Check for zero norm
            if np.linalg.norm(embedding) == 0:
                issues.append("Zero norm")

            # Check for unusual values
            if np.max(np.abs(embedding)) > 100:
                issues.append("Very large values")

            if issues:
                validity_issues.append({"name": name, "issues": issues})

        quality_analysis["validity_analysis"] = {
            "valid_embeddings": len(embeddings) - len(validity_issues),
            "invalid_embeddings": len(validity_issues),
            "issues": validity_issues,
        }

        # Outlier analysis (based on norms and unusual patterns)
        if len(norms) > 5:  # Need sufficient data for outlier analysis
            q1, q3 = np.percentile(norm_array, [25, 75])
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            outliers = []
            for name, embedding in embeddings.items():
                norm = np.linalg.norm(embedding)
                if norm < lower_bound or norm > upper_bound:
                    outliers.append(
                        {"name": name, "norm": float(norm), "type": "norm_outlier"}
                    )

            quality_analysis["outlier_analysis"] = {
                "norm_outliers": outliers,
                "outlier_count": len(outliers),
            }

        return quality_analysis

    def compare_backend_embeddings(self) -> Dict[str, Any]:
        """Compare embeddings from different backends if available"""

        comparison_results = {"backend_analysis": {}, "cross_backend_consistency": {}}

        # Look for embeddings with backend metadata
        backend_embeddings = {}

        for contestant_id, info in self.contestants_info.items():
            contestant_embeddings = {}

            # Look for embeddings with different suffixes or metadata
            base_path = self.path_manager.embedding_dir / "contestants"

            # Try to find different backend embeddings
            possible_files = [
                base_path / f"contestant_{contestant_id}_unified_embedding.npy",
                base_path / f"contestant_{contestant_id}_insightface_embedding.npy",
                base_path
                / f"contestant_{contestant_id}_face_recognition_embedding.npy",
                base_path / f"{info['nickname']}_embedding.npy",
            ]

            for file_path in possible_files:
                if file_path.exists():
                    try:
                        embedding = np.load(file_path)
                        backend = self._detect_backend_from_path(file_path)
                        contestant_embeddings[backend] = embedding
                    except Exception as e:
                        logger.debug(f"Failed to load {file_path}: {e}")

            if len(contestant_embeddings) > 1:
                backend_embeddings[info["nickname"]] = contestant_embeddings

        if backend_embeddings:
            # Analyze cross-backend consistency
            for name, backends in backend_embeddings.items():
                consistency_scores = {}
                backend_names = list(backends.keys())

                for i, backend1 in enumerate(backend_names):
                    for backend2 in backend_names[i + 1 :]:
                        emb1, emb2 = backends[backend1], backends[backend2]

                        # Calculate similarity
                        cosine_sim = np.dot(emb1.flatten(), emb2.flatten()) / (
                            np.linalg.norm(emb1) * np.linalg.norm(emb2)
                        )
                        consistency_scores[f"{backend1}_vs_{backend2}"] = float(
                            cosine_sim
                        )

                comparison_results["cross_backend_consistency"][name] = (
                    consistency_scores
                )

        return comparison_results

    def _detect_backend_from_path(self, file_path: Path) -> str:
        """Detect backend type from file path"""
        path_str = str(file_path).lower()

        if "unified" in path_str:
            return "unified"
        elif "insightface" in path_str:
            return "insightface"
        elif "face_recognition" in path_str:
            return "face_recognition"
        elif "opencv" in path_str:
            return "opencv"
        else:
            return "unknown"

    def generate_comprehensive_report(self, output_file: str = None) -> Dict[str, Any]:
        """Generate a comprehensive analysis report"""

        logger.info("Generating comprehensive embedding analysis report...")

        # Load embeddings
        embeddings = self.load_all_embeddings()

        if not embeddings:
            return {"error": "No embeddings found for analysis"}

        # Perform all analyses
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_contestants": len(self.contestants_info),
                "analyzed_embeddings": len(embeddings),
                "analyzer_version": "1.0.0",
            },
            "distance_analysis": self.analyze_distance_distribution(embeddings),
            "quality_analysis": self.analyze_embedding_quality(embeddings),
            "backend_comparison": self.compare_backend_embeddings(),
            "recommendations": self._generate_recommendations(embeddings),
        }

        # Save report if output file specified
        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_file}")

        return report

    def _generate_recommendations(self, embeddings: Dict[str, np.ndarray]) -> List[str]:
        """Generate recommendations based on analysis"""

        recommendations = []

        # Check embedding count
        if len(embeddings) < len(self.contestants_info) * 0.8:
            missing_percentage = (
                1 - len(embeddings) / len(self.contestants_info)
            ) * 100
            recommendations.append(
                f"Missing {missing_percentage:.1f}% of embeddings - consider regenerating missing ones"
            )

        # Check dimension consistency
        dimensions = [emb.shape[0] for emb in embeddings.values()]
        if len(set(dimensions)) > 1:
            recommendations.append(
                f"Inconsistent embedding dimensions detected: {set(dimensions)} - "
                "consider standardizing to unified format"
            )

        # Check normalization
        norms = [np.linalg.norm(emb) for emb in embeddings.values()]
        mean_norm = np.mean(norms)
        if abs(mean_norm - 1.0) > 0.1:
            recommendations.append(
                f"Embeddings are not normalized (mean norm: {mean_norm:.3f}) - "
                "consider using L2 normalized embeddings for better similarity calculations"
            )

        # Check for outliers
        if len(norms) > 1:
            std_norm = np.std(norms)
            if std_norm > 0.5:
                recommendations.append(
                    f"High variance in embedding norms (std: {std_norm:.3f}) - "
                    "some embeddings may be of poor quality"
                )

        return recommendations

    def visualize_embedding_space(
        self,
        embeddings: Dict[str, np.ndarray] = None,
        method: str = "tsne",
        output_file: str = None,
    ):
        """Visualize embedding space using dimensionality reduction"""

        if not SKLEARN_AVAILABLE or not VISUALIZATION_AVAILABLE:
            logger.warning("Visualization requires sklearn and matplotlib - skipping")
            return

        if embeddings is None:
            embeddings = self.load_all_embeddings()

        if len(embeddings) < 3:
            logger.error("Need at least 3 embeddings for visualization")
            return

        names = list(embeddings.keys())
        embedding_matrix = np.array(list(embeddings.values()))

        # Apply dimensionality reduction
        if method.lower() == "tsne":
            reducer = TSNE(
                n_components=2, random_state=42, perplexity=min(30, len(names) // 2)
            )
            coords = reducer.fit_transform(embedding_matrix)
        elif method.lower() == "pca":
            reducer = PCA(n_components=2)
            coords = reducer.fit_transform(embedding_matrix)
        else:
            raise ValueError(f"Unknown visualization method: {method}")

        # Create visualization
        plt.figure(figsize=(12, 8))
        plt.scatter(coords[:, 0], coords[:, 1], alpha=0.7, s=50)

        # Add labels
        for i, name in enumerate(names):
            plt.annotate(
                name,
                (coords[i, 0], coords[i, 1]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
            )

        plt.title(f"Embedding Space Visualization ({method.upper()})")
        plt.xlabel("Component 1")
        plt.ylabel("Component 2")
        plt.grid(True, alpha=0.3)

        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")
            logger.info(f"Visualization saved to {output_file}")
        else:
            plt.show()

    def export_embeddings_for_analysis(
        self, format: str = "csv", output_file: str = None
    ):
        """Export embeddings in various formats for external analysis"""

        embeddings = self.load_all_embeddings()

        if not embeddings:
            logger.error("No embeddings to export")
            return

        if format.lower() == "csv":
            # Create DataFrame with embeddings as columns
            data = []
            for name, embedding in embeddings.items():
                row = {
                    "name": name,
                    **{f"dim_{i}": val for i, val in enumerate(embedding.flatten())},
                }
                data.append(row)

            df = pd.DataFrame(data)
            output_file = output_file or "embeddings_export.csv"
            df.to_csv(output_file, index=False)

        elif format.lower() == "npz":
            # Save as numpy archive
            output_file = output_file or "embeddings_export.npz"
            np.savez(output_file, **embeddings)

        elif format.lower() == "json":
            # Save as JSON (converting numpy arrays to lists)
            output_file = output_file or "embeddings_export.json"
            json_data = {name: emb.tolist() for name, emb in embeddings.items()}

            with open(output_file, "w") as f:
                json.dump(json_data, f, indent=2)

        logger.info(f"Embeddings exported to {output_file}")


if CLICK_AVAILABLE:

    @click.command()
    @click.option(
        "--mode",
        type=click.Choice(["quick", "comprehensive", "visual"]),
        default="quick",
        help="Analysis mode",
    )
    @click.option("--output", "-o", help="Output file for report")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(["json", "yaml"]),
        default="json",
        help="Output format",
    )
    def main(mode, output, output_format):
        """Embedding Analysis CLI"""

        analyzer = EmbeddingAnalyzer()

        if mode == "quick":
            # Quick analysis
            embeddings = analyzer.load_all_embeddings()
            distance_analysis = analyzer.analyze_distance_distribution(embeddings)
            quality_analysis = analyzer.analyze_embedding_quality(embeddings)

            print("\n📊 Quick Embedding Analysis:")
            print(f"   Total embeddings: {quality_analysis['total_embeddings']}")
            print(
                f"   Valid embeddings: {quality_analysis['validity_analysis']['valid_embeddings']}"
            )

            if distance_analysis.get("distance_metrics"):
                cosine_stats = distance_analysis["distance_metrics"]["cosine"]
                print(
                    f"   Cosine distance range: {cosine_stats['min']:.3f} - {cosine_stats['max']:.3f}"
                )
                print(f"   Mean cosine distance: {cosine_stats['mean']:.3f}")

        elif mode == "comprehensive":
            # Comprehensive analysis
            report = analyzer.generate_comprehensive_report(output)

            if output:
                print(f"✅ Comprehensive report generated: {output}")
            else:
                # Display summary
                print("\n📋 Comprehensive Analysis Summary:")
                print(
                    f"   Total contestants: {report['metadata']['total_contestants']}"
                )
                print(
                    f"   Analyzed embeddings: {report['metadata']['analyzed_embeddings']}"
                )

                if report.get("recommendations"):
                    print("\n💡 Recommendations:")
                    for i, rec in enumerate(report["recommendations"], 1):
                        print(f"   {i}. {rec}")

        elif mode == "visual":
            # Visualization mode
            analyzer.visualize_embedding_space(method="tsne", output_file=output)


if __name__ == "__main__":
    if CLICK_AVAILABLE:
        main()
    else:
        print("CLI functionality requires click library")
        analyzer = EmbeddingAnalyzer()
        embeddings = analyzer.load_all_embeddings()
        print(f"Loaded {len(embeddings)} embeddings for analysis")
