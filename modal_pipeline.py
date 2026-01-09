#!/usr/bin/env python3
"""
Modal Video Processing Pipeline for MV Face Recognition System

Cloud-based video processing pipeline using Modal.com's serverless GPU infrastructure.
Provides parallel video processing with automatic scaling and persistent storage.

## Setup

1. Install dependencies:
   ```bash
   pip install modal rich
   ```

2. Authenticate with Modal:
   ```bash
   modal token new
   ```

3. Create persistent volume:
   ```bash
   modal volume create mv-face-data
   ```

4. Upload source data:
   ```bash
   modal volume put mv-face-data source /source
   modal volume put mv-face-data metadata /metadata
   modal volume put mv-face-data config.json /config.json
   ```

## Usage

Process all videos:
```bash
python modal_pipeline.py
```

Process single video:
```bash
python modal_pipeline.py --video "video1.mp4"
```

Process with custom threshold:
```bash
python modal_pipeline.py --threshold 0.3
```

Download results:
```bash
modal volume get mv-face-data processed_videos ./output
```

## Performance

- Single video: ~2-5 minutes on T4 GPU
- Parallel: Linear scaling with container count
- Cost: ~$0.05-0.10 per video on T4
"""

import sys
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import subprocess

try:
    from modal import App, Image, Volume, gpu
except ImportError:
    print("Error: modal package not installed")
    print("Install with: pip install modal")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Modal application configuration
app = App("mv-face-recognition-pipeline")

# Persistent volume for data storage
volume = Volume.from_name("mv-face-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")

# Docker image with all dependencies
modal_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install(
        "git",
        "ffmpeg",
        "libgl1",
        "libglib2.0-0",
    )
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("src", "/src")
)


