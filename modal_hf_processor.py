#!/usr/bin/env python3
"""
Unified Modal Video Processor with Huggingface Xet Storage Integration

This module handles all video processing on Modal's cloud infrastructure,
with raw videos stored on Huggingface using xet storage for efficient
chunk-level deduplication.

Architecture:
1. Raw videos stored in Huggingface repository with xet storage
2. Modal containers download videos from HF, process them
3. Processed videos and metadata uploaded to Cloudflare R2

Usage:
    # Process all videos from Huggingface
    modal run modal_hf_processor.py

    # Process a single video
    modal run modal_hf_processor.py --video "video_name.mp4"

    # Parallel processing with specified containers
    modal run modal_hf_processor.py --parallel --max-containers 4

Requirements:
    - Modal account and CLI configured (`modal setup`)
    - Huggingface account and token with read access
    - HUGGINGFACE_TOKEN environment variable or Modal secret
"""

import os
import sys
import time
import json
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from modal import App, Image, Volume, Secret, gpu

# --- Configuration ---

HF_REPO_ID = "yellowcandle/mv-face-recognition-videos"  # Huggingface repository
MODAL_APP_NAME = "mv-face-recognition-hf"
VOL_MOUNT_PATH = Path("/data")

# Video extensions to process
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}


@dataclass
class ProcessingConfig:
    """Configuration for video processing"""
    similarity_threshold: float = 0.25
    force_reprocess: bool = False
    enable_upload: bool = True
    hf_repo_id: str = HF_REPO_ID


# --- Modal App Configuration ---

app = App(MODAL_APP_NAME)

# Docker image with all required dependencies
modal_image = (
    Image.from_registry("python:3.11-slim-bookworm")
    .apt_install(
        "git",
        "ffmpeg",
        "build-essential",
        "g++",
        "cmake",
        "libopencv-dev",
        "python3-dev",
        "libgl1-mesa-glx",
        "libglib2.0-0",
    )
    .env({
        "CUDA_VISIBLE_DEVICES": "0",
        "NVIDIA_VISIBLE_DEVICES": "all",
        "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
        "HF_XET_HIGH_PERFORMANCE": "1",  # Enable xet high performance mode
    })
    .pip_install(
        # Core dependencies
        "huggingface_hub>=0.32.0",  # Required for xet support
        "hf_xet",  # Xet integration
        "rich>=13.0.0",
        "tqdm>=4.66.0",
        "pyyaml>=6.0",
        "click>=8.0.0",
        # Video processing
        "opencv-python>=4.10.0",
        "ffmpeg-python>=0.2.0",
        # Face recognition
        "insightface>=0.7.3",
        "face_recognition>=1.3.0",
        "dlib>=19.24.0",
        # ML frameworks
        "torch>=2.0.0",
        "torchvision>=0.15.0",
        "onnxruntime>=1.16.0",
        # Database
        "chromadb>=0.4.0",
        # Cloudflare
        "boto3>=1.34.0",
    )
    .run_commands([
        # Install GPU-accelerated ONNX runtime
        "pip uninstall -y onnxruntime || true",
        "pip install onnxruntime-gpu>=1.16.0 || pip install onnxruntime>=1.16.0",
        # Pre-download InsightFace model
        "python -c \"import insightface; app = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider']); app.prepare(ctx_id=0)\" || true",
    ])
    .add_local_dir("mvp-processor/src", "/app/src")
    .add_local_dir("metadata", "/app/metadata")
    .add_local_file("mvp-processor/config/processing_config.yaml", "/app/config/processing_config.yaml")
)

# Persistent volume for caching and intermediate data
volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)


# --- Huggingface Integration Functions ---

