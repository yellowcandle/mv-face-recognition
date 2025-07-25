#!/usr/bin/env python3
"""
Advanced Embedding Generator - Consolidated Embedding System
===========================================================

This module consolidates all embedding generation functionality into mvp-processor,
providing a single, comprehensive tool for generating, validating, and managing
face embeddings across multiple backends.

Consolidated functionality from:
- unified_embedding_generator.py (comprehensive multi-backend support)
- generate_embeddings.py (face_recognition library)
- generate_embeddings_enhanced.py (hardware-accelerated)
- simple_regenerate_embeddings.py (basic OpenCV)
- analyze_embeddings.py (validation and analysis)

Key Features:
- Multi-backend embedding generation (InsightFace, face_recognition, OpenCV)
- Hardware acceleration auto-detection (Apple Silicon/CUDA/CPU)
- Comprehensive validation and quality analysis
- Batch processing with progress tracking
- CLI interface with extensive options
- Performance benchmarking and statistics
"""

import numpy as np
import pandas as pd
import json
import yaml
import logging
import click
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from tqdm import tqdm
from enum import Enum
import time

# Import local modules
from unified_embedding_system import UnifiedEmbeddingSystem
from embedding_path_manager import EmbeddingPathManager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmbeddingBackend(Enum):
    """Available embedding backends"""

    UNIFIED_SYSTEM = "unified"  # Uses UnifiedEmbeddingSystem (most advanced)
    INSIGHTFACE = "insightface"  # Direct InsightFace integration
    FACE_RECOGNITION = "face_recognition"  # dlib-based face_recognition library
    OPENCV_BASIC = "opencv"  # Basic OpenCV implementation
    AUTO = "auto"  # Auto-select best available backend


class ProcessingMode(Enum):
    """Processing modes"""

    GENERATE_ALL = "generate_all"  # Generate embeddings for all contestants
    VALIDATE_ONLY = "validate"  # Only validate existing embeddings
    ANALYZE = "analyze"  # Analyze embedding quality and statistics
    REGENERATE = "regenerate"  # Regenerate specific embeddings
    BENCHMARK = "benchmark"  # Performance benchmarking


@click.group()
@click.option(
    "--config",
    "-c",
    default="config/processing_config.yaml",
    help="Configuration file path",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--backend",
    "-b",
    type=click.Choice([b.value for b in EmbeddingBackend]),
    default="auto",
    help="Embedding backend to use",
)
@click.pass_context
def cli(ctx, config, verbose, backend):
    """Advanced Embedding Generator - Consolidated embedding management system"""

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["backend"] = EmbeddingBackend(backend)
    ctx.obj["verbose"] = verbose

    # Load configuration
    try:
        with open(config, "r") as f:
            ctx.obj["config"] = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration from {config}: {e}")
        ctx.exit(1)


@cli.command()
@click.option(
    "--force", "-f", is_flag=True, help="Force regeneration of existing embeddings"
)
@click.option(
    "--contestant-ids",
    "-i",
    help='Comma-separated list of contestant IDs (e.g., "1,2,5")',
)
@click.option("--parallel", is_flag=True, help="Enable parallel processing")
@click.option("--batch-size", type=int, default=10, help="Batch size for processing")
@click.pass_context
def generate(ctx, force, contestant_ids, parallel, batch_size):
    """Generate embeddings for contestants"""

    processor = AdvancedEmbeddingProcessor(
        config=ctx.obj["config"], backend=ctx.obj["backend"], verbose=ctx.obj["verbose"]
    )

    # Parse contestant IDs if provided
    target_ids = None
    if contestant_ids:
        try:
            target_ids = [int(id.strip()) for id in contestant_ids.split(",")]
            logger.info(f"Processing specific contestants: {target_ids}")
        except ValueError:
            logger.error(f"Invalid contestant IDs format: {contestant_ids}")
            ctx.exit(1)

    # Generate embeddings
    results = processor.generate_embeddings(
        force=force,
        target_contestant_ids=target_ids,
        parallel=parallel,
        batch_size=batch_size,
    )

    # Display results
    click.echo("\n✅ Embedding Generation Summary:")
    click.echo(f"   Total processed: {results['total']}")
    click.echo(f"   Generated: {results['generated']}")
    click.echo(f"   Skipped: {results['skipped']}")
    click.echo(f"   Errors: {results['errors']}")
    click.echo(f"   Duration: {results['duration']:.2f}s")

    if results["errors"] > 0:
        click.echo(f"\n⚠️  {results['errors']} contestants had errors - check logs")


