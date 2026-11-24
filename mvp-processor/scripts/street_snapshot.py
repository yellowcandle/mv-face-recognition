#!/usr/bin/env python3
"""
Regenerate the street-photo report's measurements from the source frames.

The viewer page `apps/viewer/src/pages/StreetPhotos.tsx` publishes counts and cosines that were
first produced by one-off scripts. Numbers a page publishes must be reproducible by the repo, so
this script owns them: it reads the frames, runs the same detector and matcher the reels go
through, and writes `streetPhotos.measurements.ts` (generated; do not hand-edit).

The frames themselves are **not** stored here — they are a stranger's photographs. The manifest
this script writes records each frame's source URL and sha256, so anyone can fetch the same bytes
and prove the numbers still hold:

    uv run python scripts/street_snapshot.py --frames <dir> [--out <file>] [--check]

`<dir>` must hold (see the manifest for the URLs each came from):

    paste-a.png   1085×814   the crossing frame as it appeared in a chat paste
    paste-b.png   1085×814   the queuing frame from the same paste
    original.jpg  4032×3024  the first photo of the Threads post, at full size
    post-2.jpg     640×480   second photo of the post, as served to a logged-out reader
    post-3.jpg     640×480   third photo, likewise

`--check` compares the freshly computed numbers with the committed module and exits 1 on any
difference, without writing. The page's prose (captions, replies) lives in `streetPhotos.data.ts`
and is not this script's business.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.face_detector import ContestantDatabase, create_face_app  # noqa: E402

# Thresholds. The site value is the measured 1% false-match boundary from
# `processing_config.yaml`; the job value is what this report was run at, and is the only number
# here that is a decision rather than a measurement.
JOB_THRESHOLD = 0.35
SWEEP_CUTOFFS = (0.25, 0.30, 0.35, 0.38, 0.412)

# The cast the post's replies identified, in the order given. `None` marks a face they could not
# place. Two entries are possibilities rather than identifications.
NAMED_ORDER = ["20", "22", "83", "2", "27", "15", "5", None, "78", None, "18"]
NAMED_MAYBE = {"14", "1"}  # Elka, Ivy So — named as possible in the thread

# VIVA's lineup, for the coverage note: how many of the group the 96-person roster can even hold a
# vector for.
VIVA_MEMBERS = ["姜咏鑫", "李晞彤", "馬思惠", "張鈊貽"]

FRAME_PASTE_A = "paste-a.png"
FRAME_PASTE_B = "paste-b.png"
FRAME_ORIGINAL = "original.jpg"
FRAME_POST_2 = "post-2.jpg"
FRAME_POST_3 = "post-3.jpg"
FRAME_POST_R1 = "post-r1.jpg"

SOURCES = {
    FRAME_ORIGINAL: "https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X (og:image, full size)",
    FRAME_POST_2: "https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X (second photo, 640px)",
    FRAME_POST_3: "https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X (third photo, 640px)",
    FRAME_POST_R1: "https://www.threads.com/@rinrinrin1666/post/DfzERn0k9HS (og:image, 1600px) — "
    "the same crossing frame as post_1, reposted",
    FRAME_PASTE_A: "same photograph as original.jpg, re-encoded at 1085 px by the paste",
    FRAME_PASTE_B: "same photograph as post-3.jpg, re-encoded at 1085 px by the paste",
}

# Minimum face size and tiling, exactly as the run that produced the published numbers used them.
# The two families of frame need different windows: the 1085 px paste keeps enough pixels per tile
# at a 220 px window, while the 640 px photos only resolve the group at 160 px.
MIN_FACE_PX = 20
PASTE_TILE = {"scale": 4, "window": 220, "stride": 150, "min_native": 10, "iou": 0.35}
SMALL_TILE = {"scale": 4, "window": 160, "stride": 110, "min_native": 8, "iou": 0.35}
# Region of each frame that holds the group, as a fraction of the frame. The queuing paste needs
# tiles too: its faces are 14×19 px, under `min_face_size`, so native detection finds none.
TILE_REGIONS = {
    FRAME_PASTE_B: (0.22, 0.33, 0.75, 0.62),
    FRAME_POST_2: (0.02, 0.24, 0.98, 0.72),
    FRAME_POST_3: (0.12, 0.30, 0.90, 0.55),
}
# The queuing paste and the post's photos are the same frames at different sizes; only the pastes
# feed the page's per-face tables, so only they are matched face by face below.
PASTE_FRAMES = (("一", FRAME_PASTE_A), ("二", FRAME_PASTE_B))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nms(items: list[dict[str, Any]], iou_threshold: float) -> list[dict[str, Any]]:
    """Keep the highest-scoring box of each overlapping cluster."""
    kept: list[dict[str, Any]] = []
    for candidate in sorted(items, key=lambda item: -item["det_score"]):
        box = candidate["box"]
        duplicate = False
        for other in kept:
            peers = other["box"]
            ix1, iy1 = max(box[0], peers[0]), max(box[1], peers[1])
            ix2, iy2 = min(box[2], peers[2]), min(box[3], peers[3])
            intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            union = (
                (box[2] - box[0]) * (box[3] - box[1])
                + (peers[2] - peers[0]) * (peers[3] - peers[1])
                - intersection
            )
            if union > 0 and intersection / union > iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept


def detect_native(app: Any, image: np.ndarray) -> list[dict[str, Any]]:
    """Faces the pipeline itself would accept: both sides at least `MIN_FACE_PX`."""
    found = []
    for face in app.get(image):
        x1, y1, x2, y2 = face.bbox
        if x2 - x1 < MIN_FACE_PX or y2 - y1 < MIN_FACE_PX:
            continue
        found.append(
            {"det_score": float(face.det_score), "embedding": face.normed_embedding, "box": [x1, y1, x2, y2]}
        )
    return found


def detect_tiled(
    app: Any,
    image: np.ndarray,
    region: tuple[float, float, float, float],
    tile: dict[str, float],
) -> list[dict[str, Any]]:
    """Slide a window over `region`, upscale each tile, then map boxes back to the frame."""
    height, width = image.shape[:2]
    x1, y1, x2, y2 = (
        int(region[0] * width),
        int(region[1] * height),
        int(region[2] * width),
        int(region[3] * height),
    )
    scale, window = tile["scale"], tile["window"]
    found = []
    ys = list(range(y1, max(y1 + 1, y2 - window + 1), tile["stride"])) or [y1]
    xs = list(range(x1, max(x1 + 1, x2 - window + 1), tile["stride"])) or [x1]
    for top in ys:
        for left in xs:
            patch_w, patch_h = min(window, x2 - left), min(window, y2 - top)
            patch = image[top : top + patch_h, left : left + patch_w]
            upscaled = cv2.resize(
                patch, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
            for face in app.get(upscaled):
                ax1, ay1, ax2, ay2 = [value / scale for value in face.bbox]
                if ax2 - ax1 < tile["min_native"] or ay2 - ay1 < tile["min_native"]:
                    continue
                found.append(
                    {
                        "det_score": float(face.det_score),
                        "embedding": face.normed_embedding,
                        "box": [ax1 + left, ay1 + top, ax2 + left, ay2 + top],
                    }
                )
    return nms(found, tile["iou"])


def faces_for(app: Any, path: Path) -> tuple[list[dict[str, Any]], str]:
    """Detected faces plus the mode that found them: the pipeline path, or tiles."""
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"cannot read {path}")
    native = detect_native(app, image)
    if len(native) >= 6 or path.name not in TILE_REGIONS:
        return sorted(native, key=lambda item: item["box"][0]), "native"
    tile = PASTE_TILE if path.name in (FRAME_PASTE_A, FRAME_PASTE_B) else SMALL_TILE
    tiled = detect_tiled(app, image, TILE_REGIONS[path.name], tile)
    return sorted(tiled, key=lambda item: item["box"][0]), "tiled 4x"


def per_contestant_best(references: np.ndarray, ids: np.ndarray, embedding: np.ndarray) -> list[tuple[str, float]]:
    """Every contestant's best cosine against one face, best first (max over their reference set)."""
    similarity = references @ embedding
    best: dict[str, float] = {}
    for contestant, score in zip(ids, similarity):
        key = str(contestant)
        best[key] = max(best.get(key, -1.0), float(score))
    return sorted(best.items(), key=lambda item: -item[1])


