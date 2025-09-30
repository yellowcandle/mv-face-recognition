import pytest
import json
from pathlib import Path


class TestSegmentationConfigContract:
    def test_segmentation_config_defaults(self):
        """Test SegmentationConfig loading with defaults"""
        from src.config import SegmentationConfig

        config_data = {}
        config = SegmentationConfig.load_from_dict(config_data)

        assert config.enable_person_gating == False
        assert config.interval == 15
        assert config.min_person_area == 5000
        assert config.expand_ratio == 1.2
        assert config.max_rois_per_frame == 20
        assert config.model_path == "models/yolov8n-seg.onnx"

    def test_face_parsing_config_defaults(self):
        """Test FaceParsingConfig loading with defaults"""
        from src.config import FaceParsingConfig

        config_data = {}
        config = FaceParsingConfig.load_from_dict(config_data)

        assert config.enable_on_low_conf == False
        assert config.low_conf_threshold == 0.5
        assert config.min_skin_ratio == 0.3

    def test_segmentation_config_validation_interval(self):
        """Test interval validation (<5 or >30 should fail)"""
        from src.config import SegmentationConfig

        with pytest.raises(ValueError, match="interval"):
            SegmentationConfig.load_from_dict({"interval": 3})

        with pytest.raises(ValueError, match="interval"):
            SegmentationConfig.load_from_dict({"interval": 35})

        config = SegmentationConfig.load_from_dict({"interval": 15})
        assert config.interval == 15

    def test_segmentation_config_validation_expand_ratio(self):
        """Test expand_ratio validation (<1.0 should fail)"""
        from src.config import SegmentationConfig

        with pytest.raises(ValueError, match="expand_ratio"):
            SegmentationConfig.load_from_dict({"expand_ratio": 0.8})

        with pytest.raises(ValueError, match="expand_ratio"):
            SegmentationConfig.load_from_dict({"expand_ratio": 2.5})

        config = SegmentationConfig.load_from_dict({"expand_ratio": 1.2})
        assert config.expand_ratio == 1.2

    def test_backward_compatibility(self):
        """Test old configs without segmentation section still work"""
        config_path = (
            Path(__file__).parent.parent.parent / "config_segmentation_test.json"
        )

        with open(config_path) as f:
            full_config = json.load(f)

        del full_config["segmentation"]
        del full_config["face_parsing"]

        from src.config import SegmentationConfig, FaceParsingConfig

        seg_config = SegmentationConfig.load_from_dict(
            full_config.get("segmentation", {})
        )
        face_config = FaceParsingConfig.load_from_dict(
            full_config.get("face_parsing", {})
        )

        assert seg_config.enable_person_gating == False
        assert face_config.enable_on_low_conf == False

    def test_face_parsing_threshold_validation(self):
        """Test FaceParsingConfig threshold validation"""
        from src.config import FaceParsingConfig

        with pytest.raises(ValueError, match="low_conf_threshold"):
            FaceParsingConfig.load_from_dict({"low_conf_threshold": 1.5})

        with pytest.raises(ValueError, match="low_conf_threshold"):
            FaceParsingConfig.load_from_dict({"low_conf_threshold": -0.1})

        config = FaceParsingConfig.load_from_dict({"low_conf_threshold": 0.5})
        assert config.low_conf_threshold == 0.5

    def test_min_skin_ratio_validation(self):
        """Test min_skin_ratio validation"""
        from src.config import FaceParsingConfig

        with pytest.raises(ValueError, match="min_skin_ratio"):
            FaceParsingConfig.load_from_dict({"min_skin_ratio": 0.05})

        with pytest.raises(ValueError, match="min_skin_ratio"):
            FaceParsingConfig.load_from_dict({"min_skin_ratio": 0.95})

        config = FaceParsingConfig.load_from_dict({"min_skin_ratio": 0.3})
        assert config.min_skin_ratio == 0.3
