from __future__ import annotations

from typing import Any, List


class EmbeddingManager:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs

    def get_all_contestants(self) -> List[Any]:
        raise NotImplementedError

    def contestant_count(self) -> int:
        raise NotImplementedError

    def embedding_count(self) -> int:
        raise NotImplementedError

    def search_contestants(self, query: str) -> List[Any]:
        raise NotImplementedError
