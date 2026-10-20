"""
The labels store: a round trip that survives save/load, and the refusals that keep a label set
honest.

Ticket 018's whole point is that `labels/v1` exists so ground truth can be computed against a
specific metadata run. These tests pin the two properties that make that true:

  - what you save is what you load back, verdict for verdict;
  - labels whose `source` does not match the metadata **do not load** — a reprocess renumbers and
    re-scores detections, so a stale set must fail loudly rather than attach verdicts to whatever
    box now occupies that index.

They run against the real endpoints with the real metadata on disk (no HTTP client: httpx is not
a dependency, and adding one to test an in-process function would be the wrong trade).
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "mvp-processor")

from fastapi import HTTPException  # noqa: E402

from src import local_api  # noqa: E402

VIDEO_ID = "test-video-mv2"
METADATA = Path("../local_output/metadata") / f"{VIDEO_ID}_metadata.json"

pytestmark = pytest.mark.skipif(
    not METADATA.exists(), reason=f"{METADATA} not present — reprocess a video first"
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def labels_path():
    return local_api._labels_path(VIDEO_ID)


@pytest.fixture
def clean_labels(labels_path):
    """No labels on disk before or after, so the real file is never clobbered by a test run."""
    backup = labels_path.read_text(encoding="utf-8") if labels_path.exists() else None
    if labels_path.exists():
        labels_path.unlink()
    yield labels_path
    if labels_path.exists():
        labels_path.unlink()
    if backup is not None:
        labels_path.write_text(backup, encoding="utf-8")


def first_two_detections():
    data = json.loads(METADATA.read_text(encoding="utf-8"))
    out = []
    for frame in data["frame_data"]:
        for index, detection in enumerate(frame["detections"]):
            out.append((frame["frame_number"], index, detection))
            if len(out) == 2:
                return data, out
    raise AssertionError("no detections in the metadata")


def test_round_trip_survives_save_and_load(clean_labels):
    data, detections = first_two_detections()
    claimed = detections[0][2].get("contestant_id")

    payload = local_api.LabelsPayload(
        source=local_api._metadata_source(data),
        labels=[
            local_api.LabelRecord(frame_number=detections[0][0], detection_index=detections[0][1],
                                  verdict="contestant", contestant_id=claimed),
            local_api.LabelRecord(frame_number=detections[1][0], detection_index=detections[1][1],
                                  verdict="not_a_contestant"),
        ],
    )

    saved = run(local_api.put_labels(VIDEO_ID, payload))
    assert saved["saved"] is True and saved["count"] == 2
    assert Path(saved["path"]).exists()

    # A fresh process must see the same thing: read what actually landed on disk.
    on_disk = json.loads(clean_labels.read_text(encoding="utf-8"))
    assert on_disk["schema"] == "labels/v1"
    assert on_disk["source"] == local_api._metadata_source(data)
    assert [(lab["frame_number"], lab["detection_index"], lab["verdict"]) for lab in on_disk["labels"]] == [
        (detections[0][0], detections[0][1], "contestant"),
        (detections[1][0], detections[1][1], "not_a_contestant"),
    ]

    loaded = run(local_api.get_labels(VIDEO_ID))
    assert loaded["labels"] == on_disk["labels"]
    assert loaded["labelled_at"] == on_disk["labelled_at"]


def test_empty_labels_when_none_exist_yet(clean_labels):
    loaded = run(local_api.get_labels(VIDEO_ID))
    assert loaded["labels"] == []
    assert loaded["labelled_at"] is None
    # …and it already carries the source, so the client can label without a second round trip.
    data = json.loads(METADATA.read_text(encoding="utf-8"))
    assert loaded["source"] == local_api._metadata_source(data)


def test_labels_from_a_different_run_are_refused(clean_labels):
    """The property a reprocess depends on."""
    data, detections = first_two_detections()
    stale_source = {"processing_date": "2000-01-01T00:00:00", "detections": 123}
    assert stale_source != local_api._metadata_source(data)

    clean_labels.write_text(json.dumps({
        "schema": "labels/v1", "video_id": VIDEO_ID, "labelled_at": "2000-01-01T00:00:00",
        "source": stale_source,
        "labels": [{"frame_number": detections[0][0], "detection_index": detections[0][1],
                    "verdict": "not_a_contestant"}],
    }), encoding="utf-8")

    with pytest.raises(HTTPException) as err:
        run(local_api.get_labels(VIDEO_ID))
    assert err.value.status_code == 409
    assert "different metadata run" in err.value.detail

    # And writing a set for a run that is not the current one is refused too.
    with pytest.raises(HTTPException) as err:
        run(local_api.put_labels(VIDEO_ID, local_api.LabelsPayload(
            source=stale_source,
            labels=[local_api.LabelRecord(frame_number=detections[0][0],
                                          detection_index=detections[0][1],
                                          verdict="not_a_contestant")],
        )))
    assert err.value.status_code == 409


@pytest.mark.parametrize("label,reason", [
    ({"frame_number": 99999, "detection_index": 0, "verdict": "not_a_contestant"}, "no such frame"),
    ({"frame_number": None, "detection_index": 9999, "verdict": "not_a_contestant"}, "no such detection"),
    ({"frame_number": None, "detection_index": 0, "verdict": "probably"}, "unknown verdict"),
    ({"frame_number": None, "detection_index": 0, "verdict": "contestant"}, "contestant without an id"),
    ({"frame_number": None, "detection_index": 0, "verdict": "not_a_contestant", "contestant_id": "33"},
     "a non-contestant verdict carrying an id"),
])
def test_invalid_labels_are_rejected(clean_labels, label, reason):
    data, detections = first_two_detections()
    frame_number = detections[0][0] if label["frame_number"] is None else label["frame_number"]
    body = dict(label, frame_number=frame_number)

    with pytest.raises(HTTPException) as err:
        run(local_api.put_labels(VIDEO_ID, local_api.LabelsPayload(
            source=local_api._metadata_source(data),
            labels=[local_api.LabelRecord(**body)],
        )))
    assert err.value.status_code == 400, reason
    assert not clean_labels.exists(), "a rejected payload must not touch the file"


def test_crop_endpoint_returns_a_face(clean_labels):
    """The labeller's crops come from the served rendition, cropped by the stored fractions."""
    _, detections = first_two_detections()
    frame_number, index, detection = detections[0]
    if detection.get("bbox") is None:
        pytest.skip("no bbox on the first detection")

    response = run(local_api.face_crop(VIDEO_ID, frame_number, index, 160))
    assert response.media_type == "image/jpeg"
    assert response.body[:2] == b"\xff\xd8", "not a JPEG"
    # A 160-wide crop of a face region, not a sliver and not the whole frame.
    assert 500 < len(response.body) < 40_000

    # Cached per frame: the second call must not decode again.
    cached = local_api._crop_cache[(VIDEO_ID, frame_number)]
    assert response.body in cached, "the served crop should be the cached one"


def test_crop_rejects_unknown_frames_and_bad_width(clean_labels):
    with pytest.raises(HTTPException) as err:
        run(local_api.face_crop(VIDEO_ID, 99999, 0, 160))
    assert err.value.status_code == 404

    with pytest.raises(HTTPException) as err:
        run(local_api.face_crop(VIDEO_ID, 0, 0, 4096))
    assert err.value.status_code == 400
