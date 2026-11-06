"""Carry a label set from the run it was made against onto a newer run of the same reel.

A label names a tracker id, and a reprocess can renumber tracks, so the Worker and local API refuse
labels from another run. This maps each labelled track by box (same frame, IoU >= 0.5) and writes
a label set bound to the new run, keeping only labels whose track survives whole:

  - coverage: share of the old track's boxes found on one new track
  - extra:    of the new track's boxes the old run also had, the share on a *different* old track.
              Boxes the old run left untracked don't count, since they carry no other identity.

Two labels landing on one new track are kept only when they agree. Anything refused is listed with
its reason so it can be labelled again by hand; nothing is guessed.

Labels can live in two stores (local file and Worker KV). Pass both to --labels: they must be tied
to the same run, and a track they disagree on stops the carry-over.

    python scripts/carry_labels.py --labels L.json [KV.json] --old OLD_metadata.json \
        --new NEW_metadata.json --out OUT_labels.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from rescore_run import is_tracked, pair_boxes, run_source

LABELS_SCHEMA = "labels/v2"
MIN_COVERAGE = 0.9
MAX_EXTRA = 0.1
LABELS_DISAGREE = "two labels disagree on one new track"


def label_identity(label: dict) -> tuple:
    """What a label says about its track."""
    return label["verdict"], label.get("contestant_id")


def merge_labels(label_sets: list[list[dict]]) -> list[dict]:
    """Union of label sets, or SystemExit listing every track they disagree on."""
    merged: dict[int, dict] = {}
    conflicts = []
    for labels in label_sets:
        for label in labels:
            first = merged.setdefault(label["tracker_id"], label)
            if label_identity(first) != label_identity(label):
                conflicts.append((first, label))
    if conflicts:
        raise SystemExit(f"Label stores disagree on {len(conflicts)} tracks: {conflicts}")
    return list(merged.values())


def carry(labels: list[dict], old: dict, new: dict) -> tuple[list[dict], list[dict]]:
    """Return (carried labels, refused labels each with a `reason`)."""
    old_track_size = Counter(d["tracker_id"] for f in old["frame_data"] for d in f["detections"])
    onto: dict[object, Counter] = defaultdict(Counter)  # old track -> new track -> shared boxes
    into: dict[object, Counter] = defaultdict(Counter)  # new track -> old track -> shared boxes
    for old_det, new_det in pair_boxes(old["frame_data"], new["frame_data"]):
        onto[old_det["tracker_id"]][new_det["tracker_id"]] += 1
        into[new_det["tracker_id"]][old_det["tracker_id"]] += 1

    kept: dict[int, dict] = {}
    disputed: set[int] = set()
    refused: list[dict] = []
    for label in labels:
        old_track = label["tracker_id"]
        if not onto[old_track]:
            refused.append({**label, "reason": "no box in the new run"})
            continue
        new_track, shared = onto[old_track].most_common(1)[0]
        from_others = sum(
            boxes
            for track, boxes in into[new_track].items()
            if is_tracked(track) and track != old_track
        )
        stats = {
            "new_tracker_id": new_track,
            "coverage": round(shared / old_track_size[old_track], 3),
            "extra": round(from_others / sum(into[new_track].values()), 3),
        }
        reason = None
        if not is_tracked(new_track):
            reason = "new run left it untracked"
        elif stats["coverage"] < MIN_COVERAGE:
            reason = "track split or lost boxes in the new run"
        elif stats["extra"] > MAX_EXTRA:
            reason = "new track also holds another track's boxes"
        elif new_track in disputed:
            reason = LABELS_DISAGREE
        elif new_track in kept:
            if label_identity(kept[new_track]) == label_identity(label):
                reason = "agrees with another label on this new track, merged into it"
            else:
                reason = LABELS_DISAGREE
                refused.append({**kept.pop(new_track), "reason": reason})
                disputed.add(new_track)

        if reason:
            refused.append({**label, "reason": reason, **stats})
        else:
            kept[new_track] = label

    return [{**label, "tracker_id": track} for track, label in kept.items()], refused


def main() -> None:
    """Write the carried label set, and list whatever could not be carried."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", type=Path, required=True, nargs="+")
    for name in ("--old", "--new", "--out"):
        ap.add_argument(name, type=Path, required=True)
    args = ap.parse_args()

    records = [json.loads(p.read_text(encoding="utf-8")) for p in args.labels]
    record = records[0]
    old = json.loads(args.old.read_text(encoding="utf-8"))
    new = json.loads(args.new.read_text(encoding="utf-8"))
    for path, rec in zip(args.labels, records):
        if rec.get("schema") != LABELS_SCHEMA:
            raise SystemExit(f"{path.name} is not {LABELS_SCHEMA}: {rec.get('schema')}")
        if rec["source"] != run_source(old):
            raise SystemExit(f"{path.name} is not tied to {args.old.name}: {rec['source']}")
    if Path(old["video_info"]["filename"]).name != Path(new["video_info"]["filename"]).name:
        raise SystemExit("--old and --new are different reels")
    if new["video_info"]["processing_date"] <= old["video_info"]["processing_date"]:
        raise SystemExit("--new is not newer than --old")

    labels = merge_labels([rec["labels"] for rec in records])
    carried, refused = carry(labels, old, new)
    out = {
        **{k: v for k, v in record.items() if k != "labelled_by"},
        "source": run_source(new),
        "carried_from": record["source"],
        "labels": sorted(carried, key=lambda l: l["tracker_id"]),
    }
    if refused:
        out["refused"] = refused
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.out.name.split('-')[0]} {len(carried)} carried, {len(refused)} refused of {len(labels)}")
    for r in refused:
        print(" ", {k: r.get(k) for k in ("tracker_id", "verdict", "contestant_id", "reason", "coverage", "extra")})


if __name__ == "__main__":
    main()