@app.function(
    image=modal_image,
    secrets=[Secret.from_name("huggingface-secret")],
    timeout=600,
)
def list_hf_videos(repo_id: str = HF_REPO_ID) -> List[str]:
    """
    List all available videos in the Huggingface repository.

    Returns:
        List of video filenames in the repository
    """
    from huggingface_hub import HfApi
    from rich.console import Console

    console = Console()
    console.print(f"[blue]📋 Listing videos from HF repo: {repo_id}[/blue]")

    try:
        api = HfApi()
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")

        videos = [
            f for f in files
            if Path(f).suffix.lower() in VIDEO_EXTENSIONS
            and not f.startswith(".")
        ]

        console.print(f"[green]✅ Found {len(videos)} videos in repository[/green]")
        return sorted(videos)

    except Exception as e:
        console.print(f"[red]❌ Error listing HF videos: {e}[/red]")
        return []


@app.function(
    image=modal_image,
    secrets=[Secret.from_name("huggingface-secret")],
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=1800,  # 30 minutes for large video downloads
)
def download_video_from_hf(
    video_name: str,
    repo_id: str = HF_REPO_ID,
) -> Optional[str]:
    """
    Download a video from Huggingface repository using xet storage.

    Args:
        video_name: Name of the video file in the repository
        repo_id: Huggingface repository ID

    Returns:
        Local path to downloaded video, or None if failed
    """
    from huggingface_hub import hf_hub_download
    from rich.console import Console

    console = Console()
    console.print(f"[blue]📥 Downloading {video_name} from HF...[/blue]")

    try:
        # Create download directory
        download_dir = VOL_MOUNT_PATH / "source/videos"
        download_dir.mkdir(parents=True, exist_ok=True)

        # Download using huggingface_hub (automatically uses xet if available)
        local_path = hf_hub_download(
            repo_id=repo_id,
            filename=video_name,
            repo_type="dataset",
            local_dir=str(download_dir),
            local_dir_use_symlinks=False,
        )

        console.print(f"[green]✅ Downloaded: {local_path}[/green]")
        return local_path

    except Exception as e:
        console.print(f"[red]❌ Download failed: {e}[/red]")
        return None


# --- Video Processing Functions ---

