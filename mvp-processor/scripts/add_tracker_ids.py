"""Replay stored detections through ByteTrack and add tracker_id.

Tracker ids link the same face across frames in a shot. Re-running detection is unnecessary:
ByteTrack is deterministic given the boxes and confidence, so replaying each metadata file's
detections in order reproduces the ids the pipeline would have written (the approach validated
in docs/wayfinder/tickets/017).

    python scripts/add_tracker_ids.py ../local_output/metadata
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import supervision as sv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from process_video import _create_tracker  # noqa: E402


def add_ids(path: Path, frame_rate: float) -> tuple[int, int]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    info = doc["video_info"]
    width, height = float(info["width"]), float(info["height"])
    tracker = _create_tracker(int(frame_rate))

    tracked_count = 0
    for frame in doc.get("frame_data", []):
        detections = frame.get("detections") or []
        if not detections:
            continue
        boxes = np.array(
            [
                [
                    det["bbox"][0] * width,
                    det["bbox"][1] * height,
                    det["bbox"][2] * width,
                    det["bbox"][3] * height,
                ]
                for det in detections
            ],
            dtype=np.float32,
        )
        confidence = np.array([det["det_score"] for det in detections], dtype=np.float32)
        tracked = tracker.update(sv.Detections(xyxy=boxes, confidence=confidence))
        by_box = {tuple(np.round(box, 3)): i for i, box in enumerate(boxes)}
        for det in detections:
            det["tracker_id"] = -1
        track_ids = tracked.tracker_id if tracked.tracker_id is not None else []
        for box, track_id in zip(tracked.xyxy, track_ids):
            index = by_box.get(tuple(np.round(box, 3)))
            if index is not None:
                detections[index]["tracker_id"] = int(track_id)
                if int(track_id) != -1:
                    tracked_count += 1

    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return tracked_count, sum(len(f.get("detections") or []) for f in doc.get("frame_data", []))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata_dir", type=Path)
    parser.add_argument("--frame-rate", type=float, default=6.0)
    args = parser.parse_args()

    for path in sorted(args.metadata_dir.glob("*_metadata.json")):
        if not path.name[0].isdigit():
            continue
        tracked, total = add_ids(path, args.frame_rate)
        print(f"{path.name[:2]}: {tracked}/{total} tracked")


if __name__ == "__main__":
    main()