def box_fraction(box: list[float], width: int, height: int) -> list[float]:
    return [
        round(float(min(max(box[0] / width, 0.0), 1.0)), 4),
        round(float(min(max(box[1] / height, 0.0), 1.0)), 4),
        round(float(min(max(box[2] / width, 0.0), 1.0)), 4),
        round(float(min(max(box[3] / height, 0.0), 1.0)), 4),
    ]


def face_rows(
    faces: list[dict[str, Any]],
    width: int,
    height: int,
    references,
    ids,
    database: ContestantDatabase,
) -> list[dict[str, Any]]:
    rows = []
    for index, face in enumerate(faces, start=1):
        ranked = per_contestant_best(references, ids, face["embedding"])
        top_id, top_score = ranked[0]
        runner_up = ranked[1][1]
        rows.append(
            {
                "i": index,
                "box": box_fraction(face["box"], width, height),
                "px": [int(face["box"][2] - face["box"][0]), int(face["box"][3] - face["box"][1])],
                "det_score": round(face["det_score"], 3),
                "top1": round(top_score, 3),
                "top2": round(runner_up, 3),
                "margin": round(top_score - runner_up, 3),
                "candidate": (
                    {
                        "id": top_id,
                        "name": database.contestants_info[top_id]["name"],
                        "nickname": database.contestants_info[top_id]["nickname"],
                    }
                    if top_score >= JOB_THRESHOLD
                    else None
                ),
            }
        )
    return rows


