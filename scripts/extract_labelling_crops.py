#!/usr/bin/env python3
"""Pre-extract one JPEG face crop per detection so the labelling UI reads crops from disk.

Usage (from repo root):
    mvp-processor/.venv/bin/python scripts/extract_labelling_crops.py test-video-mv2

Writes local_output/labelling/crops/{video_id}/{frame_number}_{detection_index}.jpg and an
index.json. Re-runnable: every run rewrites all crops and the index from current metadata.
Crops come from mvp-processor/src/local_api.py:_build_frame_crops, imported, not copied, so the
margin (25% per side), rendition choice (1080p > 720p > source) and decode (ffmpeg seek by
timestamp) stay identical to the /api/faces/crop endpoint.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 160


def main(video_id: str) -> int:
    # local_api resolves every path relative to mvp-processor/, so run from there.
    os.chdir(ROOT / "mvp-processor")
    sys.path.insert(0, str(ROOT / "mvp-processor" / "src"))
    import local_api

    meta = json.loads((ROOT / "local_output/metadata" / f"{video_id}_metadata.json").read_text())
    out_dir = ROOT / "local_output/labelling/crops" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"rendition: {local_api._rendition_for(video_id)}")

    entries, failures = [], []
    frames = sorted(meta["frame_data"], key=lambda f: f["frame_number"])
    for frame in frames:
        n = frame["frame_number"]
        try:
            crops = local_api._build_frame_crops(video_id, frame, WIDTH)
        except Exception as e:  # HTTPException from decode failures
            crops = [b""] * len(frame.get("detections", []))
            reason = getattr(e, "detail", str(e))
        else:
            reason = "empty crop (bbox outside frame or encode failed)"
        for i, (det, jpg) in enumerate(zip(frame.get("detections", []), crops)):
            name = f"{n}_{i}.jpg"
            path = out_dir / name
            if not jpg:
                path.unlink(missing_ok=True)  # never leave a stale crop from an earlier run
                failures.append(f"frame {n} detection {i}: {reason}")
                continue
            path.write_bytes(jpg)
            entries.append({"frame_number": n, "detection_index": i, "file": name, "bbox": det["bbox"]})

    total = sum(len(f.get("detections", [])) for f in frames)
    index = {
        "video_id": video_id,
        "source": {"processing_date": meta["video_info"]["processing_date"]},
        "detections": total,
        "entries": entries,
    }
    (out_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"{len(entries)}/{total} crops written to {out_dir}")
    for f in failures:
        print(f"FAILED {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: extract_labelling_crops.py <video_id>")
    sys.exit(main(sys.argv[1]))
