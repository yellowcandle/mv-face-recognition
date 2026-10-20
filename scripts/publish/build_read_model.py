"""Build and publish the KV read model the Worker serves.

Two generations of metadata exist on disk and only one matches the contract the code
reads (`frame_data[].detections[]`, frame-fraction bboxes, raw `match_score`):

- `local_output/metadata/{id}-*_metadata.json` — current format (reels 4, 5)
- `metadata/{id}-*_annotated_dense_metadata.json` — July 2025 legacy: `frame_results[].faces[]`,
  pixel bboxes, `detection_confidence` / `recognition_confidence`, timeline keyed by name

This normalises both into one payload per reel, derives `contestant_timeline` from
`frame_data` (so every reel is consistent regardless of source), and either stages the
result for review (`--dry-run`) or writes it to KV (`--publish`).

Why the normalisation matters: the Worker and `useViewerMetadata` both read `frame_data`,
while every published value carried `frame_results`, so `/api/faces/detect` returned
`faces: []` for every reel and the viewer drew no boxes.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import logging
import os
import re
import subprocess
import sys
from typing import Any, TypedDict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEW_FMT = os.path.join(REPO, "local_output/metadata")
LEGACY_FMT = os.path.join(REPO, "metadata")
CSV = os.path.join(REPO, "metadata/contestant_info.csv")
STAGE = os.path.expanduser("~/.cache/mv-read-model")
BUCKET = "mv-face-recognition-videos"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("publish")


class Detection(TypedDict):
    contestant_id: str | None
    contestant_name: str | None
    contestant_nickname: str | None
    match_score: float | None
    det_score: float
    bbox: list[float]
    tracker_id: int | None


# (編號, 姓名, 暱稱)
Contestant = tuple[str, str, str]
Roster = dict[str, Contestant]


class Frame(TypedDict):
    frame_number: int
    timestamp: float
    detections_count: int
    recognitions_count: int
    detections: list[Detection]


def load_contestants() -> tuple[Roster, Roster]:
    """(by nickname, by full name) -> (id, 姓名, 暱稱)."""
    try:
        with open(CSV, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        sys.exit(f"cannot read {CSV}: {exc}")
    by_nick: Roster = {}
    by_name: Roster = {}
    for row in rows:
        try:
            cid = str(int(row["編號"].strip()))
        except (KeyError, ValueError) as exc:
            sys.exit(f"bad 編號 in {CSV}: {row!r} ({exc})")
        name, nick = row["姓名"].strip(), row["暱稱"].strip()
        by_nick[nick] = (cid, name, nick)
        by_name[name] = (cid, name, nick)
    return by_nick, by_name


def video_id_from(path: str) -> str | None:
    m = re.search(r"/(\d+)-", path)
    return str(int(m.group(1))) if m else None


def convert_legacy(
    doc: dict[str, Any], by_nick: Roster, by_name: Roster
) -> dict[str, Any]:
    """Legacy `frame_results[].faces[]` -> contract `frame_data[].detections[]`."""
    info = doc.get("video_info") or {}
    width = float(info.get("width") or 0)
    height = float(info.get("height") or 0)
    if not width or not height:
        sys.exit("legacy metadata has no video_info.width/height; cannot scale boxes")

    frames: list[Frame] = []
    for raw in doc.get("frame_results") or []:
        dets: list[Detection] = []
        for face in raw.get("faces") or []:
            box = face.get("bbox") or []
            if len(box) != 4:
                continue
            # Legacy boxes are pixels; the contract is frame fractions, canonical order.
            x1, y1, x2, y2 = (float(v) for v in box)
            name = face.get("contestant_name")
            known: Contestant | None = None
            if name:
                known = by_nick.get(name) or by_name.get(name)
            matched = bool(face.get("matched")) and known is not None
            conf = face.get("recognition_confidence")
            if matched and known is not None:
                cid, cname, cnick = known
            else:
                cid, cname, cnick = None, None, None
            dets.append(
                Detection(
                    contestant_id=cid,
                    contestant_name=cname,
                    contestant_nickname=cnick,
                    match_score=(
                        round(float(conf), 4) if matched and conf is not None else None
                    ),
                    det_score=round(float(face.get("detection_confidence") or 0), 4),
                    bbox=[
                        round(x1 / width, 6),
                        round(y1 / height, 6),
                        round(x2 / width, 6),
                        round(y2 / height, 6),
                    ],
                    tracker_id=None,  # the legacy pipeline stored no tracker ids
                )
            )
        frames.append(
            Frame(
                frame_number=int(raw.get("frame_number") or 0),
                timestamp=float(raw.get("timestamp") or 0),
                detections_count=len(dets),
                recognitions_count=sum(
                    1 for d in dets if d["contestant_id"] is not None
                ),
                detections=dets,
            )
        )
    return {"video_info": info, "legacy_source": True, "frame_data": frames}


def build_timeline(
    frames: list[Frame], by_nick: Roster, by_name: Roster
) -> dict[str, Any]:
    """Derive the contract's contestant_timeline from frame_data alone."""
    per: dict[str, dict[str, Any]] = {}
    for frame in frames:
        for det in frame["detections"]:
            cid = det["contestant_id"]
            if cid is None or det["match_score"] is None:
                continue
            entry = per.setdefault(
                cid,
                {
                    "contestant_info": {
                        "name": det["contestant_name"],
                        "nickname": det["contestant_nickname"],
                    },
                    "appearances": [],
                },
            )
            entry["appearances"].append(
                {
                    "timestamp": frame["timestamp"],
                    "frame_number": frame["frame_number"],
                    "match_score": det["match_score"],
                    "bbox": det["bbox"],
                }
            )
    timeline: dict[str, Any] = {}
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