def sweep(references: np.ndarray, ids: np.ndarray) -> list[dict[str, float]]:
    """Share of references whose best score against a *different* contestant reaches each cutoff."""
    similarity = references @ references.T
    same = ids[:, None] == ids[None, :]
    np.fill_diagonal(similarity, -9.0)
    impostor = np.where(same, -9.0, similarity).max(axis=1)
    return [
        {"cutoff": cutoff, "rate": round(float((impostor >= cutoff).mean()), 4)}
        for cutoff in SWEEP_CUTOFFS
    ]


def face_size_ceiling(app: Any, path: Path) -> list[dict[str, float]]:
    """Self-similarity of one face re-embedded after the frame is downsampled to that height."""
    from insightface.utils import face_align

    image = cv2.imread(str(path))
    recognition = app.models["recognition"]
    faces = [face for face in sorted(app.get(image), key=lambda f: -f.det_score)[:10] if face.det_score > 0.75]
    rows = []
    for target_height in (49, 32, 24, 18, 12):
        scores = []
        for face in faces:
            face_height = face.bbox[3] - face.bbox[1]
            ratio = target_height / face_height
            small = cv2.resize(image, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_AREA)
            aligned = face_align.norm_crop(small, landmark=face.kps * ratio, image_size=112)
            vector = recognition.get_feat(aligned).flatten()
            vector = vector / np.linalg.norm(vector)
            scores.append(float(np.dot(vector, face.normed_embedding)))
        rows.append(
            {
                "height": target_height,
                "mean": round(float(np.mean(scores)), 3),
                "min": round(float(np.min(scores)), 3),
            }
        )
    return rows


def matcher_check(references: np.ndarray, ids: np.ndarray, threshold: float) -> dict[str, float]:
    """Held-out genuine and impostor scores over 200 sampled references (fixed seed)."""
    rng = np.random.default_rng(0)
    genuine, impostor = [], []
    for index in rng.choice(len(references), 200, replace=False):
        similarity = references @ references[index]
        similarity[index] = -9.0
        own = similarity[ids == ids[index]]
        genuine.append(float(own.max()) if own.size and np.isfinite(own).any() else float("nan"))
        impostor.append(float(similarity[ids != ids[index]].max()))
    genuine = np.array([score for score in genuine if np.isfinite(score)])
    impostor = np.array(impostor)
    return {
        "genuineMean": round(float(genuine.mean()), 3),
        "genuineP05": round(float(np.percentile(genuine, 5)), 3),
        "genuineAboveThreshold": round(float((genuine > threshold).mean()), 3),
        "impostorMax": round(float(impostor.max()), 3),
        "impostorAboveThreshold": round(float((impostor > threshold).mean()), 3),
    }


def open_top_one(images: list[dict[str, Any]], references, ids, db) -> dict[str, Any]:
    """Where an unrestrained best-match lands: how many distinct names 23 faces produce."""
    labels, times = [], {}
    for image in images:
        for face in image["faces"]:
            ranked = per_contestant_best(references, ids, face["embedding"])
            nickname = db.contestants_info[ranked[0][0]]["nickname"]
            labels.append(nickname)
            times[nickname] = times.get(nickname, 0) + 1
    repeated = [{"nickname": name, "times": count} for name, count in times.items() if count > 1]
    repeated.sort(key=lambda item: (-item["times"], item["nickname"]))
    return {"boxes": len(labels), "distinct": len(set(labels)), "repeated": repeated}


