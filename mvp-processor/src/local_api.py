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
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


def _safe_child(base: Path, name: str) -> Path:
    """Resolve `name` under `base` and reject traversal or absolute paths."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "Invalid name")
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise HTTPException(400, "Path escapes base directory")
    return candidate

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MV Face Recognition Local API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Paths (run from mvp-processor/, see module docstring) ───

SOURCE_DIR = Path("../source/videos")
OUTPUT_DIR = Path("../local_output")
METADATA_DIR = OUTPUT_DIR / "metadata"
PROCESSED_DIR = OUTPUT_DIR / "processed_videos"
FLAGS_PATH = OUTPUT_DIR / "flagged_faces.json"
PHOTOS_DIR = Path("../source/photo/contestants/photos")
EMBEDDINGS_DIR = Path("../source/photo/contestants")
CONTESTANT_CSV = Path("../metadata/contestant_info.csv")
CONFIG_PATH = "config/processing_config.yaml"

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv")

# ─── In-memory job store ───

jobs: dict[str, dict] = {}


class ProcessRequest(BaseModel):
    video: Optional[str] = None  # specific video filename, or None for all
    no_annotate: bool = False


class FlagRequest(BaseModel):
    contestant_id: int
    video_id: str
    timestamp: float
    bbox: Optional[list[float]] = None  # [x1, y1, x2, y2]
    confidence: Optional[float] = None
    user_label: Optional[str] = None
    thumbnail: Optional[str] = None  # base64 JPEG


class FlagStatusUpdate(BaseModel):
    status: str  # pending | accepted | rejected


class FlagReassign(BaseModel):
    face_id: str
    contestant_id: int


# ─── Cached JSON loading (metadata files are re-read often during playback) ───

_json_cache: dict[str, tuple[float, dict]] = {}


def _load_json_cached(path: Path) -> dict:
    """Load a JSON file, cached by mtime."""
    key = str(path)
    mtime = path.stat().st_mtime
    hit = _json_cache.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _json_cache[key] = (mtime, data)
    return data


def _metadata_path(video_id: str) -> Path:
    return _safe_child(METADATA_DIR, f"{video_id}_metadata.json")


def _iter_metadata_files():
    """Yield (video_id, path) for each plain metadata file in METADATA_DIR."""
    if not METADATA_DIR.exists():
        return
    for f in sorted(METADATA_DIR.glob("*_metadata.json")):
        if "_dense_" in f.name or "_annotated_" in f.name:
            continue
        yield f.stem[: -len("_metadata")], f


# ─── Video listing ───

@app.get("/api/videos/local")
async def list_local_videos():
    """List all video files in source/videos/."""
    if not SOURCE_DIR.exists():
        return {"videos": []}

    videos = []
    for f in sorted(SOURCE_DIR.iterdir()):
        if f.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
            })
    return {"videos": videos}


@app.get("/api/videos/processed/list")
async def list_processed_videos():
    """List processed videos from local_output/metadata/."""
    videos = []
    for name, path in _iter_metadata_files():
        try:
            data = _load_json_cached(path)
        except (json.JSONDecodeError, OSError):
            continue
        vi = data.get("video_info", {})
        source_file = SOURCE_DIR / f"{name}.mp4"
        videos.append({
            "id": name,
            "name": name,
            "stream_url": f"/api/videos/stream/{name}",
            "filename": source_file.name if source_file.exists() else None,
            "duration": vi.get("duration", 0),
            "width": vi.get("width", 0),
            "height": vi.get("height", 0),
        })
    return videos


@app.get("/api/videos/stream/{video_id}")
async def stream_video(video_id: str):
    """Stream a processed video (FileResponse handles HTTP Range)."""
    candidates = [
        _safe_child(PROCESSED_DIR, f"{video_id}_1080p.mp4"),
        _safe_child(PROCESSED_DIR, f"{video_id}_720p.mp4"),
        _safe_child(PROCESSED_DIR, f"{video_id}_annotated.mp4"),
    ] + [_safe_child(SOURCE_DIR, f"{video_id}{ext}") for ext in VIDEO_EXTENSIONS]

    for path in candidates:
        if path.exists():
            return FileResponse(path, media_type="video/mp4")
    raise HTTPException(404, f"No video file found for {video_id}")


@app.get("/api/contestants")
async def list_contestants():
    """List contestants from CSV, with embedding availability."""
    import csv
    if not CONTESTANT_CSV.exists():
        return []

    contestants = []
    with open(CONTESTANT_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nickname = row["暱稱"].strip()
            has_embedding = (EMBEDDINGS_DIR / f"{nickname}_embedding.npy").exists()
            contestants.append({
                "id": row["編號"].strip(),
                "number": int(row["編號"].strip()),
                "name": row["姓名"].strip(),
                "nickname": nickname,
                "age": int(row["年齡"]) if row.get("年齡", "").strip() else None,
                "has_embedding": has_embedding,
                "quality": "good" if has_embedding else "missing",
            })
    return contestants


@app.get("/api/contestants/{contestant_id}/photo")
async def contestant_photo(contestant_id: int):
    """Serve a reference photo for a contestant."""
    photo_dir = PHOTOS_DIR / f"contestant_{contestant_id}"
    if photo_dir.is_dir():
        for photo in sorted(photo_dir.iterdir()):
            if photo.suffix.lower() in (".jpg", ".jpeg", ".png"):
                media_type = "image/png" if photo.suffix.lower() == ".png" else "image/jpeg"
                return FileResponse(photo, media_type=media_type)
    raise HTTPException(404, f"No photo for contestant {contestant_id}")


# ─── Processing ───

@app.post("/api/processing/trigger")
async def trigger_processing(req: ProcessRequest):
    """Start a local video processing job."""
    job_id = str(uuid.uuid4())[:8]

    if req.video:
        video_path = _safe_child(SOURCE_DIR, req.video)
        if video_path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise HTTPException(400, f"Unsupported video format: {req.video}")
        if not video_path.exists():
            raise HTTPException(404, f"Video not found: {req.video}")
        video_files = [video_path]
    else:
        if not SOURCE_DIR.exists():
            raise HTTPException(404, "No source/videos directory")
        video_files = sorted(
            f for f in SOURCE_DIR.iterdir()
            if f.suffix.lower() in VIDEO_EXTENSIONS
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


# ─── Metadata / face data ───

@app.get("/api/videos/metadata/dense/{video_id}")
async def get_dense_metadata(video_id: str):
    """Return full dense metadata JSON for a processed video."""
    meta_path = _metadata_path(video_id)
    if not meta_path.exists():
        raise HTTPException(404, f"Metadata not found for {video_id}")
    return _load_json_cached(meta_path)


@app.get("/api/faces/detect")
async def detect_faces_at_timestamp(video_id: str, timestamp: float = 0):
    """Return faces at a given timestamp from pre-computed metadata.

    Floor matching: returns the most recent frame at or before the timestamp,
    so boxes never appear ahead of the face (same convention as the annotator).
    """
    import bisect

    meta_path = _metadata_path(video_id)
    if not meta_path.exists():
        return {"faces": []}
    data = _load_json_cached(meta_path)
    frame_data = data.get("frame_data", [])
    if not frame_data:
        return {"faces": []}

    frames = sorted(frame_data, key=lambda fd: fd["timestamp"])
    timestamps = [fd["timestamp"] for fd in frames]
    idx = bisect.bisect_right(timestamps, timestamp)
    if idx == 0:
        return {"faces": []}
    frame = frames[idx - 1]

    faces = []
    for r in frame.get("recognitions", []):
        top, right, bottom, left = r["face_location"]
        faces.append({
            "bbox": [left, top, right, bottom],
            "confidence": r["confidence"],
            "contestant_name": r["contestant_nickname"],
            "contestant_id": r.get("contestant_id"),
            "contestant_nickname": r["contestant_nickname"],
            "detection_confidence": r["confidence"],
            "recognition_confidence": r["confidence"],
            "matched": True,
        })
    return {"faces": faces}


@app.get("/api/recognition/results")
async def recognition_results(contestant_id: str, video_id: Optional[str] = None):
    """Appearances of a contestant, across all videos or within one."""
    if video_id is not None:
        targets = [(video_id, _metadata_path(video_id))]
    else:
        targets = list(_iter_metadata_files())

    results = []
    for vid, path in targets:
        if not path.exists():
            continue
        try:
            data = _load_json_cached(path)
        except (json.JSONDecodeError, OSError):
            continue
        entry = data.get("contestant_timeline", {}).get(str(contestant_id))
        if not entry:
            continue
        for appearance in entry.get("appearances", []):
            results.append({
                "video_id": vid,
                "timestamp": appearance.get("timestamp", 0),
                "confidence": appearance.get("confidence", 0),
                "frame_number": appearance.get("frame_number"),
            })

    results.sort(key=lambda r: (r["video_id"], r["timestamp"]))
    return {"results": results}


# ─── Face flagging (persisted to local_output/flagged_faces.json) ───

_flags_lock = asyncio.Lock()


def _load_flags() -> list[dict]:
    if not FLAGS_PATH.exists():
        return []
    try:
        with open(FLAGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read %s — starting with empty flag list", FLAGS_PATH)
        return []


def _save_flags(flags: list[dict]) -> None:
    FLAGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = FLAGS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(flags, f, ensure_ascii=False, indent=2)
    tmp.replace(FLAGS_PATH)


@app.post("/api/faces/flag")
async def flag_face(req: FlagRequest):
    """Flag a face for review."""
    record = {
        "id": uuid.uuid4().hex[:12],
        "contestant_id": req.contestant_id,
        "video_id": req.video_id,
        "timestamp": req.timestamp,
        "confidence": req.confidence if req.confidence is not None else 0,
        "bbox": req.bbox,
        "status": "pending",
        "user_label": req.user_label,
        "thumbnail": req.thumbnail,
        "created_at": _now(),
    }
    async with _flags_lock:
        flags = _load_flags()
        flags.append(record)
        _save_flags(flags)
    return record


@app.get("/api/faces/flagged")
async def get_flagged_faces(details: bool = False):
    """Return flagged faces; thumbnails only when details=true."""
    flags = _load_flags()
    if not details:
        flags = [{k: v for k, v in f.items() if k != "thumbnail"} for f in flags]
    return {"flagged_faces": flags}


@app.patch("/api/faces/flagged/{face_id}")
async def update_flag_status(face_id: str, req: FlagStatusUpdate):
    """Accept or reject a flagged face."""
    if req.status not in ("pending", "accepted", "rejected"):
        raise HTTPException(400, f"Invalid status: {req.status}")
    async with _flags_lock:
        flags = _load_flags()
        for f in flags:
            if f["id"] == face_id:
                f["status"] = req.status
                _save_flags(flags)
                return f
    raise HTTPException(404, "Flagged face not found")


@app.delete("/api/faces/flagged/{face_id}")
async def delete_flagged_face(face_id: str):
    """Remove a flagged face."""
    async with _flags_lock:
        flags = _load_flags()
        remaining = [f for f in flags if f["id"] != face_id]
        if len(remaining) == len(flags):
            raise HTTPException(404, "Flagged face not found")
        _save_flags(remaining)
    return {"deleted": face_id}


@app.post("/api/faces/flag/update")
async def reassign_flagged_face(req: FlagReassign):
    """Reassign a flagged face to a different contestant."""
    async with _flags_lock:
        flags = _load_flags()
        for f in flags:
            if f["id"] == req.face_id:
                f["contestant_id"] = req.contestant_id
                f["status"] = "pending"
                _save_flags(flags)
                return f
    raise HTTPException(404, "Flagged face not found")


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
    # Bind to loopback only — endpoints are unauthenticated and accept paths
    # under SOURCE_DIR / metadata_dir. LAN exposure would be a path-traversal
    # vector. Override with `uvicorn ... --host 0.0.0.0` if you've added auth.
    uvicorn.run(app, host="127.0.0.1", port=8000)
