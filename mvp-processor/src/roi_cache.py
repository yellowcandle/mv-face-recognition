from typing import List, Optional, Dict, Any
import logging

from src.roi import ROI

logger = logging.getLogger(__name__)


class ROICache:
    def __init__(self, ttl_multiplier: int = 2):
        self.ttl_multiplier = ttl_multiplier
        self._cache: Dict[int, tuple[int, List[ROI]]] = {}
        self._total_hits = 0
        self._total_misses = 0

    def update(self, frame_idx: int, rois: List[ROI]) -> None:
        self._cache[frame_idx] = (frame_idx, rois)
        logger.debug(f"Updated cache for frame {frame_idx} with {len(rois)} ROIs")

    def get(
        self, frame_idx: int, interval: int, current_frame: int
    ) -> Optional[List[ROI]]:
        if frame_idx not in self._cache:
            self._total_misses += 1
            return None

        last_updated, rois = self._cache[frame_idx]

        if self.is_expired(frame_idx, current_frame, interval):
            self._total_misses += 1
            return None

        self._total_hits += 1
        return rois

    def is_expired(self, frame_idx: int, current_frame: int, interval: int) -> bool:
        if frame_idx not in self._cache:
            return True

        last_updated, _ = self._cache[frame_idx]

        ttl = interval * self.ttl_multiplier

        age = current_frame - last_updated

        return age > ttl

    def clear(self) -> None:
        self._cache.clear()
        logger.debug("ROI cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        total_requests = self._total_hits + self._total_misses

        hit_rate = self._total_hits / total_requests if total_requests > 0 else 0.0

        return {
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": hit_rate,
        }
