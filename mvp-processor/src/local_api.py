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
from functools import lru_cache
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
LABELS_DIR = OUTPUT_DIR / "labels"
PHOTOS_DIR = Path("../source/photo/contestants/ig_photos")
EMBEDDINGS_DIR = Path("../source/photo/contestants")
REFERENCE_MANIFEST = EMBEDDINGS_DIR / "reference_manifest.json"
CONTESTANT_CSV = Path("../metadata/contestant_info.csv")
CONFIG_PATH = "config/processing_config.yaml"

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv")

# ─── In-memory job store ───

jobs: dict[str, dict] = {}


class ProcessRequest(BaseModel):
    video: Optional[str] = None  # specific video filename, or None for all


class FlagRequest(BaseModel):
    contestant_id: int
    video_id: str
    timestamp: float
    bbox: Optional[list[float]] = None  # [x1, y1, x2, y2]
    confidence: Optional[float] = None
    user_label: Optional[str] = None
    thumbnail: Optional[str] = None  # base64 JPEG


class LabelRecord(BaseModel):
    tracker_id: int  # ByteTrack id within a shot; one label covers the whole track
    verdict: str  # contestant | not_a_contestant | unsure | box_wrong
    contestant_id: Optional[str] = None
    note: Optional[str] = None


class LabelsPayload(BaseModel):
    source: dict  # {processing_date, detections} of the metadata run these labels describe
    labels: list[LabelRecord] = []


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
    """Exact `<id>_metadata.json`; a bare digits id also resolves the full stem.

    The published contract keys `metadata_<video_id>` by the id `processed_videos_list`
    serves ("4-極限拍MV"), while the local files carry their verbatim stem
    ("4-《全民造星IV》…"), so the locally served API accepts both forms. Only digit ids
    are glob-resolved, so nothing else becomes a pattern.
    """
    exact = _safe_child(METADATA_DIR, f"{video_id}_metadata.json")
    if exact.exists():
        return exact
    if video_id.isdigit() and METADATA_DIR.exists():
        for path in sorted(METADATA_DIR.glob(f"{video_id}-*_metadata.json")):
            return path
    return exact


def _iter_metadata_files():
    """Yield (video_id, path) for each plain metadata file in METADATA_DIR."""
    if not METADATA_DIR.exists():
        return
    for f in sorted(METADATA_DIR.glob("*_metadata.json")):
        if "_dense_" in f.name:
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
    stems = [video_id]
    if video_id.isdigit():
        source = _metadata_path(video_id)
        if source.name.endswith("_metadata.json"):
            stems.append(source.name[: -len("_metadata.json")])
    candidates = []
    for stem in stems:
        candidates += [
            _safe_child(PROCESSED_DIR, f"{stem}_1080p.mp4"),
            _safe_child(PROCESSED_DIR, f"{stem}_720p.mp4"),
            *(_safe_child(SOURCE_DIR, f"{stem}{ext}") for ext in VIDEO_EXTENSIONS),
        ]

    for path in candidates:
        if path.exists():
            return FileResponse(path, media_type="video/mp4")
    raise HTTPException(404, f"No video file found for {video_id}")