@cli.command()
@click.option("--detailed", is_flag=True, help="Show detailed validation results")
@click.option("--fix-issues", is_flag=True, help="Attempt to fix validation issues")
@click.pass_context
def validate(ctx, detailed, fix_issues):
    """Validate existing embeddings"""

    processor = AdvancedEmbeddingProcessor(
        config=ctx.obj["config"], backend=ctx.obj["backend"], verbose=ctx.obj["verbose"]
    )

    results = processor.validate_embeddings(detailed=detailed, fix_issues=fix_issues)

    # Display validation results
    click.echo("\n📋 Embedding Validation Summary:")
    click.echo(f"   Total embeddings: {results['total']}")
    click.echo(f"   Valid: {results['valid']}")
    click.echo(f"   Invalid: {results['invalid']}")
    click.echo(f"   Missing: {results['missing']}")

    if detailed and results.get("details"):
        click.echo("\n📊 Detailed Results:")
        for detail in results["details"]:
            status = "✅" if detail["valid"] else "❌"
            click.echo(f"   {status} Contestant {detail['id']}: {detail['message']}")


@cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "yaml", "table"]),
    default="table",
    help="Output format for analysis",
)
@click.option("--save-report", help="Save detailed report to file")
@click.pass_context
def analyze(ctx, output_format, save_report):
    """Analyze embedding quality and statistics"""

    processor = AdvancedEmbeddingProcessor(
        config=ctx.obj["config"], backend=ctx.obj["backend"], verbose=ctx.obj["verbose"]
    )

    analysis = processor.analyze_embeddings()

    if output_format == "json":
        click.echo(json.dumps(analysis, indent=2))
    elif output_format == "yaml":
        click.echo(yaml.dump(analysis, default_flow_style=False))
    else:
        # Table format
        click.echo("\n📊 Embedding Analysis Report:")
        click.echo(f"   Total embeddings: {analysis['summary']['total']}")
        click.echo(f"   Valid embeddings: {analysis['summary']['valid']}")
        click.echo(f"   Average dimension: {analysis['summary']['avg_dimension']:.1f}")
        click.echo(f"   Average norm: {analysis['summary']['avg_norm']:.3f}")

        if analysis["quality_metrics"]:
            click.echo("\n🔍 Quality Metrics:")
            for metric, value in analysis["quality_metrics"].items():
                click.echo(f"   {metric}: {value}")

    if save_report:
        with open(save_report, "w") as f:
            json.dump(analysis, f, indent=2)
        click.echo(f"\n💾 Detailed report saved to: {save_report}")


@cli.command()
@click.option(
    "--backends",
    help="Comma-separated backends to benchmark (auto, unified, insightface, face_recognition, opencv)",
)
@click.option(
    "--sample-count", type=int, default=10, help="Number of samples for benchmarking"
)
@click.pass_context
def benchmark(ctx, backends, sample_count):
    """Benchmark embedding generation performance across backends"""

    # Parse backends
    if backends:
        backend_list = [EmbeddingBackend(b.strip()) for b in backends.split(",")]
    else:
        backend_list = [
            EmbeddingBackend.AUTO,
            EmbeddingBackend.UNIFIED_SYSTEM,
            EmbeddingBackend.FACE_RECOGNITION,
            EmbeddingBackend.OPENCV_BASIC,
        ]

    processor = AdvancedEmbeddingProcessor(
        config=ctx.obj["config"],
        backend=EmbeddingBackend.AUTO,  # Will be overridden during benchmarking
        verbose=ctx.obj["verbose"],
    )

    results = processor.benchmark_backends(backend_list, sample_count)

    # Display benchmark results
    click.echo("\n⚡ Performance Benchmark Results:")
    click.echo(
        f"{'Backend':<20} {'Avg Time (ms)':<15} {'Success Rate':<12} {'Quality Score':<15}"
    )
    click.echo("-" * 65)

    for backend, metrics in results.items():
        avg_time = metrics["avg_time"] * 1000 if metrics["avg_time"] else 0
        success_rate = (
            f"{metrics['success_rate']:.1%}" if metrics["success_rate"] else "N/A"
        )
        quality = (
            f"{metrics['quality_score']:.3f}" if metrics["quality_score"] else "N/A"
        )

        click.echo(f"{backend:<20} {avg_time:<15.1f} {success_rate:<12} {quality:<15}")


