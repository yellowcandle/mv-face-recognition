#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Run the MV pipeline stages on Hugging Face Jobs.

Data lives in the bucket mounted at /mnt/data:

    inputs/contestant_info.csv
    manifest/{videos,photos}.json
    videos/source/<id>/<sha>.mp4        (existing, written by scripts/hf/stage_sources.py)
    photos/reference/<id>/<sha>.jpg     (existing)
    models/home/.insightface/models/buffalo_l/   (uploaded once)
    models/reference/                   (stage cache writes the npz+manifest here)
    output/<video_id>/...               (stage video writes metadata + renditions here)

Stages:

    python hf_pipeline.py cache
    python hf_pipeline.py video --video-id 1

The repository is downloaded as a tarball from the hf-jobs branch, so the branch must be
pushed before submitting a job. Nothing here writes to the local checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

BUCKET = Path(os.environ.get("BUCKET_MOUNT", "/mnt/data"))
WORK = Path(os.environ.get("JOB_WORK", "/work"))
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
REPO_SLUG = os.environ.get("REPO_SLUG", "yellowcandle/mv-face-recognition")
REPO_REF = os.environ.get("REPO_REF", "main")

# HOME must be writable and executable (uv installs a Python under it). The InsightFace
# weights live in the bucket, so ~/.insightface is symlinked to the mount instead.
ENV = {
    **os.environ,
    "HOME": "/tmp/home",
    "INSIGHTFACE_PROVIDERS": os.environ.get(
        "INSIGHTFACE_PROVIDERS", "CPUExecutionProvider"
    ),
    "UV_CACHE_DIR": "/tmp/uv-cache",
}

# A CUDA provider that cannot load degrades to CPU silently. Build a one-node model and ask the
# session which provider it actually got, so a misconfigured GPU run dies instead of billing.
GPU_CHECK = """
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper

graph = helper.make_graph(
    [helper.make_node("Identity", ["x"], ["y"])],
    "gpu-check",
    [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
    [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
)
model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
# `onnx` writes the newest IR it knows; onnxruntime-gpu 1.22 refuses anything above 10.
model.ir_version = 10
print("onnxruntime providers available:", ort.get_available_providers(), flush=True)
session = ort.InferenceSession(model.SerializeToString(), providers=["CUDAExecutionProvider"])
active = session.get_providers()
print("onnxruntime providers:", active, flush=True)
if "CUDAExecutionProvider" not in active:
    raise SystemExit(f"CUDAExecutionProvider unavailable; ONNX Runtime chose {active}")
"""


def prepare_home() -> None:
    home = Path(ENV["HOME"])
    home.mkdir(parents=True, exist_ok=True)
    target = BUCKET / "models/home/.insightface"
    link = home / ".insightface"
    if target.exists() and not link.exists():
        link.symlink_to(target)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=ENV, check=True)


def fetch_repo() -> Path:
    repo = WORK / "repo"
    if repo.exists():
        return repo
    WORK.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{REPO_SLUG}/archive/{REPO_REF}.tar.gz"
    archive = WORK / "repo.tar.gz"
    print(f"downloading {url}", flush=True)
    urllib.request.urlretrieve(url, archive)
    with tarfile.open(archive) as tar:
        tar.extractall(WORK)
    extracted = next(p for p in WORK.iterdir() if p.is_dir() and p.name.startswith("mv-face-recognition-"))
    extracted.rename(repo)
    return repo


