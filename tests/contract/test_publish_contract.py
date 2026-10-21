"""The read model the Worker serves must satisfy the contract its consumers read.

`scripts/publish/build_read_model.py` normalises three metadata generations (legacy
`frame_results`, `frame_data[].detections`, `recognitions[]`) into one payload. These
tests run the real normaliser over every reel on disk, so a contract regression — a
missing id/duration/recognition_rate, a bad bbox — fails here instead of rendering
blank in the viewer.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "build_read_model", REPO / "scripts/publish/build_read_model.py"
)
assert _SPEC is not None and _SPEC.loader is not None
model = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(model)


def local_reels() -> list[str]:
    paths = glob.glob(os.path.join(model.LEGACY_FMT, "*_annotated_dense_metadata.json"))
    paths += glob.glob(os.path.join(model.NEW_FMT, "*.json"))
    return [p for p in paths if model.video_id_from(p) is not None]


def test_every_reel_on_disk_satisfies_the_contract() -> None:
    reels = local_reels()
    assert reels, "no metadata sources found"
    by_nick, by_name = model.load_contestants()
    for path in reels:
        vid = model.video_id_from(path)
        assert vid is not None, path
        payload = model.normalise(path, by_nick, by_name)
        assert model.validate_payload(vid, payload) == [], path


def test_normalise_backfills_the_fields_consumers_read(tmp_path: Path) -> None:
    doc: dict[str, Any] = {
        "video_info": {"fps": 25.0, "frame_count": 250, "width": 100, "height": 100},
        "frame_data": [
            {
                "frame_number": 0,
                "timestamp": 0.0,
                "detections_count": 1,
                "recognitions_count": 1,
                "detections": [
                    {
                        "contestant_id": "33",
                        "contestant_name": "黃敏蕎",
                        "contestant_nickname": "阿妹",
                        "match_score": 0.5,
                        "det_score": 0.93,
                        "bbox": [0.1, 0.1, 0.2, 0.2],
                        "tracker_id": None,
                    }
                ],
            }
        ],
        # The stale shape reel 5 shipped: no band_cutoffs, no acceptance_threshold.
        "recognition_config": {"tolerance": 0.68, "min_confidence": 0.5},
    }
    path = tmp_path / "33-test_metadata.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    by_nick, by_name = model.load_contestants()
    payload = model.normalise(str(path), by_nick, by_name)

    assert payload["video_info"]["duration"] == 10.0
    assert payload["processing_summary"]["recognition_rate"] == 1.0
    assert payload["contestant_timeline"]["33"]["contestant_info"]["id"] == "33"
    assert payload["recognition_config"]["band_cutoffs"] == {
        "high": 0.585,
        "medium": 0.451,
    }
    assert model.validate_payload("33", payload) == []


def test_validation_rejects_a_payload_missing_the_backfilled_fields() -> None:
    payload: dict[str, Any] = {
        "video_info": {},
        "processing_summary": {"frames_processed": 1},
        "contestant_timeline": {
            "33": {"contestant_info": {"name": "x", "nickname": "y"}}
        },
        "frame_data": [
            {"frame_number": 0, "timestamp": 0.0, "detections_count": 0, "detections": []}
        ],
    }

    problems = model.validate_payload("33", payload)

    assert any("duration" in p for p in problems), problems
    assert any("recognition_rate" in p for p in problems), problems
    assert any("contestant_info.id" in p for p in problems), problems
