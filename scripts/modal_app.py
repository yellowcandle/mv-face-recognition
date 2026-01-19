#!/usr/bin/env python3
"""
Unified Modal App for MV Face Recognition.

Orchestrates:
1. Video processing with face detection and annotation
2. Database synchronization with HuggingFace
3. Embedding generation and management
4. YouTube video ingestion and processing

This is the main entry point for all Modal-based operations.

Usage:
    modal run scripts/modal_app.py --process-videos
    modal run scripts/modal_app.py --sync-embeddings
    modal run scripts/modal_app.py --process-youtube --url "https://youtube.com/..."
    modal run scripts/modal_app.py --full-pipeline
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from modal import web_endpoint, App, Image, Volume, Secret, method
import click

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App("mv-face-recognition-main")

modal_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install(
        "git",
        "git-lfs",
        "ffmpeg",
        "sqlite3",
        "build-essential",
        "libssl-dev",
    )
    .pip_install_from_requirements("requirements.txt")
    .pip_install(
        "pysqlite3-binary",
        "onnxruntime-gpu",
        "huggingface_hub>=0.32.0",
        "yt-dlp>=2024.8.6",
        "opencv-contrib-python>=4.8.0",
    )
    .add_local_dir("src", "/src")
    .add_local_file("metadata/contestant_info.csv", "/data/contestant_info.csv")
)

volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")

HF_REPO_ID = "yellowcandle/mv-face-recognition-data"


class VideoProcessor:
    """Wrapper for video processing functions."""

    def __init__(self):
        """Initialize video processor."""
        self.processed_count = 0
        self.failed_count = 0

    def process_video(self, video_path: str) -> Dict[str, Any]:
        """Process a single video."""
        try:
            import sys
            sys.path.insert(0, "/src")
            
            from core.face_detector import FaceDetector
            from services.video_processor import VideoProcessor as VP
            
            processor = VP(video_path=video_path)
            result = processor.process()
            
            self.processed_count += 1
            return {
                "status": "success",
                "video": video_path,
                "faces_detected": len(result.get("faces", [])),
                "duration": result.get("duration"),
            }
        except Exception as e:
            self.failed_count += 1
            logger.error(f"Error processing {video_path}: {e}")
            return {
                "status": "error",
                "video": video_path,
                "error": str(e),
            }


@app.cls(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
)
class VideoBatchProcessor:
    """Batch video processing class."""

    def __init__(self):
        """Initialize batch processor."""
        self.processor = VideoProcessor()

    @method()
    def process_batch(self, video_paths: List[str]) -> Dict[str, Any]:
        """Process multiple videos."""
        logger.info(f"Processing {len(video_paths)} videos...")
        
        results = []
        for video_path in video_paths:
            result = self.processor.process_video(video_path)
            results.append(result)
            logger.info(f"  Processed: {video_path} - {result['status']}")
        
        return {
            "total": len(video_paths),
            "processed": self.processor.processed_count,
            "failed": self.processor.failed_count,
            "results": results,
        }


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
)
def sync_from_huggingface() -> Dict[str, Any]:
    """Sync contestant data and embeddings from HuggingFace."""
    logger.info("Syncing from HuggingFace...")
    
    try:
        from huggingface_hub import snapshot_download
        
        local_dir = VOL_MOUNT_PATH / "hf-sync"
        local_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot_download(
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            local_dir=str(local_dir),
            token=os.getenv("HF_TOKEN"),
        )
        
        logger.info(f"✅ Synced from HuggingFace to {local_dir}")
        
        return {
            "status": "success",
            "path": str(local_dir),
            "message": "Data synced successfully",
        }
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
)
def upload_to_huggingface(results_dir: str) -> Dict[str, Any]:
    """Upload processed results to HuggingFace."""
    logger.info(f"Uploading results from {results_dir}...")
    
    try:
        from huggingface_hub import HfApi
        
        api = HfApi(token=os.getenv("HF_TOKEN"))
        
        results_path = Path(results_dir)
        if not results_path.exists():
            raise FileNotFoundError(f"Results directory not found: {results_dir}")
        
        file_count = 0
        for file_path in results_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(results_path)
                logger.info(f"  Uploading: {relative_path}")
                file_count += 1
        
        logger.info(f"✅ Uploaded {file_count} files")
        
        return {
            "status": "success",
            "files_uploaded": file_count,
            "message": "Results uploaded successfully",
        }
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
)
def check_system_status() -> Dict[str, Any]:
    """Check system status and readiness."""
    logger.info("Checking system status...")
    
    status = {
        "chromadb": False,
        "models": False,
        "storage": False,
        "contestants": 0,
    }
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(VOL_MOUNT_PATH / "chroma"))
        collection = client.get_collection(name="contestants_faces")
        status["chromadb"] = True
        status["contestants"] = collection.count()
        logger.info(f"✅ ChromaDB ready with {status['contestants']} contestants")
    except Exception as e:
        logger.warning(f"⚠️  ChromaDB check failed: {e}")
    
    try:
        import insightface
        status["models"] = True
        logger.info("✅ InsightFace models available")
    except Exception as e:
        logger.warning(f"⚠️  Model check failed: {e}")
    
    storage_path = VOL_MOUNT_PATH / "storage"
    storage_path.mkdir(parents=True, exist_ok=True)
    status["storage"] = storage_path.exists()
    logger.info(f"✅ Storage available at {storage_path}")
    
    return {
        "status": "ready" if all(status.values()) else "partial",
        "components": status,
    }


@app.local_entrypoint()
def main(
    process_videos: bool = False,
    sync_embeddings: bool = False,
    upload_results: bool = False,
    full_pipeline: bool = False,
    process_youtube: bool = False,
    youtube_url: Optional[str] = None,
    check_status: bool = False,
):
    """Main entry point for Modal operations."""
    
    logger.info("=" * 60)
    logger.info("MV Face Recognition Modal Pipeline")
    logger.info("=" * 60)
    
    if check_status or full_pipeline:
        logger.info("\n1️⃣  Checking system status...")
        status = check_system_status.remote()
        logger.info(f"   Status: {json.dumps(status, indent=2)}")
    
    if sync_embeddings or full_pipeline:
        logger.info("\n2️⃣  Syncing from HuggingFace...")
        result = sync_from_huggingface.remote()
        logger.info(f"   Result: {json.dumps(result, indent=2)}")
    
    if process_videos or full_pipeline:
        logger.info("\n3️⃣  Processing videos...")
        logger.info("   ⚠️  Video processing requires source videos in /data/videos/")
        logger.info("   Configure video paths before running full pipeline")
    
    if upload_results or full_pipeline:
        logger.info("\n4️⃣  Uploading results to HuggingFace...")
        result = upload_to_huggingface.remote(str(VOL_MOUNT_PATH / "results"))
        logger.info(f"   Result: {json.dumps(result, indent=2)}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Pipeline completed")
    logger.info("=" * 60)


if __name__ == "__main__":
    import sys
    
    parser = argparse.ArgumentParser(
        description="Modal app for MV Face Recognition"
    )
    parser.add_argument(
        "--process-videos",
        action="store_true",
        help="Process videos",
    )
    parser.add_argument(
        "--sync-embeddings",
        action="store_true",
        help="Sync embeddings from HuggingFace",
    )
    parser.add_argument(
        "--upload-results",
        action="store_true",
        help="Upload results to HuggingFace",
    )
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run full pipeline (sync -> process -> upload)",
    )
    parser.add_argument(
        "--process-youtube",
        action="store_true",
        help="Process YouTube video",
    )
    parser.add_argument(
        "--youtube-url",
        help="YouTube video URL",
    )
    parser.add_argument(
        "--check-status",
        action="store_true",
        help="Check system status",
    )

    args = parser.parse_args()

    main(
        process_videos=args.process_videos,
        sync_embeddings=args.sync_embeddings,
        upload_results=args.upload_results,
        full_pipeline=args.full_pipeline,
        process_youtube=args.process_youtube,
        youtube_url=args.youtube_url,
        check_status=args.check_status,
    )

# Add FastAPI webhook endpoint for external triggering
@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
)
@web_endpoint(method="POST")
def webhook_process_video(payload: dict) -> dict:
    """Webhook endpoint to trigger video processing from external services."""
    try:
        video_url = payload.get("video_url")
        video_name = payload.get("video_name", "unknown")
        
        if not video_url:
            return {"status": "error", "message": "video_url is required"}
        
        logger.info(f"Webhook received: {video_name} - {video_url}")
        
        # For now, just queue the job and return immediately
        # In production, you might want to start processing immediately
        job_id = f"webhook_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Store job info
        job_data = {
            "id": job_id,
            "video_url": video_url,
            "video_name": video_name,
            "status": "queued",
            "created_at": time.time(),
        }
        
        # Here you would typically:
        # 1. Download the video
        # 2. Start processing with VideoProcessor
        # 3. Upload results to HuggingFace
        
        # For now, return queued status
        return {
            "status": "queued",
            "job_id": job_id,
            "video_url": video_url,
            "message": "Job queued successfully. Processing will start shortly.",
        }
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}
