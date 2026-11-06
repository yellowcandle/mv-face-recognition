"""The saved embeddings must line up with the metadata's frame and detection order."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from process_video import save_detection_embeddings


def test_rows_align_with_frame_and_detection_order(tmp_path):
    a, b, c = (np.full(512, v, dtype=np.float64) for v in (0.1, 0.2, 0.3))
    frames = [
        (4, [SimpleNamespace(encoding=a), SimpleNamespace(encoding=b)]),
        (9, [SimpleNamespace(encoding=c)]),
    ]
    path = tmp_path / "reel_embeddings.npz"

    save_detection_embeddings(path, frames)

    saved = np.load(path)
    assert saved["frame_number"].tolist() == [4, 4, 9]
    assert saved["detection_index"].tolist() == [0, 1, 0]
    assert saved["embeddings"].dtype == np.float32
    assert np.allclose(saved["embeddings"][1], b)


def test_a_reel_with_no_faces_still_writes_a_readable_file(tmp_path):
    path = tmp_path / "empty_embeddings.npz"

    save_detection_embeddings(path, [])

    assert np.load(path)["embeddings"].shape == (0, 512)
