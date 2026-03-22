"""
Tests for supervision_annotator.py — Supervision-based annotation pipeline.
"""

import sys
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np
import pytest

sv = pytest.importorskip("supervision")

sys.path.insert(0, "mvp-processor")

from src.supervision_annotator import (
    annotate_frame,
    build_contestant_id_map,
    create_annotator_pipeline,
    create_tracker,
    draw_timeline_bar,
    get_color_for_contestant,
    insightface_to_sv_detections,
)


# ---------------------------------------------------------------------------
# Mock objects matching face_detector.py's FaceDetection / FaceRecognition
# ---------------------------------------------------------------------------

@dataclass
class MockDetection:
    location: Tuple[int, int, int, int]  # (top, right, bottom, left)
    encoding: np.ndarray = None
    timestamp: float = 0.0
    frame_number: int = 0
    confidence: float = 0.8


@dataclass
class MockRecognition:
    detection: MockDetection = field(default_factory=lambda: MockDetection((0, 0, 0, 0)))
    contestant_id: str = "1"
    contestant_name: str = "Test Name"
    contestant_nickname: str = "TestNick"
    match_confidence: float = 0.85


# ---------------------------------------------------------------------------
# ①-④  Detection conversion tests
# ---------------------------------------------------------------------------

class TestDetectionConversion:

    def test_recognized_faces_to_sv_detections(self):
        """① Two recognized faces produce correct xyxy shape and values."""
        recognitions = [
            MockRecognition(
                detection=MockDetection(location=(100, 200, 300, 50)),
                contestant_nickname="TestNick",
                match_confidence=0.9,
            ),
            MockRecognition(
                detection=MockDetection(location=(150, 250, 350, 100)),
                contestant_nickname="TestNick2",
                match_confidence=0.85,
            ),
        ]
        contestant_id_map = {"TestNick": 1, "TestNick2": 2}

        detections = insightface_to_sv_detections(recognitions, [], contestant_id_map)

        assert detections.xyxy.shape == (2, 4)
        # location = (top=100, right=200, bottom=300, left=50) → xyxy = [left, top, right, bottom]
        np.testing.assert_array_equal(detections.xyxy[0], [50, 100, 200, 300])

    def test_unmatched_faces_get_class_id_zero(self):
        """② Unmatched faces receive class_id == 0 and label 'Unknown'."""
        unmatched = [MockDetection(location=(10, 100, 80, 5))]

        detections = insightface_to_sv_detections([], unmatched, {})

        assert detections.class_id[0] == 0
        assert detections.data["labels"][0] == "Unknown"

    def test_empty_input_returns_empty_detections(self):
        """③ Empty inputs yield an empty Detections object."""
        detections = insightface_to_sv_detections([], [], {})

        assert len(detections) == 0

    def test_bbox_format_mapping(self):
        """④ location (top, right, bottom, left) maps to xyxy [left, top, right, bottom]."""
        recognitions = [
            MockRecognition(
                detection=MockDetection(location=(10, 200, 150, 50)),
                contestant_nickname="Nick",
                match_confidence=0.9,
            ),
        ]

        detections = insightface_to_sv_detections(recognitions, [], {"Nick": 0})

        np.testing.assert_array_equal(detections.xyxy[0], [50, 10, 200, 150])


# ---------------------------------------------------------------------------
# ⑤-⑥  ByteTrack tests
# ---------------------------------------------------------------------------

class TestByteTrack:

    def test_tracker_assigns_consistent_ids(self):
        """⑤ A single face moving slightly keeps the same tracker ID across 3 frames."""
        tracker = create_tracker(frame_rate=6)
        tracker_ids = []

        for offset in range(3):
            x1 = 100 + offset * 5
            y1 = 100 + offset * 5
            x2 = 200 + offset * 5
            y2 = 200 + offset * 5
            det = sv.Detections(
                xyxy=np.array([[x1, y1, x2, y2]], dtype=np.float32),
                confidence=np.array([0.9], dtype=np.float32),
                class_id=np.array([1], dtype=int),
            )
            tracked = tracker.update_with_detections(det)
            if len(tracked) > 0:
                tracker_ids.append(tracked.tracker_id[0])

        # All captured IDs should be the same (tracker maintains identity)
        assert len(tracker_ids) >= 2, "Tracker should produce IDs for at least 2 frames"
        assert all(tid == tracker_ids[0] for tid in tracker_ids)

    def test_tracker_handles_empty_detections(self):
        """⑥ Updating with empty detections does not crash."""
        tracker = create_tracker()
        result = tracker.update_with_detections(sv.Detections.empty())

        assert len(result) == 0


# ---------------------------------------------------------------------------
# ⑦-⑧  Annotation tests
# ---------------------------------------------------------------------------

class TestAnnotation:

    def test_annotate_frame_returns_same_dimensions(self):
        """⑦ annotate_frame output has the same shape as the input frame."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = sv.Detections(
            xyxy=np.array([[50, 50, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9], dtype=np.float32),
            class_id=np.array([1], dtype=int),
            data={"labels": ["TestNick"]},
        )
        annotators = create_annotator_pipeline()

        result = annotate_frame(frame, detections, annotators, screen_time=None, color_map=None)

        assert result.shape == (480, 640, 3)

    def test_annotate_frame_handles_empty_detections(self):
        """⑧ Empty detections cause no crash; output dimensions match input."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        annotators = create_annotator_pipeline()

        result = annotate_frame(frame, sv.Detections.empty(), annotators)

        assert result.shape == (480, 640, 3)


# ---------------------------------------------------------------------------
# ⑨-⑩  Timeline bar tests
# ---------------------------------------------------------------------------

class TestTimelineBar:

    def test_timeline_bar_renders_at_bottom(self):
        """⑨ The bottom 60 rows differ from pure black after drawing the timeline bar."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = draw_timeline_bar(
            frame,
            active_contestants=["Ivy So"],
            screen_time={"Ivy So": 120.0},
            color_map={"Ivy So": (75, 25, 230)},
        )

        bottom_60 = result[1080 - 60 :, :, :]
        assert bottom_60.any(), "Timeline bar should modify pixels in the bottom 60 rows"

    def test_timeline_bar_empty_contestants(self):
        """⑩ Empty active list and screen_time cause no crash; dimensions preserved."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = draw_timeline_bar(
            frame,
            active_contestants=[],
            screen_time={},
            color_map={},
        )

        assert result.shape == (1080, 1920, 3)


# ---------------------------------------------------------------------------
# ⑪  End-to-end test
# ---------------------------------------------------------------------------

class TestEndToEnd:

    def test_full_annotation_pipeline(self):
        """⑪ Full pipeline: mock recognitions → sv.Detections → annotate_frame."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        recognitions = [
            MockRecognition(
                detection=MockDetection(location=(50, 200, 200, 30)),
                contestant_nickname="Alice",
                match_confidence=0.9,
            ),
        ]
        unmatched = [MockDetection(location=(300, 500, 450, 250))]
        contestant_id_map = {"Alice": 1}

        detections = insightface_to_sv_detections(recognitions, unmatched, contestant_id_map)

        annotators = create_annotator_pipeline()
        screen_time = {"Alice": 45.0}
        color_map = {"Alice": (75, 25, 230)}

        result = annotate_frame(frame, detections, annotators, screen_time, color_map)

        assert result.shape == (480, 640, 3)
        assert not np.array_equal(result, np.zeros((480, 640, 3), dtype=np.uint8)), (
            "Annotated frame should differ from the blank input"
        )