class AdvancedEmbeddingProcessor:
    """Core processor for advanced embedding operations"""

    def __init__(
        self, config: Dict[str, Any], backend: EmbeddingBackend, verbose: bool = False
    ):
        self.config = config
        self.backend = backend
        self.verbose = verbose

        # Initialize embedding system
        self.embedding_system = UnifiedEmbeddingSystem(config)
        self.path_manager = EmbeddingPathManager(config)

        # Load contestant info
        self.contestants_df = self._load_contestant_info()

        logger.info(
            f"Initialized AdvancedEmbeddingProcessor with backend: {backend.value}"
        )

    def _load_contestant_info(self) -> pd.DataFrame:
        """Load contestant information"""
        contestant_csv = Path("../source/contestant_info.csv")
        if not contestant_csv.exists():
            # Try relative to mvp-processor
            contestant_csv = Path("../../source/contestant_info.csv")

        if not contestant_csv.exists():
            raise FileNotFoundError("Contestant info CSV not found")

        return pd.read_csv(contestant_csv)

    def generate_embeddings(
        self,
        force: bool = False,
        target_contestant_ids: Optional[List[int]] = None,
        parallel: bool = False,
        batch_size: int = 10,
    ) -> Dict[str, Any]:
        """Generate embeddings for contestants"""

        start_time = time.time()
        stats = {"total": 0, "generated": 0, "skipped": 0, "errors": 0}

        # Filter contestants if specific IDs provided
        if target_contestant_ids:
            contestants_to_process = self.contestants_df[
                self.contestants_df["編號"].isin(target_contestant_ids)
            ]
        else:
            contestants_to_process = self.contestants_df

        stats["total"] = len(contestants_to_process)

        logger.info(
            f"Processing {stats['total']} contestants with backend: {self.backend.value}"
        )

        # Process contestants
        with tqdm(total=stats["total"], desc="Processing contestants") as pbar:
            for _, row in contestants_to_process.iterrows():
                try:
                    result = self._process_contestant(
                        int(row["編號"]), row["姓名"], row["暱稱"], force=force
                    )

                    if result == "generated":
                        stats["generated"] += 1
                    elif result == "skipped":
                        stats["skipped"] += 1
                    elif result == "error":
                        stats["errors"] += 1

                except Exception as e:
                    logger.error(
                        f"Failed to process contestant {row['編號']} ({row['暱稱']}): {e}"
                    )
                    stats["errors"] += 1

                pbar.update(1)

        duration = time.time() - start_time
        stats["duration"] = duration

        return stats

    def _process_contestant(
        self, contestant_id: int, name: str, nickname: str, force: bool = False
    ) -> str:
        """Process a single contestant's embedding"""

        # Check if embedding already exists
        embedding_path = self.path_manager.get_embedding_path(contestant_id)
        metadata_path = self.path_manager.get_metadata_path(contestant_id)

        if embedding_path.exists() and metadata_path.exists() and not force:
            logger.debug(f"Embedding already exists for contestant {contestant_id}")
            return "skipped"

        # Find photo file
        photo_path = self._find_contestant_photo(contestant_id)
        if not photo_path:
            logger.error(f"No photo found for contestant {contestant_id}")
            return "error"

        try:
            # Generate embedding
            embedding, metadata = self.embedding_system.generate_embedding(
                str(photo_path)
            )

            if embedding is None:
                logger.error(
                    f"Failed to generate embedding for contestant {contestant_id}"
                )
                return "error"

            # Save embedding and metadata
            np.save(embedding_path, embedding)

            enhanced_metadata = {
                "contestant_id": contestant_id,
                "name": name,
                "nickname": nickname,
                "photo_path": str(photo_path),
                "generated_at": datetime.now().isoformat(),
                "backend": self.backend.value,
                **metadata,
            }

            with open(metadata_path, "w") as f:
                json.dump(enhanced_metadata, f, indent=2)

            logger.debug(
                f"Generated embedding for contestant {contestant_id} ({nickname})"
            )
            return "generated"

        except Exception as e:
            logger.error(
                f"Error generating embedding for contestant {contestant_id}: {e}"
            )
            return "error"

    def _find_contestant_photo(self, contestant_id: int) -> Optional[Path]:
        """Find photo file for contestant"""
        photo_base_dir = Path("../source/photo/contestants")
        if not photo_base_dir.exists():
            # Try relative to mvp-processor
            photo_base_dir = Path("../../source/photo/contestants")

        contestant_dir = photo_base_dir / str(contestant_id)
        if not contestant_dir.exists():
            return None

        # Look for primary photo
        for ext in [".jpg", ".jpeg", ".png"]:
            photo_path = contestant_dir / f"{contestant_id}-1{ext}"
            if photo_path.exists():
                return photo_path

        return None

    def validate_embeddings(
        self, detailed: bool = False, fix_issues: bool = False
    ) -> Dict[str, Any]:
        """Validate existing embeddings"""

        results = {"total": 0, "valid": 0, "invalid": 0, "missing": 0, "details": []}

        for _, row in self.contestants_df.iterrows():
            contestant_id = int(row["編號"])
            results["total"] += 1

            embedding_path = self.path_manager.get_embedding_path(contestant_id)
            metadata_path = self.path_manager.get_metadata_path(contestant_id)

            # Check if files exist
            if not embedding_path.exists() or not metadata_path.exists():
                results["missing"] += 1
                if detailed:
                    results["details"].append(
                        {
                            "id": contestant_id,
                            "valid": False,
                            "message": "Missing embedding or metadata files",
                        }
                    )
                continue

            try:
                # Validate embedding
                embedding = np.load(embedding_path)
                with open(metadata_path, "r") as f:
                    json.load(f)

                # Basic validation checks
                is_valid = True
                issues = []

                if embedding.shape[0] != 512:
                    is_valid = False
                    issues.append(f"Wrong dimension: {embedding.shape[0]}")

                if np.any(np.isnan(embedding)):
                    is_valid = False
                    issues.append("Contains NaN values")

                if np.linalg.norm(embedding) == 0:
                    is_valid = False
                    issues.append("Zero norm (invalid embedding)")

                if is_valid:
                    results["valid"] += 1
                    message = "Valid embedding"
                else:
                    results["invalid"] += 1
                    message = f"Invalid: {', '.join(issues)}"

                if detailed:
                    results["details"].append(
                        {
                            "id": contestant_id,
                            "valid": is_valid,
                            "message": message,
                            "dimension": embedding.shape[0],
                            "norm": float(np.linalg.norm(embedding)),
                        }
                    )

                # Fix issues if requested
                if not is_valid and fix_issues:
                    logger.info(
                        f"Attempting to fix embedding for contestant {contestant_id}"
                    )
                    self._process_contestant(
                        contestant_id, row["姓名"], row["暱稱"], force=True
                    )

            except Exception as e:
                results["invalid"] += 1
                if detailed:
                    results["details"].append(
                        {
                            "id": contestant_id,
                            "valid": False,
                            "message": f"Error loading: {e}",
                        }
                    )

        return results

    def analyze_embeddings(self) -> Dict[str, Any]:
        """Analyze embedding quality and statistics"""

        embeddings = []
        valid_count = 0
        total_count = 0

        for _, row in self.contestants_df.iterrows():
            contestant_id = int(row["編號"])
            total_count += 1

            embedding_path = self.path_manager.get_embedding_path(contestant_id)

            if embedding_path.exists():
                try:
                    embedding = np.load(embedding_path)
                    embeddings.append(embedding)
                    valid_count += 1
                except Exception:
                    continue

        if not embeddings:
            return {"error": "No valid embeddings found"}

        embeddings = np.array(embeddings)

        # Calculate statistics
        norms = np.linalg.norm(embeddings, axis=1)
        dimensions = [emb.shape[0] for emb in embeddings]

        # Distance matrix for quality analysis
        distances = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                dist = np.linalg.norm(embeddings[i] - embeddings[j])
                distances.append(dist)

        analysis = {
            "summary": {
                "total": total_count,
                "valid": valid_count,
                "avg_dimension": np.mean(dimensions),
                "avg_norm": float(np.mean(norms)),
                "std_norm": float(np.std(norms)),
            },
            "quality_metrics": {
                "min_distance": float(np.min(distances)) if distances else 0,
                "max_distance": float(np.max(distances)) if distances else 0,
                "avg_distance": float(np.mean(distances)) if distances else 0,
                "std_distance": float(np.std(distances)) if distances else 0,
            },
            "distribution": {
                "norm_percentiles": {
                    "p25": float(np.percentile(norms, 25)),
                    "p50": float(np.percentile(norms, 50)),
                    "p75": float(np.percentile(norms, 75)),
                }
            },
        }

        return analysis

    def benchmark_backends(
        self, backends: List[EmbeddingBackend], sample_count: int = 10
    ) -> Dict[str, Dict[str, float]]:
        """Benchmark performance across different backends"""

        results = {}

        # Find sample photos
        sample_photos = self._get_sample_photos(sample_count)

        if not sample_photos:
            logger.error("No sample photos found for benchmarking")
            return results

        for backend in backends:
            logger.info(f"Benchmarking backend: {backend.value}")

            backend_results = {
                "avg_time": None,
                "success_rate": None,
                "quality_score": None,
            }

            times = []
            successes = 0
            qualities = []

            for photo_path in sample_photos:
                try:
                    # Configure backend
                    temp_config = self.config.copy()
                    if backend != EmbeddingBackend.AUTO:
                        # Set specific backend in config
                        temp_config["embedding"] = {"method": backend.value}

                    temp_system = UnifiedEmbeddingSystem(temp_config)

                    start_time = time.time()
                    embedding, metadata = temp_system.generate_embedding(
                        str(photo_path)
                    )
                    end_time = time.time()

                    if embedding is not None:
                        times.append(end_time - start_time)
                        successes += 1

                        # Calculate quality score (based on norm and consistency)
                        norm = np.linalg.norm(embedding)
                        quality = 1.0 / (
                            1.0 + abs(norm - 1.0)
                        )  # Closer to unit norm is better
                        qualities.append(quality)

                except Exception as e:
                    logger.debug(f"Backend {backend.value} failed on {photo_path}: {e}")
                    continue

            if times:
                backend_results["avg_time"] = np.mean(times)
                backend_results["success_rate"] = successes / len(sample_photos)
                backend_results["quality_score"] = (
                    np.mean(qualities) if qualities else 0
                )

            results[backend.value] = backend_results

        return results

    def _get_sample_photos(self, count: int) -> List[Path]:
        """Get sample photos for benchmarking"""
        photos = []

        # Try to find photos from different contestants
        for _, row in self.contestants_df.head(
            count * 2
        ).iterrows():  # Get more than needed
            contestant_id = int(row["編號"])
            photo_path = self._find_contestant_photo(contestant_id)

            if photo_path and photo_path.exists():
                photos.append(photo_path)

                if len(photos) >= count:
                    break

        return photos[:count]


if __name__ == "__main__":
    cli()