@app.function(
    image=modal_image,
    secrets=[Secret.from_name("huggingface-secret")],
    volumes={str(VOL_MOUNT_PATH): volume},
    gpu=gpu.T4(),
    timeout=7200,  # 2 hours per video
    cpu=2.0,
    memory=8192,
)
def process_video(
    video_name: str,
    config: ProcessingConfig = ProcessingConfig(),
) -> Dict[str, Any]:
    """
    Process a single video through the face recognition pipeline.

    This function:
    1. Downloads the video from Huggingface (if not cached)
    2. Runs face detection and recognition
    3. Generates metadata and processed outputs
    4. Returns processing results

    Args:
        video_name: Name of the video file
        config: Processing configuration

    Returns:
        Dictionary with processing results and statistics
    """
    import random
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    start_time = time.time()

    # Generate unique container ID
    container_id = f"C-{video_name[:6].upper().replace('.', '')}-{int(time.time()) % 10000}"

    console.print(Panel(
        f"🚀 Processing: {video_name}\n"
        f"📍 Container: {container_id}\n"
        f"🎯 Threshold: {config.similarity_threshold}",
        title=f"[bold blue]{container_id}[/bold blue]",
        border_style="blue"
    ))

    try:
        # Setup Python path
        sys.path.insert(0, "/app")
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["TQDM_DISABLE"] = "1"

        # Check GPU availability
        try:
            import torch
            if torch.cuda.is_available():
                console.print(f"[green]⚡ {container_id}[/green] GPU: {torch.cuda.get_device_name()}")
            else:
                console.print(f"[yellow]⚠️ {container_id}[/yellow] Running on CPU")
        except Exception:
            pass

        # Step 1: Ensure video is downloaded
        console.print(f"[blue]📥 {container_id}[/blue] Checking video cache...")
        video_path = VOL_MOUNT_PATH / "source/videos" / video_name

        if not video_path.exists():
            console.print(f"[blue]📥 {container_id}[/blue] Downloading from Huggingface...")
            downloaded_path = download_video_from_hf.local(video_name, config.hf_repo_id)
            if not downloaded_path:
                return {video_name: {"error": "Failed to download video from HF"}}
            video_path = Path(downloaded_path)
        else:
            console.print(f"[green]✅ {container_id}[/green] Video found in cache")

        # Step 2: Setup processing configuration
        console.print(f"[blue]📋 {container_id}[/blue] Setting up configuration...")

        config_path = "/app/config/processing_config.yaml"
        import yaml

        with open(config_path, "r") as f:
            proc_config = yaml.safe_load(f)

        # Update paths for Modal environment
        proc_config["contestants"]["photo_dir"] = str(VOL_MOUNT_PATH / "source/photo/contestants")
        proc_config["contestants"]["info_csv"] = "/app/metadata/contestant_info.csv"
        proc_config["contestants"]["chroma_db_path"] = str(VOL_MOUNT_PATH / "data/chroma_db")
        proc_config["output"]["processed_dir"] = str(VOL_MOUNT_PATH / "processed_videos")
        proc_config["output"]["metadata_dir"] = str(VOL_MOUNT_PATH / "metadata")
        proc_config["output"]["thumbnails_dir"] = str(VOL_MOUNT_PATH / "thumbnails")
        proc_config["output"]["galleries_dir"] = str(VOL_MOUNT_PATH / "galleries")
        proc_config["face_recognition"]["similarity_threshold"] = config.similarity_threshold

        # Write modified config with sanitized filename
        # Handle path separators and special characters in video names
        import re
        safe_name = re.sub(r'[^\w\-]', '_', video_name)
        modified_config_path = str(VOL_MOUNT_PATH / f"config_{safe_name}.yaml")
        with open(modified_config_path, "w") as f:
            yaml.dump(proc_config, f)

        # Create output directories
        for dir_path in [
            VOL_MOUNT_PATH / "processed_videos",
            VOL_MOUNT_PATH / "metadata",
            VOL_MOUNT_PATH / "thumbnails",
            VOL_MOUNT_PATH / "galleries",
            VOL_MOUNT_PATH / "data/chroma_db",
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Step 3: Initialize and run processing pipeline
        console.print(f"[blue]🔧 {container_id}[/blue] Initializing processor...")

        from src.process_video import VideoProcessingPipeline

        pipeline = VideoProcessingPipeline(
            config_path=modified_config_path,
            enable_upload=False,  # We'll upload separately
            local_only=True,
        )

        # Initialize contestant database
        console.print(f"[blue]📚 {container_id}[/blue] Loading contestant database...")
        pipeline.initialize_database(force_rebuild=False)

        # Process video
        console.print(f"[bold green]🎬 {container_id}[/bold green] Processing video...")

        result = pipeline.process_video(video_path)

        processing_time = time.time() - start_time

        # Extract statistics
        metadata = result.get("metadata", {})
        processing_summary = metadata.get("processing_summary", {})

        stats = {
            "total_faces_detected": processing_summary.get("total_faces_detected", 0),
            "total_faces_recognized": processing_summary.get("total_recognitions", 0),
            "frames_processed": processing_summary.get("frames_processed", 0),
            "unique_contestants": len(metadata.get("contestant_timeline", {})),
        }

        # Success panel
        console.print(Panel(
            f"✅ Processing completed in {processing_time:.1f}s\n"
            f"👥 {stats['total_faces_detected']} faces detected\n"
            f"✅ {stats['total_faces_recognized']} faces recognized\n"
            f"🎬 {stats['frames_processed']} frames processed\n"
            f"👤 {stats['unique_contestants']} unique contestants",
            title=f"[bold green]{container_id} - SUCCESS[/bold green]",
            border_style="green"
        ))

        # Commit volume changes
        volume.commit()

        gc.collect()

        return {
            video_name: {
                "success": True,
                "processing_time": processing_time,
                "container_id": container_id,
                "stats": stats,
                "output_files": result.get("processed_videos", []),
                "metadata_file": result.get("metadata_file"),
            }
        }

    except Exception as e:
        processing_time = time.time() - start_time
        console.print(Panel(
            f"❌ Processing failed after {processing_time:.1f}s\n"
            f"Error: {str(e)[:200]}",
            title=f"[bold red]{container_id} - FAILED[/bold red]",
            border_style="red"
        ))

        import traceback
        traceback.print_exc()

        gc.collect()

        return {
            video_name: {
                "success": False,
                "error": str(e),
                "processing_time": processing_time,
                "container_id": container_id,
            }
        }


@app.function(
    image=modal_image,
    secrets=[Secret.from_name("huggingface-secret")],
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=3600,
)
def process_all_videos_parallel(
    video_list: List[str],
    config: ProcessingConfig = ProcessingConfig(),
    max_concurrent: int = 50,
) -> List[Dict[str, Any]]:
    """
    Process multiple videos in parallel using Modal's starmap with batching.

    Args:
        video_list: List of video filenames to process
        config: Processing configuration
        max_concurrent: Maximum number of videos to process concurrently

    Returns:
        List of processing results for each video
    """
    from rich.console import Console

    console = Console()
    total_videos = len(video_list)
    all_results = []

    start_time = time.time()

    # Process in batches to control concurrency
    for batch_start in range(0, total_videos, max_concurrent):
        batch_end = min(batch_start + max_concurrent, total_videos)
        batch = video_list[batch_start:batch_end]
        batch_num = (batch_start // max_concurrent) + 1
        total_batches = (total_videos + max_concurrent - 1) // max_concurrent

        console.print(f"[bold blue]🚀 Processing batch {batch_num}/{total_batches}: {len(batch)} videos...[/bold blue]")

        # Create parameter tuples for starmap
        params = [(video, config) for video in batch]

        # Process batch in parallel
        batch_results = list(process_video.starmap(params))
        all_results.extend(batch_results)

        console.print(f"[green]✅ Batch {batch_num} complete ({len(batch)} videos)[/green]")

    elapsed = time.time() - start_time
    console.print(f"[bold green]✅ All {total_videos} videos processed in {elapsed:.1f}s[/bold green]")

    return all_results


# --- Utility Functions ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=600,
)
def get_processing_status() -> Dict[str, Any]:
    """
    Get the current status of processed videos on the Modal volume.

    Returns:
        Dictionary with volume status and processed files
    """
    status = {
        "processed_videos": [],
        "metadata_files": [],
        "cached_source_videos": [],
        "disk_usage": {},
    }

    # Check processed videos
    processed_dir = VOL_MOUNT_PATH / "processed_videos"
    if processed_dir.exists():
        status["processed_videos"] = [f.name for f in processed_dir.iterdir() if f.is_file()]

    # Check metadata
    metadata_dir = VOL_MOUNT_PATH / "metadata"
    if metadata_dir.exists():
        status["metadata_files"] = [f.name for f in metadata_dir.iterdir() if f.suffix == ".json"]

    # Check cached source videos
    source_dir = VOL_MOUNT_PATH / "source/videos"
    if source_dir.exists():
        status["cached_source_videos"] = [f.name for f in source_dir.iterdir() if f.is_file()]

    return status


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=300,
)
def clear_cache(clear_processed: bool = False, clear_source: bool = False):
    """
    Clear cached data from the Modal volume.

    Args:
        clear_processed: Whether to clear processed videos
        clear_source: Whether to clear source video cache
    """
    import shutil
    from rich.console import Console

    console = Console()

    if clear_source:
        source_dir = VOL_MOUNT_PATH / "source/videos"
        if source_dir.exists():
            shutil.rmtree(source_dir)
            console.print("[yellow]🗑️ Cleared source video cache[/yellow]")

    if clear_processed:
        for dir_name in ["processed_videos", "metadata", "thumbnails", "galleries"]:
            dir_path = VOL_MOUNT_PATH / dir_name
            if dir_path.exists():
                shutil.rmtree(dir_path)
                console.print(f"[yellow]🗑️ Cleared {dir_name}[/yellow]")

    volume.commit()
    console.print("[green]✅ Cache cleared[/green]")


