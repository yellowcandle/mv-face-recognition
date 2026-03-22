#!/usr/bin/env python3
"""
Generate embedding coverage report for the Embedding Workbench.

Scans contestant CSV, embedding files, and video metadata to produce
coverage.json — a per-contestant quality assessment used by the
Coverage Dashboard (Tab 1).

Usage:
    python scripts/generate_coverage.py
    python scripts/generate_coverage.py --output ../data/coverage.json
"""

import argparse
import csv
import json
import logging
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Paths relative to mvp-processor/
DEFAULT_CSV = Path("../metadata/contestant_info.csv")
DEFAULT_EMBEDDINGS_DIR = Path("../source/photo/contestants")
DEFAULT_METADATA_DIR = Path("../metadata")
DEFAULT_OUTPUT = Path("../data/coverage.json")


def load_contestants(csv_path: Path) -> list[dict]:
    """Load contestant info from CSV."""
    contestants = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            contestants.append({
                "id": row["編號"].strip(),
                "name": row["姓名"].strip(),
                "nickname": row["暱稱"].strip(),
                "age": int(row["年齡"]) if row.get("年齡", "").strip() else None,
            })
    return contestants


def check_embedding(embeddings_dir: Path, nickname: str) -> dict:
    """Check if a nickname embedding exists and get its properties."""
    path = embeddings_dir / f"{nickname}_embedding.npy"
    if not path.exists():
        return {"exists": False, "dim": 0, "path": None}

    try:
        arr = np.load(str(path))
        return {
            "exists": True,
            "dim": int(arr.flatten().shape[0]),
            "path": str(path),
        }
    except Exception as e:
        logger.warning(f"Failed to load embedding for {nickname}: {e}")
        return {"exists": False, "dim": 0, "path": None}


def aggregate_metadata(metadata_dir: Path) -> dict:
    """
    Aggregate recognition stats across all video metadata files.

    Returns:
        Dict mapping contestant nickname -> {
            detection_count, avg_confidence, max_confidence, videos_seen_in
        }
    """
    stats: dict[str, dict] = {}

    for meta_file in sorted(metadata_dir.glob("*_metadata.json")):
        # Skip dense metadata files
        if "_dense_metadata" in meta_file.name:
            continue

        try:
            with open(meta_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping {meta_file.name}: {e}")
            continue

        video_name = meta_file.stem.replace("_metadata", "")
        timeline = data.get("contestant_timeline", {})

        for contestant_key, info in timeline.items():
            if contestant_key not in stats:
                stats[contestant_key] = {
                    "detection_count": 0,
                    "confidences": [],
                    "max_confidence": 0.0,
                    "videos_seen_in": [],
                }

            appearances = info.get("total_appearances", 0)
            avg_conf = info.get("avg_confidence", 0.0)
            max_conf = info.get("max_confidence", 0.0)

            stats[contestant_key]["detection_count"] += appearances
            if avg_conf > 0:
                stats[contestant_key]["confidences"].append(avg_conf)
            stats[contestant_key]["max_confidence"] = max(
                stats[contestant_key]["max_confidence"], max_conf
            )
            stats[contestant_key]["videos_seen_in"].append(video_name)

    # Compute averages
    for key, s in stats.items():
        confs = s.pop("confidences")
        s["avg_confidence"] = sum(confs) / len(confs) if confs else 0.0

    return stats


def classify_quality(has_embedding: bool, avg_confidence: float, detection_count: int) -> str:
    """Classify embedding quality as good/weak/missing."""
    if not has_embedding:
        return "missing"
    if avg_confidence >= 0.4 or detection_count >= 10:
        return "good"
    if avg_confidence >= 0.25 or detection_count >= 3:
        return "weak"
    return "weak"


def generate_coverage(
    csv_path: Path,
    embeddings_dir: Path,
    metadata_dir: Path,
) -> dict:
    """Generate the full coverage report."""
    contestants = load_contestants(csv_path)
    meta_stats = aggregate_metadata(metadata_dir)

    results = []
    good_count = 0
    weak_count = 0
    missing_count = 0
    total_confidence = 0.0
    conf_count = 0

    for c in contestants:
        emb = check_embedding(embeddings_dir, c["nickname"])

        # Look up metadata stats by nickname (primary key in contestant_timeline)
        m = meta_stats.get(c["nickname"], {
            "detection_count": 0,
            "avg_confidence": 0.0,
            "max_confidence": 0.0,
            "videos_seen_in": [],
        })

        quality = classify_quality(emb["exists"], m["avg_confidence"], m["detection_count"])

        if quality == "good":
            good_count += 1
        elif quality == "weak":
            weak_count += 1
        else:
            missing_count += 1

        if m["avg_confidence"] > 0:
            total_confidence += m["avg_confidence"]
            conf_count += 1

        results.append({
            "id": c["id"],
            "name": c["name"],
            "nickname": c["nickname"],
            "age": c["age"],
            "has_embedding": emb["exists"],
            "embedding_dim": emb["dim"],
            "avg_confidence": round(m["avg_confidence"], 4),
            "max_confidence": round(m["max_confidence"], 4),
            "detection_count": m["detection_count"],
            "videos_seen_in": len(m["videos_seen_in"]),
            "quality": quality,
        })

    # Recognition rate from all metadata
    total_detected = 0
    total_recognized = 0
    for meta_file in metadata_dir.glob("*_metadata.json"):
        if "_dense_metadata" in meta_file.name:
            continue
        try:
            with open(meta_file, encoding="utf-8") as f:
                data = json.load(f)
            rs = data.get("recognition_summary", {})
            total_detected += rs.get("total_faces_detected", 0)
            total_recognized += rs.get("total_faces_recognized", 0)
        except (json.JSONDecodeError, OSError):
            continue

    recognition_rate = total_recognized / total_detected if total_detected > 0 else 0.0

    return {
        "contestants": results,
        "summary": {
            "total": len(contestants),
            "good": good_count,
            "weak": weak_count,
            "missing": missing_count,
            "avg_confidence": round(total_confidence / conf_count, 4) if conf_count > 0 else 0.0,
            "recognition_rate": round(recognition_rate, 6),
            "total_faces_detected": total_detected,
            "total_faces_recognized": total_recognized,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate embedding coverage report")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to contestant_info.csv")
    parser.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS_DIR, help="Embeddings directory")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_DIR, help="Metadata directory")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output coverage.json path")
    args = parser.parse_args()

    logger.info(f"CSV: {args.csv}")
    logger.info(f"Embeddings: {args.embeddings}")
    logger.info(f"Metadata: {args.metadata}")

    coverage = generate_coverage(args.csv, args.embeddings, args.metadata)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(coverage, f, indent=2, ensure_ascii=False)

    s = coverage["summary"]
    logger.info(f"Coverage: {s['good']} good, {s['weak']} weak, {s['missing']} missing (of {s['total']})")
    logger.info(f"Avg confidence: {s['avg_confidence']}, Recognition rate: {s['recognition_rate']:.4%}")
    logger.info(f"Written to {args.output}")


if __name__ == "__main__":
    main()