def install(repo: Path) -> Path:
    mvp = repo / "mvp-processor"
    run(["uv", "sync", "--frozen"], cwd=mvp)
    python = mvp / ".venv/bin/python"
    if os.environ.get("ONNXRUNTIME_GPU") == "1":
        # The lock carries CPU onnxruntime, which shadows the GPU wheel (same module name).
        # 1.31 targets CUDA 13; the torch wheels in this venv are CUDA 12.8 + cuDNN 9, so pin
        # the CUDA-12 build (1.22) and expose the nvidia wheels to the loader.
        run(["uv", "pip", "uninstall", "--python", str(python), "onnxruntime"], cwd=mvp)
        run(
            ["uv", "pip", "install", "--python", str(python), "onnxruntime-gpu==1.22.0"],
            cwd=mvp,
        )
        nvidia = mvp / ".venv/lib/python3.12/site-packages/nvidia"
        lib_dirs = [str(path) for path in sorted(nvidia.glob("*/lib"))]
        if lib_dirs:
            existing = ENV.get("LD_LIBRARY_PATH", "")
            ENV["LD_LIBRARY_PATH"] = ":".join(lib_dirs + ([existing] if existing else ""))
        # ONNX Runtime falls back to CPU without failing when CUDA cannot initialise, which
        # bills GPU hours at CPU speed (#86). Create one real session and stop if it did.
        run([str(python), "-c", GPU_CHECK], cwd=mvp)
    return python


def stage_common(repo: Path) -> None:
    """Contestant CSV plus the curated reference cache for the recognition stage."""
    source = repo / "source"
    (source / "photo/contestants").mkdir(parents=True, exist_ok=True)
    shutil.copy(BUCKET / "inputs/contestant_info.csv", source / "contestant_info.csv")
    for name in ("reference_embeddings.npz", "reference_manifest.json"):
        shutil.copy(BUCKET / "models/reference" / name, source / "photo/contestants" / name)


def stage_photos() -> Path:
    photos = WORK / "photos"
    if photos.exists():
        return photos
    manifest = json.loads((BUCKET / "manifest/photos.json").read_text())
    count = 0
    for contestant_id, entries in manifest.items():
        target = photos / f"contestant_{contestant_id}"
        target.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            shutil.copy(BUCKET / entry["key"], target / Path(entry["original_name"]).name)
            count += 1

    # Older appearances add reference diversity. Synced as photos/historical/<id>/*.jpg.
    historical = BUCKET / "photos/historical"
    if historical.is_dir():
        for directory in sorted(p for p in historical.iterdir() if p.is_dir()):
            cid = directory.name.removeprefix("contestant_")
            if not cid.isdigit():
                continue
            target = photos / f"contestant_{cid}"
            target.mkdir(parents=True, exist_ok=True)
            for photo in sorted(directory.iterdir()):
                if photo.suffix.lower() in IMAGE_SUFFIXES:
                    shutil.copy(photo, target / photo.name)
                    count += 1

    print(f"staged {count} photos for {len(manifest)} contestants", flush=True)
    return photos


def stage_video(video_id: str) -> Path:
    manifest = json.loads((BUCKET / "manifest/videos.json").read_text())
    if video_id not in manifest:
        raise SystemExit(f"unknown video id {video_id!r}; known: {sorted(manifest)}")
    entry = manifest[video_id]
    videos = WORK / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    target = videos / Path(entry["original_name"]).name
    if not target.exists():
        shutil.copy(BUCKET / entry["key"], target)
    return target


def cache_stage() -> None:
    prepare_home()
    repo = fetch_repo()
    python = install(repo)
    photos = stage_photos()
    out = BUCKET / "models/reference"
    out.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(python),
            "scripts/build_reference_cache.py",
            "--photos",
            str(photos),
            "--out",
            str(out),
        ],
        cwd=repo / "mvp-processor",
    )


def video_stage(video_id: str) -> None:
    prepare_home()
    repo = fetch_repo()
    python = install(repo)
    stage_common(repo)
    video = stage_video(video_id)
    out = BUCKET / "output" / video_id
    run(
        [
            str(python),
            "src/process_video.py",
            "-i",
            str(video),
            "--local-only",
            "--no-upload",
            "--output-dir",
            str(out),
            *(["--metadata-only"] if os.environ.get("METADATA_ONLY") == "1" else []),
        ],
        cwd=repo / "mvp-processor",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("cache", help="rebuild the reference embedding cache from the bucket photos")
    video = sub.add_parser("video", help="detect, recognize and render one source video")
    video.add_argument("--video-id", required=True)
    args = parser.parse_args()

    if args.stage == "cache":
        cache_stage()
    else:
        video_stage(args.video_id)


if __name__ == "__main__":
    main()
