"""
Integrations module for MV Face Recognition.

This module provides integrations with external services:
- HuggingFace XET: Dataset storage for contestant data, embeddings, and videos
"""

from .huggingface_xet import HuggingFaceDataset

__all__ = ["HuggingFaceDataset"]
