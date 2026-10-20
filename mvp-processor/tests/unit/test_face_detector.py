"""
Unit tests for InsightFace-based face detection pipeline.
All InsightFace model calls are mocked so tests run without the 300MB model.
"""

import sys
import json
import pytest
import numpy as np
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


def _write_reference_cache(photo_dir, contestant_ids, embeddings, reference_count=None):
    """Write a synthetic reference_embeddings.npz + reference_manifest.json pair.

    *reference_count* defaults to the true row count; pass a different value to fake a
    stale manifest.
    """
    photo_dir.mkdir(parents=True, exist_ok=True)
    embeddings = np.asarray(embeddings, dtype=np.float32)
    n = len(contestant_ids)
    np.savez(
        photo_dir / "reference_embeddings.npz",
        embeddings=embeddings,
        contestant_ids=np.array(contestant_ids, dtype="U8"),
        photo_paths=np.array([f"contestant_{c}/photo_{i}.jpg" for i, c in enumerate(contestant_ids)]),
        n_faces=np.ones(n, dtype=np.int32),
        det_scores=np.full(n, 0.9, dtype=np.float32),
    )
    manifest = {
        "generated_at": "2026-09-08T00:00:00+00:00",
        "photo_count": n,
        "reference_count": len(embeddings) if reference_count is None else reference_count,
        "contestant_count": len(set(contestant_ids)),
        "photo_list_sha256": "0" * 64,
        "dropped": {},
        "references_per_contestant": {c: contestant_ids.count(c) for c in set(contestant_ids)},
    }
    (photo_dir / "reference_manifest.json").write_text(json.dumps(manifest))


