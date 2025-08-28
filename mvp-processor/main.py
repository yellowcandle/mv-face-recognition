#!/usr/bin/env python3
"""
Consolidated Video Processing Pipeline Entry Point
Uses unified engines to streamline processing
"""

import sys
import argparse
import yaml
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Rich imports for beautiful console output
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Import consolidated engines
from src.video_processing_engine import VideoProcessor, VideoProcessingConfig
from src.face_detection_engine import FaceDetectionEngine
from src.face_recognition_engine import FaceRecognitionEngine


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = (
        logging.DEBUG if verbose else logging.WARNING
    )  # Changed from INFO to WARNING to reduce console noise
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("processing.log"),
        ],
    )


def load_config(config_path: Optional[str] = None) -> dict:
    """Load processing configuration"""
    if config_path is None:
        config_path = "config/processing_config.yaml"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return get_default_config()


def get_default_config() -> dict:
    """Get default configuration if config file not found"""
    return {
        "face_detection": {
            "model": "opencv",
            "min_confidence": 0.5,
            "max_faces_per_frame": 20,
            "enable_hardware_acceleration": False,
        },
        "face_recognition": {
            "tolerance": 0.6,
            "similarity_threshold": 0.15,
            "max_distance": 15.0,
        },
        "contestants": {
            "info_csv": "source/contestant_info.csv",
            "photo_dir": "source/photo/contestants",
            "embeddings_cache": "cache/embeddings",
        },
        "processing": {
            "mode": "standard",
            "enable_optimization": False,
            "output_dir": "processed_videos",
        },
    }


@dataclass
class ProcessingResult:
    """Result of video processing"""

    success: bool
    video_path: str
    output_path: str = None
    metadata_path: str = None
    processing_stats: dict = None
    error_message: str = None