@dataclass
class VideoProcessingResult:
    """Data class for video processing results."""
    video_name: str
    success: bool
    processing_time: float
    frames_processed: int
    faces_detected: int
    faces_recognized: int
    error: Optional[str] = None
    container_id: Optional[str] = None


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=600,
)
def list_available_videos() -> List[str]:
    """List all available videos from volume."""
    try:
        videos_dir = VOL_MOUNT_PATH / "source/videos"
        if not videos_dir.exists():
            logger.warning(f"Videos directory not found: {videos_dir}")
            return []

        video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
        videos = sorted([
            f.name for f in videos_dir.iterdir()
            if f.is_file() and f.suffix.lower() in video_extensions
        ])
        logger.info(f"Found {len(videos)} videos in volume")
        return videos
    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        return []


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    gpu="T4",
    timeout=3600,
    cpu=2.0,
    memory=8192,
)
def process_video_task(
    video_name: str,
    similarity_threshold: float = 0.25,
    force_reprocess: bool = False,
) -> VideoProcessingResult:
    """Process a single video in Modal container."""
    import os
    import gc
    import random
    import cv2
    from pathlib import Path

    container_id = f"C-{video_name[:8].replace('.', '')}-{random.randint(1000, 9999)}"
    start_time = time.time()

    logger.info(f"[{container_id}] Starting: {video_name}")

    try:
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
        os.environ["TQDM_DISABLE"] = "1"

        sys.path.insert(0, "/src")

        from src.core.face_detector import FaceDetector
        from src.core.face_matcher import FaceMatcher

        config_path = str(VOL_MOUNT_PATH / "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)

        config["paths"]["videos_dir"] = str(VOL_MOUNT_PATH / "source/videos")
        config["paths"]["chroma_db_path"] = str(VOL_MOUNT_PATH / "data/chroma_db")
        config["paths"]["processed_videos_dir"] = str(VOL_MOUNT_PATH / "processed_videos")
        config["paths"]["metadata_dir"] = str(VOL_MOUNT_PATH / "metadata")
        config["paths"]["clips_dir"] = str(VOL_MOUNT_PATH / "clips")

        face_detector = FaceDetector(
            model_name=config.get("face_detection", {}).get("model_name", "buffalo_l"),
            confidence_threshold=config.get("face_detection", {}).get("detection_threshold", 0.5)
        )

        face_matcher = FaceMatcher(config_path=config_path)

        video_path = VOL_MOUNT_PATH / "source/videos" / video_name
        processed_path = VOL_MOUNT_PATH / "processed_videos" / video_name
        metadata_path = VOL_MOUNT_PATH / "metadata" / f"{video_path.stem}_metadata.json"

        if not force_reprocess and processed_path.exists() and metadata_path.exists():
            logger.info(f"[{container_id}] Video already processed, skipping")
            return VideoProcessingResult(
                video_name=video_name,
                success=True,
                processing_time=time.time() - start_time,
                frames_processed=0,
                faces_detected=0,
                faces_recognized=0,
                container_id=container_id,
            )

        logger.info(f"[{container_id}] Processing video...")
        frames_processed = 0
        faces_detected = 0
        faces_recognized = 0

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_skip = 5

        fourcc_code = 0x7634706d  # 'mp4v' in hex

        fourcc = cv2.VideoWriter_fourcc(
            'm', 'p', '4', 'v'
        )  # type: ignore[attr-defined]
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(
            str(processed_path),
            fourcc,
            fps,
            (frame_width, frame_height),
            True
        )

        metadata = {
            "video_name": video_name,
            "processed_at": datetime.now().isoformat(),
            "frames": [],
        }

        frame_number = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_number % frame_skip == 0:
                face_detections = face_detector.detect(frame)

                frame_metadata = {
                    "frame_number": frame_number,
                    "timestamp": frame_number / fps,
                    "faces": [],
                }

                for face in face_detections:
                    faces_detected += 1
                    embedding = face.get("embedding")

                    if embedding is not None:
                        match = face_matcher.match_face(embedding)

                        if match:
                            faces_recognized += 1
                            contestant_name, confidence = match

                            bbox = face.get("bbox")
                            if bbox:
                                x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

                                cv2.rectangle(
                                    frame,
                                    (x1, y1),
                                    (x2, y2),
                                    (0, 255, 0),
                                    2
                                )
                                cv2.putText(
                                    frame,
                                    f"{contestant_name} ({confidence:.2f})",
                                    (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (0, 255, 0),
                                    2
                                )

                                frame_metadata["faces"].append({
                                    "contestant_name": contestant_name,
                                    "similarity": float(confidence),
                                    "bbox": [x1, y1, x2, y2],
                                })

                metadata["frames"].append(frame_metadata)
                frames_processed += 1

            out.write(frame)
            frame_number += 1

            if frame_number % 100 == 0:
                logger.info(
                    f"[{container_id}] Progress: {frame_number}/{total_frames} frames"
                )

        cap.release()
        out.release()

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

        processing_time = time.time() - start_time
        logger.info(f"[{container_id}] Completed: {processing_time:.1f}s")

        gc.collect()

        return VideoProcessingResult(
            video_name=video_name,
            success=True,
            processing_time=processing_time,
            frames_processed=frames_processed,
            faces_detected=faces_detected,
            faces_recognized=faces_recognized,
            container_id=container_id,
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[{container_id}] Failed: {str(e)}")
        import traceback
        traceback.print_exc()

        gc.collect()

        return VideoProcessingResult(
            video_name=video_name,
            success=False,
            processing_time=processing_time,
            frames_processed=0,
            faces_detected=0,
            faces_recognized=0,
            error=str(e),
            container_id=container_id,
        )


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    timeout=1800,
)
def run_parallel_pipeline(
    video_list: List[str],
    similarity_threshold: float = 0.25,
    force_reprocess: bool = False,
) -> List[VideoProcessingResult]:
    """Run parallel video processing pipeline."""
    import time
    start_time = time.time()

    logger.info(f"Starting parallel processing of {len(video_list)} videos")
    logger.info(f"Similarity threshold: {similarity_threshold}")

    video_params = [
        (video, similarity_threshold, force_reprocess)
        for video in video_list
    ]

    results = list(process_video_task.starmap(video_params))

    total_time = time.time() - start_time
    logger.info(f"All containers completed in {total_time:.1f}s")

    return results


@app.local_entrypoint()
def main(
    video: str = "",
    threshold: float = 0.25,
    force: bool = False,
    parallel: bool = False,
    list_only: bool = False,
):
    """Main entry point for Modal pipeline."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        print("Error: rich package not installed")
        print("Install with: pip install rich")
        sys.exit(1)

    console = Console()

    console.print(
        Panel(
            "🚀 MV Face Recognition - Modal Video Processing Pipeline",
            title="[bold blue]Modal Pipeline[/bold blue]",
            border_style="blue",
        )
    )

    if list_only:
        console.print("[cyan]Listing available videos...[/cyan]")
        videos = list_available_videos.remote()

        if not videos:
            console.print("[yellow]No videos found in volume[/yellow]")
            return

        table = Table(title="Available Videos")
        table.add_column("Index", style="cyan")
        table.add_column("Video Name", style="green")

        for i, v in enumerate(videos, 1):
            table.add_row(str(i), v)

        console.print(table)
        return

    if not 0.0 <= threshold <= 1.0:
        console.print("[red]Error: Threshold must be between 0.0 and 1.0[/red]")
        sys.exit(1)

    console.print(f"[cyan]Fetching video list...[/cyan]")
    available_videos = list_available_videos.remote()

    if not available_videos:
        console.print("[red]No videos found in volume[/red]")
        console.print("\n[yellow]To upload videos:[/yellow]")
        console.print("  modal volume put mv-face-data source /source")
        return

    if video:
        if video not in available_videos:
            console.print(f"[red]Video '{video}' not found[/red]")
            console.print(f"\n[yellow]Available videos:[/yellow] {', '.join(available_videos[:5])}")
            sys.exit(1)

        videos_to_process = [video]
        console.print(f"[green]Processing single video: {video}[/green]")
    else:
        videos_to_process = available_videos
        console.print(f"[green]Processing {len(videos_to_process)} videos[/green]")

    console.print(f"[cyan]Threshold: {threshold}[/cyan]")
    console.print(f"[cyan]Force reprocess: {force}[/cyan]")
    console.print(f"[cyan]Parallel mode: {parallel}[/cyan]")

    start_time = time.time()

    if parallel:
        console.print(
            Panel(
                f"🚀 Launching {len(videos_to_process)} containers",
                title="[bold green]Parallel Processing[/bold green]",
                border_style="green",
            )
        )

        results = run_parallel_pipeline.remote(
            video_list=videos_to_process,
            similarity_threshold=threshold,
            force_reprocess=force,
        )
    else:
        console.print("[cyan]Processing videos sequentially...[/cyan]")
        results = []
        for v in videos_to_process:
            result = process_video_task.remote(
                video_name=v,
                similarity_threshold=threshold,
                force_reprocess=force,
            )
            results.append(result)

    total_time = time.time() - start_time

    print_summary(console, results, total_time, parallel)


def print_summary(
    console,
    results: List[VideoProcessingResult],
    total_time: float,
    parallel: bool,
):
    """Print processing summary with Rich formatting."""
    from rich.table import Table
    from rich.panel import Panel

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if successful:
        total_frames = sum(r.frames_processed for r in successful)
        total_faces = sum(r.faces_detected for r in successful)
        total_recognized = sum(r.faces_recognized for r in successful)
        total_proc_time = sum(r.processing_time for r in successful)

        speedup = total_proc_time / total_time if total_time > 0 else 1
        recognition_rate = (total_recognized / max(total_faces, 1)) * 100
    else:
        total_frames = total_faces = total_recognized = total_proc_time = 0
        speedup = recognition_rate = 0

    console.print(
        Panel(
            f"✅ Videos: {len(results)} total\n"
            f"✓ Success: {len(successful)}\n"
            f"✗ Failed: {len(failed)}\n"
            f"⏱️  Wall time: {total_time/60:.1f} min\n"
            f"⚡ Speedup: {speedup:.1f}x",
            title="[bold green]Processing Summary[/bold green]",
            border_style="green",
        )
    )

    if successful:
        console.print(
            Panel(
                f"🎬 Frames: {total_frames:,}\n"
                f"👥 Faces: {total_faces:,}\n"
                f"✅ Recognized: {total_recognized:,}\n"
                f"📊 Rate: {recognition_rate:.1f}%",
                title="[bold blue]Performance Metrics[/bold blue]",
                border_style="blue",
            )
        )

        table = Table(title="Per-Video Results")
        table.add_column("Video", style="cyan", max_width=40)
        table.add_column("Time", style="green", justify="right")
        table.add_column("Frames", style="yellow", justify="right")
        table.add_column("Faces", style="magenta", justify="right")
        table.add_column("Recognized", style="blue", justify="right")
        table.add_column("Container", style="white", justify="right")

        for r in successful:
            table.add_row(
                r.video_name[:35] + "..." if len(r.video_name) > 35 else r.video_name,
                f"{r.processing_time:.1f}s",
                str(r.frames_processed),
                str(r.faces_detected),
                str(r.faces_recognized),
                r.container_id or "N/A",
            )

        console.print(table)

    if failed:
        table = Table(title="Failed Videos", style="red")
        table.add_column("Video", style="red", max_width=40)
        table.add_column("Error", style="red", max_width=60)

        for r in failed:
            error_msg = r.error[:55] + "..." if r.error and len(r.error) > 55 else (r.error or "Unknown")
            table.add_row(
                r.video_name[:35] + "..." if len(r.video_name) > 35 else r.video_name,
                error_msg,
            )

        console.print(table)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Modal Video Processing Pipeline")
    parser.add_argument("--video", "-v", help="Process single video")
    parser.add_argument("--threshold", "-t", type=float, default=0.25, help="Similarity threshold (0.0-1.0)")
    parser.add_argument("--force", "-f", action="store_true", help="Force reprocessing")
    parser.add_argument("--parallel", "-p", action="store_true", help="Enable parallel processing")
    parser.add_argument("--list", "-l", action="store_true", dest="list_only", help="List available videos")

    args = parser.parse_args()

    main(
        video=args.video,
        threshold=args.threshold,
        force=args.force,
        parallel=args.parallel,
        list_only=args.list_only,
    )