# --- Local Entrypoint ---

@app.local_entrypoint()
def main(
    video: str = "",
    parallel: bool = False,
    max_containers: int = 4,
    force_reprocess: bool = False,
    similarity_threshold: float = 0.25,
    list_videos: bool = False,
    status: bool = False,
    clear_cache_all: bool = False,
):
    """
    MV Face Recognition - Modal + Huggingface Processing

    Args:
        video: Single video name to process
        parallel: Process all videos in parallel
        max_containers: Maximum parallel containers
        force_reprocess: Force reprocessing even if already done
        similarity_threshold: Face matching threshold (0.0-1.0)
        list_videos: List available videos in HF repository
        status: Show processing status
        clear_cache_all: Clear all cached data
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console = Console()

    # Validation
    if not 0.0 <= similarity_threshold <= 1.0:
        console.print("[red]Error: Similarity threshold must be between 0.0 and 1.0[/red]")
        sys.exit(1)

    # Header
    console.print(Panel(
        f"🚀 MV Face Recognition - Modal + Huggingface Pipeline\n"
        f"📦 HF Repository: {HF_REPO_ID}\n"
        f"🎯 Similarity threshold: {similarity_threshold}",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue"
    ))

    # Handle different commands
    if list_videos:
        console.print("[bold blue]📋 Listing videos from Huggingface...[/bold blue]")
        videos = list_hf_videos.remote()

        if videos:
            table = Table(title="Available Videos")
            table.add_column("Index", style="cyan")
            table.add_column("Video Name", style="magenta")

            for i, v in enumerate(videos, 1):
                table.add_row(str(i), v)

            console.print(table)
        else:
            console.print("[yellow]No videos found in repository[/yellow]")
        return

    if status:
        console.print("[bold blue]📊 Getting processing status...[/bold blue]")
        vol_status = get_processing_status.remote()

        console.print(Panel(
            f"📥 Cached source videos: {len(vol_status['cached_source_videos'])}\n"
            f"📹 Processed videos: {len(vol_status['processed_videos'])}\n"
            f"📄 Metadata files: {len(vol_status['metadata_files'])}",
            title="[bold green]Volume Status[/bold green]",
            border_style="green"
        ))
        return

    if clear_cache_all:
        console.print("[yellow]🗑️ Clearing all cached data...[/yellow]")
        clear_cache.remote(clear_processed=True, clear_source=True)
        return

    # Create processing config
    config = ProcessingConfig(
        similarity_threshold=similarity_threshold,
        force_reprocess=force_reprocess,
    )

    if video:
        # Single video processing
        console.print(f"[bold blue]🎬 Processing single video: {video}[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Processing video...", total=None)
            result = process_video.remote(video, config)

        print_results(console, result)

    elif parallel:
        # Parallel processing
        console.print("[bold blue]📋 Getting video list from Huggingface...[/bold blue]")

        videos = list_hf_videos.remote()

        if not videos:
            console.print("[red]❌ No videos found to process[/red]")
            return

        # Process all videos with controlled concurrency
        videos_to_process = videos

        console.print(f"[green]✅ Processing {len(videos_to_process)} videos (max {max_containers} concurrent)[/green]")

        # Show video list
        table = Table(title="Videos to Process")
        table.add_column("Index", style="cyan")
        table.add_column("Video Name", style="magenta")

        for i, v in enumerate(videos_to_process, 1):
            table.add_row(str(i), v[:60] + "..." if len(v) > 60 else v)

        console.print(table)

        # Start parallel processing
        start_time = time.time()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Processing all videos in parallel...", total=None)
            results = process_all_videos_parallel.remote(videos_to_process, config, max_containers)

        total_time = time.time() - start_time
        print_batch_results(console, results, total_time)

    else:
        # Show help
        console.print(Panel(
            "Usage:\n"
            "• modal run modal_hf_processor.py --list-videos\n"
            "• modal run modal_hf_processor.py --video video1.mp4\n"
            "• modal run modal_hf_processor.py --parallel --max-containers 4\n"
            "• modal run modal_hf_processor.py --status\n"
            "• modal run modal_hf_processor.py --clear-cache-all",
            title="[bold yellow]Help[/bold yellow]",
            border_style="yellow"
        ))


def print_results(console, result: Dict[str, Any]):
    """Print processing results for a single video."""
    from rich.panel import Panel

    for video_name, data in result.items():
        if data.get("success"):
            stats = data.get("stats", {})
            console.print(Panel(
                f"✅ Video: {video_name}\n"
                f"⏱️ Processing time: {data['processing_time']:.1f}s\n"
                f"👥 Faces detected: {stats.get('total_faces_detected', 0)}\n"
                f"✅ Faces recognized: {stats.get('total_faces_recognized', 0)}\n"
                f"🎬 Frames processed: {stats.get('frames_processed', 0)}\n"
                f"👤 Unique contestants: {stats.get('unique_contestants', 0)}",
                title="[bold green]SUCCESS[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"❌ Video: {video_name}\n"
                f"Error: {data.get('error', 'Unknown error')}",
                title="[bold red]FAILED[/bold red]",
                border_style="red"
            ))


def print_batch_results(console, results: List[Dict[str, Any]], total_time: float):
    """Print processing results for batch processing."""
    from rich.panel import Panel
    from rich.table import Table

    # Flatten results
    all_results = {}
    for r in results:
        if isinstance(r, dict):
            all_results.update(r)

    successful = [v for v, r in all_results.items() if r.get("success")]
    failed = [v for v, r in all_results.items() if not r.get("success")]

    # Calculate aggregate stats
    if successful:
        total_proc_time = sum(all_results[v].get("processing_time", 0) for v in successful)
        total_faces = sum(all_results[v].get("stats", {}).get("total_faces_detected", 0) for v in successful)
        total_recognized = sum(all_results[v].get("stats", {}).get("total_faces_recognized", 0) for v in successful)
        speedup = total_proc_time / total_time if total_time > 0 else 1
    else:
        total_proc_time = total_faces = total_recognized = speedup = 0

    # Summary panel
    console.print(Panel(
        f"📊 Videos processed: {len(all_results)}\n"
        f"✅ Successful: {len(successful)}\n"
        f"❌ Failed: {len(failed)}\n"
        f"⏱️ Wall time: {total_time/60:.1f} minutes\n"
        f"⚡ Speedup: {speedup:.1f}x\n"
        f"👥 Total faces detected: {total_faces}\n"
        f"✅ Total faces recognized: {total_recognized}",
        title="[bold green]BATCH PROCESSING COMPLETE[/bold green]",
        border_style="green"
    ))

    # Per-video results table
    if successful:
        table = Table(title="Per-Video Results")
        table.add_column("Video", style="cyan", max_width=40)
        table.add_column("Time", style="green", justify="right")
        table.add_column("Faces", style="yellow", justify="right")
        table.add_column("Recognized", style="magenta", justify="right")

        for video in successful:
            data = all_results[video]
            stats = data.get("stats", {})
            table.add_row(
                video[:35] + "..." if len(video) > 35 else video,
                f"{data.get('processing_time', 0):.1f}s",
                str(stats.get("total_faces_detected", 0)),
                str(stats.get("total_faces_recognized", 0)),
            )

        console.print(table)

    # Failed videos
    if failed:
        table = Table(title="Failed Videos")
        table.add_column("Video", style="red", max_width=40)
        table.add_column("Error", style="red", max_width=50)

        for video in failed:
            error = all_results[video].get("error", "Unknown")
            table.add_row(
                video[:35] + "..." if len(video) > 35 else video,
                error[:45] + "..." if len(error) > 45 else error,
            )

        console.print(table)


if __name__ == "__main__":
    print("Use 'modal run modal_hf_processor.py --help' for usage")
