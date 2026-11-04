"""`/api/faces/detect` stops returning a frame once its faces have left the shot."""

import asyncio
import json
import sys

import pytest

sys.path.insert(0, "mvp-processor")

from src import local_api


def frame(number: int, timestamp: float) -> dict:
    return {
        "frame_number": number,
        "timestamp": timestamp,
        "detections": [{"bbox": [0.1, 0.2, 0.3, 0.4], "contestant_id": "1"}],
    }


def write_reel(tmp_path, monkeypatch, frames: list[dict]) -> None:
    path = tmp_path / "reel.json"
    path.write_text(json.dumps({"frame_data": frames}), encoding="utf-8")
    monkeypatch.setattr(local_api, "_metadata_path", lambda _video_id: path)


def faces_at(timestamp: float) -> list[dict]:
    return asyncio.run(local_api.detect_faces_at_timestamp("reel", timestamp))["faces"]


@pytest.mark.parametrize(
    ("timestamp", "count"),
    [(14.8, 1), (15, 0), (18, 0), (24.9, 0), (25, 1), (1, 0)],
)
def test_faces_only_hold_for_their_own_sample(tmp_path, monkeypatch, timestamp, count):
    # Sampled every 0.16s; frames with no faces aren't stored, so the next one is 10s away.
    frames = [frame(90, 14.4), frame(91, 14.56), frame(92, 14.72), frame(150, 25)]
    write_reel(tmp_path, monkeypatch, frames)
    assert len(faces_at(timestamp)) == count


def test_a_single_frame_reel_has_no_gap_to_measure(tmp_path, monkeypatch):
    write_reel(tmp_path, monkeypatch, [frame(1, 3)])
    assert len(faces_at(9)) == 1
