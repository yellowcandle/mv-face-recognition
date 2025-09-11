#!/usr/bin/env python3
"""
Rich-enhanced parallel batch processing script for MV Face Recognition using Modal.com.

This version uses Rich for clean progress visualization and Modal's map() for true parallelism.

**Usage Examples:**

1. **Process all videos in parallel:**
   ```bash
   modal run modal_rich_parallel.py --parallel --max-containers 4
   ```

2. **Process single video:**
   ```bash
   modal run modal_rich_parallel.py --single-video video1.mp4
   ```
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any

from modal import App, Image, Volume

# --- Modal Configuration ---

app = App("mv-face-recognition-rich")

# Docker image with Rich added
modal_image = (
    Image.from_registry("python:3.11-slim-bookworm")
    .apt_install(
        "git", 
        "ffmpeg", 
        "build-essential",
        "g++",
        "cmake",
        "libopencv-dev",
        "python3-dev"
    )
    .env({
        "CUDA_VISIBLE_DEVICES": "0",
        "NVIDIA_VISIBLE_DEVICES": "all",
        "NVIDIA_DRIVER_CAPABILITIES": "compute,utility"
    })
    .pip_install_from_requirements("requirements.txt")
    .run_commands([
        "pip uninstall -y onnxruntime",
        "pip install onnxruntime-gpu>=1.16.0",
        "python -c \"import insightface; app = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider']); app.prepare(ctx_id=0)\"",
    ])
    .add_local_dir("src", "/src")
)

volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")

# --- Simple video listing function ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=600,  # 10 minutes for listing videos
)
def get_videos_list() -> list[str]:
    """Get list of available videos from the volume."""
    try:
        videos_dir = VOL_MOUNT_PATH / "source/videos"
        if not videos_dir.exists():
            return []
        
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        videos = []
        
        for file_path in videos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                videos.append(file_path.name)
        
        return sorted(videos)
    except Exception as e:
        print(f"Error listing videos: {e}")
        return []


# --- Individual video processing function ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    gpu="T4",
    timeout=7200,
    # Force new containers by adding resource constraints
    cpu=2.0,
    memory=8192,
    max_containers=50,
)
def process_single_video_rich(
    video_name: str,
    similarity_threshold: float = 0.25,
    force_reprocess: bool = False,
) -> Dict[str, Any]:
    """
    Process a single video with Rich-enhanced logging.
    """
    import os
    import gc
    import time
    import random
    from rich.console import Console
    from rich.panel import Panel
    
    console = Console()
    # Create unique container ID using video name and timestamp
    unique_suffix = f"{int(time.time() * 1000) % 10000}{random.randint(10, 99)}"
    container_id = f"C-{video_name[:3].upper()}-{unique_suffix}"
    
    # Create a Rich panel for this container
    console.print(Panel(
        f"🚀 Processing: {video_name[:50]}...\n"
        f"📍 Container: {container_id}\n"
        f"🎯 Threshold: {similarity_threshold}",
        title=f"[bold blue]{container_id}[/bold blue]",
        border_style="blue"
    ))
    
    try:
        # Setup environment
        sys.path.insert(0, '/')
        os.environ['OMP_NUM_THREADS'] = '1'
        os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
        # Suppress tqdm to avoid progress bar conflicts
        os.environ['TQDM_DISABLE'] = '1'
        
        # Quick GPU check
        try:
            import torch
            if torch.cuda.is_available():
                console.print(f"[green]⚡ {container_id}[/green] GPU: {torch.cuda.get_device_name()}")
            else:
                console.print(f"[yellow]⚠️ {container_id}[/yellow] No CUDA GPU")
        except Exception:
            console.print(f"[red]❌ {container_id}[/red] GPU check failed")
        
        # Import modules
        console.print(f"[blue]📦 {container_id}[/blue] Loading modules...")
        try:
            from src.services.enhanced_video_processor import EnhancedVideoProcessor
            from src.core.hardware_acceleration import HardwareAccelerator
            console.print(f"[green]✅ {container_id}[/green] Modules loaded")
        except Exception as e:
            console.print(f"[red]❌ {container_id}[/red] Module import failed: {e}")
            return {video_name: {"error": f"Import error: {e}"}}
        # Setup config
        console.print(f"[blue]📋 {container_id}[/blue] Loading configuration...")
        config_path = str(VOL_MOUNT_PATH / "config.json")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            config["paths"]["videos_dir"] = str(VOL_MOUNT_PATH / "source/videos")
            config["paths"]["contestants_dir"] = str(VOL_MOUNT_PATH / "source/photo/contestants")
            config["paths"]["chroma_db_path"] = str(VOL_MOUNT_PATH / "data/chroma_db")
            
            safe_name = video_name.replace('.', '_').replace('/', '_')
            modified_config_path = str(VOL_MOUNT_PATH / f"config_{safe_name}.json")
            
            with open(modified_config_path, 'w') as f:
                json.dump(config, f, indent=2)
                
            console.print(f"[green]✅ {container_id}[/green] Configuration ready")
        except Exception as e:
            console.print(f"[red]❌ {container_id}[/red] Config setup failed: {e}")
            return {video_name: {"error": f"Config error: {e}"}}
        
        # Initialize processor
        console.print(f"[blue]🔧 {container_id}[/blue] Initializing processor...")
        try:
            processor = EnhancedVideoProcessor(config_path=modified_config_path)
            processor.set_similarity_threshold(similarity_threshold)
            
            # Check database stats for debugging
            if hasattr(processor, 'face_matcher') and hasattr(processor.face_matcher, 'db_manager'):
                db_stats = processor.face_matcher.db_manager.get_database_stats()
                console.print(f"[cyan]📊 {container_id}[/cyan] DB Stats: {db_stats['total_embeddings']} embeddings loaded")
                console.print(f"[cyan]🎯 {container_id}[/cyan] Similarity threshold: {db_stats['similarity_threshold']}")
            else:
                console.print(f"[yellow]⚠️ {container_id}[/yellow] Could not access database stats")
            
            console.print(f"[green]✅ {container_id}[/green] Processor ready")
        except Exception as e:
            console.print(f"[red]❌ {container_id}[/red] Processor init failed: {e}")
            return {video_name: {"error": f"Processor error: {e}"}}
        
        # Hardware info
        try:
            accelerator = HardwareAccelerator()
            console.print(f"[green]🔧 {container_id}[/green] Hardware acceleration active")
        except Exception:
            console.print(f"[yellow]⚠️ {container_id}[/yellow] Hardware check failed")
        
        # Start processing with Rich progress
        console.print(f"[bold green]🎬 {container_id}[/bold green] Starting video processing...")
        start_time = time.time()
        
        try:
            # Monkey patch tqdm to suppress output during processing
            import tqdm
            original_tqdm = tqdm.tqdm
            
            class SilentTqdm:
                def __init__(self, *args, **kwargs):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def update(self, *args):
                    pass
                def set_description(self, *args):
                    pass
                def close(self):
                    pass
            
            # Replace tqdm temporarily
            tqdm.tqdm = SilentTqdm
            
            # Process video with suppressed progress bars
            result = processor.process_video_comprehensive(video_name)
            
            # Restore original tqdm
            tqdm.tqdm = original_tqdm
            
            processing_time = time.time() - start_time
            
            # Extract statistics
            stats = result.get('stats', {})
            faces_detected = stats.get('total_faces_detected', 0)
            faces_recognized = stats.get('total_faces_recognized', 0)
            frames_processed = stats.get('total_frames_processed', 0)
            frames_skipped = stats.get('total_frames_skipped', 0)
            
            # Success panel
            console.print(Panel(
                f"✅ Processing completed in {processing_time:.1f}s\n"
                f"👥 {faces_detected} faces detected\n"
                f"✅ {faces_recognized} faces recognized\n"
                f"🎬 {frames_processed:,} frames processed\n"
                f"⏩ {frames_skipped:,} frames skipped (no faces)",
                title=f"[bold green]{container_id} - SUCCESS[/bold green]",
                border_style="green"
            ))
            
            result['processing_time'] = processing_time
            result['container_id'] = container_id
            
            gc.collect()
            return {video_name: result}
            
        except Exception as e:
            processing_time = time.time() - start_time
            console.print(Panel(
                f"❌ Processing failed after {processing_time:.1f}s\n"
                f"Error: {str(e)[:100]}...",
                title=f"[bold red]{container_id} - FAILED[/bold red]",
                border_style="red"
            ))
            
            gc.collect()
            return {video_name: {"error": str(e), "processing_time": processing_time}}
        
    except Exception as e:
        console.print(Panel(
            f"❌ Container error: {str(e)[:100]}...",
            title=f"[bold red]{container_id} - ERROR[/bold red]",
            border_style="red"
        ))
        return {video_name: {"error": f"Container error: {e}"}}


# --- Parallel processing using Modal's map() ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=3600,  # 1 hour for orchestrating parallel processing
)
def launch_parallel_processing(
    video_list: list[str],
    similarity_threshold: float = 0.25,
    force_reprocess: bool = False,
) -> list[Dict[str, Any]]:
    """
    Launch parallel processing using Modal's starmap for true parallelism.
    """
    from rich.console import Console
    import time
    
    console = Console()
    
    console.print(f"[bold blue]🚀 Launching {len(video_list)} containers with starmap...[/bold blue]")
    
    # Create parameter tuples for starmap
    video_params = [
        (video_name, similarity_threshold, force_reprocess)
        for video_name in video_list
    ]
    
    start_time = time.time()
    
    # Use starmap for guaranteed parallelism
    results = list(process_single_video_rich.starmap(video_params))
    
    elapsed = time.time() - start_time
    console.print(f"[bold green]✅ All {len(video_list)} containers completed in {elapsed:.1f}s![/bold green]")
    
    return results


# --- Local entry point ---

@app.local_entrypoint()
def main(
    single_video: str = "",
    parallel: bool = False,
    max_containers: int = 4,
    force_reprocess: bool = False,
    similarity_threshold: float = 0.25,
):
    """
    Main entry point with Rich console output.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    
    console = Console()
    
    # Validation
    if not 0.0 <= similarity_threshold <= 1.0:
        console.print("[red]Error: Similarity threshold must be between 0.0 and 1.0[/red]")
        sys.exit(1)
    
    # Header
    console.print(Panel(
        f"🚀 MV Face Recognition - Modal Parallel Processing\n"
        f"🎯 Similarity threshold: {similarity_threshold}\n"
        f"🔄 Force reprocess: {force_reprocess}",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue"
    ))
    
    if single_video:
        # Single video processing
        console.print(f"[bold blue]🎬 Processing single video: {single_video}[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing video...", total=None)
            
            result = process_single_video_rich.remote(
                video_name=single_video,
                similarity_threshold=similarity_threshold,
                force_reprocess=force_reprocess,
            )
        
        console.print("[bold green]✅ Single video processing completed![/bold green]")
        
    elif parallel:
        # Parallel processing mode
        console.print("[bold blue]📋 Getting video list...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching videos...", total=None)
            available_videos = get_videos_list.remote()
        
        if not available_videos:
            console.print("[red]❌ No videos found to process[/red]")
            return
        
        console.print(f"[green]✅ Found {len(available_videos)} videos[/green]")
        
        # Show video list
        table = Table(title="Videos to Process")
        table.add_column("Index", style="cyan", no_wrap=True)
        table.add_column("Video Name", style="magenta")
        
        for i, video in enumerate(available_videos, 1):
            table.add_row(str(i), video[:60] + "..." if len(video) > 60 else video)
        
        console.print(table)
        
        # Start parallel processing
        start_time = time.time()
        
        console.print(Panel(
            f"🚀 Launching {len(available_videos)} containers in parallel...\n"
            f"📊 Max containers: {max_containers}\n"
            f"⚡ Using Modal's map() for guaranteed parallelism",
            title="[bold green]Starting Parallel Processing[/bold green]",
            border_style="green"
        ))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing all videos in parallel...", total=None)
            
            # Use starmap for true parallel processing
            results_list = launch_parallel_processing.remote(
                video_list=available_videos,
                similarity_threshold=similarity_threshold,
                force_reprocess=force_reprocess,
            )
        
        total_time = time.time() - start_time
        
        # Aggregate results from starmap format
        all_results = {}
        for result_dict in results_list:
            if isinstance(result_dict, dict):
                all_results.update(result_dict)
            else:
                # Handle unexpected format
                print(f"Unexpected result format: {type(result_dict)}")
                continue
        
        # Print comprehensive summary
        print_rich_summary(console, all_results, total_time, len(available_videos))
        
    else:
        console.print(Panel(
            "Usage:\n"
            "• modal run modal_rich_parallel.py --single-video video1.mp4\n"
            "• modal run modal_rich_parallel.py --parallel --max-containers 4",
            title="[bold yellow]Help[/bold yellow]",
            border_style="yellow"
        ))


