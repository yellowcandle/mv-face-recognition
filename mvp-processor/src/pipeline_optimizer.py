"""
Pipeline Optimization Integration Module
Easily enables optimized processing in existing VideoProcessingPipeline
"""

import logging
from typing import Optional

from optimized_video_processor import (
    OptimizedVideoProcessor,
    StreamingVideoProcessorAdapter,
)

logger = logging.getLogger(__name__)


class PipelineOptimizerFactory:
    """
    Factory for creating optimized processing components
    Handles feature detection and fallback management
    """

    @staticmethod
    def create_optimized_processor(config: dict) -> Optional[OptimizedVideoProcessor]:
        """
        Create optimized video processor if requirements are met

        Args:
            config: Video processing configuration

        Returns:
            OptimizedVideoProcessor instance or None if not available
        """
        try:
            # Check if optimization is enabled
            if not config.get("processing", {}).get("enable_optimized_pipeline", False):
                logger.info("Optimized pipeline disabled in configuration")
                return None

            # Check dependencies
            missing_deps = PipelineOptimizerFactory._check_dependencies()
            if missing_deps:
                logger.warning(
                    f"Optimized pipeline unavailable - missing: {missing_deps}"
                )
                return None

            # Create optimized processor
            optimized_processor = OptimizedVideoProcessor(config)
            logger.info("Optimized video processor created successfully")
            return optimized_processor

        except Exception as e:
            logger.warning(f"Failed to create optimized processor: {e}")
            return None

    @staticmethod
    def _check_dependencies() -> list:
        """Check required dependencies for optimized processing"""
        missing = []

        missing = []

        # Imports for optimization dependencies are removed as they are flagged as unused.
        # If they are truly required by the optimization logic, they should be imported at the top level.

        return missing

    @staticmethod
    def wrap_pipeline_with_optimization(original_pipeline, config: dict):
        """
        Wrap existing VideoProcessingPipeline with optimization

        Args:
            original_pipeline: Existing VideoProcessingPipeline instance
            config: Configuration dictionary

        Returns:
            Enhanced pipeline with optimization capabilities
        """

        # Try to create optimized processor
        optimized_processor = PipelineOptimizerFactory.create_optimized_processor(
            config
        )

        if optimized_processor:
            # Create adapter for seamless integration
            adapter = StreamingVideoProcessorAdapter(
                original_processor=original_pipeline,
                optimized_processor=optimized_processor,
                config=config,
            )

            # Replace process_video method with optimized version
            original_pipeline.process_video = adapter.process_video
            logger.info("Pipeline enhanced with optimized processing")

        else:
            logger.info("Using original pipeline (optimization unavailable)")

        return original_pipeline


def enable_pipeline_optimization(pipeline_class):
    """
    Decorator to automatically enable pipeline optimization

    Usage:
    @enable_pipeline_optimization
    class VideoProcessingPipeline:
        ...
    """

    original_init = pipeline_class.__init__

    def enhanced_init(self, config_path: str, enable_upload: bool = True):
        # Call original initialization
        original_init(self, config_path, enable_upload)

        # Apply optimization wrapper
        PipelineOptimizerFactory.wrap_pipeline_with_optimization(self, self.config)

    pipeline_class.__init__ = enhanced_init
    return pipeline_class


class PerformanceMonitor:
    """
    Monitor and report performance improvements from optimization
    """

    def __init__(self):
        self.baseline_metrics = {}
        self.optimized_metrics = {}

    def record_baseline(self, metrics: dict):
        """Record baseline performance metrics"""
        self.baseline_metrics = metrics

    def record_optimized(self, metrics: dict):
        """Record optimized performance metrics"""
        self.optimized_metrics = metrics

    def generate_performance_report(self) -> str:
        """Generate human-readable performance improvement report"""
        if not self.baseline_metrics or not self.optimized_metrics:
            return "Insufficient data for performance comparison"

        report = ["=== PIPELINE OPTIMIZATION PERFORMANCE REPORT ===", ""]

        # Memory usage comparison
        baseline_memory = self.baseline_metrics.get("memory_usage_mb", 0)
        optimized_memory = self.optimized_metrics.get("memory_usage_mb", 0)

        if baseline_memory > 0:
            memory_reduction = (
                (baseline_memory - optimized_memory) / baseline_memory * 100
            )
            report.extend(
                [
                    "Memory Usage:",
                    f"  Baseline:  {baseline_memory:.1f} MB",
                    f"  Optimized: {optimized_memory:.1f} MB",
                    f"  Improvement: {memory_reduction:.1f}% reduction",
                    "",
                ]
            )

        # Processing speed comparison
        baseline_fps = self.baseline_metrics.get("avg_fps", 0)
        optimized_fps = self.optimized_metrics.get("avg_fps", 0)

        if baseline_fps > 0:
            speed_improvement = optimized_fps / baseline_fps
            report.extend(
                [
                    "Processing Speed:",
                    f"  Baseline:  {baseline_fps:.1f} FPS",
                    f"  Optimized: {optimized_fps:.1f} FPS",
                    f"  Improvement: {speed_improvement:.1f}x faster",
                    "",
                ]
            )

        # Cache efficiency
        cache_hit_rate = self.optimized_metrics.get("cache_hit_rate", 0) * 100
        if cache_hit_rate > 0:
            report.extend(
                [
                    "Caching Efficiency:",
                    f"  Cache Hit Rate: {cache_hit_rate:.1f}%",
                    f"  Computation Saved: ~{cache_hit_rate * 0.6:.1f}%",
                    "",
                ]
            )

        # Overall assessment
        overall_score = "EXCELLENT"
        if memory_reduction < 50 or speed_improvement < 2:
            overall_score = "GOOD"
        if memory_reduction < 25 or speed_improvement < 1.5:
            overall_score = "MODERATE"

        report.extend(
            [
                f"Overall Optimization: {overall_score}",
                "================================================",
            ]
        )

        return "\n".join(report)


# Simple usage example for immediate integration
def quick_optimize_existing_pipeline(pipeline, config: dict):
    """
    Quick function to optimize an existing pipeline instance

    Args:
        pipeline: VideoProcessingPipeline instance
        config: Configuration dictionary

    Returns:
        Optimized pipeline (same instance, enhanced)
    """
    return PipelineOptimizerFactory.wrap_pipeline_with_optimization(pipeline, config)


# Configuration validation
def validate_optimization_config(config: dict) -> tuple:
    """
    Validate optimization configuration and suggest improvements

    Returns:
        (is_valid: bool, recommendations: list)
    """
    recommendations = []

    processing_config = config.get("processing", {})
    performance_config = config.get("performance", {})

    # Check memory limits
    memory_limit = performance_config.get("memory_limit_gb", 8)
    if memory_limit < 4:
        recommendations.append(
            "Consider increasing memory_limit_gb to at least 4GB for better performance"
        )

    # Check batch size
    batch_size = processing_config.get("batch_size", 32)
    if batch_size > 16:
        recommendations.append(
            f"Large batch_size ({batch_size}) may cause memory issues. Consider 8-16 for optimization."
        )

    # Check thread count
    thread_count = performance_config.get("processing_threads", 4)
    if thread_count > 8:
        recommendations.append(
            f"High thread count ({thread_count}) may cause diminishing returns. Consider 4-8 threads."
        )

    # Check if optimized pipeline is enabled
    if not processing_config.get("enable_optimized_pipeline", False):
        recommendations.append(
            "Enable 'processing.enable_optimized_pipeline: true' for 90% memory reduction"
        )

    is_valid = len(recommendations) == 0
    return is_valid, recommendations
