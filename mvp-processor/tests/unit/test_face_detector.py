"""
Unit tests for InsightFace-based face detection pipeline.
All InsightFace model calls are mocked so tests run without the 300MB model.
"""

import sys
import pytest
import numpy as np
import logging
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

sys.path.insert(0, "mvp-processor")

from src.face_detector import (
    FaceDetector,
    FaceRecognizer,
    ContestantDatabase,
    FaceDetection,
    _get_insightface_app,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockFace:
    """Mimics an InsightFace face object returned by app.get()."""

    def __init__(self, bbox, det_score, normed_embedding):
        self.bbox = np.array(bbox, dtype=np.float32)  # [x1, y1, x2, y2]
        self.det_score = det_score
        self.normed_embedding = normed_embedding  # 512-dim, L2-normalized


def _normalized_vec(dim=512, seed=None):
    """Return a random L2-normalized vector."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


def _similar_vec(base, noise_scale=0.02, seed=None):
    """Return a vector close to *base* (small cosine distance)."""
    rng = np.random.RandomState(seed)
    noisy = base + rng.randn(*base.shape).astype(np.float32) * noise_scale
    return noisy / np.linalg.norm(noisy)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    return {
        "face_detection": {
            "model": "insightface",
            "min_confidence": 0.6,
            "min_face_size": 20,
        },
        "face_recognition": {
            "tolerance": 0.4,
            "max_distance": 0.4,
            "high_confidence_threshold": 0.85,
        },
        "contestants": {
            "photo_dir": "/tmp/test_contestants",
            "embeddings_cache": "/tmp/test_cache.pkl",
            "info_csv": "/tmp/test_info.csv",
        },
    }


@pytest.fixture
def mock_app():
    """A mock InsightFace FaceAnalysis instance."""
    app = MagicMock()
    app.get.return_value = []
    return app


@pytest.fixture
def base_embedding():
    """A deterministic 512-dim normalized vector used as a reference."""
    return _normalized_vec(seed=42)


# ---------------------------------------------------------------------------
# ① – ③  Singleton tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSingleton:

    def test_singleton_returns_same_instance(self):
        """① _get_insightface_app() returns the same object on repeated calls."""
        import src.face_detector as fd

        fake_app = MagicMock()
        mock_fa = MagicMock(return_value=fake_app)

        # Reset singleton
        fd._insightface_app = None

        with patch.dict("sys.modules", {"insightface": MagicMock(), "insightface.app": MagicMock()}):
            with patch("src.face_detector.FaceAnalysis", mock_fa, create=True):
                # Patch the import inside the function
                import importlib
                with patch("builtins.__import__", side_effect=lambda name, *a, **kw: (
                    type("mod", (), {"FaceAnalysis": mock_fa})() if name == "insightface.app" else __builtins__.__import__(name, *a, **kw)
                )):
                    # Simpler approach: directly set the singleton and verify
                    fd._insightface_app = fake_app
                    first = fd._get_insightface_app()
                    second = fd._get_insightface_app()
                    assert first is second
                    # Cleanup
                    fd._insightface_app = None

    def test_singleton_handles_provider_fallback(self):
        """② FaceAnalysis is called with CoreML+CPU providers."""
        import src.face_detector as fd

        fd._insightface_app = None
        mock_fa_cls = MagicMock()
        mock_fa_instance = MagicMock()
        mock_fa_cls.return_value = mock_fa_instance

        mock_module = MagicMock()
        mock_module.FaceAnalysis = mock_fa_cls

        with patch.dict("sys.modules", {"insightface": MagicMock(), "insightface.app": mock_module}):
            fd._get_insightface_app()

            mock_fa_cls.assert_called_once_with(
                name="buffalo_l",
                providers=["CoreMLExecutionProvider", "CPUExecutionProvider"],
            )
        # Cleanup
        fd._insightface_app = None

    def test_singleton_initializes_with_correct_params(self):
        """③ prepare() is called with ctx_id=0 and det_size=(640, 640)."""
        import src.face_detector as fd

        fd._insightface_app = None
        mock_fa_cls = MagicMock()
        mock_fa_instance = MagicMock()
        mock_fa_cls.return_value = mock_fa_instance

        mock_module = MagicMock()
        mock_module.FaceAnalysis = mock_fa_cls

        with patch.dict("sys.modules", {"insightface": MagicMock(), "insightface.app": mock_module}):
            fd._get_insightface_app()

            mock_fa_instance.prepare.assert_called_once_with(
                ctx_id=0, det_size=(640, 640)
            )
        # Cleanup
        fd._insightface_app = None


# ---------------------------------------------------------------------------
# ④ – ⑦  FaceDetector tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFaceDetector:

    def test_detect_faces_returns_512dim_encoding(self, sample_config, mock_app, base_embedding):
        """④ FaceDetection.encoding has shape (512,)."""
        face = MockFace(bbox=[100, 50, 200, 180], det_score=0.9, normed_embedding=base_embedding)
        mock_app.get.return_value = [face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            detector = FaceDetector(sample_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = detector.detect_faces(frame, timestamp=1.0, frame_number=30)

        assert len(detections) == 1
        assert detections[0].encoding.shape == (512,)

    def test_detect_faces_bbox_mapping(self, sample_config, mock_app, base_embedding):
        """⑤ InsightFace [x1,y1,x2,y2] maps to (top=y1, right=x2, bottom=y2, left=x1)."""
        x1, y1, x2, y2 = 100, 50, 200, 180
        face = MockFace(bbox=[x1, y1, x2, y2], det_score=0.9, normed_embedding=base_embedding)
        mock_app.get.return_value = [face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            detector = FaceDetector(sample_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = detector.detect_faces(frame, timestamp=0.0, frame_number=0)

        top, right, bottom, left = detections[0].location
        assert top == y1
        assert right == x2
        assert bottom == y2
        assert left == x1

    def test_detect_faces_min_size_filter(self, sample_config, mock_app, base_embedding):
        """⑥ Faces smaller than min_face_size are filtered out."""
        # 10x10 face, min_face_size is 20
        tiny_face = MockFace(bbox=[50, 50, 60, 60], det_score=0.95, normed_embedding=base_embedding)
        mock_app.get.return_value = [tiny_face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            detector = FaceDetector(sample_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = detector.detect_faces(frame, timestamp=0.0, frame_number=0)

        assert len(detections) == 0

    def test_detect_faces_uses_real_det_score(self, sample_config, mock_app, base_embedding):
        """⑦ FaceDetection.confidence equals the InsightFace det_score."""
        face = MockFace(bbox=[100, 50, 200, 180], det_score=0.85, normed_embedding=base_embedding)
        mock_app.get.return_value = [face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            detector = FaceDetector(sample_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = detector.detect_faces(frame, timestamp=0.0, frame_number=0)

        assert detections[0].confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# ⑧ – ⑩  FaceRecognizer tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFaceRecognizer:

    def _make_db(self, sample_config, encodings_dict, info_dict=None):
        """Helper to build a ContestantDatabase with preset encodings."""
        db = ContestantDatabase(sample_config)
        db.face_encodings = encodings_dict
        db.contestant_names = list(encodings_dict.keys())
        if info_dict:
            db.contestants_info = info_dict
        return db

    def test_recognize_known_face(self, sample_config, base_embedding):
        """⑧ A detection close to a known encoding is matched."""
        known = {"1": base_embedding}
        info = {"1": {"name": "Alice", "nickname": "A", "age": "20"}}
        db = self._make_db(sample_config, known, info)

        recognizer = FaceRecognizer(sample_config, db)

        similar = _similar_vec(base_embedding, noise_scale=0.01, seed=99)
        det = FaceDetection(
            location=(50, 200, 180, 100),
            encoding=similar,
            timestamp=1.0,
            frame_number=30,
            confidence=0.9,
        )

        results = recognizer.recognize_faces([det])
        assert len(results) == 1
        assert results[0].contestant_id == "1"
        assert results[0].contestant_name == "Alice"

    def test_reject_unknown_face(self, sample_config, base_embedding):
        """⑨ A detection far from all known encodings returns no recognition."""
        known = {"1": base_embedding}
        db = self._make_db(sample_config, known)

        recognizer = FaceRecognizer(sample_config, db)

        distant = _normalized_vec(seed=999)  # independent random vector
        det = FaceDetection(
            location=(50, 200, 180, 100),
            encoding=distant,
            timestamp=2.0,
            frame_number=60,
            confidence=0.9,
        )

        results = recognizer.recognize_faces([det])
        assert len(results) == 0

    def test_recognize_empty_encodings(self, sample_config, base_embedding):
        """⑩ Empty contestant_db.face_encodings yields empty result list."""
        db = self._make_db(sample_config, {})
        recognizer = FaceRecognizer(sample_config, db)

        det = FaceDetection(
            location=(50, 200, 180, 100),
            encoding=base_embedding,
            timestamp=0.0,
            frame_number=0,
            confidence=0.9,
        )

        results = recognizer.recognize_faces([det])
        assert results == []


# ---------------------------------------------------------------------------
# ⑪ – ⑫  Batch recognition tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBatchRecognition:

    def test_batch_matches_single_path(self, sample_config, base_embedding):
        """⑪ recognize_faces_batch() produces the same match as recognize_faces()."""
        known = {"1": base_embedding}
        info = {"1": {"name": "Bob", "nickname": "B", "age": "25"}}
        db = ContestantDatabase(sample_config)
        db.face_encodings = known
        db.contestant_names = ["1"]
        db.contestants_info = info

        recognizer = FaceRecognizer(sample_config, db)

        similar = _similar_vec(base_embedding, noise_scale=0.01, seed=77)
        det = FaceDetection(
            location=(50, 200, 180, 100),
            encoding=similar,
            timestamp=1.0,
            frame_number=30,
            confidence=0.9,
        )

        single_results = recognizer.recognize_faces([det])
        batch_results = recognizer.recognize_faces_batch([[det]])

        assert len(batch_results) == 1
        assert len(batch_results[0]) == len(single_results)
        if single_results:
            assert batch_results[0][0].contestant_id == single_results[0].contestant_id

    def test_batch_uses_cosine_distance(self, sample_config, base_embedding):
        """⑫ Batch path computes cosine distances (not L2)."""
        known = {"1": base_embedding}
        info = {"1": {"name": "Carol", "nickname": "C", "age": "22"}}
        db = ContestantDatabase(sample_config)
        db.face_encodings = known
        db.contestant_names = ["1"]
        db.contestants_info = info

        recognizer = FaceRecognizer(sample_config, db)

        similar = _similar_vec(base_embedding, noise_scale=0.01, seed=88)
        det = FaceDetection(
            location=(50, 200, 180, 100),
            encoding=similar,
            timestamp=1.0,
            frame_number=30,
            confidence=0.9,
        )

        results = recognizer.recognize_faces_batch([[det]])
        assert len(results[0]) == 1

        # Manually compute expected cosine distance
        cosine_dist = 1 - np.dot(similar, base_embedding)
        expected_confidence = 1 - (cosine_dist / sample_config["face_recognition"]["tolerance"])

        assert results[0][0].match_confidence == pytest.approx(expected_confidence, abs=1e-4)


# ---------------------------------------------------------------------------
# ⑬ – ⑭  ContestantDatabase tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestContestantDatabase:

    def test_load_npy_embeddings_512dim(self, sample_config, tmp_path, base_embedding):
        """⑬ A 512-dim .npy file is loaded correctly into face_encodings."""
        # Set up directory and files
        photo_dir = tmp_path / "contestants"
        photo_dir.mkdir()
        nickname = "TestNick"
        npy_path = photo_dir / f"{nickname}_embedding.npy"
        np.save(str(npy_path), base_embedding)

        config = dict(sample_config)
        config["contestants"] = {
            "photo_dir": str(photo_dir),
            "embeddings_cache": str(tmp_path / "cache.pkl"),
            "info_csv": str(tmp_path / "info.csv"),
        }

        db = ContestantDatabase(config)
        db.contestants_info = {"1": {"id": "1", "name": "Test", "nickname": nickname, "age": "20"}}

        db.build_face_encodings()

        assert "1" in db.face_encodings
        assert db.face_encodings["1"].shape == (512,)
        np.testing.assert_allclose(db.face_encodings["1"], base_embedding, atol=1e-6)

    def test_photo_fallback_produces_512dim(self, sample_config, tmp_path, base_embedding):
        """⑭ When no .npy exists, InsightFace encodes photos and produces 512-dim embedding."""
        photo_dir = tmp_path / "contestants"
        photos_subdir = photo_dir / "photos" / "contestant_1"
        photos_subdir.mkdir(parents=True)

        # Create a dummy jpg (content doesn't matter since we mock InsightFace)
        dummy_jpg = photos_subdir / "face.jpg"
        dummy_jpg.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        config = dict(sample_config)
        config["contestants"] = {
            "photo_dir": str(photo_dir),
            "embeddings_cache": str(tmp_path / "cache.pkl"),
            "info_csv": str(tmp_path / "info.csv"),
        }

        db = ContestantDatabase(config)
        db.contestants_info = {"1": {"id": "1", "name": "Test", "nickname": "NoEmbedding", "age": "20"}}

        mock_face = MockFace(bbox=[0, 0, 100, 100], det_score=0.95, normed_embedding=base_embedding)
        mock_app = MagicMock()
        mock_app.get.return_value = [mock_face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            with patch("cv2.imread", return_value=np.zeros((100, 100, 3), dtype=np.uint8)):
                db.build_face_encodings()

        assert "1" in db.face_encodings
        assert db.face_encodings["1"].shape == (512,)


# ---------------------------------------------------------------------------
# ⑮  Embedding validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEmbeddingValidation:

    def test_zero_vector_embedding_skipped(self, sample_config, tmp_path, caplog):
        """⑮ A .npy with all zeros is skipped and a warning is logged."""
        photo_dir = tmp_path / "contestants"
        photo_dir.mkdir()
        nickname = "ZeroVec"
        npy_path = photo_dir / f"{nickname}_embedding.npy"
        np.save(str(npy_path), np.zeros(512, dtype=np.float32))

        config = dict(sample_config)
        config["contestants"] = {
            "photo_dir": str(photo_dir),
            "embeddings_cache": str(tmp_path / "cache.pkl"),
            "info_csv": str(tmp_path / "info.csv"),
        }

        db = ContestantDatabase(config)
        db.contestants_info = {"1": {"id": "1", "name": "Zero", "nickname": nickname, "age": "20"}}

        with caplog.at_level(logging.WARNING, logger="src.face_detector"):
            db.build_face_encodings()

        assert "1" not in db.face_encodings
        assert any("Zero-norm" in msg or "zero-norm" in msg.lower() or "Zero" in msg for msg in caplog.messages)
