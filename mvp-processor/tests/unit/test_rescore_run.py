"""Re-scoring applies the pipeline's rule, and label outcomes count the right tracks."""

import importlib.util
from collections import Counter
from pathlib import Path

import numpy as np

_path = Path(__file__).resolve().parents[2] / "scripts/rescore_run.py"
_spec = importlib.util.spec_from_file_location("rescore_run", _path)
rescore_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rescore_run)

BOX = [0.1, 0.1, 0.2, 0.2]


def det(track, cid=None):
    return {"tracker_id": track, "bbox": BOX, "contestant_id": cid, "match_score": None}


def test_rescore_accepts_above_threshold_then_fills_the_track():
    doc = {
        "frame_data": [
            {"frame_number": n, "detections": [det(7)]} for n in (0, 1, 2)
        ]
    }
    embeddings = {
        "frame_number": np.array([0, 1, 2]),
        "detection_index": np.array([0, 0, 0]),
        # cosine 1.0, 1.0 and 0.0 against the only reference
        "embeddings": np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
    }
    rescore_run.rescore(doc, embeddings, np.array([[1.0, 0.0]]), np.array(["5"]), 0.4)
    dets = [f["detections"][0] for f in doc["frame_data"]]
    assert [d["contestant_id"] for d in dets] == ["5", "5", "5"]
    assert dets[2]["match_source"] == "track"
    assert dets[0]["match_score"] == 1.0


def test_score_labels_outcomes():
    old = [{"frame_number": n, "detections": [det(n)]} for n in range(5)]
    new_ids = ["1", "2", None, "3", None]
    new = [
        {"frame_number": n, "detections": [det(100 + n, cid)]} for n, cid in enumerate(new_ids)
    ]
    labels = [
        {"tracker_id": 0, "verdict": "contestant", "contestant_id": "1"},
        {"tracker_id": 1, "verdict": "contestant", "contestant_id": "9"},
        {"tracker_id": 2, "verdict": "contestant", "contestant_id": "4"},
        {"tracker_id": 3, "verdict": "not_a_contestant"},
        {"tracker_id": 4, "verdict": "not_a_contestant"},
        {"tracker_id": 4, "verdict": "unsure"},
    ]
    out = rescore_run.score_labels(labels, old, new)
    assert out == Counter(
        right=1, misnamed=1, missed=1, impostor=1, rejected=1,
        boxes_right=1, boxes_wrong=1, boxes_none=1,
        stranger_boxes_named=1, stranger_boxes_none=1,
    )
