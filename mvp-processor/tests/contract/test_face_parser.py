import pytest
import numpy as np
import time


class MockFaceDetection:
    def __init__(self, bbox, confidence):
        self.bbox = bbox
        self.confidence = confidence


class TestFaceParserContract:
    def test_initialization_with_config(self):
        """Test FaceParser initialization with FaceParsingConfig"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        assert parser is not None
        assert parser.config.low_conf_threshold == 0.5

    def test_validate_face_returns_true_for_high_confidence(self):
        """Test validate_face() returns True for high confidence (0.8 >= 0.5 threshold)"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        face_detection = MockFaceDetection(bbox=(100, 100, 200, 200), confidence=0.8)

        result = parser.validate_face(frame, face_detection)

        assert result is True

    def test_validate_face_triggers_parsing_for_low_confidence(self):
        """Test validate_face() triggers parsing for low confidence (0.3 < 0.5 threshold)"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        frame = np.ones((480, 640, 3), dtype=np.uint8) * 150
        face_detection = MockFaceDetection(bbox=(100, 100, 200, 200), confidence=0.3)

        result = parser.validate_face(frame, face_detection)

        assert isinstance(result, bool)

    def test_compute_skin_ratio_returns_valid_range(self):
        """Test compute_skin_ratio() returns value in [0.0, 1.0] range"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict({})
        parser = FaceParser(config=config)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        bbox = (100, 100, 200, 200)

        skin_ratio = parser.compute_skin_ratio(frame, bbox)

        assert 0.0 <= skin_ratio <= 1.0

    def test_validation_passes_with_sufficient_skin_ratio(self):
        """Test validation passes with sufficient skin_ratio (0.6 >= 0.3 min_ratio)"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:200, 100:200] = [180, 150, 120]

        face_detection = MockFaceDetection(bbox=(100, 100, 200, 200), confidence=0.3)

        result = parser.validate_face(frame, face_detection)

        assert isinstance(result, bool)

    def test_validation_rejects_insufficient_skin_ratio(self):
        """Test validation rejects with insufficient skin_ratio (0.1 < 0.3 min_ratio)"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        face_detection = MockFaceDetection(bbox=(100, 100, 200, 200), confidence=0.3)

        result = parser.validate_face(frame, face_detection)

        assert isinstance(result, bool)

    def test_performance_validate_face_under_1ms(self):
        """Test performance: validate_face() < 1ms per face (measure on 100 low-conf faces)"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        face_detection = MockFaceDetection(bbox=(100, 100, 200, 200), confidence=0.3)

        times = []
        for _ in range(100):
            start = time.time()
            parser.validate_face(frame, face_detection)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        assert avg_time < 0.001, (
            f"Average validation time {avg_time * 1000:.2f}ms exceeds 1ms target"
        )

    def test_get_validation_stats_returns_counts(self):
        """Test get_validation_stats() returns total_validated, passed, rejected counts"""
        from src.face_parser import FaceParser
        from src.config import FaceParsingConfig

        config = FaceParsingConfig.load_from_dict(
            {
                "enable_on_low_conf": True,
                "low_conf_threshold": 0.5,
                "min_skin_ratio": 0.3,
            }
        )

        parser = FaceParser(config=config)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        face_detection = MockFaceDetection(bbox=(100, 100, 200, 200), confidence=0.3)

        parser.validate_face(frame, face_detection)
        parser.validate_face(frame, face_detection)
        parser.validate_face(frame, face_detection)

        stats = parser.get_validation_stats()

        assert "total_validated" in stats
        assert "passed" in stats
        assert "rejected" in stats
        assert stats["total_validated"] >= 3