def process_single_video(
    video_path: str, output_path: Optional[str] = None, config: Optional[dict] = None
) -> ProcessingResult:
    """Process a single video file with beautiful Rich console output"""
    if config is None:
        config = load_config()

    # Initialize Rich console
    console = Console()

    # Initialize consolidated video processing engine
    # Create VideoProcessingConfig from the config dict
    # Default to processed_videos directory if no output path specified
    if output_path is None:
        output_dir = Path("processed_videos")
        output_dir.mkdir(exist_ok=True)
        output_path = str(
            output_dir / f"{Path(video_path).stem}_processed{Path(video_path).suffix}"
        )

    video_config = VideoProcessingConfig(
        source_path=video_path,
        target_path=output_path,
        confidence_threshold=config.get("face_detection", {}).get(
            "min_confidence", 0.5
        ),
        enable_tracking=config.get("processing", {}).get("enable_tracking", True),
        enable_smoothing=config.get("processing", {}).get("enable_smoothing", True),
    )
    engine = VideoProcessor(video_config, full_config=config)

    try:
        # Create processing info panel
        video_info_table = Table(show_header=True, header_style="bold blue")
        video_info_table.add_column("Property", style="cyan", width=12)
        video_info_table.add_column("Value", style="magenta")

        video_info_table.add_row("Input File", Path(video_path).name)
        video_info_table.add_row(
            "Output File",
            Path(
                output_path
                or f"{Path(video_path).stem}_processed{Path(video_path).suffix}"
            ).name,
        )
        video_info_table.add_row(
            "Output Path",
            str(
                Path(
                    output_path
                    or f"{Path(video_path).stem}_processed{Path(video_path).suffix}"
                ).parent
            ),
        )

        info_panel = Panel(
            video_info_table,
            title="[bold green]🚀 Video Processing Started[/bold green]",
            border_style="blue",
            padding=(1, 2),
        )
        console.print(info_panel)

        # Show processing progress with spinner
        with console.status(
            "[bold green]Processing video...[/bold green]", spinner="dots"
        ):
            # Process video
            success = engine.process_video()

        # Get performance stats
        stats = engine.get_performance_stats()

        # Create ProcessingResult
        result = ProcessingResult(
            success=success,
            video_path=video_path,
            output_path=output_path
            or f"{Path(video_path).stem}_processed{Path(video_path).suffix}",
            processing_stats=stats,
        )

        # Display results
        if success:
            # Create success panel
            success_text = Text(
                "✅ VIDEO PROCESSING COMPLETED SUCCESSFULLY!", style="bold green"
            )
            success_panel = Panel(
                success_text,
                title="[bold green]🎉 Success![/bold green]",
                border_style="green",
                padding=(1, 2),
            )
            console.print(success_panel)

            # Create performance table
            if stats:
                perf_table = Table(
                    show_header=True,
                    header_style="bold cyan",
                    title="📊 Performance Summary",
                )
                perf_table.add_column("Metric", style="cyan", width=20)
                perf_table.add_column("Value", style="magenta", justify="right")
                perf_table.add_column("Unit", style="yellow", width=10)

                perf_table.add_row(
                    "Frames Processed", f"{stats.get('total_frames', 0):,}", "frames"
                )
                perf_table.add_row("Average Frame Time", ".3f", "seconds")
                perf_table.add_row("Processing Speed", ".1f", "FPS")
                perf_table.add_row("Total Processing Time", ".2f", "seconds")

                console.print(perf_table)

            # Final celebration message
            celebration_text = Text(
                "🎉 Processing finished! Your video is ready.", style="bold yellow"
            )
            celebration_panel = Panel(
                celebration_text, border_style="yellow", padding=(1, 2)
            )
            console.print(celebration_panel)

        else:
            # Error panel
            error_text = Text(
                "❌ VIDEO PROCESSING FAILED\nPlease check the error messages above for details.",
                style="bold red",
            )
            error_panel = Panel(
                error_text,
                title="[bold red]Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
            console.print(error_panel)

        return result

    finally:
        engine.cleanup()


def process_batch_videos(
    video_dir: str, output_dir: Optional[str] = None, config: Optional[dict] = None
):
    """Process multiple videos in a directory with Rich console output"""
    if config is None:
        config = load_config()

    # Initialize Rich console
    console = Console()

    video_dir_path = Path(video_dir)
    if output_dir:
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
    else:
        # Default to processed_videos directory in current directory
        output_dir_path = Path("processed_videos")
        output_dir_path.mkdir(parents=True, exist_ok=True)

    # Find video files
    video_extensions = [".mp4", ".avi", ".mov", ".mkv"]
    video_files = []
    for ext in video_extensions:
        video_files.extend(video_dir_path.glob(f"*{ext}"))

    if not video_files:
        error_text = Text(f"No video files found in {video_dir}", style="bold red")
        error_panel = Panel(
            error_text, title="[bold red]Error[/bold red]", border_style="red"
        )
        console.print(error_panel)
        return

    # Batch info panel
    batch_info_table = Table(show_header=True, header_style="bold blue")
    batch_info_table.add_column("Property", style="cyan", width=15)
    batch_info_table.add_column("Value", style="magenta")

    batch_info_table.add_row("Videos Found", f"{len(video_files)}")
    batch_info_table.add_row("Input Directory", str(video_dir_path))
    batch_info_table.add_row("Output Directory", str(output_dir_path))

    batch_panel = Panel(
        batch_info_table,
        title="[bold blue]📁 Batch Processing Started[/bold blue]",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(batch_panel)

    results = []
    for i, video_file in enumerate(video_files, 1):
        console.print(
            f"\n[bold cyan]🎬 Processing {i}/{len(video_files)}: {video_file.name}[/bold cyan]"
        )

        output_path = (
            output_dir_path / f"{video_file.stem}_processed{video_file.suffix}"
        )
        result = process_single_video(str(video_file), str(output_path), config)
        results.append(result)

    # Summary table
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    summary_table = Table(
        show_header=True, header_style="bold cyan", title="📊 Batch Processing Summary"
    )
    summary_table.add_column("Status", style="bold", width=12)
    summary_table.add_column("Count", style="magenta", justify="right")
    summary_table.add_column("Percentage", style="yellow", justify="right")

    summary_table.add_row(
        "✅ Successful", f"{successful}", f"{successful / len(results) * 100:.1f}%"
    )
    summary_table.add_row(
        "❌ Failed", f"{failed}", f"{failed / len(results) * 100:.1f}%"
    )
    summary_table.add_row("📊 Total", f"{len(results)}", "100%")

    console.print(summary_table)


def test_engines(config: Optional[dict] = None):
    """Test all consolidated engines with Rich console output"""
    if config is None:
        config = load_config()

    # Initialize Rich console
    console = Console()

    # Test info panel
    test_panel = Panel(
        Text("🧪 Testing all video processing engines...", style="bold blue"),
        title="[bold blue]Engine Testing[/bold blue]",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(test_panel)

    # Test results table
    results_table = Table(
        show_header=True, header_style="bold cyan", title="🧪 Engine Test Results"
    )
    results_table.add_column("Engine", style="cyan", width=20)
    results_table.add_column("Status", style="bold", width=12)
    results_table.add_column("Details", style="magenta")

    # Test Face Detection Engine
    console.print("\n[bold cyan]1. Testing Face Detection Engine...[/bold cyan]")
    try:
        face_detector = FaceDetectionEngine(config)
        stats = face_detector.get_performance_stats()
        results_table.add_row(
            "Face Detection", "✅ PASS", f"Backend: {stats.get('backend', 'unknown')}"
        )
        face_detector.cleanup()
    except Exception as e:
        results_table.add_row("Face Detection", "❌ FAIL", str(e))

    # Test Face Recognition Engine
    console.print("[bold cyan]2. Testing Face Recognition Engine...[/bold cyan]")
    try:
        face_recognizer = FaceRecognitionEngine(config)
        stats = face_recognizer.get_performance_stats()
        results_table.add_row(
            "Face Recognition",
            "✅ PASS",
            f"Contestants: {stats.get('contestants_loaded', 0)}",
        )
        face_recognizer.cleanup()
    except Exception as e:
        results_table.add_row("Face Recognition", "❌ FAIL", str(e))

    # Test Video Processing Engine
    console.print("[bold cyan]3. Testing Video Processing Engine...[/bold cyan]")
    try:
        # Create a dummy video config for testing
        dummy_config = VideoProcessingConfig(
            source_path="dummy.mp4",
            target_path="dummy_output.mp4",
            confidence_threshold=0.5,
            enable_tracking=True,
            enable_smoothing=True,
        )
        video_processor = VideoProcessor(dummy_config, full_config=config)
        stats = video_processor.get_performance_stats()
        results_table.add_row(
            "Video Processing", "✅ PASS", "Engine initialized successfully"
        )
        video_processor.cleanup()
    except Exception as e:
        results_table.add_row("Video Processing", "❌ FAIL", str(e))

    # Display results
    console.print("\n", results_table)

    # Completion message
    completion_text = Text("🏁 Engine testing complete!", style="bold green")
    completion_panel = Panel(completion_text, border_style="green", padding=(1, 2))
    console.print(completion_panel)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Consolidated Video Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single video
  python main.py --input video.mp4

  # Process with custom output
  python main.py --input video.mp4 --output processed_video.mp4
  
  # Process batch of videos
  python main.py --batch-dir /path/to/videos --output-dir /path/to/processed
  
  # Test engines
  python main.py --test-engines
  
  # Use custom config
  python main.py --config custom_config.yaml --input video.mp4
        """,
    )

    parser.add_argument("--input", "-i", help="Input video file")
    parser.add_argument("--output", "-o", help="Output video file (optional)")
    parser.add_argument("--batch-dir", help="Process all videos in directory")
    parser.add_argument("--output-dir", help="Output directory for batch processing")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument(
        "--test-engines", action="store_true", help="Test all consolidated engines"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load configuration
    config = load_config(args.config)

    try:
        if args.test_engines:
            test_engines(config)
        elif args.batch_dir:
            process_batch_videos(args.batch_dir, args.output_dir, config)
        elif args.input:
            result = process_single_video(args.input, args.output, config)
            sys.exit(0 if result.success else 1)
        else:
            parser.print_help()
            print("\n❗ Please specify --input, --batch-dir, or --test-engines")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
