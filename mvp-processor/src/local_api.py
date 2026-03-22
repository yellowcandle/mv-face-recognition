"""
Local API server for the React admin frontend.

Wraps the video processing pipeline as a FastAPI app so the admin UI
can trigger processing, check job status, and browse results.

Usage:
    cd mvp-processor && .venv/bin/python -m uvicorn src.local_api:app --port 8000
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MV Face Recognition Local API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory job store ───

jobs: dict[str, dict] = {}
SOURCE_DIR = Path("../source/videos")
CONFIG_PATH = "config/processing_config.yaml"


class ProcessRequest(BaseModel):
    video: Optional[str] = None  # specific video filename, or None for all
    no_annotate: bool = False


# ─── Video listing ───

@app.get("/api/videos/local")
async def list_local_videos():
    """List all video files in source/videos/."""
    if not SOURCE_DIR.exists():
        return {"videos": []}

    videos = []
    for f in sorted(SOURCE_DIR.iterdir()):
        if f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv"):
            videos.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
            })
    return {"videos": videos}


@app.get("/api/videos/processed/list")
async def list_processed_videos():
    """List processed video metadata from metadata/ dir."""
    metadata_dir = Path("../metadata")
    if not metadata_dir.exists():
        return []

    videos = []
    for f in sorted(metadata_dir.glob("*_metadata.json")):
        if "_dense_" in f.name or "_annotated_" in f.name:
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            vi = data.get("video_info", {})
            name = f.stem.replace("_metadata", "")
            videos.append({
                "id": name,
                "name": name,
                "stream_url": f"/api/videos/stream/{name}",
                "duration": vi.get("duration", 0),
                "width": vi.get("width", 0),
                "height": vi.get("height", 0),
            })
        except (json.JSONDecodeError, OSError):
            continue

    return videos


@app.get("/api/contestants")
async def list_contestants():
    """List contestants from CSV."""
    import csv
    csv_path = Path("../metadata/contestant_info.csv")
    if not csv_path.exists():
        return []

    contestants = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            contestants.append({
                "id": row["編號"].strip(),
                "number": int(row["編號"].strip()),
                "name": row["姓名"].strip(),
                "nickname": row["暱稱"].strip(),
                "age": int(row["年齡"]) if row.get("年齡", "").strip() else None,
            })
    return contestants


# ─── Processing ───

@app.post("/api/processing/trigger")
async def trigger_processing(req: ProcessRequest):
    """Start a local video processing job."""
    job_id = str(uuid.uuid4())[:8]

    if req.video:
        video_path = SOURCE_DIR / req.video
        if not video_path.exists():
            raise HTTPException(404, f"Video not found: {req.video}")
        video_files = [video_path]
    else:
        if not SOURCE_DIR.exists():
            raise HTTPException(404, "No source/videos directory")
        video_files = sorted(
            f for f in SOURCE_DIR.iterdir()
            if f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv")
        )

    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "mode": "local",
        "total_videos": len(video_files),
        "videos_processed": 0,
        "current_video": None,
        "created_at": _now(),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "no_annotate": req.no_annotate,
        "video_files": [str(f) for f in video_files],
    }

    # Run processing in background
    asyncio.create_task(_run_processing(job_id))

    return {"job_id": job_id, "status": "queued", "total_videos": len(video_files)}


@app.get("/api/processing/jobs")
async def get_jobs():
    """List all processing jobs."""
    return {"jobs": [
        {k: v for k, v in j.items() if k != "video_files"}
        for j in jobs.values()
    ]}


@app.get("/api/processing/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job's status."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    j = jobs[job_id]
    return {k: v for k, v in j.items() if k != "video_files"}


@app.post("/api/processing/cancel/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    if jobs[job_id]["status"] in ("queued", "running"):
        jobs[job_id]["status"] = "cancelled"
    return {"status": "cancelled"}


@app.post("/api/processing/clear-completed")
async def clear_completed():
    """Remove completed jobs from the list."""
    to_remove = [jid for jid, j in jobs.items() if j["status"] in ("completed", "failed", "cancelled")]
    for jid in to_remove:
        del jobs[jid]
    return {"cleared": len(to_remove)}


# ─── Data endpoints (for Embedding Workbench) ───

@app.get("/api/faces/flagged")
async def get_flagged_faces(details: bool = False):
    """Return flagged faces (stub — returns empty for now)."""
    return {"flagged_faces": []}


@app.get("/api/system/status")
async def system_status():
    """Health check."""
    return {"status": "online", "mode": "local"}


# ─── Background processing ───

async def _run_processing(job_id: str):
    """Run the video processing pipeline in a background task."""
    import sys
    sys.path.insert(0, "src")

    job = jobs[job_id]
    job["status"] = "running"
    job["started_at"] = _now_ts()

    try:
        from process_video import VideoProcessingPipeline

        pipeline = VideoProcessingPipeline(CONFIG_PATH, enable_upload=False, local_only=True)
        pipeline.initialize_database()

        video_files = job["video_files"]

        for i, video_path in enumerate(video_files):
            if job["status"] == "cancelled":
                break

            video_path = Path(video_path)
            job["current_video"] = video_path.name
            job["progress"] = int((i / len(video_files)) * 100)

            logger.info(f"[{job_id}] Processing {i+1}/{len(video_files)}: {video_path.name}")

            try:
                await asyncio.to_thread(
                    pipeline.process_video,
                    video_path,
                    video_path.stem,
                    job["no_annotate"],
                )
                job["videos_processed"] = i + 1
            except Exception as e:
                logger.error(f"[{job_id}] Failed on {video_path.name}: {e}")
                # Continue with next video

        if job["status"] != "cancelled":
            job["status"] = "completed"
            job["progress"] = 100

    except Exception as e:
        logger.error(f"[{job_id}] Processing failed: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
    finally:
        job["completed_at"] = _now_ts()
        job["current_video"] = None


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    import time
    return time.time() * 1000


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
