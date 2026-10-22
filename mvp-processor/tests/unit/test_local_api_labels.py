"""
The track labels store: one verdict per `tracker_id`, pinned to a metadata run.

`labels/v2` exists because the tracker now links a face across frames: one human answer covers
a whole track, and untracked detections (`tracker_id < 0`) are not labelable. These tests pin
the properties that make a label set honest:

  - what you save is what you load back, track for track;
  - only tracker ids that exist in the current metadata can be labelled, once each;
  - verdict/contestant rules are enforced before anything is written;
  - a v2 file whose `source` does not match the metadata fails loudly with a 409;
  - a legacy `labels/v1` file is reported with `legacy_ignored` and left byte-for-byte intact.

Everything runs against a synthetic metadata file in `tmp_path`, so the suite is deterministic
and never touches the real `local_output/` labels.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "mvp-processor")

from fastapi import HTTPException  # noqa: E402

from src import local_api  # noqa: E402

VIDEO_ID = "synthetic-mv"
PROCESSING_DATE = "2026-10-22T00:00:00"


def synthetic_metadata() -> dict:
    """Two tracks plus two untracked detections (negative and missing tracker_id)."""
    return {
        "video_info": {
            "filename": f"{VIDEO_ID}.mp4",
            "fps": 25.0,
            "frame_count": 3,
            "width": 640,
            "height": 360,
            "duration": 0.12,
            "processing_date": PROCESSING_DATE,
        },
        "frame_data": [
            {
                "frame_number": 1,
                "timestamp": 0.04,
                "detections": [
                    {
                        "tracker_id": 3,
                        "contestant_id": "38",
                        "contestant_name": "沈貞巧",
                        "contestant_nickname": "Gao",
                        "match_score": 0.61,
                        "det_score": 0.9,
                        "bbox": [0.1, 0.1, 0.2, 0.2],
                    },
                    {
                        "tracker_id": -1,
                        "contestant_id": None,
                        "contestant_name": None,
                        "contestant_nickname": None,
                        "match_score": None,
                        "det_score": 0.7,
                        "bbox": [0.3, 0.1, 0.4, 0.2],
                    },
                    {
                        "tracker_id": None,
                        "contestant_id": None,
                        "contestant_name": None,
                        "contestant_nickname": None,
                        "match_score": None,
                        "det_score": 0.6,
                        "bbox": [0.5, 0.1, 0.6, 0.2],
                    },
                ],
            },
            {
                "frame_number": 2,
                "timestamp": 0.08,
                "detections": [
                    {
                        "tracker_id": 3,
                        "contestant_id": "38",
                        "contestant_name": "沈貞巧",
                        "contestant_nickname": "Gao",
                        "match_score": 0.58,
                        "det_score": 0.8,
                        "bbox": [0.12, 0.1, 0.22, 0.2],
                    },
                    {
                        "tracker_id": 5,
                        "contestant_id": "21",
                        "contestant_name": "謝裕鈴",
                        "contestant_nickname": "Ling",
                        "match_score": 0.72,
                        "det_score": 0.85,
                        "bbox": [0.7, 0.1, 0.8, 0.2],
                    },
                ],
            },
            {
                "frame_number": 5,
                "timestamp": 0.2,
                "detections": [
                    {
                        "tracker_id": 5,
                        "contestant_id": "21",
                        "contestant_name": "謝裕鈴",
                        "contestant_nickname": "Ling",
                        "match_score": 0.55,
                        "det_score": 0.75,
                        "bbox": [0.72, 0.1, 0.82, 0.2],
                    }
                ],
            },
        ],
    }


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Point the module at an isolated metadata file, roster and labels directory."""
    metadata_dir = tmp_path / "metadata"
    labels_dir = tmp_path / "labels"
    metadata_dir.mkdir()
    metadata = synthetic_metadata()
    (metadata_dir / f"{VIDEO_ID}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )
    contestants = tmp_path / "contestant_info.csv"
    contestants.write_text(
        "編號,姓名,暱稱,年齡\n38,沈貞巧,Gao,23\n21,謝裕鈴,Ling,24\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(local_api, "METADATA_DIR", metadata_dir)
    monkeypatch.setattr(local_api, "LABELS_DIR", labels_dir)
    monkeypatch.setattr(local_api, "CONTESTANT_CSV", contestants)
    local_api._json_cache.clear()
    yield {
        "video_id": VIDEO_ID,
        "metadata": metadata,
        "labels_dir": labels_dir,
        "labels_path": labels_dir / f"{VIDEO_ID}_labels.json",
    }
    local_api._json_cache.clear()


def run(coro):
    return asyncio.run(coro)


def label(tracker_id: int, verdict: str, contestant_id: str | None = None):
    return local_api.LabelRecord(
        tracker_id=tracker_id, verdict=verdict, contestant_id=contestant_id
    )


def assert_rejected(video_id: str, payload, status: int, fragment: str) -> None:
    with pytest.raises(HTTPException) as err:
        run(local_api.put_labels(video_id, payload))
    assert err.value.status_code == status
    assert fragment in err.value.detail


def test_empty_labels_when_none_exist_yet(api):
    loaded = run(local_api.get_labels(api["video_id"]))

    assert loaded["schema"] == "labels/v2"
    assert loaded["labels"] == []
    assert loaded["labelled_at"] is None
    assert loaded["legacy_ignored"] is False
    # …and it already carries the current run, so the client can label without another trip.
    assert loaded["source"] == {
        "processing_date": PROCESSING_DATE,
        "detections": 6,
    }
    assert not api["labels_path"].exists()


def test_put_get_round_trip(api):
    payload = local_api.LabelsPayload(
        source=local_api._metadata_source(api["metadata"]),
        labels=[
            label(3, "contestant", "38"),
            label(5, "not_a_contestant"),
        ],
    )

    saved = run(local_api.put_labels(api["video_id"], payload))
    assert saved["saved"] is True
    assert saved["count"] == 2
    assert Path(saved["path"]) == api["labels_path"]

    on_disk = json.loads(api["labels_path"].read_text(encoding="utf-8"))
    assert on_disk["schema"] == "labels/v2"
    assert on_disk["source"] == {"processing_date": PROCESSING_DATE, "detections": 6}
    assert on_disk["labels"] == [
        {"tracker_id": 3, "verdict": "contestant", "contestant_id": "38"},
        {"tracker_id": 5, "verdict": "not_a_contestant"},
    ]
    assert all("frame_number" not in entry for entry in on_disk["labels"])

    loaded = run(local_api.get_labels(api["video_id"]))
    assert loaded["schema"] == "labels/v2"
    assert loaded["legacy_ignored"] is False
    assert loaded["labels"] == on_disk["labels"]
    assert loaded["labelled_at"] == on_disk["labelled_at"]
    assert loaded["source"] == on_disk["source"]


def test_duplicate_tracker_is_rejected(api):
    payload = local_api.LabelsPayload(
        source=local_api._metadata_source(api["metadata"]),
        labels=[label(3, "not_a_contestant"), label(3, "unsure")],
    )
    assert_rejected(api["video_id"], payload, 400, "Duplicate label for track 3")
    assert not api["labels_path"].exists()


@pytest.mark.parametrize(
    "tracker_id,fragment",
    [
        (999, "No track 999"),
        (-1, "is untracked"),
    ],
)
def test_unknown_trackers_are_rejected(api, tracker_id, fragment):
    payload = local_api.LabelsPayload(
        source=local_api._metadata_source(api["metadata"]),
        labels=[label(tracker_id, "not_a_contestant")],
    )
    assert_rejected(api["video_id"], payload, 400, fragment)
    assert not api["labels_path"].exists()


@pytest.mark.parametrize(
    "record,fragment",
    [
        (label(3, "probably"), "Unknown verdict"),
        (label(3, "contestant"), "needs a contestant_id"),
        (label(3, "contestant", "999"), "Unknown contestant"),
        (label(3, "not_a_contestant", "38"), "must not carry a contestant_id"),
        (label(3, "unsure", "38"), "must not carry a contestant_id"),
    ],
)
def test_verdict_rules_are_enforced(api, record, fragment):
    payload = local_api.LabelsPayload(
        source=local_api._metadata_source(api["metadata"]),
        labels=[record],
    )
    assert_rejected(api["video_id"], payload, 400, fragment)
    assert not api["labels_path"].exists(), "a rejected payload must not touch the file"


def test_legacy_v1_get_is_ignored_and_left_untouched(api):
    legacy = {
        "schema": "labels/v1",
        "video_id": api["video_id"],
        "labelled_at": "2026-01-01T00:00:00",
        "source": {"processing_date": PROCESSING_DATE, "detections": 6},
        "labels": [
            {"frame_number": 1, "detection_index": 0, "verdict": "not_a_contestant"}
        ],
    }
    legacy_path = api["labels_path"]
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    before = legacy_path.read_bytes()

    loaded = run(local_api.get_labels(api["video_id"]))

    assert loaded["schema"] == "labels/v2"
    assert loaded["labels"] == []
    assert loaded["labelled_at"] is None
    assert loaded["legacy_ignored"] is True
    assert "labels/v1" in loaded["legacy_detail"]
    assert "left untouched" in loaded["legacy_detail"]
    assert loaded["source"] == {"processing_date": PROCESSING_DATE, "detections": 6}
    assert legacy_path.read_bytes() == before, "GET must not rewrite the legacy file"

    # A second read is still a read: no 409, no migration, no bytes changed.
    again = run(local_api.get_labels(api["video_id"]))
    assert again["legacy_ignored"] is True
    assert legacy_path.read_bytes() == before


def test_v2_from_a_different_run_is_refused(api):
    data = api["metadata"]
    stale_source = {"processing_date": "2000-01-01T00:00:00", "detections": 123}
    assert stale_source != local_api._metadata_source(data)

    api["labels_path"].parent.mkdir(parents=True)
    api["labels_path"].write_text(
        json.dumps(
            {
                "schema": "labels/v2",
                "video_id": api["video_id"],
                "labelled_at": "2000-01-01T00:00:00",
                "source": stale_source,
                "labels": [{"tracker_id": 3, "verdict": "not_a_contestant"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as err:
        run(local_api.get_labels(api["video_id"]))
    assert err.value.status_code == 409
    assert "different metadata run" in err.value.detail

    with pytest.raises(HTTPException) as err:
        run(
            local_api.put_labels(
                api["video_id"],
                local_api.LabelsPayload(
                    source=stale_source,
                    labels=[label(3, "not_a_contestant")],
                ),
            )
        )
    assert err.value.status_code == 409


def test_list_labels_counts_v2_tracks_and_zeroes_legacy(api):
    run(
        local_api.put_labels(
            api["video_id"],
            local_api.LabelsPayload(
                source=local_api._metadata_source(api["metadata"]),
                labels=[label(3, "contestant", "38")],
            ),
        )
    )
    (api["labels_dir"] / "old-video_labels.json").write_text(
        json.dumps(
            {
                "schema": "labels/v1",
                "video_id": "old-video",
                "labelled_at": "2026-01-01T00:00:00",
                "source": {"processing_date": "2026-01-01T00:00:00", "detections": 2},
                "labels": [
                    {"frame_number": 1, "detection_index": 0, "verdict": "unsure"},
                    {"frame_number": 1, "detection_index": 1, "verdict": "unsure"},
                ],
            }
        ),
        encoding="utf-8",
    )

    listed = {entry["video_id"]: entry for entry in run(local_api.list_labels())["labels"]}
    assert listed[api["video_id"]]["schema"] == "labels/v2"
    assert listed[api["video_id"]]["count"] == 1
    assert listed[api["video_id"]]["legacy_ignored"] is False
    assert listed["old-video"]["schema"] == "labels/v1"
    assert listed["old-video"]["count"] == 0
    assert listed["old-video"]["legacy_ignored"] is True
