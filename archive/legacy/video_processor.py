# video_processor.py
"""
Compatibility wrapper for MVP VideoProcessor
This module exposes VideoProcessor (and FrameProcessor when available)
by dynamically loading the real implementation from the MVP package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Optional


def _load_real_video_processor():
    # This file is at archive/legacy/video_processor.py
    # Need to go up 3 levels: legacy -> archive -> repo_root
    root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        root / "mvp-processor" / "src" / "video_processor.py",
        root / "mvp-processor" / "video_processor.py",
    ]
    real_path: Optional[Path] = None
    for p in candidates:
        if p.exists():
            real_path = p
            break
    if real_path is None:
        raise ImportError(
            "Cannot locate MVP VideoProcessor implementation at expected paths: "
            f"{[str(c) for c in candidates]}"
        )

    spec = importlib.util.spec_from_file_location("mv_video_processor", str(real_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create import spec for {real_path}")

    module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore
    return module


_real = _load_real_video_processor()

# Expose the real classes if they exist in the MVP module
VideoProcessor = getattr(_real, "VideoProcessor", None)
FrameProcessor = getattr(_real, "FrameProcessor", None)

if VideoProcessor is None:

    class _NoVideoProcessor:  # pragma: no cover
        pass

    VideoProcessor = _NoVideoProcessor  # type: ignore

__all__ = ["VideoProcessor"]
if FrameProcessor is not None:
    __all__.append("FrameProcessor")
