"""Contract test for SupervisionDetection class."""
import numpy as np
import pytest
from src.models.detection import SupervisionDetection


class TestSupervisionDetectionContract:
    """Contract tests for SupervisionDetection class."""
    
    def test_supervision_detection_class_exists(self):
        """Test that SupervisionDetection class can be imported."""
        # This will fail until the class is implemented
        detection = SupervisionDetection()
        assert detection is not None
    
    def test_to_supervision_detections_method_exists(self):
        """Test that to_supervision_detections method exists."""
        detection = SupervisionDetection()
        # Should have the method
        assert hasattr(detection, 'to_supervision_detections')
        assert callable(getattr(detection, 'to_supervision_detections'))
    
    def test_from_supervision_detections_classmethod_exists(self):
        """Test that from_supervision_detections classmethod exists."""
        # Should have the classmethod
        assert hasattr(SupervisionDetection, 'from_supervision_detections')
        assert callable(getattr(SupervisionDetection, 'from_supervision_detections'))
    
    def test_filter_by_confidence_method_exists(self):
        """Test that filter_by_confidence method exists."""
        detection = SupervisionDetection()
        # Should have the method
        assert hasattr(detection, 'filter_by_confidence')
        assert callable(getattr(detection, 'filter_by_confidence'))
    
    def test_apply_nms_method_exists(self):
        """Test that apply_nms method exists."""
        detection = SupervisionDetection()
        # Should have the method
        assert hasattr(detection, 'apply_nms')
        assert callable(getattr(detection, 'apply_nms'))
    
    def test_supervision_detection_has_required_fields(self):
        """Test that SupervisionDetection has required fields."""
        detection = SupervisionDetection()
        # Should have required fields from contract
        required_fields = ['xyxy', 'confidence', 'class_id', 'tracker_id', 'data']
        for field in required_fields:
            assert hasattr(detection, field), f"Missing required field: {field}"