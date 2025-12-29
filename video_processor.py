"""Compatibility shim for legacy imports.

Some tests/tools import `video_processor.VideoProcessor` from the repo root.
The active implementation lives in `mvp-processor/src/video_processor.py`.

This shim loads that file by path and re-exports `VideoProcessor`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_mvp_video_processor_module() -> ModuleType:
    module_path = (
        Path(__file__).resolve().parent / "mvp-processor" / "src" / "video_processor.py"
    )

    spec = importlib.util.spec_from_file_location("mvp_video_processor", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mvp_video_processor = _load_mvp_video_processor_module()

VideoProcessor = _mvp_video_processor.VideoProcessor  # type: ignore[attr-defined]

__all__ = ["VideoProcessor"]
