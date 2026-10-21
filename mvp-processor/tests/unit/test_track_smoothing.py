"""Track smoothing fills only clear, multi-frame track identities."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "track_smoothing",
    Path(__file__).resolve().parents[2] / "src" / "track_smoothing.py",
)
assert _SPEC is not None and _SPEC.loader is not None
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)


def detection(tracker_id: int, contestant_id=None, score=None) -> dict:
    return {
        "tracker_id": tracker_id,
        "contestant_id": contestant_id,
        "contestant_name": "Name" if contestant_id else None,
        "contestant_nickname": "Nick" if contestant_id else None,
        "match_score": score,
    }


def frames(*detections: dict) -> list[dict]:
    return [{"detections": [d]} for d in detections]


def test_fills_an_unmatched_frame_from_a_clear_track() -> None:
    data = frames(
        detection(3, "33", 0.5),
        detection(3, "33", 0.7),
        detection(3),
    )

    stats = module.smooth_track_identities(data)

    filled = data[2]["detections"][0]
    assert filled["contestant_id"] == "33"
    assert filled["match_source"] == "track"
    assert filled["match_score"] == 0.6
    assert stats["filled"] == 1
    assert data[2]["recognitions_count"] == 1


def test_does_not_overwrite_frame_level_matches() -> None:
    data = frames(detection(4, "1", 0.5), detection(4, "2", 0.6), detection(4))

    module.smooth_track_identities(data, dominance=0.5)

    assert data[0]["detections"][0]["contestant_id"] == "1"
    assert data[2]["detections"][0]["contestant_id"] == "1"


def test_requires_two_accepted_frames_and_a_majority() -> None:
    single = frames(detection(1, "33", 0.5), detection(1))
    module.smooth_track_identities(single)
    assert single[1]["detections"][0]["contestant_id"] is None

    split = frames(
        detection(2, "1", 0.5),
        detection(2, "2", 0.5),
        detection(2, "3", 0.5),
        detection(2),
    )
    module.smooth_track_identities(split)
    assert split[3]["detections"][0]["contestant_id"] is None


def test_untracked_detections_are_ignored() -> None:
    data = frames(detection(-1), detection(-1))

    stats = module.smooth_track_identities(data)

    assert stats["filled"] == 0
    assert all(d["detections"][0]["contestant_id"] is None for d in data)