def print_rich_summary(console, results: Dict[str, Any], total_time: float, containers_used: int):
    """Print Rich-formatted summary."""
    from rich.table import Table
    from rich.panel import Panel
    
    successful = [v for v, r in results.items() if "error" not in r]
    failed = [v for v, r in results.items() if "error" in r]
    
    # Calculate statistics
    if successful:
        total_proc_time = sum(results[v].get('processing_time', 0) for v in successful)
        total_faces_detected = sum(
            results[v].get('stats', {}).get('total_faces_detected', 0) for v in successful
        )
        total_faces_recognized = sum(
            results[v].get('stats', {}).get('total_faces_recognized', 0) for v in successful
        )
        total_frames_processed = sum(
            results[v].get('stats', {}).get('total_frames_processed', 0) for v in successful
        )
        total_frames_skipped = sum(
            results[v].get('stats', {}).get('total_frames_skipped', 0) for v in successful
        )
        
        speedup = total_proc_time / total_time if total_time > 0 else 1
        recognition_rate = (total_faces_recognized / max(total_faces_detected, 1)) * 100
        skip_rate = (total_frames_skipped / max(total_frames_processed + total_frames_skipped, 1)) * 100
    else:
        total_proc_time = speedup = recognition_rate = skip_rate = 0
        total_faces_detected = total_faces_recognized = total_frames_processed = total_frames_skipped = 0
    
    # Summary panel
    console.print(Panel(
        f"📊 Videos processed: {len(results)} total\n"
        f"✅ Successful: {len(successful)}\n"
        f"❌ Failed: {len(failed)}\n"
        f"⏱️  Wall time: {total_time/60:.1f} minutes\n"
        f"⚡ Speedup: {speedup:.1f}x\n"
        f"🎯 Sequential time: {total_proc_time/60:.1f} min → Parallel: {total_time/60:.1f} min",
        title="[bold green]🚀 PARALLEL PROCESSING SUMMARY[/bold green]",
        border_style="green"
    ))
    
    # Performance metrics
    console.print(Panel(
        f"👥 Total faces detected: {total_faces_detected:,}\n"
        f"✅ Total faces recognized: {total_faces_recognized:,}\n"
        f"📊 Recognition rate: {recognition_rate:.1f}%\n"
        f"🎬 Frames processed: {total_frames_processed:,}\n"
        f"⏩ Frames skipped (no faces): {total_frames_skipped:,} ({skip_rate:.1f}%)",
        title="[bold blue]📈 Performance Metrics[/bold blue]",
        border_style="blue"
    ))
    
    # Per-video results table
    if successful:
        table = Table(title="📹 Per-Video Results")
        table.add_column("Video", style="cyan", max_width=40)
        table.add_column("Time", style="green", justify="right")
        table.add_column("Faces", style="yellow", justify="right")
        table.add_column("Recognized", style="magenta", justify="right")
        table.add_column("Container", style="blue", justify="right")
        
        for video in successful:
            result = results[video]
            stats = result.get('stats', {})
            proc_time = result.get('processing_time', 0)
            container_id = result.get('container_id', 'unknown')
            faces_det = stats.get('total_faces_detected', 0)
            faces_rec = stats.get('total_faces_recognized', 0)
            
            video_short = video[:35] + "..." if len(video) > 35 else video
            
            table.add_row(
                video_short,
                f"{proc_time:.1f}s",
                str(faces_det),
                str(faces_rec),
                container_id
            )
        
        console.print(table)
    
    # Failed videos
    if failed:
        table = Table(title="❌ Failed Videos")
        table.add_column("Video", style="red", max_width=40)
        table.add_column("Error", style="red", max_width=50)
        
        for video in failed:
            error = results[video].get('error', 'Unknown error')
            video_short = video[:35] + "..." if len(video) > 35 else video
            error_short = error[:45] + "..." if len(error) > 45 else error
            table.add_row(video_short, error_short)
        
        console.print(table)


if __name__ == "__main__":
    print("Use 'modal run modal_rich_parallel.py --help' for usage")