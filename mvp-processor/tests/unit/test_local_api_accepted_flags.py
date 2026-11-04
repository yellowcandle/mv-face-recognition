"""Accepted flags are overlaid at read time, the same way the Worker does it.

Stored metadata, including the cached dict, is untouched: re-pending a flag undoes it.
"""

import asyncio
import copy
import json
import sys

import pytest

sys.path.insert(0, "mvp-processor")

from src import local_api

BOX_A = [0.1, 0.2, 0.3, 0.4]
BOX_B = [0.5, 0.6, 0.7, 0.8]


def unmatched(bbox: list[float], tracker_id: int = 7) -> dict:
    return {
        "tracker_id": tracker_id,
        "match_source": None,
        "contestant_id": None,
        "contestant_name": None,
        "contestant_nickname": None,
        "match_score": None,
        "det_score": 0.81,
        "bbox": bbox,
    }


def recognised(bbox: list[float], contestant_id: str, score: float) -> dict:
    return {
        **unmatched(bbox, 8),
        "match_source": "frame",
        "contestant_id": contestant_id,
        "contestant_name": f"名{contestant_id}",
        "contestant_nickname": f"Nick{contestant_id}",
        "match_score": score,
    }


STORED = {
    "processing_summary": {
        "frames_processed": 3,
        "total_faces_detected": 5,
        "total_recognitions": 3,
        "unique_contestants": 2,
        "recognition_rate": 0.6,
    },
    "contestant_timeline": {
        "2": {
            "contestant_info": {"id": "2", "name": "名2", "nickname": "Nick2"},
            "appearances": [
                {"timestamp": 10.32, "frame_number": 62, "match_score": 0.6, "bbox": BOX_A}
            ],
            "total_appearances": 1,
            "average_match_score": 0.6,
            "max_match_score": 0.6,
            "first_appearance": 10.32,
            "last_appearance": 10.32,
        },
        "5": {
            "contestant_info": {"id": "5", "name": "名5", "nickname": "Nick5"},
            "appearances": [
                {"timestamp": 10, "frame_number": 60, "match_score": 0.5, "bbox": BOX_B},
                {"timestamp": 10.32, "frame_number": 62, "match_score": 0.7, "bbox": BOX_B},
            ],
            "total_appearances": 2,
            "average_match_score": 0.6,
            "max_match_score": 0.7,
            "first_appearance": 10,
            "last_appearance": 10.32,
        },
    },
    "frame_data": [
        {
            "frame_number": 60,
            "timestamp": 10,
            "detections_count": 2,
            "recognitions_count": 1,
            "detections": [unmatched(BOX_A), recognised(BOX_B, "5", 0.5)],
        },
        # Same track, same box a frame later: a flag covers one detection, never the track.
        {
            "frame_number": 61,
            "timestamp": 10.16,
            "detections_count": 1,
            "recognitions_count": 0,
            "detections": [unmatched(BOX_A)],
        },
        {
            "frame_number": 62,
            "timestamp": 10.32,
            "detections_count": 2,
            "recognitions_count": 2,
            "detections": [recognised(BOX_B, "5", 0.7), recognised(BOX_A, "2", 0.6)],
        },
    ],
}


def flag(**overrides) -> dict:
    return {
        "id": "f1",
        "contestant_id": 1,
        "video_id": "reel",
        "timestamp": 10.03,
        "confidence": 0,
        "bbox": BOX_A,
        "status": "accepted",
        "user_label": "SECRET-LABEL",
        "thumbnail": "SECRET-THUMB",
        "created_at": "2026-10-01T00:00:00+00:00",
        **overrides,
    }


@pytest.fixture
def reel(tmp_path, monkeypatch):
    """Point the API at a temp reel, flag file and roster; returns the flag writer."""
    meta_dir = tmp_path / "metadata"
    meta_dir.mkdir()
    (meta_dir / "reel_metadata.json").write_text(json.dumps(STORED), encoding="utf-8")
    roster = tmp_path / "roster.csv"
    roster.write_text(
        "編號,姓名,暱稱,年齡\n1,蘇雅琳,Ivy So,20\n2,黃雅慧,咖喱,27\n", encoding="utf-8"
    )
    flags_path = tmp_path / "flagged_faces.json"
    monkeypatch.setattr(local_api, "METADATA_DIR", meta_dir)
    monkeypatch.setattr(local_api, "CONTESTANT_CSV", roster)
    monkeypatch.setattr(local_api, "FLAGS_PATH", flags_path)
    local_api._json_cache.clear()

    def write_flags(*flags: dict) -> None:
        flags_path.write_text(json.dumps(list(flags)), encoding="utf-8")

    return write_flags


