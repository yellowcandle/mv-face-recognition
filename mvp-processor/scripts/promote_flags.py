#!/usr/bin/env python3
"""
Promote accepted face flags into reference vectors.

An accepted **flag** is a human assertion that one detection in a reel is contestant N
(`CONTEXT.md`, "Flag"). It is the only identity evidence this project gains after the reference
photos were taken, so it is worth feeding back into matching — but the reference cache is built
from aligned faces, and a flag's tray thumbnail is not one: two of three accepted flags have no
detectable face in their crop at all.

The detection's embedding, however, was already computed and stored in
`<reel>_embeddings.npz` (`frame_number`, `detection_index`, `embeddings`). That vector is aligned,
and a human has vouched for whose it is. So a flag is resolved to that vector:

    uv run python scripts/promote_flags.py [--flags FILE] [--labels DIR] [--out DIR] [--dry-run]

Labels (`local_output/labels/<reel>_labels.json`) are the same idea one level up: a **label** is a
human verdict on a whole track, so every detection in a track the reviewer called `contestant` is
identity-confirmed. Each such track contributes its best-scoring detection's embedding — one vector
per track, never one per frame, so a track that runs for ten seconds does not outweigh ten people.

Writes, under `--out` (default `../source/photo/contestants/flagged/`):

    contestant_<id>/flag_<flag_id>.npy   one 512-d vector per accepted flag
    manifest.json                        flag id, reel, timestamp, frame, detection, IoU, sha256

`build_reference_cache.py --promoted <dir>` is what makes them count. Delete the directory and
rebuild to undo the promotion.

A flag whose detection cannot be located in the stored metadata is refused rather than guessed:
the box and the timestamp both have to agree with a detection that the run actually produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

DEFAULT_FLAGS = Path("../local_output/flagged_faces.json")
DEFAULT_METADATA = Path("../local_output/metadata")
DEFAULT_OUT = Path("../source/photo/contestants/flagged")
DEFAULT_LABELS = Path("../local_output/labels")

# Near-duplicate crops from the same face are not new evidence.
DUPLICATE_COSINE = 0.95

# How closely a flag has to match a stored detection. The box is what the reviewer clicked, and
# the timestamp is the frame it was filed against; both are checked.
MIN_IOU = 0.5
MAX_SECONDS_APART = 0.5


def load_accepted(flags_path: Path) -> list[dict]:
    if not flags_path.is_file():
        raise SystemExit(f"no flag store at {flags_path}")
    records = json.loads(flags_path.read_text())
    if isinstance(records, dict):
        records = records.get("flags", [])
    accepted = [record for record in records if record.get("status") == "accepted"]
    if not accepted:
        raise SystemExit(f"{flags_path} holds no accepted flags")
    return accepted


def iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def locate(
    flag: dict, frames: list[dict], embeddings: dict[tuple[int, int], np.ndarray]
) -> tuple[int, int, float, float, float]:
    """The stored detection a flag names: (frame_number, detection_index, iou, seconds_apart)."""
    timestamp = float(flag["timestamp"])
    nearest = min(frames, key=lambda frame: abs(float(frame["timestamp"]) - timestamp))
    seconds_apart = abs(float(nearest["timestamp"]) - timestamp)
    if seconds_apart > MAX_SECONDS_APART:
        raise SystemExit(
            f"flag {flag['id']}: nearest stored frame is {seconds_apart:.2f}s away "
            f"(limit {MAX_SECONDS_APART}s) — the run that produced this reel is not the one flagged"
        )

    best_index, best_iou = -1, 0.0
    for index, detection in enumerate(nearest["detections"]):
        overlap = iou(flag["bbox"], detection["bbox"])
        if overlap > best_iou:
            best_index, best_iou = index, overlap
    if best_index < 0 or best_iou < MIN_IOU:
        raise SystemExit(
            f"flag {flag['id']}: no detection at frame {nearest['frame_number']} matches the box "
            f"(best IoU {best_iou:.2f}, need {MIN_IOU})"
        )

    key = (int(nearest["frame_number"]), best_index)
    if key not in embeddings:
        raise SystemExit(f"flag {flag['id']}: frame {key[0]} detection {key[1]} has no stored embedding")
    detection_score = float(nearest["detections"][best_index].get("det_score", 0.0))
    return key[0], key[1], best_iou, seconds_apart, detection_score


def load_reel(reel_id: str, metadata_dir: Path):
    metadata_path = metadata_dir / f"{reel_id}_metadata.json"
    embeddings_path = metadata_dir / f"{reel_id}_embeddings.npz"
    for path in (metadata_path, embeddings_path):
        if not path.is_file():
            raise SystemExit(f"missing {path}: cannot resolve a flag against a reel that was not processed here")
    frames = json.loads(metadata_path.read_text())["frame_data"]
    with np.load(embeddings_path, allow_pickle=False) as store:
        index = {
            (int(frame), int(detection)): np.asarray(vector, dtype=np.float32)
            for frame, detection, vector in zip(
                store["frame_number"], store["detection_index"], store["embeddings"]
            )
        }
    return frames, index


def load_labels(labels_dir: Path) -> list[tuple[str, dict]]:
    """(reel id, label) for every label set that names a contestant for a whole track."""
    if not labels_dir.is_dir():
        raise SystemExit(f"no label directory at {labels_dir}")
    labelled: list[tuple[str, dict]] = []
    for path in sorted(labels_dir.glob("*_labels.json")):
        reel = path.name[: -len("_labels.json")]
        payload = json.loads(path.read_text())
        labels = payload.get("labels", payload) if isinstance(payload, dict) else payload
        if isinstance(labels, dict):
            labels = list(labels.values())
        for label in labels:
            if label.get("verdict") == "contestant" and label.get("contestant_id"):
                labelled.append((reel, label))
    if not labelled:
        raise SystemExit(f"{labels_dir} holds no `contestant` verdicts")
    return labelled


def track_detections(frames: list[dict], tracker_id: int) -> list[tuple[int, int, dict]]:
    """Every (frame_number, detection_index, detection) the tracker produced."""
    found = []
    for frame in frames:
        for index, detection in enumerate(frame["detections"]):
            if int(detection.get("tracker_id", -1)) == int(tracker_id):
                found.append((int(frame["frame_number"]), index, detection))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flags", type=Path, default=DEFAULT_FLAGS)
    parser.add_argument("--labels", type=Path, default=None, help="label directory to promote tracks from")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written")
    args = parser.parse_args()

    accepted = load_accepted(args.flags)
    print(f"{len(accepted)} accepted flags")

    reels: dict[str, tuple[list[dict], dict]] = {}
    entries = []
    refused = []
    for flag in accepted:
        reel = str(flag["video_id"])
        if reel not in reels:
            reels[reel] = load_reel(reel, args.metadata)
        frames, embeddings = reels[reel]
        try:
            frame_number, detection_index, overlap, apart, det_score = locate(flag, frames, embeddings)
        except SystemExit as error:
            refused.append((flag["id"], str(error)))
            print(f"  REFUSED {flag['id']}: {error}")
            continue

        vector = embeddings[(frame_number, detection_index)]
        contestant = str(flag["contestant_id"])
        target = args.out / f"contestant_{contestant}" / f"flag_{flag['id']}.npy"
        entries.append(
            {
                "flag_id": flag["id"],
                "contestant_id": contestant,
                "video_id": reel,
                "timestamp": round(float(flag["timestamp"]), 3),
                "frame_number": frame_number,
                "detection_index": detection_index,
                "iou": round(overlap, 3),
                "seconds_apart": round(apart, 3),
                "det_score": round(det_score, 3),
                "path": str(target.relative_to(args.out)),
                "sha256": hashlib.sha256(vector.astype(np.float32).tobytes()).hexdigest(),
            }
        )
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            np.save(target, vector.astype(np.float32))
        print(
            f"  contestant {contestant:>2}  frame {frame_number} det {detection_index} "
            f"IoU {overlap:.2f} Δt {apart:.2f}s  -> {target.name}"
        )

    track_entries = []
    if args.labels is not None:
        labelled = load_labels(args.labels)
        print(f"{len(labelled)} labels name a contestant for a whole track")
        by_contestant: dict[str, list[np.ndarray]] = {}
        for reel, label in labelled:
            if reel not in reels:
                try:
                    reels[reel] = load_reel(reel, args.metadata)
                except SystemExit as error:
                    print(f"  skipped {reel[:12]}…: {error}")
                    continue
            frames, embeddings = reels[reel]
            detections = track_detections(frames, label["tracker_id"])
            if not detections:
                continue
            # One vector per track: its clearest detection.
            frame_number, detection_index, detection = max(
                detections, key=lambda item: float(item[2].get("det_score", 0.0))
            )
            key = (frame_number, detection_index)
            if key not in embeddings:
                continue
            vector = embeddings[key]
            contestant = str(label["contestant_id"])
            existing = by_contestant.setdefault(contestant, [])
            if existing and max(float(vector @ other) for other in existing) >= DUPLICATE_COSINE:
                continue
            existing.append(vector.astype(np.float32))

            path = args.out / f"contestant_{contestant}" / f"track_{reel[:12]}_{int(label['tracker_id'])}.npy"
            track_entries.append(
                {
                    "video_id": reel,
                    "tracker_id": int(label["tracker_id"]),
                    "contestant_id": contestant,
                    "frame_number": frame_number,
                    "detection_index": detection_index,
                    "det_score": round(float(detection.get("det_score", 0.0)), 3),
                    "path": str(path.relative_to(args.out)),
                    "sha256": hashlib.sha256(vector.astype(np.float32).tobytes()).hexdigest(),
                }
            )
            if not args.dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                np.save(path, vector.astype(np.float32))
        print(f"  promoted {len(track_entries)} track vectors across {len(by_contestant)} contestants")

    if not entries and not track_entries:
        raise SystemExit("nothing could be resolved; nothing written")

    by_contestant: dict[str, int] = {}
    for entry in [*entries, *track_entries]:
        by_contestant[entry["contestant_id"]] = by_contestant.get(entry["contestant_id"], 0) + 1
    print("contestants gaining a reference:", ", ".join(
        f"{cid}×{count}" for cid, count in sorted(by_contestant.items(), key=lambda kv: int(kv[0]))
    ))
    if refused:
        print(f"{len(refused)} refused: {', '.join(flag_id for flag_id, _ in refused)}")

    if not args.dry_run:
        manifest = {
            "note": "Derived from human verdicts — accepted flags and labelled tracks — as the "
            "per-detection embeddings the matcher already computed. Regenerate with "
            "scripts/promote_flags.py; delete this directory and rebuild the cache to undo.",
            "source_flags": str(args.flags),
            "vectors": entries,
            "refused": [{"flag_id": flag_id, "reason": reason} for flag_id, reason in refused],
            "tracks": track_entries,
        }
        (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {len(entries)} vectors + manifest.json to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