def summarise(frames: list[Frame], timeline: dict[str, Any]) -> dict[str, Any]:
    faces = sum(f["detections_count"] for f in frames)
    recogs = sum(f["recognitions_count"] for f in frames)
    return {
        "frames_processed": len(frames),
        "total_faces_detected": faces,
        "total_recognitions": recogs,
        "unique_contestants": len(timeline),
    }


def convert_recognitions(doc: dict[str, Any]) -> dict[str, Any]:
    """The `recognitions[]` variant -> contract frames.

    Its `face_location` is `[top, right, bottom, left]` in pixels (CONTEXT.md's warned
    ordering), so the corners are transposed here, not read as [x1, y1, x2, y2]. Only
    matched faces were stored, so unmatched detections cannot be recovered, and no
    detector score exists — recorded as 0 with provenance saying so.
    """
    info = doc.get("video_info") or {}
    width = float(info.get("width") or 0)
    height = float(info.get("height") or 0)
    if not width or not height:
        sys.exit("recognitions metadata has no video_info.width/height; cannot scale")

    frames: list[Frame] = []
    for raw in doc.get("frame_data") or []:
        dets: list[Detection] = []
        trackers = raw.get("tracker_ids") or []
        for i, rec in enumerate(raw.get("recognitions") or []):
            loc = rec.get("face_location") or []
            if len(loc) != 4:
                continue
            top, right, bottom, left = (float(v) for v in loc)
            cid = rec.get("contestant_id")
            dets.append(
                Detection(
                    contestant_id=str(cid) if cid is not None else None,
                    contestant_name=rec.get("contestant_name"),
                    contestant_nickname=rec.get("contestant_nickname"),
                    match_score=(
                        round(float(rec["confidence"]), 4)
                        if rec.get("confidence") is not None
                        else None
                    ),
                    det_score=0.0,  # not stored in this variant
                    bbox=[
                        round(left / width, 6),
                        round(top / height, 6),
                        round(right / width, 6),
                        round(bottom / height, 6),
                    ],
                    tracker_id=(trackers[i] if i < len(trackers) else None),
                )
            )
        frames.append(
            Frame(
                frame_number=int(raw.get("frame_number") or 0),
                timestamp=float(raw.get("timestamp") or 0),
                detections_count=int(raw.get("detections_count") or len(dets)),
                recognitions_count=len(dets),
                detections=dets,
            )
        )
    return {"video_info": info, "frame_data": frames}


def normalise(path: str, by_nick: Roster, by_name: Roster) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        sys.exit(f"cannot read {path}: {exc}")

    if "frame_data" in doc:
        frames = doc["frame_data"]
        if frames and "detections" in frames[0]:
            source = "current"
        elif frames and "recognitions" in frames[0]:
            frames = convert_recognitions(doc)["frame_data"]
            source = "recognitions-converted"
        else:
            sys.exit(f"{path}: frame_data in an unknown shape")
    elif "frame_results" in doc:
        converted = convert_legacy(doc, by_nick, by_name)
        frames = converted["frame_data"]
        source = "legacy-converted"
    else:
        sys.exit(f"{path} has neither frame_data nor frame_results")

    timeline = build_timeline(frames, by_nick, by_name)
    payload = {
        "video_info": doc.get("video_info") or {},
        "processing_summary": summarise(frames, timeline),
        "contestant_timeline": timeline,
        "frame_data": frames,
        "read_model": {"source": source, "frames": len(frames)},
    }
    if "recognition_config" in doc:
        payload["recognition_config"] = doc["recognition_config"]
    return payload


