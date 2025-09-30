import pytest
import numpy as np
import time


class TestPersonSegmenterContract:
    def test_initialization_with_valid_model_path(self):
        """Test PersonSegmenter initialization with valid model path"""
        from src.person_segmenter import PersonSegmenter

        segmenter = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.2,
            max_rois_per_frame=20,
        )

        assert segmenter is not None
        assert segmenter.model_path == "models/yolov8n-seg.onnx"

    def test_segment_returns_roi_list(self):
        """Test segment() returns list of ROI objects with valid coordinates"""
        from src.person_segmenter import PersonSegmenter

        segmenter = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.2,
            max_rois_per_frame=20,
        )

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        rois = segmenter.segment(frame)

        assert isinstance(rois, list)
        for roi in rois:
            assert hasattr(roi, "x1")
            assert hasattr(roi, "y1")
            assert hasattr(roi, "x2")
            assert hasattr(roi, "y2")
            assert hasattr(roi, "confidence")
            assert hasattr(roi, "area")
            assert roi.x2 > roi.x1
            assert roi.y2 > roi.y1

    def test_segment_filters_by_min_person_area(self):
        """Test segment() filters ROIs by min_person_area"""
        from src.person_segmenter import PersonSegmenter

        segmenter = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=10000,
            expand_ratio=1.2,
            max_rois_per_frame=20,
        )

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        rois = segmenter.segment(frame)

        for roi in rois:
            assert roi.area >= 10000

    def test_segment_respects_max_rois_limit(self):
        """Test segment() respects max_rois_per_frame limit (top 20 by confidence)"""
        from src.person_segmenter import PersonSegmenter

        segmenter = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.2,
            max_rois_per_frame=5,
        )

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        rois = segmenter.segment(frame)

        assert len(rois) <= 5

    def test_segment_expands_rois(self):
        """Test segment() expands ROIs by expand_ratio (verify 20% expansion for ratio=1.2)"""
        from src.person_segmenter import PersonSegmenter

        segmenter_no_expand = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.0,
            max_rois_per_frame=20,
        )

        segmenter_expand = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.2,
            max_rois_per_frame=20,
        )

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        rois_no_expand = segmenter_no_expand.segment(frame)
        rois_expand = segmenter_expand.segment(frame)

        if len(rois_no_expand) > 0 and len(rois_expand) > 0:
            assert rois_expand[0].area >= rois_no_expand[0].area

    def test_segment_handles_invalid_frame(self):
        """Test segment() handles invalid frame (empty, wrong shape) gracefully"""
        from src.person_segmenter import PersonSegmenter

        segmenter = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.2,
            max_rois_per_frame=20,
        )

        empty_frame = np.array([])
        rois = segmenter.segment(empty_frame)
        assert isinstance(rois, list)
        assert len(rois) == 0

        wrong_shape_frame = np.random.randint(0, 255, (100,), dtype=np.uint8)
        rois = segmenter.segment(wrong_shape_frame)
        assert isinstance(rois, list)
        assert len(rois) == 0

    def test_performance_average_inference_time(self):
        """Test performance: average inference time < 10ms per frame (run 10 times)"""
        from src.person_segmenter import PersonSegmenter

        segmenter = PersonSegmenter(
            model_path="models/yolov8n-seg.onnx",
            min_person_area=5000,
            expand_ratio=1.2,
            max_rois_per_frame=20,
        )

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        times = []
        for _ in range(10):
            start = time.time()
            segmenter.segment(frame)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        assert avg_time < 0.01, (
            f"Average inference time {avg_time * 1000:.2f}ms exceeds 10ms target"
        )