def dense(video_id: str = "reel") -> dict:
    return asyncio.run(local_api.get_dense_metadata(video_id))


def faces_at(timestamp: float, video_id: str = "reel") -> list[dict]:
    return asyncio.run(local_api.detect_faces_at_timestamp(video_id, timestamp))["faces"]


def face(metadata: dict, frame: int = 0, detection: int = 0) -> dict:
    return metadata["frame_data"][frame]["detections"][detection]


def test_accepted_flag_turns_unmatched_into_the_contestant_in_both_reads(reel):
    reel(flag())
    expected = {
        "contestant_id": "1",
        "contestant_name": "蘇雅琳",
        "contestant_nickname": "Ivy So",
        "matched": True,
        "match_source": "flag",
        "match_score": None,
        "det_score": 0.81,
        "tracker_id": 7,
        "bbox": BOX_A,
    }
    assert face(dense()) == expected
    faces = faces_at(10.03)
    assert faces[0] == expected
    assert faces[1]["contestant_id"] == "5" and faces[1]["match_score"] == 0.5


def test_a_flag_covers_one_detection_not_the_track(reel):
    reel(flag())
    assert face(dense(), 1)["contestant_id"] is None
    assert faces_at(10.16)[0]["contestant_id"] is None


def test_a_recognition_flagged_as_someone_else_loses_its_cosine(reel):
    reel(flag(contestant_id=2, bbox=BOX_B))
    corrected = face(dense(), 0, 1)
    assert corrected["contestant_nickname"] == "咖喱"
    assert corrected["match_score"] is None
    assert corrected["match_source"] == "flag"


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "pending"},
        {"status": "rejected"},
        {"video_id": "another-reel"},
        {"bbox": None},
        {"bbox": [0.1, 0.2, 0.3]},
        {"bbox": [0.1, 0.2, 0.3, 0.401]},
        {"contestant_id": 95},  # not on the roster
        {"timestamp": 9},  # before any frame
        {"timestamp": None},
    ],
)
def test_flags_that_do_not_apply_change_nothing(reel, overrides):
    reel(flag(**overrides))
    assert dense() == STORED
    assert faces_at(10.03)[0]["contestant_id"] is None


def test_bbox_equality_has_float_slack(reel):
    reel(flag(bbox=[0.1 + 1e-7, 0.2, 0.3, 0.4 - 1e-7]))
    assert face(dense())["contestant_id"] == "1"


def test_a_flag_lands_on_the_floor_frame_only(reel):
    reel(flag(timestamp=10.2))
    later = dense()
    assert face(later, 1)["contestant_id"] == "1"
    assert face(later, 0)["contestant_id"] is None
    reel(flag(timestamp=10))
    assert face(dense())["contestant_id"] == "1"


@pytest.mark.parametrize("newest_first", [True, False])
def test_the_newest_accepted_flag_wins_in_any_stored_order(reel, newest_first):
    older = flag(id="a", contestant_id=2, created_at="2026-10-01T00:00:00+00:00")
    newer = flag(id="b", contestant_id=1, created_at="2026-10-02T00:00:00+00:00")
    reel(*([newer, older] if newest_first else [older, newer]))
    assert face(dense())["contestant_id"] == "1"
    assert faces_at(10.03)[0]["contestant_id"] == "1"


def test_private_flag_fields_never_reach_a_read(reel):
    reel(flag())
    assert "SECRET" not in json.dumps(dense())
    assert "SECRET" not in json.dumps(faces_at(10.03))


def results(contestant: str, video_id: str | None = "reel") -> list[dict]:
    return asyncio.run(local_api.recognition_results(contestant, video_id))["results"]


