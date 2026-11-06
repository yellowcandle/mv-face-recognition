"""Re-score a finished run against another reference set, without touching the video.

A run's `<stem>_embeddings.npz` holds every detection's embedding, so a new reference set only
needs the pipeline's matching rule applied again: max cosine over references, accepted above the
threshold, then track smoothing. Boxes and tracks stay the run's own.

With --labels, each labelled track is scored through the metadata its labels are tied to: a box
in that run maps to the new run's box in the same frame at IoU >= 0.5.

    python scripts/rescore_run.py --run DIR --references reference_embeddings.npz \
        [--labels DIR --labelled-metadata DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from track_smoothing import smooth_track_identities  # noqa: E402


def rescore(doc: dict, embeddings: dict, ref_embeddings, ref_ids, threshold: float) -> None:
    """Replace every detection's identity in `doc`, in place, using the pipeline's rule."""
    by_key = {
        (int(f), int(i)): row
        for f, i, row in zip(
            embeddings["frame_number"], embeddings["detection_index"], range(len(embeddings["embeddings"]))
        )
    }
    sims = np.asarray(embeddings["embeddings"]) @ np.asarray(ref_embeddings).T
    best = sims.argmax(axis=1) if len(sims) else np.array([], dtype=int)

    for frame in doc["frame_data"]:
        for i, det in enumerate(frame["detections"]):
            row = by_key[(int(frame["frame_number"]), i)]
            score = float(sims[row, best[row]])
            accepted = score > threshold
            det["contestant_id"] = str(ref_ids[best[row]]) if accepted else None
            det["match_score"] = score if accepted else None
            det["match_source"] = None
    smooth_track_identities(doc["frame_data"])


def track_claims(frames: list[dict]) -> dict[int, str]:
    """Each track's most common contestant, which is the name a viewer sees on it."""
    votes: dict[int, Counter] = defaultdict(Counter)
    for frame in frames:
        for det in frame["detections"]:
            if det["contestant_id"] is not None:
                votes[det["tracker_id"]][det["contestant_id"]] += 1
    return {track: c.most_common(1)[0][0] for track, c in votes.items()}


def iou(a: list[float], b: list[float]) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def score_labels(labels: list[dict], labelled_frames: list[dict], frames: list[dict]) -> Counter:
    """Outcome counts for labelled tracks. `unsure` labels have no truth and are left out."""
    new_by_frame = {f["frame_number"]: f["detections"] for f in frames}
    mapped: dict[int, list[dict]] = defaultdict(list)
    for frame in labelled_frames:
        for det in frame["detections"]:
            options = new_by_frame.get(frame["frame_number"], [])
            match = max(options, key=lambda o: iou(det["bbox"], o["bbox"]), default=None)
            if match is not None and iou(det["bbox"], match["bbox"]) >= 0.5:
                mapped[det["tracker_id"]].append(match)

    claims = track_claims(frames)
    out: Counter = Counter()
    for label in labels:
        if label.get("verdict") not in ("contestant", "not_a_contestant"):
            continue
        dets = mapped.get(label["tracker_id"], [])
        if not dets:
            out["unmapped"] += 1
            continue
        track = Counter(d["tracker_id"] for d in dets).most_common(1)[0][0]
        claim = claims.get(track)
        if label["verdict"] == "contestant":
            truth = str(label["contestant_id"])
            out["right" if claim == truth else "missed" if claim is None else "misnamed"] += 1
            out["boxes_right"] += sum(d["contestant_id"] == truth for d in dets)
            out["boxes_wrong"] += sum(d["contestant_id"] not in (None, truth) for d in dets)
            out["boxes_none"] += sum(d["contestant_id"] is None for d in dets)
        else:
            out["impostor" if claim is not None else "rejected"] += 1
            out["stranger_boxes_named"] += sum(d["contestant_id"] is not None for d in dets)
            out["stranger_boxes_none"] += sum(d["contestant_id"] is None for d in dets)
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    default = yaml.safe_load((root / "config/processing_config.yaml").read_text())
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True, help="searched for *_metadata.json")
    ap.add_argument("--references", type=Path, required=True)
    ap.add_argument(
        "--threshold", type=float, default=default["face_recognition"]["acceptance_threshold"]
    )
    ap.add_argument("--labels", type=Path)
    ap.add_argument("--labelled-metadata", type=Path)
    args = ap.parse_args()

    refs = np.load(args.references)
    print(f"{len(refs['embeddings'])} references, threshold {args.threshold}")
    total: Counter = Counter()
    for path in sorted(args.run.rglob("*_metadata.json")):
        stem = path.name.removesuffix("_metadata.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        before = [d["contestant_id"] for f in doc["frame_data"] for d in f["detections"]]
        rescore(
            doc, np.load(path.with_name(f"{stem}_embeddings.npz")),
            refs["embeddings"], refs["contestant_ids"], args.threshold,
        )
        after = [d["contestant_id"] for f in doc["frame_data"] for d in f["detections"]]
        row = Counter(
            recognitions=sum(a is not None for a in after),
            changed=sum(a != b for a, b in zip(after, before)),
            tracks_named=len(track_claims(doc["frame_data"])),
        )
        if args.labels and args.labelled_metadata:
            labels = json.loads((args.labels / f"{stem}_labels.json").read_text(encoding="utf-8"))
            old = json.loads(
                (args.labelled_metadata / f"{stem}_metadata.json").read_text(encoding="utf-8")
            )
            row += score_labels(labels["labels"], old["frame_data"], doc["frame_data"])
        print(stem[:2].rstrip("-"), dict(sorted(row.items())))
        total += row
    print("all", dict(sorted(total.items())))


if __name__ == "__main__":
    main()
