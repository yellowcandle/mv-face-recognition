"""
Video processing service for face recognition in MV videos.
"""

from __future__ import annotations

from typing import Any, List


class VideoProcessor:
    """
    Minimal skeleton for a video processing service.

    This placeholder provides an API that can be wired to actual video processing
    in subsequent iterations (e.g., frame extraction, embedding computation, etc.).
    """

    def __init__(self, model_name: str = "default"):
        self.model_name = model_name

    def process(self, video_input: Any) -> Any:
        """
        Process the given video input and return a processed representation.

        This placeholder simply returns the input unchanged to keep the pipeline
        functional during early integration.
        """
        return video_input

def load_model(model_name: str = "default") -> str:
    """
    Placeholder loader for the video processor model.

    Returns the model name as a stand-in for a loaded model handle.
    """
    return model_name

__all__ = ["VideoProcessor", "load_model"]
