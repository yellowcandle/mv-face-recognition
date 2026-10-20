"""
Contract checks on stored face metadata.

These guard the two things that broke real consumers and are invisible in a summary count:

  - **frame fractions**: every stored box is a proportion of the frame, in canonical
    [x1, y1, x2, y2] order, so no consumer needs a width to place it. See
    docs/adr/0002-face-boxes-are-frame-fractions.md.
  - **raw cosines**: `match_score` is the cosine itself (higher = more similar) and `det_score`
    is the detector's own face confidence, for every detection, matched or not.

Plus the rendition check: every processed rendition must keep the source's aspect ratio, or a
fractional box lands somewhere else in it. That is what catches a future rendition that
letterboxes instead of scaling.

The pipeline writes metadata to `local_output/metadata/`. Files written before this contract
exist (they carry no `recognition_config.acceptance_threshold`) and are reported as stale rather
than asserted against — the ticket that settled this decided to regenerate, not migrate.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, "mvp-processor")

REPO_ROOT = Path(__file__).resolve().parents[3]
METADATA_DIR = REPO_ROOT / "local_output" / "metadata"
PROCESSED_DIR = REPO_ROOT / "local_output" / "processed_videos"
SOURCE_DIR = REPO_ROOT / "source" / "videos"

# Names the contract deleted. Their reappearance means a writer regressed.
DELETED_KEYS = {"face_location", "confidence", "match_confidence", "detection_confidence",
                "recognition_confidence", "recognitions", "confidence_stats"}


def _current_metadata_files():
    """Metadata files written under the current contract, as (video_name, data)."""
    if not METADATA_DIR.exists():
        return []
    current = []
    for path in sorted(METADATA_DIR.glob("*_metadata.json")):
        if "_dense_" in path.name:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "acceptance_threshold" in data.get("recognition_config", {}):
            current.append((path.stem[: -len("_metadata")], data))
    return current


_CURRENT = _current_metadata_files()
_VIDEO_IDS = [video_id for video_id, _ in _CURRENT]

# A pre-014 file is not a failure of this contract, but it is worth saying out loud.
_STALE = sorted(
    p.stem[: -len("_metadata")]
    for p in (METADATA_DIR.glob("*_metadata.json") if METADATA_DIR.exists() else [])
    if "_dense_" not in p.name
    and p.stem[: -len("_metadata")] not in _VIDEO_IDS
)


def _probe_dimensions(path: Path):
    """(width, height) of a video file, or None when ffprobe is unavailable.

    A file ffprobe *cannot* read is a failure, not a skip: mid-reprocess is the only benign
    reason for it, so run this after the pipeline has finished writing.
    """
    if not shutil.which("ffprobe"):
        return None
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0 and result.stdout.strip(), (
        f"ffprobe could not read {path}: {result.stderr.strip()[:200]}"
    )
    width, height = result.stdout.strip().split("x")[:2]
    return int(width), int(height)


@pytest.fixture(scope="module")
def metadata():
    if not _CURRENT:
        pytest.skip(
            f"No metadata under {METADATA_DIR} carries the current contract. "
            f"Reprocess a video first (stale files: {_STALE})."
        )
    return _CURRENT


@pytest.mark.unit
class TestStoredContract:

    def test_every_box_is_a_frame_fraction(self, metadata):
        """Boxes are proportions of the frame, in order, with positive extent."""
        for video_id, data in metadata:
            boxes = _all_boxes(data)
            assert boxes, f"{video_id} stores no boxes at all"
            for box, where in boxes:
                assert len(box) == 4, f"{video_id}: {where} has {len(box)} values"
                assert all(isinstance(v, (int, float)) for v in box), f"{video_id}: {where} not numeric"
                assert 0.0 <= box[0] < box[2] <= 1.0, f"{video_id}: {where} x range {box}"
                assert 0.0 <= box[1] < box[3] <= 1.0, f"{video_id}: {where} y range {box}"

    def test_no_deleted_key_survives(self, metadata):
        """The names the contract deleted must not come back."""
        for video_id, data in metadata:
            found = sorted(DELETED_KEYS & set(_walk_keys(data)))
            assert not found, f"{video_id} still carries deleted keys: {found}"

    def test_detections_carry_every_face_with_both_scores(self, metadata):
        """Matched or not, each detection has a bbox and its detector score."""
        for video_id, data in metadata:
            threshold = data["recognition_config"]["acceptance_threshold"]
            for frame in data["frame_data"]:
                detections = frame["detections"]
                assert len(detections) == frame["detections_count"], (
                    f"{video_id} frame {frame['frame_number']}: "
                    f"{len(detections)} detections stored, {frame['detections_count']} detected"
                )
                for detection in detections:
                    assert detection["det_score"] is not None, "det_score is the only score an unmatched detection has"
                    if detection["contestant_id"] is None:
                        assert detection["match_score"] is None, "an unmatched detection has no match score"
                    else:
                        assert detection["match_score"] > threshold, (
                            f"a recognition is stored below the acceptance threshold "
                            f"({detection['match_score']} <= {threshold})"
                        )

    def test_timeline_agrees_with_frame_data(self, metadata):
        """Every recognition appears in the timeline, at the same score."""
        for video_id, data in metadata:
            stored = sorted(
                (d["match_score"], d["contestant_id"])
                for frame in data["frame_data"]
                for d in frame["detections"]
                if d["contestant_id"] is not None
            )
            timeline = sorted(
                (a["match_score"], contestant_id)
                for contestant_id, entry in data["contestant_timeline"].items()
                for a in entry["appearances"]
            )
            assert timeline == stored, f"{video_id}: timeline and frame_data disagree"
            assert len(timeline) == data["processing_summary"]["total_recognitions"]

    def test_renditions_keep_the_source_aspect_ratio(self, metadata):
        """A letterboxed rendition would move every fractional box; catch it here."""
        checked = 0
        for video_id, data in metadata:
            video_info = data["video_info"]
            source_ratio = video_info["width"] / video_info["height"]
            renditions = [SOURCE_DIR / f"{video_id}.mp4"] + sorted(PROCESSED_DIR.glob(f"{video_id}_*.mp4"))
            for path in renditions:
                if not path.exists():
                    continue
                dimensions = _probe_dimensions(path)
                if dimensions is None:
                    pytest.skip("ffprobe unavailable — cannot check rendition geometry")
                width, height = dimensions
                checked += 1
                assert abs(width / height - source_ratio) < 0.01, (
                    f"{path.name} is {width}x{height} ({width / height:.3f}), but the stored boxes "
                    f"assume the source ratio {source_ratio:.3f}"
                )
        assert checked, "no rendition was found to check"
        if _STALE:
            print(f"NOTE: stale pre-contract metadata present for {_STALE}; regenerate to cover it")


    def test_renditions_place_the_same_box_on_the_same_face(self, metadata):
        """The same stored box crops the same face out of every rendition.

        Aspect ratios matching is necessary but not sufficient; this compares the actual pixels.
        If a consumer or rendition disagreed about scale, these crops would be different regions
        and the difference would jump (identical regions land around 2-3% after re-encoding).
        """
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            pytest.skip("ffmpeg/ffprobe unavailable — cannot compare renditions pixel-wise")

        for video_id, data in metadata:
            renditions = [SOURCE_DIR / f"{video_id}.mp4"] + sorted(PROCESSED_DIR.glob(f"{video_id}_*.mp4"))
            renditions = [path for path in renditions if path.exists()]
            if len(renditions) < 2:
                continue

            frame = _busiest_frame(data)
            assert frame is not None, f"{video_id}: no frame with a detection to sample"
            timestamp = frame["timestamp"]

            crops = {}
            for path in renditions:
                image = _frame_at(path, timestamp)
                height, width = image.shape[:2]
                crops[path.name] = [
                    cv2.resize(
                        image[
                            int(d["bbox"][1] * height):int(d["bbox"][3] * height),
                            int(d["bbox"][0] * width):int(d["bbox"][2] * width),
                        ],
                        (64, 64),
                    ).astype("float32")
                    for d in frame["detections"]
                ]

            reference_name = renditions[0].name
            for name, per_box in crops.items():
                if name == reference_name:
                    continue
                for crop, expected, detection in zip(per_box, crops[reference_name], frame["detections"]):
                    difference = float(abs(crop - expected).mean())
                    assert difference < 60, (
                        f"{video_id}: {name} shows a different region for "
                        f"{detection.get('contestant_nickname') or 'an unmatched detection'} at "
                        f"{timestamp:.2f}s than {reference_name} does (mean abs difference "
                        f"{difference:.1f} of 255) — the box does not mean the same place"
                    )


def _busiest_frame(data):
    """The stored frame with the most detections, so the sample is not a lone face."""
    frames = [f for f in data.get("frame_data", []) if f.get("detections")]
    if not frames:
        return None
    return max(frames, key=lambda f: len(f["detections"]))


def _frame_at(path: Path, timestamp: float):
    """Decode one frame of a video at a timestamp, as a BGR array."""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True,
    )
    assert result.returncode == 0, f"ffmpeg could not decode {path}: {result.stderr.decode()[:200]}"
    image = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None, f"ffmpeg produced no frame for {path} at {timestamp}s"
    return image


def _all_boxes(data):
    """Every stored box, with a label saying where it came from."""
    for frame in data.get("frame_data", []):
        for i, detection in enumerate(frame.get("detections", [])):
            yield detection.get("bbox"), f"frame {frame['frame_number']} detection {i}"
    for contestant_id, entry in data.get("contestant_timeline", {}).items():
        for i, appearance in enumerate(entry.get("appearances", [])):
            yield appearance.get("bbox"), f"contestant {contestant_id} appearance {i}"


def _walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)
