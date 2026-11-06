"""A label only follows a track that survived whole, and never onto someone else's boxes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pytest  # noqa: E402
from carry_labels import carry, merge_labels  # noqa: E402

A, B = [0.1, 0.1, 0.2, 0.2], [0.5, 0.5, 0.6, 0.6]


def run(*frames):
    return {
        "frame_data": [
            {"frame_number": n, "detections": [{"tracker_id": t, "bbox": b} for t, b in dets]}
            for n, dets in enumerate(frames)
        ]
    }


def label(track, cid="1"):
    return {"tracker_id": track, "verdict": "contestant", "contestant_id": cid}


def test_renumbered_track_follows_its_boxes():
    carried, refused = carry([label(3)], run([(3, A)], [(3, A)]), run([(9, A)], [(9, A)]))
    assert carried == [{**label(3), "tracker_id": 9}] and refused == []


def test_split_track_is_refused():
    _, refused = carry([label(3)], run([(3, A)], [(3, A)]), run([(9, A)], [(8, A)]))
    assert refused[0]["reason"] == "track split or lost boxes in the new run"


def test_track_holding_another_tracks_boxes_is_refused():
    old = run([(3, A)], [(4, A)])
    _, refused = carry([label(3)], old, run([(9, A)], [(9, A)]))
    assert refused[0]["reason"] == "new track also holds another track's boxes"


def test_boxes_the_old_run_left_untracked_do_not_block():
    carried, _ = carry([label(3)], run([(3, A)], [(-1, A)]), run([(9, A)], [(9, A)]))
    assert carried[0]["tracker_id"] == 9


def test_disagreeing_labels_on_one_new_track_are_both_refused():
    old = run(*[[(3, A), (4, B)]] * 1)
    new = run([(9, A), (9, B)])
    carried, refused = carry([label(3, "1"), label(4, "2")], old, new)
    assert carried == [] and {r["tracker_id"] for r in refused} == {3, 4}


def test_merge_keeps_the_union_and_stops_on_a_conflict():
    assert {x["tracker_id"] for x in merge_labels([[label(1)], [label(1), label(2)]])} == {1, 2}
    with pytest.raises(SystemExit):
        merge_labels([[label(1, "1")], [label(1, "2")]])


def test_boxes_the_old_run_never_saw_do_not_dilute_extra():
    old = run([(3, A)], [(4, A)])
    new = run([(9, A)], [(9, A)], *[[(9, A)]] * 200)
    _, refused = carry([label(3)], old, new)
    assert refused[0]["reason"] == "new track also holds another track's boxes"


def test_agreeing_labels_on_one_new_track_are_listed_not_lost():
    untracked = [[(-1, A)]] * 18
    old = run([(3, A)], [(4, A)], *untracked)
    new = run(*[[(9, A)]] * 20)
    carried, refused = carry([label(3), label(4)], old, new)
    assert len(carried) == 1 and "merged" in refused[0]["reason"]


def test_none_means_untracked_in_either_run():
    carried, _ = carry([label(3)], run([(3, A)], [(None, A)]), run([(9, A)], [(9, A)]))
    assert carried[0]["tracker_id"] == 9
    _, refused = carry([label(3)], run([(3, A)]), run([(None, A)]))
    assert refused[0]["reason"] == "new run left it untracked"
