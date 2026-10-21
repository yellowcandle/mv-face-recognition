#!/usr/bin/env python3
"""Submit the HF Jobs pipeline without the CLI's script-upload step.

`hf jobs uv run` first syncs the script to the jobs-artifacts bucket, which a token with
`job.write` but not bucket-write cannot do. `hf jobs run` also mangles a multi-word `bash -lc`
command, so the command list is built here and passed through the Python API.

Usage:
    uv run --with "huggingface_hub>=1.8" python scripts/hf/jobs/submit.py
    ... --ref <commit> --bucket yellowcandle/mv-face-recognition --flavor cpu-upgrade
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from huggingface_hub import Volume, run_job

IMAGE = "ghcr.io/astral-sh/uv:python3.12-bookworm"
GPU_IMAGE = "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime"
APT = "apt-get update -qq && apt-get install -y -qq libgl1 libglib2.0-0"


def submit(
    bucket: str,
    ref: str,
    flavor: str,
    timeout: str,
    name: str,
    args: list[str],
    *,
    gpu: bool = False,
    metadata_only: bool = False,
) -> str:
    url = (
        f"https://raw.githubusercontent.com/yellowcandle/mv-face-recognition/{ref}"
        "/scripts/hf/jobs/hf_pipeline.py"
    )
    setup = APT + (" build-essential" if gpu else "") + (" && pip install -q uv" if gpu else "")
    command = (
        f"{setup} && "
        f"python -c \"import urllib.request; urllib.request.urlretrieve('{url}','/tmp/j.py')\" && "
        f"python /tmp/j.py {' '.join(args)}"
    )
    job = run_job(
        image=GPU_IMAGE if gpu else IMAGE,
        command=["bash", "-lc", command],
        flavor=flavor,
        timeout=timeout,
        name=name,
        env={
            "REPO_REF": ref,
            **({"ONNXRUNTIME_GPU": "1", "INSIGHTFACE_PROVIDERS": "CUDAExecutionProvider"} if gpu else {}),
            **({"METADATA_ONLY": "1"} if metadata_only else {}),
        },
        volumes=[Volume(type="bucket", source=bucket, mount_path="/mnt/data")],
    )
    print(f"{name}: {job.id}", flush=True)
    return job.id


def wait(job_id: str) -> None:
    subprocess.run(["hf", "jobs", "wait", job_id], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default="yellowcandle/mv-face-recognition")
    parser.add_argument("--ref", default="main", help="branch, tag or commit both the job script and the repo download")
    parser.add_argument("--flavor", default=None, help="default: cpu-upgrade, or a10g-small with --gpu")
    parser.add_argument("--gpu", action="store_true", help="CUDA image + onnxruntime-gpu (CUDA 12)")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="skip rendition transcoding (pair with a CPU runner or existing videos)",
    )
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument("--only", type=int, action="append", help="restrict to these video ids")
    args = parser.parse_args()

    flavor = args.flavor or ("a10g-small" if args.gpu else "cpu-upgrade")
    if not args.skip_cache:
        cache = submit(
            args.bucket, args.ref, flavor, "45m", "mv-cache", ["cache"], gpu=args.gpu
        )
        wait(cache)

    ids = args.only or [1, 2, 3, 4, 5]
    jobs = [
        submit(
            args.bucket,
            args.ref,
            flavor,
            "3h",
            f"mv-video-{i}",
            ["video", "--video-id", str(i)],
            gpu=args.gpu,
            metadata_only=args.metadata_only,
        )
        for i in ids
    ]
    if len(jobs) == 1:
        wait(jobs[0])
    else:
        for job in jobs:
            wait(job)
    print(f"outputs: hf://buckets/{args.bucket}/output/")


if __name__ == "__main__":
    sys.exit(main())
