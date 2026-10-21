"""Fill unmatched detections from the identity their track already established.

A tracker links the same face across frames. When most accepted frames of a track agree on a
contestant, an unmatched detection on that track is much more likely that contestant than an
unknown stranger. This pass is deliberately conservative: it never overwrites a frame-level
match, requires at least two accepted frames, and requires a clear majority. Filled detections
carry ``match_source = "track"`` so they stay distinguishable from frame-level recognition.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from typing import Any

MATCH_SOURCE_FRAME = "frame"
MATCH_SOURCE_TRACK = "track"


def refresh_summary(doc: dict[str, Any]) -> None:
    """Recompute the frame-derived summary fields after track filling."""
    frames = doc.get("frame_data") or []
    detections = [d for f in frames for d in (f.get("detections") or [])]
    matched = sum(1 for d in detections if d.get("contestant_id"))
    summary = doc.setdefault("processing_summary", {})
    summary["frames_processed"] = len(frames)
    summary["total_faces_detected"] = len(detections)
    summary["total_recognitions"] = matched
    summary["unique_contestants"] = len(doc.get("contestant_timeline") or {})
    summary["recognition_rate"] = round(matched / len(detections), 4) if detections else 0.0


def rebuild_timeline(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Derive ``contestant_timeline`` from frame_data, including track-filled detections.

    Mirrors scripts/publish/build_read_model.py::build_timeline so stored metadata and the
    published payload agree on what a detection contributes.
    """
    per: dict[str, dict[str, Any]] = {}
    for frame in frames:
        for det in frame.get("detections") or []:
            cid = det.get("contestant_id")
            score = det.get("match_score")
            if cid is None or score is None:
                continue
            entry = per.setdefault(
                str(cid),
                {
                    "contestant_info": {
                        "id": str(cid),
                        "name": det.get("contestant_name"),
                        "nickname": det.get("contestant_nickname"),
                    },
                    "appearances": [],
                },
            )
            entry["appearances"].append(
                {
                    "timestamp": float(frame["timestamp"]),
                    "frame_number": int(frame["frame_number"]),
                    "match_score": float(score),
                    "bbox": det["bbox"],
                }
            )

    timeline: dict[str, dict[str, Any]] = {}
    for cid, entry in per.items():
        apps = entry["appearances"]
        scores = [a["match_score"] for a in apps]
        timeline[cid] = {
            "contestant_info": entry["contestant_info"],
            "appearances": apps,
            "total_appearances": len(apps),
            "average_match_score": round(sum(scores) / len(scores), 4),
            "max_match_score": round(max(scores), 4),
            "first_appearance": apps[0]["timestamp"],
            "last_appearance": apps[-1]["timestamp"],
        }
    return timeline


def smooth_track_identities(
    frames: list[dict[str, Any]],
    *,
    min_accepted: int = 2,
    dominance: float = 0.75,
) -> dict[str, int]:
    """Fill unmatched detections from their track's dominant identity, in place.

    Args:
        frames: ``frame_data`` entries; each detection may carry ``tracker_id``.
        min_accepted: accepted frames required before a track may fill anything.
        dominance: share of accepted frames that must agree on the contestant.

    Returns:
        Counts: ``filled``, ``tracks_filled``, ``tracks_considered``.
    """
    by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame in frames:
        for detection in frame.get("detections") or []:
            tracker_id = detection.get("tracker_id")
            if isinstance(tracker_id, int) and tracker_id >= 0:
                by_track[tracker_id].append(detection)

    filled = 0
    tracks_filled = 0
    for detections in by_track.values():
        accepted = [d for d in detections if d.get("contestant_id")]
        counts = Counter(str(d["contestant_id"]) for d in accepted)
        if len(accepted) < min_accepted or not counts:
            continue
        contestant_id, votes = counts.most_common(1)[0]
        if votes / len(accepted) < dominance:
            continue

        exemplar = next(
            d for d in accepted if str(d["contestant_id"]) == contestant_id
        )
        scores = [
            float(d["match_score"])
            for d in accepted
            if str(d["contestant_id"]) == contestant_id
            and d.get("match_score") is not None
        ]
        track_score = median(scores) if scores else None

        filled_here = 0
        for detection in detections:
            if detection.get("contestant_id"):
                detection.setdefault("match_source", MATCH_SOURCE_FRAME)
                continue
            detection["contestant_id"] = contestant_id
            detection["contestant_name"] = exemplar.get("contestant_name")
            detection["contestant_nickname"] = exemplar.get("contestant_nickname")
            detection["match_score"] = track_score
            detection["match_source"] = MATCH_SOURCE_TRACK
            filled_here += 1
        if filled_here:
            filled += filled_here
            tracks_filled += 1

    for frame in frames:
        detections = frame.get("detections") or []
        if detections:
            frame["recognitions_count"] = sum(
                1 for d in detections if d.get("contestant_id")
            )

    return {
        "filled": filled,
        "tracks_filled": tracks_filled,
        "tracks_considered": len(by_track),
    }