def _cache_config(sample_config, photo_dir, tmp_path):
    """sample_config with contestants.photo_dir pointed at a synthetic cache directory."""
    config = dict(sample_config)
    config["contestants"] = {
        "photo_dir": str(photo_dir),
        "embeddings_cache": str(tmp_path / "cache.pkl"),
        "info_csv": str(tmp_path / "info.csv"),
    }
    return config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    return {
        "face_detection": {
            "model": "insightface",
            "min_face_size": 20,
        },
        "face_recognition": {
            # A cosine, not a distance: 0.6 is the old tolerance 0.4 read the other way up.
            "acceptance_threshold": 0.6,
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

    def test_detect_faces_bbox_is_frame_fractions(self, sample_config, mock_app, base_embedding):
        """⑤ InsightFace [x1,y1,x2,y2] in pixels becomes frame fractions, same order."""
        x1, y1, x2, y2 = 100, 50, 200, 180
        face = MockFace(bbox=[x1, y1, x2, y2], det_score=0.9, normed_embedding=base_embedding)
        mock_app.get.return_value = [face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            detector = FaceDetector(sample_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)  # height 480, width 640
            detections = detector.detect_faces(frame, timestamp=0.0, frame_number=0)

        assert detections[0].bbox == pytest.approx((x1 / 640, y1 / 480, x2 / 640, y2 / 480))
        # ...and a fraction is a fraction: the same box against a differently sized frame is
        # what makes it correct against the 1080p and 720p renditions too.
        assert all(0.0 <= v <= 1.0 for v in detections[0].bbox)

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
        """⑦ FaceDetection.det_score equals the InsightFace det_score."""
        face = MockFace(bbox=[100, 50, 200, 180], det_score=0.85, normed_embedding=base_embedding)
        mock_app.get.return_value = [face]

        with patch("src.face_detector._get_insightface_app", return_value=mock_app):
            detector = FaceDetector(sample_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = detector.detect_faces(frame, timestamp=0.0, frame_number=0)

        assert detections[0].det_score == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# ⑧ – ⑩  FaceRecognizer tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFaceRecognizer:

    def _make_db(self, sample_config, encodings_dict, info_dict=None):
        """Build a ContestantDatabase with a preset reference set.

        *encodings_dict* maps contestant_id -> (K, 512) reference block. Flattening goes
        through the real flatten_references() so the flat lists the recognizer reads are
        built exactly as production builds them.
        """
        db = ContestantDatabase(sample_config)
        db.face_encodings = {cid: np.atleast_2d(v) for cid, v in encodings_dict.items()}
        db.contestant_names = list(db.face_encodings)
        db.flatten_references()
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
            bbox=(0.078, 0.104, 0.312, 0.375),
            encoding=similar,
            timestamp=1.0,
            frame_number=30,
            det_score=0.9,
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
            bbox=(0.078, 0.104, 0.312, 0.375),
            encoding=distant,
            timestamp=2.0,
            frame_number=60,
            det_score=0.9,
        )

        results = recognizer.recognize_faces([det])
        assert len(results) == 0

    def test_recognize_empty_encodings(self, sample_config, base_embedding):
        """⑩ Empty contestant_db.face_encodings yields empty result list."""
        db = self._make_db(sample_config, {})
        recognizer = FaceRecognizer(sample_config, db)

        det = FaceDetection(
            bbox=(0.078, 0.104, 0.312, 0.375),
            encoding=base_embedding,
            timestamp=0.0,
            frame_number=0,
            det_score=0.9,
        )

        results = recognizer.recognize_faces([det])
        assert results == []

    def test_matches_nearest_reference_photo_not_the_average(self, sample_config):
        """A contestant with 3 reference photos matches on ANY ONE of them.

        This is the whole point of the reference-set migration: the query is close to the
        third reference and far from the other two, which is exactly the case a single
        averaged vector per contestant gets wrong.
        """
        refs = np.stack([_normalized_vec(seed=s) for s in (1, 2, 3)])
        known = {
            "7": refs,
            "8": np.atleast_2d(_normalized_vec(seed=400)),
        }
        info = {
            "7": {"name": "Multi", "nickname": "M", "age": "21"},
            "8": {"name": "Other", "nickname": "O", "age": "23"},
        }
        db = self._make_db(sample_config, known, info)
        recognizer = FaceRecognizer(sample_config, db)

        query = _similar_vec(refs[2], noise_scale=0.01, seed=555)
        # Below the acceptance threshold against the other two references of the same
        # contestant, so only a per-photo max can match it.
        threshold = sample_config["face_recognition"]["acceptance_threshold"]
        assert np.dot(query, refs[0]) < threshold
        assert np.dot(query, refs[1]) < threshold
        # And the old averaged-vector representation would have rejected it outright.
        averaged = refs.mean(axis=0)
        averaged /= np.linalg.norm(averaged)
        assert np.dot(query, averaged) < threshold

        det = FaceDetection(
            bbox=(0.078, 0.104, 0.312, 0.375),
            encoding=query,
            timestamp=3.0,
            frame_number=90,
            det_score=0.9,
        )

        results = recognizer.recognize_faces([det])
        assert len(results) == 1
        assert results[0].contestant_id == "7"
        assert results[0].contestant_name == "Multi"


# ---------------------------------------------------------------------------
# ⑪ – ⑫  Batch recognition tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBatchRecognition:

    def test_batch_matches_single_path(self, sample_config, base_embedding):
        """⑪ recognize_faces_batch() produces the same match as recognize_faces()."""
        info = {"1": {"name": "Bob", "nickname": "B", "age": "25"}}
        db = ContestantDatabase(sample_config)
        db.face_encodings = {"1": np.atleast_2d(base_embedding)}
        db.contestant_names = ["1"]
        db.contestants_info = info
        db.flatten_references()

        recognizer = FaceRecognizer(sample_config, db)

        similar = _similar_vec(base_embedding, noise_scale=0.01, seed=77)
        det = FaceDetection(
            bbox=(0.078, 0.104, 0.312, 0.375),
            encoding=similar,
            timestamp=1.0,
            frame_number=30,
            det_score=0.9,
        )

        single_results = recognizer.recognize_faces([det])
        batch_results = recognizer.recognize_faces_batch([[det]])

        assert len(batch_results) == 1
        assert len(batch_results[0]) == len(single_results)
        if single_results:
            assert batch_results[0][0].contestant_id == single_results[0].contestant_id

    def test_batch_uses_cosine_distance(self, sample_config, base_embedding):
        """⑫ Batch path computes cosine distances (not L2)."""
        info = {"1": {"name": "Carol", "nickname": "C", "age": "22"}}
        db = ContestantDatabase(sample_config)
        db.face_encodings = {"1": np.atleast_2d(base_embedding)}
        db.contestant_names = ["1"]
        db.contestants_info = info
        db.flatten_references()

        recognizer = FaceRecognizer(sample_config, db)

        similar = _similar_vec(base_embedding, noise_scale=0.01, seed=88)
        det = FaceDetection(
            bbox=(0.078, 0.104, 0.312, 0.375),
            encoding=similar,
            timestamp=1.0,
            frame_number=30,
            det_score=0.9,
        )

        results = recognizer.recognize_faces_batch([[det]])
        assert len(results[0]) == 1

        # The stored score IS the cosine — never a value rescaled by the threshold, which
        # would mean the same face scored differently whenever the threshold moved.
        expected_match_score = np.dot(similar, base_embedding)

        assert results[0][0].match_score == pytest.approx(expected_match_score, abs=1e-4)


# ---------------------------------------------------------------------------
# ⑬ – ⑭  ContestantDatabase tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestContestantDatabase:

    def test_load_reference_cache(self, sample_config, tmp_path):
        """⑬ The consolidated .npz cache loads as a per-contestant reference set."""
        photo_dir = tmp_path / "contestants"
        ids = ["1", "1", "1", "2", "42"]
        embeddings = np.stack([_normalized_vec(seed=s) for s in range(len(ids))])
        _write_reference_cache(photo_dir, ids, embeddings)

        db = ContestantDatabase(_cache_config(sample_config, photo_dir, tmp_path))
        db.contestants_info = {
            c: {"id": c, "name": f"Name{c}", "nickname": f"Nick{c}", "age": "20"}
            for c in ("1", "2", "42")
        }

        db.build_face_encodings()

        assert set(db.face_encodings) == {"1", "2", "42"}
        assert db.face_encodings["1"].shape == (3, 512)
        assert db.face_encodings["2"].shape == (1, 512)
        assert db.face_encodings["42"].shape == (1, 512)
        np.testing.assert_allclose(db.face_encodings["1"], embeddings[:3], atol=1e-6)
        assert sorted(db.contestant_names) == ["1", "2", "42"]

    def test_reference_set_is_not_flattened(self, sample_config, tmp_path):
        """⑭ An (N, 512) block stays N separate references — not 1, and not one 1536-vector.

        Regression guard for the trap in ADR 0001: the old loader flattened before checking
        the dimension, so a 3-photo contestant became a (1536,) vector, failed the `== 512`
        check, and was silently dropped.
        """
        photo_dir = tmp_path / "contestants"
        ids = ["1", "1", "1"]
        embeddings = np.stack([_normalized_vec(seed=s) for s in (10, 11, 12)])
        _write_reference_cache(photo_dir, ids, embeddings)

        db = ContestantDatabase(_cache_config(sample_config, photo_dir, tmp_path))
        db.build_face_encodings()

        assert len(db.reference_encodings) == 3
        assert db.reference_ids == ["1", "1", "1"]
        assert all(ref.shape == (512,) for ref in db.reference_encodings)
        np.testing.assert_allclose(np.asarray(db.reference_encodings), embeddings, atol=1e-6)

    def test_stale_manifest_raises(self, sample_config, tmp_path):
        """A manifest whose reference_count disagrees with the .npz is a loud failure."""
        photo_dir = tmp_path / "contestants"
        ids = ["1", "2"]
        embeddings = np.stack([_normalized_vec(seed=s) for s in (20, 21)])
        _write_reference_cache(photo_dir, ids, embeddings, reference_count=663)

        db = ContestantDatabase(_cache_config(sample_config, photo_dir, tmp_path))

        with pytest.raises(ValueError, match="Stale reference cache"):
            db.build_face_encodings()


# ---------------------------------------------------------------------------
# ⑮  Reference cache validation — a bad cache raises, it never loads empty
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEmbeddingValidation:

    def test_missing_cache_raises(self, sample_config, tmp_path):
        """⑮ No cache file at all raises instead of quietly recognising nobody."""
        photo_dir = tmp_path / "contestants"
        photo_dir.mkdir()

        db = ContestantDatabase(_cache_config(sample_config, photo_dir, tmp_path))

        with pytest.raises(FileNotFoundError, match="Reference embedding cache not found"):
            db.build_face_encodings()

    def test_wrong_dimension_cache_raises(self, sample_config, tmp_path):
        """A cache with the wrong embedding width raises rather than loading garbage."""
        photo_dir = tmp_path / "contestants"
        _write_reference_cache(photo_dir, ["1", "2"], np.zeros((2, 128), dtype=np.float32))

        db = ContestantDatabase(_cache_config(sample_config, photo_dir, tmp_path))

        with pytest.raises(ValueError, match=r"expected \(N, 512\)"):
            db.build_face_encodings()

    def test_empty_cache_raises(self, sample_config, tmp_path):
        """A well-formed but empty cache raises — recognition would match nobody."""
        photo_dir = tmp_path / "contestants"
        _write_reference_cache(photo_dir, [], np.zeros((0, 512), dtype=np.float32))

        db = ContestantDatabase(_cache_config(sample_config, photo_dir, tmp_path))

        with pytest.raises(ValueError, match="zero reference embeddings"):
            db.build_face_encodings()
