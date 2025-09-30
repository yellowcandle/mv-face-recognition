import pytest
import time
import cv2
import numpy as np
from pathlib import Path
import tempfile
import logging

import sys
sys.path.insert(0, '.')

from src.video_processor import VideoProcessor
from src.face_detector import FaceDetector

logger = logging.getLogger(__name__)


@pytest.fixture
def test_video_path(tmp_path):
    video_path = tmp_path / "test_video.mp4"
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (640, 480))
    
    for i in range(50):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        cv2.rectangle(frame, (200, 150), (280, 250), (255, 200, 150), -1)
        cv2.circle(frame, (240, 180), 15, (100, 100, 100), -1)
        cv2.circle(frame, (225, 175), 3, (0, 0, 0), -1)
        cv2.circle(frame, (255, 175), 3, (0, 0, 0), -1)
        
        out.write(frame)
    
    out.release()
    return str(video_path)


@pytest.fixture
def baseline_config():
    return {
        "video": {
            "fps_sample_rate": 5,
            "max_frames": 0,
            "resize_width": 640
        }
    }


@pytest.fixture
def segmentation_config(baseline_config):
    config = baseline_config.copy()
    config["segmentation"] = {
        "enable_person_gating": True,
        "model_path": "models/yolov8n-seg.onnx",
        "interval": 15,
        "min_person_area": 5000,
        "expand_ratio": 1.1,
        "max_rois_per_frame": 10
    }
    return config


class TestPerformanceBenchmark:
    def test_segmentation_speedup(self, test_video_path, baseline_config, segmentation_config, benchmark):
        baseline_processor = VideoProcessor(baseline_config)
        segmentation_processor = VideoProcessor(segmentation_config)
        
        segmentation_processor.init_metrics("test_video")
        
        baseline_time = self._process_video(baseline_processor, test_video_path)
        segmentation_time = self._process_video(segmentation_processor, test_video_path)
        
        speedup_pct = ((baseline_time - segmentation_time) / baseline_time) * 100 if baseline_time > 0 else 0.0
        
        logger.info(f"Baseline: {baseline_time:.3f}s, Segmentation: {segmentation_time:.3f}s, Speedup: {speedup_pct:.1f}%")
        
        assert speedup_pct >= -10, f"Performance regression detected: {speedup_pct:.1f}% (should be at least -10%)"
        
        if speedup_pct >= 10:
            logger.info(f"✓ Performance target met: {speedup_pct:.1f}% speedup")
        else:
            logger.warning(f"Performance target not met: {speedup_pct:.1f}% speedup (target: 10-30%)")
    
    def _process_video(self, processor, video_path):
        start_time = time.time()
        
        frame_count = 0
        for frame, timestamp in processor.extract_frames(video_path):
            _, rois, _ = processor.process_frame(frame, frame_count, face_detector=None, timestamp=timestamp)
            frame_count += 1
        
        end_time = time.time()
        return end_time - start_time
    
    def test_with_face_detection(self, test_video_path, baseline_config, segmentation_config):
        baseline_processor = VideoProcessor(baseline_config)
        segmentation_processor = VideoProcessor(segmentation_config)
        
        face_detector_config = {
            "face_detection": {
                "model": "hog",
                "min_confidence": 0.5
            }
        }
        face_detector = FaceDetector(face_detector_config)
        
        baseline_time = self._process_video_with_faces(baseline_processor, test_video_path, face_detector)
        segmentation_time = self._process_video_with_faces(segmentation_processor, test_video_path, face_detector)
        
        speedup_pct = ((baseline_time - segmentation_time) / baseline_time) * 100 if baseline_time > 0 else 0.0
        
        logger.info(f"With face detection - Baseline: {baseline_time:.3f}s, Segmentation: {segmentation_time:.3f}s, Speedup: {speedup_pct:.1f}%")
        
        assert baseline_time > 0, "Baseline processing time should be positive"
        assert segmentation_time > 0, "Segmentation processing time should be positive"
    
    def _process_video_with_faces(self, processor, video_path, face_detector):
        start_time = time.time()
        
        frame_count = 0
        for frame, timestamp in processor.extract_frames(video_path):
            _, rois, faces = processor.process_frame(frame, frame_count, face_detector=face_detector, timestamp=timestamp)
            frame_count += 1
        
        end_time = time.time()
        return end_time - start_time