def posed_section(app, path: Path, references, ids, database, threshold: float) -> dict:
    """A single frame measured on its own, for photos that are not part of the resolution ladder.

    Faces are called what they are: a **recognition** at or above the site threshold, a
    **candidate** above the job threshold, and nothing worth printing below that.
    """
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"cannot read {path}")
    height, width = image.shape[:2]
    native = detect_native(app, image)
    faces, mode = (native, "native") if len(native) >= 6 else (
        detect_tiled(app, image, (0.0, 0.0, 1.0, 1.0), SMALL_TILE),
        "tiled 4x",
    )
    faces.sort(key=lambda item: item["box"][0])
    rows = []
    for index, face in enumerate(faces, start=1):
        ranked = per_contestant_best(references, ids, face["embedding"])
        top_id, top_score = ranked[0]
        info = database.contestants_info[top_id]
        rows.append(
            {
                "i": index,
                "box": box_fraction(face["box"], width, height),
                "px": [int(face["box"][2] - face["box"][0]), int(face["box"][3] - face["box"][1])],
                "det_score": round(float(face["det_score"]), 3),
                "score": round(top_score, 3),
                "id": top_id,
                "name": info["name"],
                "nickname": info["nickname"],
                "verdict": "recognition" if top_score >= threshold else (
                    "candidate" if top_score >= JOB_THRESHOLD else "none"
                ),
            }
        )
    return {
        "width": width,
        "height": height,
        "mode": mode,
        "faces": rows,
        "recognitionCount": sum(1 for row in rows if row["verdict"] == "recognition"),
        "candidateCount": sum(1 for row in rows if row["verdict"] != "none"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--frames",
        type=Path,
        required=False,
        help="directory holding the five source frames (not needed with --posed)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "apps/viewer/src/pages/streetPhotos.measurements.ts",
        help="generated module to write",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "apps/viewer/src/pages/streetPhotos.fixtures.json",
        help="source URLs and hashes for the frames this run used",
    )
    parser.add_argument("--check", action="store_true", help="diff against the committed module; write nothing")
    parser.add_argument(
        "--posed",
        type=Path,
        default=None,
        help="a stand-alone frame to measure (a posed group shot, say); emits its own module instead "
        "of the ladder, so an ephemeral frame never blocks regenerating the rest",
    )
    parser.add_argument(
        "--posed-out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "apps/viewer/src/pages/streetPhotos.posed.ts",
    )
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/processing_config.yaml")
    parser.add_argument(
        "--gallery-label",
        default=None,
        help="stable name for --gallery in the fixtures (a bucket URI, say). Without it the path is "
        "recorded, which is wrong for a file outside the repo: the sha256 is the identity, the "
        "label is where to fetch it.",
    )
    parser.add_argument(
        "--gallery",
        type=Path,
        default=None,
        help="reference_embeddings.npz to measure against; defaults to the one in the config's "
        "photo_dir. Point this at the deployed cache (bucket models/reference) to publish numbers "
        "that describe what the site actually serves, not what this machine happens to hold.",
    )
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    database = ContestantDatabase(config)
    database.load_contestants_info()
    # Load the gallery directly rather than through `build_face_encodings`, which refuses a cache
    # whose manifest count disagrees with the file. That gate is right for a reel run — matching
    # against a half-rebuilt gallery is how a reel gets silently wrong names — but this script
    # snapshots a gallery and records its hash, so the counts are evidence, not a precondition.
    gallery_path = args.gallery or (Path(config["contestants"]["photo_dir"]) / "reference_embeddings.npz")
    with np.load(gallery_path, allow_pickle=False) as cache:
        if "embeddings" not in cache.files or "contestant_ids" not in cache.files:
            raise SystemExit(
                f"{gallery_path} is not a reference cache: it holds {sorted(cache.files)}.\n"
                "Rebuild it with mvp-processor/scripts/build_reference_cache.py, or point --config "
                "at a config whose contestants.photo_dir holds the cache these numbers came from. "
                "Refusing to publish cosines measured against a different gallery."
            )
        references = np.asarray(cache["embeddings"], dtype=np.float32)
        ids = np.asarray(cache["contestant_ids"]).astype(str)
    database.face_encodings = {
        contestant: references[ids == contestant] for contestant in np.unique(ids)
    }
    database.flatten_references()
    gallery_digest = sha256(gallery_path)
    manifest_path = gallery_path.with_name("reference_manifest.json")
    if manifest_path.exists():
        recorded = json.loads(manifest_path.read_text()).get("reference_count")
        if recorded != len(references):
            print(
                f"warning: {manifest_path.name} records {recorded} references but the cache holds "
                f"{len(references)}; the numbers below describe the cache, not the manifest",
                file=sys.stderr,
            )
    site_threshold = float(config["face_recognition"]["acceptance_threshold"])
    app = create_face_app(["CPUExecutionProvider"])

    if args.posed is None and args.frames is None:
        raise SystemExit("either --frames or --posed is required")

    if args.posed is not None:
        section = posed_section(app, args.posed, references, ids, database, site_threshold)
        import hashlib as _hash

        digest = _hash.sha256(args.posed.read_bytes()).hexdigest()
        rendered = render_posed(section, digest)
        if args.check:
            current = args.posed_out.read_text() if args.posed_out.exists() else ""
            if _literals(current) != _literals(rendered):
                print(f"{args.posed_out} is out of date", file=sys.stderr)
                return 1
            print(f"{args.posed_out} matches a fresh run")
            return 0
        args.posed_out.write_text(rendered)
        print(f"wrote {args.posed_out} ({len(section['faces'])} faces, "
              f"{section['recognitionCount']} recognition, {section['candidateCount']} candidate)")
        return 0

    paths = {name: args.frames / name for name in SOURCES}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise SystemExit("missing frames:\n  " + "\n  ".join(missing))

    # Per-face tables come from the two pastes: the sizes the page's figures actually show.
    images = []
    for tag, name in PASTE_FRAMES:
        path = paths[name]
        faces, mode = faces_for(app, path)
        with_image = cv2.imread(str(path))
        height, width = with_image.shape[:2]
        images.append(
            {
                "key": "a" if tag == "一" else "b",
                "file": "frame-1.jpg" if tag == "一" else "frame-2.jpg",
                "mode": mode,
                "width": width,
                "height": height,
                "faces": face_rows(faces, width, height, references, ids, database),
                "raw": faces,
                "image": with_image,
            }
        )

    all_faces = [face for image in images for face in image["raw"]]
    matrix = np.asarray([face["embedding"] for face in all_faces])

    # Named cast, scored over every face of both pastes.
    best_per_contestant = {}
    for contestant in np.unique(ids):
        rows = references[ids == contestant]
        best_per_contestant[str(contestant)] = float((matrix @ rows.T).max())
    ranked_contestants = sorted(best_per_contestant.items(), key=lambda item: -item[1])
    rank_of = {contestant: place + 1 for place, (contestant, _) in enumerate(ranked_contestants)}
    named_ids = [contestant for contestant in NAMED_ORDER if contestant]
    not_named = [score for contestant, score in best_per_contestant.items() if contestant not in named_ids]
    noise = {
        "mean": round(float(np.mean(not_named)), 3),
        "p90": round(float(np.percentile(not_named, 90)), 3),
        "max": round(float(np.max(not_named)), 3),
    }

    named_rows = []
    # One entry per face across both pastes, so a global best-scoring face maps back to its frame.
    face_positions = [
        (letter, number, face)
        for letter, image in zip("一二", images)
        for number, face in enumerate(image["raw"], start=1)
    ]
    for contestant in sorted(set(named_ids) | NAMED_MAYBE, key=lambda item: -best_per_contestant[item]):
        scores = matrix @ references[ids == contestant].T
        best_face = int(scores.max(axis=1).argmax())
        letter, number, face = face_positions[best_face]
        info = database.contestants_info[contestant]
        named_rows.append(
            {
                "id": contestant,
                "nickname": info["nickname"],
                "name": info["name"],
                "best": round(float(scores.max()), 3),
                "rank": rank_of[contestant],
                "face": f"{letter}-{number}",
                "px": [int(face["box"][2] - face["box"][0]), int(face["box"][3] - face["box"][1])],
                "aboveNoise": bool(best_per_contestant[contestant] > noise["p90"]),
                "maybe": contestant in NAMED_MAYBE,
            }
        )

    # 12 MP original against the same people in the paste: does more resolution move the score?
    original_faces, _ = faces_for(app, paths[FRAME_ORIGINAL])
    original_matrix = np.asarray([face["embedding"] for face in original_faces])
    original_best = {}
    for contestant in np.unique(ids):
        rows = references[ids == contestant]
        original_best[str(contestant)] = float((original_matrix @ rows.T).max())
    # The same photograph at three served sizes: 1085 px paste, a 1600 px repost, the 4032 px
    # original. Two of the four people are recognisable enough to anchor the comparison; the other
    # two show what box placement alone does to a score.
    ladder_faces, _ = faces_for(app, paths[FRAME_POST_R1])
    ladder_matrix = np.asarray([face["embedding"] for face in ladder_faces])
    rungs = [
        ("1085 px 截圖", images[0]["width"], len(images[0]["raw"]), [f["box"] for f in images[0]["raw"]], matrix),
        ("1600 px 轉貼", int(cv2.imread(str(paths[FRAME_POST_R1])).shape[1]), len(ladder_faces), [f["box"] for f in ladder_faces], ladder_matrix),
        ("4032 px 原檔", int(cv2.imread(str(paths[FRAME_ORIGINAL])).shape[1]), len(original_faces), [f["box"] for f in original_faces], original_matrix),
    ]
    ladder_people = ("22", "15", "83", "2")
    ladder_rows = []
    for contestant in ladder_people:
        scores = []
        for _, _, _, _, gallery in rungs:
            best = float((gallery @ references[ids == contestant].T).max()) if len(gallery) else 0.0
            scores.append(round(best, 3))
        ladder_rows.append(
            {"nickname": database.contestants_info[contestant]["nickname"], "scores": scores}
        )
    ladder_frames = []
    for label, width, count, boxes, _ in rungs:
        widths = [int(box[2] - box[0]) for box in boxes] or [0]
        ladder_frames.append(
            {"label": label, "width": width, "faces": count, "facePx": f"{min(widths)}–{max(widths)}"}
        )


    # The post's three photos as a logged-out reader receives them.
    post_rows = []
    for number, name in ((1, FRAME_ORIGINAL), (2, FRAME_POST_2), (3, FRAME_POST_3)):
        faces = original_faces if name == FRAME_ORIGINAL else faces_for(app, paths[name])[0]
        embedding_matrix = np.asarray([face["embedding"] for face in faces])
        best = (
            max(
                float((embedding_matrix @ references[ids == contestant].T).max())
                for contestant in np.unique(ids)
            )
            if len(faces)
            else 0.0
        )
        widths = [int(face["box"][2] - face["box"][0]) for face in faces] or [0]
        height, width = cv2.imread(str(paths[name])).shape[:2]
        post_rows.append(
            {
                "n": number,
                "served": f"{width}×{height}",
                "faces": len(faces),
                "facePx": f"{min(widths)}–{max(widths)}",
                "best": round(best, 3),
            }
        )

    in_roster = sum(
        1
        for member in VIVA_MEMBERS
        if any(info["name"] == member for info in database.contestants_info.values())
    )

    measurements = {
        "JOB_THRESHOLD": JOB_THRESHOLD,
        "SITE_THRESHOLD": site_threshold,
        "REFERENCE_COUNT": int(len(references)),
        "CONTESTANT_COUNT": int(len(set(ids))),
        "STREET_IMAGES": [
            {
                "key": image["key"],
                "mode": image["mode"],
                "width": image["width"],
                "height": image["height"],
                "faces": image["faces"],
            }
            for image in images
        ],
        "CUTOFF_SWEEP": sweep(references, ids),
        "FACE_SIZE_CEILING": face_size_ceiling(app, paths[FRAME_PASTE_A]),
        "MATCHER_CHECK": matcher_check(references, ids, site_threshold),
        "NAMED_PRESENT": named_rows,
        "ROSTER_NOISE": noise,
        "OPEN_TOP1": open_top_one(
            [{"faces": image["raw"]} for image in images], references, ids, database
        ),
        "RESOLUTION_LADDER": {"frames": ladder_frames, "rows": ladder_rows},
        "POST_PHOTOS": post_rows,
        "VIVA_COVERAGE": {"members": len(VIVA_MEMBERS), "inRoster": in_roster},
    }

    manifest = {
        "note": "Frames are not committed: they are a third party's photographs. Fetch these URLs, "
        "check the sha256, then run scripts/street_snapshot.py --frames <dir>.",
        # The gallery decides every cosine here, and it is rebuilt independently of this page, so
        # the snapshot names the exact vector file it measured.
        "gallery": {
            "label": args.gallery_label or _describe_gallery(gallery_path),
            "sha256": gallery_digest,
            "measured_from": "the file given by --gallery" if args.gallery else "the config's photo_dir",
            "reference_count": int(len(references)),
            "contestant_count": int(len(set(ids))),
        },
        "frames": [
            {"name": name, "source": SOURCES[name], "sha256": sha256(paths[name])}
            for name in SOURCES
        ],
    }

    rendered = render_module(measurements)
    if args.check:
        current = args.out.read_text() if args.out.exists() else ""
        # The committed module is reformatted by the app's formatter (`vp check --fix`), which
        # reflows lines and adds trailing commas, so comparing text reports layout as a stale
        # number. Compare the literals instead: same values in the same order, whatever the layout.
        current_tokens, fresh_tokens = _literals(current), _literals(rendered)
        if current_tokens != fresh_tokens:
            diff = _first_literal_differences(current_tokens, fresh_tokens)
            print(
                f"{args.out} is out of date (values or layout):\n{diff}\n"
                "Re-run without --check to rewrite it, then re-format the module.",
                file=sys.stderr,
            )
            return 1
        print(f"{args.out} matches a fresh run")
        return 0

    args.out.write_text(rendered)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {args.out} and {args.manifest}")
    return 0


def render_posed(section: dict[str, Any], digest: str) -> str:
    out = [
        "/**",
        " * A posed group shot, measured on its own. **Generated by mvp-processor/scripts/street_snapshot.py --posed.**",
        " * Do not hand-edit. The frame is not committed; this sha256 identifies it.",
        f" * frame sha256: {digest}",
        " */",
        "",
        "import type { PosedFrame } from './streetPhotos.data';",
        "",
        "export const POSED_FRAME: PosedFrame = {",
        f"  width: {section['width']},",
        f"  height: {section['height']},",
        f"  mode: '{section['mode']}',",
        f"  recognitionCount: {section['recognitionCount']},",
        f"  candidateCount: {section['candidateCount']},",
        "  faces: [",
    ]
    for face in section["faces"]:
        out.append(
            "    {{ i: {i}, box: [{b}], px: [{w}, {h}], det_score: {d}, score: {s}, id: '{cid}', "
            "name: '{name}', nickname: '{nick}', verdict: '{verdict}' }},".format(
                i=face["i"],
                b=", ".join(
                    f"{value:.4f}".rstrip("0").rstrip(".") for value in face["box"]
                ),
                w=face["px"][0],
                h=face["px"][1],
                d=face["det_score"],
                s=face["score"],
                cid=face["id"],
                name=face["name"],
                nick=face["nickname"],
                verdict=face["verdict"],
            )
        )
    out.append("  ],")
    out.append("};")
    out.append("")
    return "\n".join(out)


def _describe_gallery(path: Path) -> str:
    """A name that survives the machine: repo-relative when it can, the bare name otherwise."""
    repo = Path(__file__).resolve().parents[2]
    try:
        return str(path.resolve().relative_to(repo))
    except ValueError:
        return path.name


def _literals(text: str) -> list[str]:
    """Numbers and quoted strings, in order — the payload of a generated data module.

    Comments go first: an apostrophe in prose ("a third party's photographs") would otherwise
    pair with a real string literal and swallow the code between them.
    """
    import re

    code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return re.findall(r"-?\d+\.?\d*|'[^'\n]*'|\"[^\"\n]*\"", code)


def _first_literal_differences(current: list[str], fresh: list[str], limit: int = 6) -> str:
    for index, (left, right) in enumerate(zip(current, fresh)):
        if left != right:
            return f"  literal #{index}: committed {left} vs fresh {right}"
    if len(current) != len(fresh):
        return f"  committed has {len(current)} literals, fresh has {len(fresh)}"
    return "  literals match but their order differs"


def render_module(measurements: dict[str, Any]) -> str:
    """Emit the measurements module. Data only: the prose lives in streetPhotos.data.ts."""
    out = [
        "/**",
        " * Street-photo measurements. **Generated by mvp-processor/scripts/street_snapshot.py.**",
        " * Do not hand-edit: re-run the script. The frames it reads are a third party's photographs",
        " * and are not committed; streetPhotos.fixtures.json records their sources and hashes.",
        " *",
        " * Thresholds are the only decided values (SITE_THRESHOLD comes from",
        " * processing_config.yaml); everything else is measured.",
        " */",
        "",
        "import type { MeasuredImage, NamedContestant } from './streetPhotos.data';",
        "",
        f"export const JOB_THRESHOLD = {measurements['JOB_THRESHOLD']!r};",
        f"export const SITE_THRESHOLD = {measurements['SITE_THRESHOLD']!r};",
        "",
        f"export const REFERENCE_COUNT = {measurements['REFERENCE_COUNT']};",
        f"export const CONTESTANT_COUNT = {measurements['CONTESTANT_COUNT']};",
        "",
        "export const STREET_IMAGES: MeasuredImage[] = [",
    ]
    for image in measurements["STREET_IMAGES"]:
        out.append("  {")
        out.append(f"    key: '{image['key']}',")
        out.append(f"    mode: '{image['mode']}',")
        out.append(f"    width: {image['width']},")
        out.append(f"    height: {image['height']},")
        out.append("    faces: [")
        for face in image["faces"]:
            candidate = (
                "{{ id: '{id}', name: '{name}', nickname: '{nickname}' }}".format(**face["candidate"])
                if face["candidate"]
                else "null"
            )
            out.append(
                "      {{ i: {i}, box: [{b}], px: [{w}, {h}], det_score: {d}, top1: {t1}, "
                "top2: {t2}, margin: {m}, candidate: {c} }},".format(
                    i=face["i"],
                    # No trailing zeros: the app's formatter strips them, and `--check` compares
                    # literals, so `0.1860` and `0.186` must not count as a stale number.
                    b=", ".join(
                        f"{value:.4f}".rstrip("0").rstrip(".") for value in face["box"]
                    ),
                    w=face["px"][0],
                    h=face["px"][1],
                    d=face["det_score"],
                    t1=face["top1"],
                    t2=face["top2"],
                    m=face["margin"],
                    c=candidate,
                )
            )
        out.append("    ],")
        out.append("  },")
    out.append("];")
    out.append("")
    out.append("export const CUTOFF_SWEEP = [")
    for row in measurements["CUTOFF_SWEEP"]:
        out.append(f"  {{ cutoff: {row['cutoff']}, rate: {row['rate']} }},")
    out.append("];")
    out.append("")
    out.append("export const FACE_SIZE_CEILING = [")
    for row in measurements["FACE_SIZE_CEILING"]:
        out.append(f"  {{ height: {row['height']}, mean: {row['mean']}, min: {row['min']} }},")
    out.append("];")
    out.append("")
    check = measurements["MATCHER_CHECK"]
    out.append("export const MATCHER_CHECK = {")
    for key in ("genuineMean", "genuineP05", "genuineAboveThreshold", "impostorMax", "impostorAboveThreshold"):
        out.append(f"  {key}: {check[key]},")
    out.append("};")
    out.append("")
    out.append("export const NAMED_PRESENT: NamedContestant[] = [")
    for row in measurements["NAMED_PRESENT"]:
        out.append(
            "  {{ id: '{id}', nickname: '{nickname}', name: '{name}', best: {best}, rank: {rank}, "
            "face: '{face}', px: [{w}, {h}], aboveNoise: {above}, maybe: {maybe} }},".format(
                id=row["id"],
                nickname=row["nickname"],
                name=row["name"],
                best=row["best"],
                rank=row["rank"],
                face=row["face"],
                w=row["px"][0],
                h=row["px"][1],
                above="true" if row["aboveNoise"] else "false",
                maybe="true" if row["maybe"] else "false",
            )
        )
    out.append("];")
    out.append("")
    noise = measurements["ROSTER_NOISE"]
    out.append(
        f"export const ROSTER_NOISE = {{ mean: {noise['mean']}, p90: {noise['p90']}, max: {noise['max']} }};"
    )
    out.append("")
    open_top = measurements["OPEN_TOP1"]
    out.append("export const OPEN_TOP1 = {")
    out.append(f"  boxes: {open_top['boxes']},")
    out.append(f"  distinct: {open_top['distinct']},")
    out.append("  repeated: [")
    for row in open_top["repeated"]:
        out.append(f"    {{ nickname: '{row['nickname']}', times: {row['times']} }},")
    out.append("  ],")
    out.append("};")
    out.append("")
    ladder = measurements["RESOLUTION_LADDER"]
    out.append("export const RESOLUTION_LADDER = {")
    out.append("  frames: [")
    for frame in ladder["frames"]:
        out.append(
            "    {{ label: '{label}', width: {width}, faces: {faces}, facePx: '{facePx}' }},".format(
                **frame
            )
        )
    out.append("  ],")
    out.append("  rows: [")
    for row in ladder["rows"]:
        out.append(
            "    {{ nickname: '{}', scores: [{}] }},".format(
                row["nickname"], ", ".join(str(score) for score in row["scores"])
            )
        )
    out.append("  ],")
    out.append("};")
    out.append("")
    out.append("export const POST_PHOTOS = [")
    for row in measurements["POST_PHOTOS"]:
        out.append(
            "  {{ n: {n}, served: '{served}', faces: {faces}, facePx: '{px}', best: {best} }},".format(
                n=row["n"], served=row["served"], faces=row["faces"], px=row["facePx"], best=row["best"]
            )
        )
    out.append("];")
    out.append("")
    coverage = measurements["VIVA_COVERAGE"]
    out.append(
        f"export const VIVA_COVERAGE = {{ members: {coverage['members']}, inRoster: {coverage['inRoster']} }};"
    )
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())