def test_a_flag_on_an_unrecognised_face_adds_an_appearance_and_removes_none(reel):
    reel(flag())
    metadata = dense()
    timeline = metadata["contestant_timeline"]
    assert timeline["1"] == {
        "contestant_info": {"id": "1", "name": "蘇雅琳", "nickname": "Ivy So"},
        "appearances": [
            {
                "timestamp": 10,
                "frame_number": 60,
                "match_score": None,
                "bbox": BOX_A,
                "match_source": "flag",
            }
        ],
        "total_appearances": 1,
        "average_match_score": None,
        "max_match_score": None,
        "first_appearance": 10,
        "last_appearance": 10,
    }
    assert timeline["5"] == STORED["contestant_timeline"]["5"]
    assert timeline["2"] == STORED["contestant_timeline"]["2"]
    summary = metadata["processing_summary"]
    assert summary["total_recognitions"] == 4
    assert summary["unique_contestants"] == 3
    assert summary["recognition_rate"] == 0.8
    assert metadata["frame_data"][0]["recognitions_count"] == 2
    assert metadata["frame_data"][1]["recognitions_count"] == 0


def test_a_flag_on_a_recognition_moves_that_appearance(reel):
    reel(flag(contestant_id=2, bbox=BOX_B))
    metadata = dense()
    timeline = metadata["contestant_timeline"]

    # The old contestant is recounted from what remains: only the 0.7 at 10.32.
    assert timeline["5"]["total_appearances"] == 1
    assert timeline["5"]["average_match_score"] == 0.7
    assert timeline["5"]["max_match_score"] == 0.7
    assert timeline["5"]["first_appearance"] == 10.32

    # The new one's average skips the null rather than counting it as 0, and stays time-ordered.
    assert timeline["2"]["total_appearances"] == 2
    assert timeline["2"]["average_match_score"] == 0.6
    assert timeline["2"]["first_appearance"] == 10
    assert timeline["2"]["last_appearance"] == 10.32
    assert [a["match_score"] for a in timeline["2"]["appearances"]] == [None, 0.6]

    # A recognition stayed a recognition.
    assert metadata["processing_summary"]["total_recognitions"] == 3
    assert metadata["processing_summary"]["unique_contestants"] == 2
    assert metadata["frame_data"][0]["recognitions_count"] == 1


def test_a_contestant_left_with_no_appearances_leaves_the_timeline(reel):
    reel(
        flag(id="a", contestant_id=1, bbox=BOX_B),
        flag(id="b", contestant_id=1, bbox=BOX_B, timestamp=10.33),
    )
    metadata = dense()
    assert "5" not in metadata["contestant_timeline"]
    assert metadata["contestant_timeline"]["1"]["total_appearances"] == 2
    assert metadata["processing_summary"]["unique_contestants"] == 2


def test_results_follow_the_moved_appearance(reel):
    reel(flag(contestant_id=2, bbox=BOX_B))
    assert [r["timestamp"] for r in results("5")] == [10.32]
    moved, own = results("2")
    assert moved == {
        "video_id": "reel",
        "timestamp": 10,
        "match_score": None,
        "match_source": "flag",
        "frame_number": 60,
        "bbox": BOX_B,
        "detection_index": 1,
    }
    assert own["match_score"] == 0.6
    assert "match_source" not in own


def test_results_find_a_contestant_only_a_flag_names_and_leak_nothing(reel):
    reel(flag())
    found = results("1", None)
    assert [r["match_score"] for r in found] == [None]
    assert "SECRET" not in json.dumps(found)


def test_stored_metadata_stays_as_it_was_and_undo_works(reel):
    reel(flag())
    before = copy.deepcopy(local_api._load_json_cached(local_api._metadata_path("reel")))
    dense()
    faces_at(10.03)
    results("1")
    assert local_api._load_json_cached(local_api._metadata_path("reel")) == before

    reel(flag(status="pending"))
    assert dense() == STORED


def test_a_bare_number_id_reaches_flags_filed_on_the_full_stem(reel, tmp_path):
    (tmp_path / "metadata" / "4-long-title_metadata.json").write_text(
        json.dumps(STORED), encoding="utf-8"
    )
    reel(flag(video_id="4-long-title"))
    assert face(dense("4"))["contestant_id"] == "1"


def test_the_staleness_limit_still_holds_for_a_flagged_frame(reel):
    reel(flag(timestamp=10.2))
    assert len(faces_at(10.2)) == 1
    assert faces_at(12) == []