@lru_cache(maxsize=1)
def _references_per_contestant() -> dict[str, int]:
    """Reference-photo counts from the embedding-cache manifest, keyed by contestant number.

    Read once per process; the manifest only changes when the cache is rebuilt.
    """
    try:
        manifest = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
        return manifest["references_per_contestant"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        logger.warning(f"Cannot read {REFERENCE_MANIFEST} ({e}); reporting 0 references for all")
        return {}


@app.get("/api/contestants")
async def list_contestants():
    """List contestants from CSV, with reference-embedding availability."""
    import csv
    if not CONTESTANT_CSV.exists():
        return []

    counts = _references_per_contestant()
    contestants = []
    with open(CONTESTANT_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            contestant_id = row["編號"].strip()
            reference_count = int(counts.get(contestant_id, 0))
            contestants.append({
                "id": contestant_id,
                "number": int(contestant_id),
                "name": row["姓名"].strip(),
                "nickname": row["暱稱"].strip(),
                "age": int(row["年齡"]) if row.get("年齡", "").strip() else None,
                "has_embedding": reference_count > 0,
                "reference_count": reference_count,
                "quality": "good" if reference_count else "missing",
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
    for detection in frame.get("detections", []):
        contestant_id = detection.get("contestant_id")
        faces.append({
            "bbox": detection["bbox"],
            "tracker_id": detection.get("tracker_id"),
            "match_source": detection.get("match_source"),
            "match_score": detection.get("match_score"),
            "det_score": detection.get("det_score"),
            "contestant_name": detection.get("contestant_name"),
            "contestant_id": contestant_id,
            "contestant_nickname": detection.get("contestant_nickname"),
            "matched": contestant_id is not None,
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
                "match_score": appearance.get("match_score"),
                "frame_number": appearance.get("frame_number"),
            })

    results.sort(key=lambda r: (r["video_id"], r["timestamp"]))
    return {"results": results}


# ─── Ground-truth labels (local_output/labels/<video_id>_labels.json) ───
#
# A label is a verdict on one *track* — a face linked across frames by `tracker_id` — so one
# human answer covers every frame the track appears in. Detections with `tracker_id < 0` were
# never tracked and cannot be labelled. Flags are a separate thing entirely (a human-proposed
# correction with a review lifecycle); labels are the answer, and they live in their own file.
#
# `labels/v2` replaced the per-detection `labels/v1` format. v1 keys (frame_number +
# detection_index) cannot be mapped to a track reliably, so a v1 file is reported and left
# untouched rather than guessed at.

VERDICTS = ("contestant", "not_a_contestant", "unsure", "box_wrong")
LABELS_SCHEMA = "labels/v2"

_labels_lock = asyncio.Lock()


def _labels_path(video_id: str) -> Path:
    return _safe_child(LABELS_DIR, f"{video_id}_labels.json")


def _metadata_source(data: dict) -> dict:
    """The identity of a metadata run: what a label set was made against.

    A reprocess can renumber tracks and re-score their detections, so labels from a previous run
    must be refused rather than silently attached to whatever track now carries that id.
    """
    return {
        "processing_date": data.get("video_info", {}).get("processing_date"),
        "detections": sum(len(f.get("detections", [])) for f in data.get("frame_data", [])),
    }


def _current_metadata(video_id: str) -> tuple[Path, dict]:
    meta_path = _metadata_path(video_id)
    if not meta_path.exists():
        raise HTTPException(404, f"Metadata not found for {video_id}")
    return meta_path, _load_json_cached(meta_path)


def _contestant_ids() -> set[str]:
    import csv
    if not CONTESTANT_CSV.exists():
        return set()
    with open(CONTESTANT_CSV, encoding="utf-8") as f:
        return {row["編號"].strip() for row in csv.DictReader(f)}


def _known_tracker_ids(data: dict) -> set[int]:
    """Every tracked id the current metadata can attach a label to."""
    trackers: set[int] = set()
    for frame in data.get("frame_data", []):
        for detection in frame.get("detections", []):
            tracker_id = detection.get("tracker_id")
            if isinstance(tracker_id, int) and not isinstance(tracker_id, bool) and tracker_id >= 0:
                trackers.add(tracker_id)
    return trackers


def _validate_labels(data: dict, labels: list[LabelRecord]) -> None:
    """Reject anything that does not point at a real track. Loud on purpose."""
    known_trackers = _known_tracker_ids(data)
    known_contestants = _contestant_ids()
    seen = set()

    for label in labels:
        if label.tracker_id in seen:
            raise HTTPException(400, f"Duplicate label for track {label.tracker_id}")
        seen.add(label.tracker_id)

        if label.tracker_id < 0:
            raise HTTPException(
                400,
                f"Track {label.tracker_id} is untracked; only tracker_id >= 0 can be labelled",
            )
        if label.tracker_id not in known_trackers:
            raise HTTPException(400, f"No track {label.tracker_id} in this video's metadata")
        if label.verdict not in VERDICTS:
            raise HTTPException(400, f"Unknown verdict {label.verdict!r}; expected one of {VERDICTS}")
        if label.verdict == "contestant":
            if not label.contestant_id:
                raise HTTPException(400, f"Track {label.tracker_id}: verdict 'contestant' needs a contestant_id")
            if known_contestants and label.contestant_id not in known_contestants:
                raise HTTPException(400, f"Unknown contestant {label.contestant_id!r}")
        elif label.contestant_id:
            raise HTTPException(
                400,
                f"Track {label.tracker_id}: verdict {label.verdict!r} must not carry a contestant_id",
            )


@app.get("/api/labels/{video_id}")
async def get_labels(video_id: str):
    """Labels for a video, or an empty set ready to label when none exist yet.

    A `labels/v1` file is reported as `legacy_ignored` with an empty v2 label set and is left
    untouched on disk: its frame/detection keys have no safe mapping onto tracker ids. A v2 file
    from a different metadata run is a 409 — the caller has to decide what to do about that, not
    the server.
    """
    _, data = _current_metadata(video_id)
    current = _metadata_source(data)
    path = _labels_path(video_id)
    empty = {
        "schema": LABELS_SCHEMA,
        "video_id": video_id,
        "labelled_at": None,
        "source": current,
        "labels": [],
        "legacy_ignored": False,
    }

    if not path.exists():
        return empty

    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(500, f"Could not read {path.name}: {e}")

    stored_schema = stored.get("schema")
    if stored_schema != LABELS_SCHEMA:
        return {
            **empty,
            "legacy_ignored": True,
            "legacy_detail": (
                f"{path.name} uses schema {stored_schema or 'unknown'} (per-detection "
                "frame_number/detection_index labels). It was ignored and left untouched: those "
                "keys cannot be mapped onto tracker ids. Re-label the tracks to write labels/v2."
            ),
        }

    stored_source = stored.get("source", {})
    if stored_source != current:
        raise HTTPException(
            409,
            f"Labels at {path.name} were made against a different metadata run "
            f"(labels: {stored_source}, current: {current}). They were not loaded: a reprocess "
            f"renumbers and re-scores detections, so the keys no longer mean the same tracks.",
        )

    return {**stored, "legacy_ignored": False}


@app.put("/api/labels/{video_id}")
async def put_labels(video_id: str, payload: LabelsPayload):
    """Replace a video's labels (one per track). Validated against the metadata, then written atomically."""
    _, data = _current_metadata(video_id)
    current = _metadata_source(data)

    if payload.source != current:
        raise HTTPException(
            409,
            f"Refusing labels for metadata run {payload.source}; the current run is {current}.",
        )

    _validate_labels(data, payload.labels)

    record = {
        "schema": LABELS_SCHEMA,
        "video_id": video_id,
        "labelled_at": _now(),
        "source": current,
        "labels": [
            {k: v for k, v in label.model_dump().items() if v is not None}
            for label in payload.labels
        ],
    }

    async with _labels_lock:
        LABELS_DIR.mkdir(parents=True, exist_ok=True)
        path = _labels_path(video_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    logger.info(f"Saved {len(record['labels'])} labels for {video_id}")
    return {"saved": True, "count": len(record["labels"]), "path": str(path)}


@app.get("/api/labels")
async def list_labels():
    """Which videos have v2 labels, and how many tracks each file labels.

    A v1 file is listed with `count: 0` and `legacy_ignored: true` so callers do not mistake its
    per-detection count for progress on the track contract.
    """
    out = []
    if LABELS_DIR.exists():
        for path in sorted(LABELS_DIR.glob("*_labels.json")):
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            schema = stored.get("schema")
            legacy = schema != LABELS_SCHEMA
            out.append({
                "video_id": stored.get("video_id", path.stem[: -len("_labels")]),
                "schema": schema,
                "count": 0 if legacy else len(stored.get("labels", [])),
                "labelled_at": stored.get("labelled_at"),
                "legacy_ignored": legacy,
            })
    return {"labels": out}


# ─── Face crops for labelling (decoded from the served rendition, on demand) ───

_crop_cache: dict[tuple[str, int], list[bytes]] = {}
_CROP_CACHE_MAX_FRAMES = 240


def _rendition_for(video_id: str) -> Path:
    """The rendered file to crop from, most preferred first."""
    for name in (f"{video_id}_1080p.mp4", f"{video_id}_720p.mp4"):
        candidate = _safe_child(PROCESSED_DIR, name)
        if candidate.exists():
            return candidate
    for ext in VIDEO_EXTENSIONS:
        candidate = _safe_child(SOURCE_DIR, f"{video_id}{ext}")
        if candidate.exists():
            return candidate
    raise HTTPException(404, f"No video file found for {video_id}")


def _build_frame_crops(video_id: str, frame: dict, width: int) -> list[bytes]:
    """Decode one frame of the rendition and crop every detection in it.

    Cropping here rather than in the browser keeps the one conversion — frame fractions to
    pixels — on the side that actually knows the decoded frame's dimensions.
    """
    import cv2
    import numpy as np
    import subprocess

    video = _rendition_for(video_id)
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(frame["timestamp"]), "-i", str(video),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise HTTPException(500, f"Could not decode {video.name} at {frame['timestamp']}s")

    image = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(500, "Decoded frame was empty")

    height, width_px = image.shape[:2]
    crops = []
    for detection in frame.get("detections", []):
        x1, y1, x2, y2 = detection["bbox"]
        pad_x, pad_y = (x2 - x1) * 0.25, (y2 - y1) * 0.25
        cx1, cy1 = int(max(0.0, x1 - pad_x) * width_px), int(max(0.0, y1 - pad_y) * height)
        cx2, cy2 = int(min(1.0, x2 + pad_x) * width_px), int(min(1.0, y2 + pad_y) * height)
        crop = image[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            crops.append(b"")
            continue
        scale = width / crop.shape[1]
        crop = cv2.resize(crop, (width, max(1, int(crop.shape[0] * scale))))
        ok, buffer = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
        crops.append(buffer.tobytes() if ok else b"")
    return crops


@app.get("/api/faces/crop")
async def face_crop(video_id: str, frame_number: int, detection_index: int = 0, width: int = 160):
    """One detection's face, as a JPEG crop of the served rendition.

    Cached per frame: a grid asks for crops in frame order, so each frame is decoded once and
    every detection in it comes from that decode.
    """
    from fastapi import Response

    if not 64 <= width <= 512:
        raise HTTPException(400, "width must be between 64 and 512")

    _, data = _current_metadata(video_id)
    frames = {f["frame_number"]: f for f in data.get("frame_data", [])}
    frame = frames.get(frame_number)
    if frame is None:
        raise HTTPException(404, f"No frame {frame_number} for {video_id}")
    if not 0 <= detection_index < len(frame.get("detections", [])):
        raise HTTPException(404, f"Frame {frame_number} has no detection {detection_index}")

    key = (video_id, frame_number)
    crops = _crop_cache.get(key)
    if crops is None:
        crops = await asyncio.to_thread(_build_frame_crops, video_id, frame, width)
        if len(_crop_cache) >= _CROP_CACHE_MAX_FRAMES:
            _crop_cache.pop(next(iter(_crop_cache)))
        _crop_cache[key] = crops

    image = crops[detection_index]
    if not image:
        raise HTTPException(500, "Crop was empty")
    return Response(content=image, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600"})


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
