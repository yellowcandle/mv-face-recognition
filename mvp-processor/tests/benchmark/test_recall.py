import pytest
import cv2
import numpy as np
from pathlib import Path
import logging

import sys
sys.path.insert(0, '.')

from src.video_processor import VideoProcessor
from src.face_detector import FaceDetector

logger = logging.getLogger(__name__)


@pytest.fixture
def test_video_with_faces(tmp_path):
    video_path = tmp_path / "test_video_faces.mp4"
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (640, 480))
    
    for i in range(60):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        cv2.rectangle(frame, (200, 150), (280, 250), (255, 200, 150), -1)
        cv2.circle(frame, (240, 180), 15, (100, 100, 100), -1)
        cv2.circle(frame, (225, 175), 3, (0, 0, 0), -1)
        cv2.circle(frame, (255, 175), 3, (0, 0, 0), -1)
        cv2.ellipse(frame, (240, 200), (20, 10), 0, 0, 180, (150, 100, 100), -1)
        
        if i % 20 < 15:
            cv2.rectangle(frame, (400, 200), (480, 300), (255, 200, 150), -1)
            cv2.circle(frame, (440, 230), 15, (100, 100, 100), -1)
            cv2.circle(frame, (425, 225), 3, (0, 0, 0), -1)
            cv2.circle(frame, (455, 225), 3, (0, 0, 0), -1)
        
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


class TestRecallPreservation:
    def test_recall_preservation(self, test_video_with_faces, baseline_config, segmentation_config):
        baseline_processor = VideoProcessor(baseline_config)
        segmentation_processor = VideoProcessor(segmentation_config)
        
        face_detector_config = {
            "face_detection": {
                "model": "hog",
                "min_confidence": 0.5
            }
        }
        face_detector = FaceDetector(face_detector_config)
        
        baseline_faces = self._count_faces(baseline_processor, test_video_with_faces, face_detector)
        segmentation_faces = self._count_faces(segmentation_processor, test_video_with_faces, face_detector)
        
        recall_pct = (segmentation_faces / baseline_faces * 100) if baseline_faces > 0 else 0.0
        
        logger.info(f"Baseline faces: {baseline_faces}, Segmentation faces: {segmentation_faces}, Recall: {recall_pct:.1f}%")
        
        assert recall_pct >= 95.0, f"Recall too low: {recall_pct:.1f}% (target: >=99.5%, acceptable: >=95%)"
        
        if recall_pct >= 99.5:
            logger.info(f"✓ Recall target met: {recall_pct:.1f}%")
        elif recall_pct >= 95.0:
            logger.warning(f"Recall acceptable but below target: {recall_pct:.1f}% (target: >=99.5%)")
    
    def test_detailed_recall_tracking(self, test_video_with_faces, baseline_config, segmentation_config):
        baseline_processor = VideoProcessor(baseline_config)
        segmentation_processor = VideoProcessor(segmentation_config)
        
        face_detector_config = {
            "face_detection": {
                "model": "hog",
                "min_confidence": 0.5
            }
        }
        face_detector = FaceDetector(face_detector_config)
        
        baseline_detections = self._collect_face_locations(baseline_processor, test_video_with_faces, face_detector)
        segmentation_detections = self._collect_face_locations(segmentation_processor, test_video_with_faces, face_detector)
        
        missed_faces = []
        for frame_idx, bbox in baseline_detections:
            if not self._is_bbox_detected(frame_idx, bbox, segmentation_detections):
                missed_faces.append((frame_idx, bbox))
        
        if missed_faces:
            logger.warning(f"Missed {len(missed_faces)} faces:")
            for frame_idx, bbox in missed_faces[:5]:
                logger.warning(f"  Frame {frame_idx}: bbox={bbox}")
        else:
            logger.info("✓ All baseline faces detected by segmentation-gated system")
    
    def _count_faces(self, processor, video_path, face_detector):
        face_count = 0
        frame_idx = 0
        
        for frame, timestamp in processor.extract_frames(video_path):
            _, rois, faces = processor.process_frame(frame, frame_idx, face_detector=face_detector, timestamp=timestamp)
            face_count += len(faces)
            frame_idx += 1
        
        return face_count
    
    def _collect_face_locations(self, processor, video_path, face_detector):
        detections = []
        frame_idx = 0
        
        for frame, timestamp in processor.extract_frames(video_path):
            _, rois, faces = processor.process_frame(frame, frame_idx, face_detector=face_detector, timestamp=timestamp)
            
            for face in faces:
                detections.append((frame_idx, face.location))
            
            frame_idx += 1
        
        return detections
    
    def _is_bbox_detected(self, target_frame, target_bbox, detections, tolerance=50):
        for frame_idx, bbox in detections:
            if frame_idx == target_frame:
                top1, right1, bottom1, left1 = target_bbox
                top2, right2, bottom2, left2 = bbox
                
                if (abs(top1 - top2) < tolerance and 
                    abs(left1 - left2) < tolerance and
                    abs(bottom1 - bottom2) < tolerance and
                    abs(right1 - right2) < tolerance):
                    return True
        
        return False