def pick_sources() -> dict[str, list[str]]:
    """video id -> every candidate local file, so the richest can be chosen per reel."""
    candidates: dict[str, list[str]] = {}
    for pattern in (
        os.path.join(LEGACY_FMT, "*_annotated_dense_metadata.json"),
        os.path.join(NEW_FMT, "*.json"),
    ):
        for path in sorted(glob.glob(pattern)):
            vid = video_id_from(path)
            if vid:
                candidates.setdefault(vid, []).append(path)
    return candidates


def wrangler(*args: str) -> bool:
    proc = subprocess.run(
        ["npx", "wrangler", *args], cwd=REPO, capture_output=True, text=True
    )
    if proc.returncode != 0:
        logger.error(
            "wrangler %s failed: %s",
            " ".join(args[:4]),
            (proc.stderr or proc.stdout)[-400:],
        )
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument(
        "--publish", action="store_true", help="write to KV (default: stage only)"
    )
    args = ap.parse_args()

    by_nick, by_name = load_contestants()
    sources = pick_sources()
    if not sources:
        sys.exit("no metadata sources found")

    try:
        os.makedirs(STAGE, exist_ok=True)
    except OSError as exc:
        sys.exit(f"cannot create {STAGE}: {exc}")

    videos = []
    chosen: dict[str, str] = {}
    for vid, candidates in sorted(sources.items(), key=lambda kv: int(kv[0])):
        # Pick the candidate that actually recognises the most faces: the generations
        # differ enormously (one reel: 0 matched in legacy, 596 in another variant).
        best: dict[str, Any] | None = None
        best_path = ""
        best_matches = -1
        for candidate in candidates:
            try:
                payload = normalise(candidate, by_nick, by_name)
            except SystemExit as exc:
                logger.warning("skipping %s: %s", candidate, exc)
                continue
            matches = sum(
                1
                for f in payload["frame_data"]
                for d in f["detections"]
                if d["match_score"] is not None
            )
            if matches > best_matches:
                best, best_path, best_matches = payload, candidate, matches
        if best is None:
            logger.error("no usable metadata for reel %s", vid)
            continue
        payload = best
        chosen[vid] = best_path
        frames = payload["frame_data"]
        empty = sum(1 for f in frames if f["detections_count"] == 0)
        src = payload["read_model"]["source"]
        with_match = sum(
            1 for f in frames for d in f["detections"] if d["match_score"] is not None
        )
        print(
            f"  reel {vid}: {len(frames):>4} frames, {empty:>3} empty, "
            f"{with_match:>4} matched detections, {len(payload['contestant_timeline']):>2} contestants "
            f"[{src}] from {os.path.basename(best_path)[:34]}"
        )
        out = os.path.join(STAGE, f"metadata_dense_{vid}.json")
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        except OSError as exc:
            sys.exit(f"cannot write {out}: {exc}")
        size = os.path.getsize(out)
        if size > 24 * 1024 * 1024:
            sys.exit(f"{out} is {size / 1e6:.1f} MB, over the 25 MiB KV value limit")

        info = payload["video_info"]
        filename = str(info.get("filename") or f"{vid}_annotated.mp4")
        videos.append(
            {
                "id": f"{vid}-{os.path.splitext(filename)[0].split('-', 1)[-1]}",
                "name": os.path.splitext(filename)[0],
                "filename": filename,
                "stream_url": f"/videos/processed_videos/{filename}",
                "has_metadata": True,
            }
        )

    list_path = os.path.join(STAGE, "processed_videos_list.json")
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            json.dump(videos, f, ensure_ascii=False, separators=(",", ":"))
    except OSError as exc:
        sys.exit(f"cannot write {list_path}: {exc}")

    print(f"\nstaged {len(videos)} reels + processed_videos_list in {STAGE}")
    if not args.publish:
        print("dry run: nothing written to KV")
        return 0

    for vid in sorted(chosen, key=int):
        staged = os.path.join(STAGE, f"metadata_dense_{vid}.json")
        if not wrangler(
            "kv",
            "key",
            "put",
            f"metadata_dense_{vid}",
            "--path",
            staged,
            "--binding",
            "METADATA_KV",
            "--remote",
        ):
            return 1
        print(f"  put metadata_dense_{vid}")
    if not wrangler(
        "kv",
        "key",
        "put",
        "processed_videos_list",
        "--path",
        list_path,
        "--binding",
        "METADATA_KV",
        "--remote",
    ):
        return 1
    print("  put processed_videos_list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
