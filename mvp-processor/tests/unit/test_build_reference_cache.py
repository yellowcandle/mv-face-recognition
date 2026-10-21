"""Curation of the reference cache: drop photos that look like another contestant."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_SPEC = importlib.util.spec_from_file_location(
    "build_reference_cache", _SCRIPTS / "build_reference_cache.py"
)
assert _SPEC is not None and _SPEC.loader is not None
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)


def test_drops_a_reference_that_matches_another_contestant_better() -> None:
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],  # contestant 1: identical to contestant 2's photo
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],  # contestant 2
        ],
        dtype=np.float32,
    )
    ids = np.array(["1", "1", "1", "2"])

    keep = module.curate_references(embeddings, ids)

    assert not keep[0], "the cross-contestant duplicate must be dropped"
    assert keep[1] and keep[2], "the floor keeps two references for contestant 1"
    assert keep[3], "a thin roster entry is never erased"


def test_keeps_every_contestant_with_at_most_two_photos() -> None:
    embeddings = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    ids = np.array(["1", "1", "2"])

    keep = module.curate_references(embeddings, ids)

    assert keep.all()
