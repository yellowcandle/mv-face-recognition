"""Face embedding value object.

`DetectedFace` carries an optional embedding and serialises it through this class. The
original module also held dataset helpers; they had no remaining callers when the legacy
pipeline surface was removed, so this keeps only the value object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FaceEmbedding:
    """A face embedding vector plus the provenance needed to reproduce it."""

    vector: list[float]
    contestant_id: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vector": list(self.vector),
            "contestant_id": self.contestant_id,
            "model": self.model,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FaceEmbedding":
        vector = data.get("vector") or data.get("embedding") or []
        return cls(
            vector=[float(value) for value in vector],
            contestant_id=data.get("contestant_id"),
            model=data.get("model"),
            metadata=dict(data.get("metadata") or {}),
        )
