"""Build and publish the KV read model the Worker serves.

One metadata generation is current: `local_output/metadata/{id}-*_metadata.json`,
written by `mvp-processor/src/process_video.py` (`frame_data[].detections[]`,
frame-fraction bboxes, raw `match_score`). The July 2025 generation
(`frame_results[].faces[]`, pixel bboxes, timeline keyed by name) was retired on
2026-10-22 when reels 1–3 were reprocessed; its files are gone and `normalise()`
refuses that shape with a message pointing at the pipeline.

This still normalises the *current* generation's two frame shapes (`detections` and the
older `recognitions` arrays), derives `contestant_timeline` from `frame_data` (so every
reel is consistent), and either stages the result for review (default) or writes it to
KV (`--publish`).

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
WORKER = os.path.join(REPO, "worker")
NEW_FMT = os.path.join(REPO, "local_output/metadata")
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


class Frame(TypedDict):
    frame_number: int
    timestamp: float
    detections_count: int
    recognitions_count: int
    detections: list[Detection]


def video_id_from(path: str) -> str | None:
    m = re.search(r"/(\d+)-", path)
    return str(int(m.group(1))) if m else None


def clamp_box(x1: float, y1: float, x2: float, y2: float) -> list[float]:
    """Clamp a pixel box to the frame, then convert to frame fractions.

    Legacy runs stored boxes that extend past the frame edge (y = -127, x = 3867 on a
    3840-wide source). CONTEXT.md's contract says a bbox is a fraction of the frame in
    0-1, so the off-frame part is trimmed here rather than published out of range.
    """
    lo_x, hi_x = sorted((max(0.0, x1), min(1.0, x2)))
    lo_y, hi_y = sorted((max(0.0, y1), min(1.0, y2)))
    return [lo_x, lo_y, hi_x, hi_y]


def build_timeline(frames: list[Frame]) -> dict[str, Any]:
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
                        "id": cid,
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
        # Required by apps/shared/types (ProcessingSummary); no generation stored it.
        "recognition_rate": round(recogs / faces, 4) if faces else 0.0,
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
                        round(v, 6)
                        for v in clamp_box(
                            left / width, top / height, right / width, bottom / height
                        )
                    ],
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


REQUIRED_FIELDS = (
    "video_info",
    "processing_summary",
    "contestant_timeline",
    "frame_data",
)
REQUIRED_FRAME_FIELDS = ("frame_number", "timestamp", "detections_count", "detections")
# bands.ts and processing_config.yaml agree on these; a payload that disagrees is stale.
EXPECTED_CUTOFFS = {"high": 0.445, "medium": 0.412}
EXPECTED_ACCEPTANCE = 0.412


def validate_payload(vid: str, payload: dict[str, Any]) -> list[str]:
    """The contract, checked at publish time.

    Reel 5 shipped `recognition_config {tolerance: 0.68, min_confidence: 0.5}` — the
    pre-contract shape — while every confidence it stored sat below its own
    min_confidence. Nothing caught it because the publisher copied the block verbatim.
    These checks make that a failed publish instead of a silent lie.
    """
    problems: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in payload:
            problems.append(f"missing required field {field!r}")

    frames = payload.get("frame_data") or []
    if not frames:
        problems.append("frame_data is empty")
    else:
        first = frames[0]
        for field in REQUIRED_FRAME_FIELDS:
            if field not in first:
                problems.append(f"frame is missing {field!r}")

    # bboxes are frame fractions in canonical [x1,y1,x2,y2] order (CONTEXT.md).
    bad_boxes = 0
    bad_scores = 0
    bad_trackers = 0
    bad_sources = 0
    for frame in frames:
        for det in frame.get("detections") or []:
            tracker_id = det.get("tracker_id")
            if tracker_id is not None and (
                not isinstance(tracker_id, int) or tracker_id < -1
            ):
                bad_trackers += 1
            if det.get("match_source") not in (None, "frame", "track"):
                bad_sources += 1
            box = det.get("bbox")
            if (
                not isinstance(box, list)
                or len(box) != 4
                or any(not isinstance(v, (int, float)) or v < 0 or v > 1 for v in box)
                or box[2] < box[0]
                or box[3] < box[1]
            ):
                bad_boxes += 1
            score = det.get("match_score")
            if score is not None and not (-1 <= float(score) <= 1):
                bad_scores += 1
    if bad_boxes:
        problems.append(
            f"{bad_boxes} detections have a bbox outside [0,1] or misordered"
        )
    if bad_scores:
        problems.append(f"{bad_scores} match scores outside the cosine range [-1,1]")
    if bad_trackers:
        problems.append(
            f"{bad_trackers} detections have a tracker_id that is not an int >= -1"
        )
    if bad_sources:
        problems.append(
            f"{bad_sources} detections have a match_source outside frame|track|null"
        )

    config = payload.get("recognition_config")
    if config is None:
        logger.warning(
            "reel %s: no recognition_config; the bands applied are unknown", vid
        )
    elif not isinstance(config, dict):
        problems.append("recognition_config is not an object")
    else:
        cutoffs = config.get("band_cutoffs")
        acceptance = config.get("acceptance_threshold")
        if cutoffs is None and acceptance is None:
            problems.append(
                "recognition_config has neither band_cutoffs nor acceptance_threshold "
                f"(stale shape: {sorted(config)})"
            )
        else:
            for band, expected in EXPECTED_CUTOFFS.items():
                actual = (cutoffs or {}).get(band)
                if actual is not None and abs(float(actual) - expected) > 1e-6:
                    problems.append(
                        f"band cutoff {band}={actual} disagrees with bands.ts ({expected})"
                    )
            if (
                acceptance is not None
                and abs(float(acceptance) - EXPECTED_ACCEPTANCE) > 1e-6
            ):
                problems.append(
                    f"acceptance_threshold={acceptance} disagrees with the config "
                    f"({EXPECTED_ACCEPTANCE})"
                )

    # Fields the apps read unconditionally (apps/shared/types): a payload without
    # them renders blank or NaN instead of failing at publish time.
    info = payload.get("video_info") or {}
    duration = info.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        problems.append("video_info.duration is missing or not positive")

    summary = payload.get("processing_summary") or {}
    rate = summary.get("recognition_rate")
    if not isinstance(rate, (int, float)) or not 0 <= float(rate) <= 1:
        problems.append("processing_summary.recognition_rate missing or outside [0,1]")

    for cid, entry in (payload.get("contestant_timeline") or {}).items():
        person = (entry or {}).get("contestant_info") or {}
        if person.get("id") != cid:
            problems.append(
                f"contestant_timeline[{cid}].contestant_info.id is {person.get('id')!r}"
            )

    return problems


def normalise_video_info(info: dict[str, Any], frames: list[Frame]) -> dict[str, Any]:
    """Backfill what every consumer reads but no generation stores.

    `VideoInfo.duration` is required by apps/shared/types and the Player's timeline,
    and no source file carries it: both generations stored only `fps` and
    `frame_count`. Derive seconds from those rather than publish a missing field; when
    neither exists, leave 0.0 so validate_payload fails loudly instead of guessing.
    """
    out = dict(info)
    duration = out.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        fps = float(out.get("fps") or 0)
        frame_count = float(out.get("frame_count") or len(frames) or 0)
        out["duration"] = round(frame_count / fps, 3) if fps > 0 and frame_count else 0.0
    return out


def normalise(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        sys.exit(f"cannot read {path}: {exc}")

    if "frame_data" not in doc:
        sys.exit(
            f"{path}: no frame_data. Generation A (`frame_results`) was retired on "
            "2026-10-22; reprocess the reel with "
            "`mvp-processor/src/process_video.py --local-only`."
        )
    frames = doc["frame_data"]
    if frames and "detections" in frames[0]:
        source = "current"
    elif frames and "recognitions" in frames[0]:
        frames = convert_recognitions(doc)["frame_data"]
        source = "recognitions-converted"
    else:
        sys.exit(f"{path}: frame_data in an unknown shape")

    timeline = build_timeline(frames)

    # The pipeline's cutoffs, as bands.ts and processing_config.yaml agree on them. A run
    # that carries its own contract block is trusted but checked by validate_payload(); a
    # run from before the contract (reel 5: {tolerance, min_confidence}) is normalised here
    # and says so, rather than publishing a block that contradicts what the UI renders.
    canonical = {
        "acceptance_threshold": EXPECTED_ACCEPTANCE,
        "band_cutoffs": dict(EXPECTED_CUTOFFS),
        "provisional": True,
    }
    run_config = doc.get("recognition_config")
    config_source = "run"
    if not isinstance(run_config, dict) or (
        "band_cutoffs" not in run_config and "acceptance_threshold" not in run_config
    ):
        config_source = "normalised" if run_config is not None else "absent"
        run_config = canonical

    payload = {
        "video_info": normalise_video_info(doc.get("video_info") or {}, frames),
        "processing_summary": summarise(frames, timeline),
        "contestant_timeline": timeline,
        "frame_data": frames,
        "recognition_config": run_config,
        "read_model": {
            "source": source,
            "frames": len(frames),
            "config": config_source,
        },
    }
    return payload


def pick_sources() -> dict[str, list[str]]:
    """video id -> local metadata files. One file per reel today; the caller still
    keeps the richest, which is what let the two generations coexist."""
    candidates: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(NEW_FMT, "*.json"))):
        vid = video_id_from(path)
        if vid:
            candidates.setdefault(vid, []).append(path)
    return candidates


# The high band cutoff from apps/shared/lib/bands.ts (measured false-match boundary).
# Duplicated as a constant until workstream B gives both sides one source.
HIGH_BAND = 0.445


def load_roster() -> list[dict[str, Any]]:
    """The 96 contestants from the CSV, in the Contestant shape the apps read."""
    try:
        with open(CSV, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        sys.exit(f"cannot read {CSV}: {exc}")
    roster: list[dict[str, Any]] = []
    for row in rows:
        try:
            cid = str(int(row["編號"].strip()))
        except (KeyError, ValueError) as exc:
            sys.exit(f"bad 編號 in {CSV}: {row!r} ({exc})")
        age = row.get("年齡", "").strip()
        roster.append(
            {
                "id": cid,
                "number": int(cid),
                "name": row["姓名"].strip(),
                "nickname": row["暱稱"].strip(),
                "age": int(age) if age else None,
            }
        )
    return roster


def load_reference_counts() -> dict[str, int]:
    """References per contestant, keyed by 編號 (ADR 0001: the manifest is the record)."""
    path = os.path.join(REPO, "source/photo/contestants/reference_manifest.json")
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        logger.warning("no reference manifest (%s); reference counts will read 0", exc)
        return {}
    raw = manifest.get("references_per_contestant") or {}
    return {str(k): int(v) for k, v in raw.items()}


def build_roster(
    payloads: dict[str, dict[str, Any]], refs: dict[str, int]
) -> list[dict[str, Any]]:
    """Join CSV + reference manifest + the published reels into Contestant rows.

    The Worker served a raw CSV dump here, so every field the apps read (`id`,
    `has_embedding`, `reference_count`, `quality`) was `undefined` in production, and
    the hardcoded fallback claimed `has_embedding: true` for all 96.
    """
    stats: dict[str, dict[str, Any]] = {}
    for payload in payloads.values():
        for cid, entry in (payload.get("contestant_timeline") or {}).items():
            scores = [a["match_score"] for a in entry.get("appearances") or []]
            if not scores:
                continue
            s = stats.setdefault(cid, {"scores": [], "detections": 0, "videos": set()})
            s["scores"].extend(scores)
            s["detections"] += len(scores)
            s["videos"].add(payload["video_info"].get("filename", ""))

    roster = []
    for person in load_roster():
        cid = person["id"]
        reference_count = int(refs.get(cid, 0))
        s = stats.get(cid) or {"scores": [], "detections": 0, "videos": set()}
        avg = round(sum(s["scores"]) / len(s["scores"]), 4) if s["scores"] else 0.0
        peak = round(max(s["scores"]), 4) if s["scores"] else 0.0
        if reference_count == 0:
            quality = "missing"
        elif avg >= HIGH_BAND or s["detections"] >= 20:
            quality = "good"
        else:
            quality = "weak"
        roster.append(
            {
                **person,
                "has_embedding": reference_count > 0,
                "reference_count": reference_count,
                "portrait_url": f"/api/contestants/{cid}/thumb/face",
                "avg_match_score": avg,
                "max_match_score": peak,
                "detection_count": s["detections"],
                "videos_seen_in": len(s["videos"]),
                "quality": quality,
            }
        )
    return roster


def build_coverage(
    roster: list[dict[str, Any]], payloads: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """The coverage report the Embedding Workbench reads.

    Same shape `generate_coverage()` returns (contestants + summary), built from the
    roster and payloads already normalised above so the numbers match what shipped in
    `contestants_structured` instead of a second scan of the metadata directory.
    """
    good = sum(1 for r in roster if r["quality"] == "good")
    weak = sum(1 for r in roster if r["quality"] == "weak")
    missing = sum(1 for r in roster if r["quality"] == "missing")
    scored = [r["avg_match_score"] for r in roster if r["avg_match_score"] > 0]
    avg_score = round(sum(scored) / len(scored), 4) if scored else 0.0
    total_det = sum(
        p["processing_summary"]["total_faces_detected"] for p in payloads.values()
    )
    total_rec = sum(
        p["processing_summary"]["total_recognitions"] for p in payloads.values()
    )
    rate = round(total_rec / total_det, 6) if total_det > 0 else 0.0
    return {
        "contestants": roster,
        "summary": {
            "total": len(roster),
            "good": good,
            "weak": weak,
            "missing": missing,
            "avg_match_score": avg_score,
            "recognition_rate": rate,
            "total_faces_detected": total_det,
            "total_faces_recognized": total_rec,
        },
    }


def wrangler(*args: str) -> bool:
    # The namespace has a preview id too; `--preview false` is required to write the
    # production namespace from a non-interactive shell.
    extra = ("--preview", "false") if args and args[0] == "kv" else ()
    proc = subprocess.run(
        ["npx", "wrangler", *args, *extra], cwd=WORKER, capture_output=True, text=True
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

    sources = pick_sources()
    if not sources:
        sys.exit("no metadata sources found")

    try:
        os.makedirs(STAGE, exist_ok=True)
    except OSError as exc:
        sys.exit(f"cannot create {STAGE}: {exc}")

    videos = []
    payloads: dict[str, dict[str, Any]] = {}
    chosen: dict[str, str] = {}
    video_ids: dict[str, str] = {}
    for vid, candidates in sorted(sources.items(), key=lambda kv: int(kv[0])):
        # Pick the candidate that actually recognises the most faces. With one file per
        # reel this is a no-op, but it kept the richer generation while both existed.
        best: dict[str, Any] | None = None
        best_path = ""
        best_matches = -1
        for candidate in candidates:
            try:
                payload = normalise(candidate)
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
        problems = validate_payload(vid, payload)
        if problems:
            for problem in problems:
                logger.error("reel %s: %s", vid, problem)
            sys.exit(f"reel {vid} does not satisfy the metadata contract")
        chosen[vid] = best_path
        payloads[vid] = payload
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
        info = payload["video_info"]
        stem = os.path.splitext(str(info.get("filename") or f"{vid}-video.mp4"))[0]
        # Ticket 007 Q1: the KV key is the full video id the list serves, not the
        # numeric 編號 — a wrong prefix can no longer serve another reel's metadata.
        video_id = f"{vid}-{stem.split('-', 1)[-1]}"
        video_ids[vid] = video_id
        # Ticket 007 Q5: `stream_url` must name the same object `scripts/upload-to-r2.js`
        # writes. Use the 1080p encode when the pipeline produced one; a reel with no
        # local encode keeps its source filename (its R2 object predates the rule).
        encoded = f"{stem}_1080p.mp4"
        published = (
            encoded
            if os.path.exists(
                os.path.join(REPO, "local_output/processed_videos", encoded)
            )
            else f"{stem}.mp4"
        )
        out = os.path.join(STAGE, f"metadata_{video_id}.json")
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        except OSError as exc:
            sys.exit(f"cannot write {out}: {exc}")
        size = os.path.getsize(out)
        if size > 24 * 1024 * 1024:
            sys.exit(f"{out} is {size / 1e6:.1f} MB, over the 25 MiB KV value limit")

        videos.append(
            {
                "id": video_id,
                "name": stem,
                "filename": published,
                "stream_url": f"/videos/processed_videos/{published}",
                "has_metadata": True,
            }
        )

    # Drop staged metadata from earlier keys/runs so the directory mirrors what KV gets.
    expected = {f"metadata_{video_id}.json" for video_id in video_ids.values()}
    for stale in glob.glob(os.path.join(STAGE, "metadata_*.json")):
        if os.path.basename(stale) not in expected:
            try:
                os.remove(stale)
            except OSError:
                pass

    list_path = os.path.join(STAGE, "processed_videos_list.json")
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            json.dump(videos, f, ensure_ascii=False, separators=(",", ":"))
    except OSError as exc:
        sys.exit(f"cannot write {list_path}: {exc}")

    print(f"\nstaged {len(videos)} reels + processed_videos_list in {STAGE}")

    # The roster joins the CSV, the reference manifest and the reels published above, so
    # `has_embedding` / `reference_count` / `quality` describe what actually shipped.
    roster = build_roster(payloads, load_reference_counts())
    roster_path = os.path.join(STAGE, "contestants_structured.json")
    try:
        with open(roster_path, "w", encoding="utf-8") as f:
            json.dump(roster, f, ensure_ascii=False, separators=(",", ":"))
    except OSError as exc:
        sys.exit(f"cannot write {roster_path}: {exc}")
    by_quality: dict[str, int] = {}
    for person in roster:
        by_quality[person["quality"]] = by_quality.get(person["quality"], 0) + 1
    no_refs = [p["id"] for p in roster if not p["has_embedding"]]
    print(
        f"  roster: {len(roster)} contestants "
        f"(good {by_quality.get('good', 0)}, weak {by_quality.get('weak', 0)}, "
        f"missing {by_quality.get('missing', 0)}); no references: {no_refs}"
    )

    # Coverage is derived from the same roster, so it cannot disagree with the KV roster.
    coverage = build_coverage(roster, payloads)
    coverage_path = os.path.join(STAGE, "embedding_coverage.json")
    data_coverage_path = os.path.join(REPO, "data/coverage.json")
    for path in (coverage_path, data_coverage_path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(coverage, f, ensure_ascii=False, separators=(",", ":"))
        except OSError as exc:
            sys.exit(f"cannot write {path}: {exc}")
    summary = coverage["summary"]
    print(
        f"  coverage: {summary['good']} good, {summary['weak']} weak, "
        f"{summary['missing']} missing of {summary['total']}; "
        f"recognition rate {summary['recognition_rate']}"
    )

    # Similarity inputs are produced by the embedding scripts, not by this publisher; stage
    # them verbatim when present so the Workbench reads them from the same origin.
    similarity_sources = (
        ("embedding_similarity_matrix.json", "data/similarity_matrix.json"),
        ("embedding_top_pairs.json", "data/top_pairs.json"),
    )
    for stage_name, data_name in similarity_sources:
        source = os.path.join(REPO, data_name)
        if not os.path.exists(source):
            print(f"  skip {stage_name}: {data_name} not present")
            continue
        try:
            with open(source, encoding="utf-8") as f:
                document = json.load(f)
        except (OSError, ValueError) as exc:
            sys.exit(f"cannot read {source}: {exc}")
        staged = os.path.join(STAGE, stage_name)
        try:
            with open(staged, "w", encoding="utf-8") as f:
                json.dump(document, f, ensure_ascii=False, separators=(",", ":"))
        except OSError as exc:
            sys.exit(f"cannot write {staged}: {exc}")
        print(f"  staged {stage_name}")

    if not args.publish:
        print("dry run: nothing written to KV")
        return 0

    for vid in sorted(chosen, key=int):
        video_id = video_ids[vid]
        staged = os.path.join(STAGE, f"metadata_{video_id}.json")
        if not wrangler(
            "kv",
            "key",
            "put",
            f"metadata_{video_id}",
            "--path",
            staged,
            "--binding",
            "METADATA_KV",
            "--remote",
        ):
            return 1
        print(f"  put metadata_{video_id}")
    if not wrangler(
        "kv",
        "key",
        "put",
        "contestants_structured",
        "--path",
        roster_path,
        "--binding",
        "METADATA_KV",
        "--remote",
    ):
        return 1
    print("  put contestants_structured")

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

    # The Workbench reads these three through `/api/embedding/*`; stage names match the
    # KV keys so the loop stays mechanical.
    for key in (
        "embedding_coverage",
        "embedding_similarity_matrix",
        "embedding_top_pairs",
    ):
        staged_path = os.path.join(STAGE, f"{key}.json")
        if not os.path.exists(staged_path):
            print(f"  skip {key}: not staged")
            continue
        if not wrangler(
            "kv",
            "key",
            "put",
            key,
            "--path",
            staged_path,
            "--binding",
            "METADATA_KV",
            "--remote",
        ):
            return 1
        print(f"  put {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
