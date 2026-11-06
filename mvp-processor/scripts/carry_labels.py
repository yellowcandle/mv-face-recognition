"""Carry a label set from the run it was made against onto a newer run of the same reel.

A label names a tracker id, and a reprocess can renumber tracks, so the Worker and local API refuse
labels from another run. This maps each labelled track by box (same frame, IoU >= 0.5) and writes
a label set bound to the new run, keeping only labels whose track survives whole:

  - coverage: share of the old track's boxes found on one new track
  - extra:    share of that new track's boxes that were on a *different* old track. Boxes the old
              run left untracked don't count, since they carry no other identity.

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

from rescore_run import iou

MIN_COVERAGE = 0.9
MAX_EXTRA = 0.1


def run_source(doc: dict) -> dict:
    """Same identity as `_metadata_source` in local_api.py and the Worker's label check."""
    return {
        "processing_date": doc["video_info"]["processing_date"],
        "detections": sum(len(f["detections"]) for f in doc["frame_data"]),
    }


def merge_labels(label_sets: list[list[dict]]) -> list[dict]:
    """Union of label sets, or SystemExit when two of them say different things about a track."""
    merged: dict[int, dict] = {}
    for labels in label_sets:
        for label in labels:
            track = label["tracker_id"]
            first = merged.setdefault(track, label)
            if (first["verdict"], first.get("contestant_id")) != (
                label["verdict"],
                label.get("contestant_id"),
            ):
                raise SystemExit(f"Label stores disagree on track {track}: {first} vs {label}")
    return list(merged.values())


def carry(labels: list[dict], old: dict, new: dict) -> tuple[list[dict], list[dict]]:
    """Return (carried labels, refused labels with `reason`, plus stats on both)."""
    new_by_frame = {f["frame_number"]: f["detections"] for f in new["frame_data"]}
    old_track_size: Counter = Counter()
    pairs: Counter = Counter()  # (old track, new track) -> boxes in common
    for frame in old["frame_data"]:
        for det in frame["detections"]:
            old_track_size[det["tracker_id"]] += 1
            options = new_by_frame.get(frame["frame_number"], [])
            match = max(options, key=lambda o: iou(det["bbox"], o["bbox"]), default=None)
            if match is not None and iou(det["bbox"], match["bbox"]) >= 0.5:
                pairs[(det["tracker_id"], match["tracker_id"])] += 1

    new_track_size = Counter(
        d["tracker_id"] for f in new["frame_data"] for d in f["detections"]
    )
    onto: dict[int, Counter] = defaultdict(Counter)
    into: dict[int, Counter] = defaultdict(Counter)
    for (o, n), boxes in pairs.items():
        onto[o][n] += boxes
        into[n][o] += boxes

    kept: dict[int, dict] = {}
    refused: list[dict] = []
    for label in labels:
        o = label["tracker_id"]

        def refuse(reason: str, **stats) -> None:
            refused.append({**label, "reason": reason, **stats})

        if not onto[o]:
            refuse("no box in the new run")
            continue
        n, shared = onto[o].most_common(1)[0]
        others = sum(b for t, b in into[n].items() if t not in (o, -1))
        stats = {
            "new_tracker_id": n,
            "coverage": round(shared / old_track_size[o], 3),
            "extra": round(others / new_track_size[n], 3),
        }
        if n < 0:
            refuse("new run left it untracked", **stats)
        elif stats["coverage"] < MIN_COVERAGE:
            refuse("track split in the new run", **stats)
        elif stats["extra"] > MAX_EXTRA:
            refuse("new track also holds another track's boxes", **stats)
        elif n in kept:
            first = kept[n]
            if (first["verdict"], first.get("contestant_id")) != (
                label["verdict"],
                label.get("contestant_id"),
            ):
                refuse("two labels disagree on one new track", **stats)
                refused.append({**first, "reason": "two labels disagree on one new track"})
                first["_drop"] = True
        else:
            kept[n] = {**label, "tracker_id": n}

    return [l for l in kept.values() if not l.get("_drop")], refused


def main() -> None:
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
        if rec["source"] != run_source(old):
            raise SystemExit(f"{path.name} is not tied to {args.old.name}: {rec['source']}")

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
    print(f"{args.out.name[:2]} {len(carried)} carried, {len(refused)} refused of {len(labels)}")
    for r in refused:
        print(" ", {k: r.get(k) for k in ("tracker_id", "verdict", "contestant_id", "reason", "coverage", "extra")})


if __name__ == "__main__":
    main()
