import pytest


class TestROICacheContract:
    def test_initialization_with_ttl_multiplier(self):
        """Test ROICache initialization with ttl_multiplier=2"""
        from src.roi_cache import ROICache

        cache = ROICache(ttl_multiplier=2)

        assert cache is not None
        assert cache.ttl_multiplier == 2

    def test_update_stores_rois_at_frame_idx(self):
        """Test update() stores ROIs at frame_idx"""
        from src.roi_cache import ROICache
        from src.roi import ROI

        cache = ROICache(ttl_multiplier=2)

        rois = [
            ROI(x1=10, y1=10, x2=100, y2=100, confidence=0.9, area=8100),
            ROI(x1=200, y1=200, x2=300, y2=300, confidence=0.8, area=10000),
        ]

        cache.update(frame_idx=0, rois=rois)

        stored_rois = cache.get(frame_idx=0, interval=10, current_frame=0)
        assert len(stored_rois) == 2

    def test_get_returns_cached_rois_within_ttl(self):
        """Test get() returns cached ROIs within TTL (frame 0 stored, retrieved at frame 15 with interval=10)"""
        from src.roi_cache import ROICache
        from src.roi import ROI

        cache = ROICache(ttl_multiplier=2)

        rois = [ROI(x1=10, y1=10, x2=100, y2=100, confidence=0.9, area=8100)]

        cache.update(frame_idx=0, rois=rois)

        retrieved_rois = cache.get(frame_idx=0, interval=10, current_frame=15)

        assert retrieved_rois is not None
        assert len(retrieved_rois) == 1

    def test_get_returns_none_when_expired(self):
        """Test get() returns None when expired (frame 0 stored, frame 25 retrieved, TTL=20)"""
        from src.roi_cache import ROICache
        from src.roi import ROI

        cache = ROICache(ttl_multiplier=2)

        rois = [ROI(x1=10, y1=10, x2=100, y2=100, confidence=0.9, area=8100)]

        cache.update(frame_idx=0, rois=rois)

        retrieved_rois = cache.get(frame_idx=0, interval=10, current_frame=25)

        assert retrieved_rois is None

    def test_get_returns_none_for_cache_miss(self):
        """Test get() returns None for cache miss (frame not in cache)"""
        from src.roi_cache import ROICache

        cache = ROICache(ttl_multiplier=2)

        retrieved_rois = cache.get(frame_idx=999, interval=10, current_frame=999)

        assert retrieved_rois is None

    def test_is_expired_logic(self):
        """Test is_expired() logic: (current_frame - last_updated) > (interval * ttl_multiplier)"""
        from src.roi_cache import ROICache
        from src.roi import ROI

        cache = ROICache(ttl_multiplier=2)

        rois = [ROI(x1=10, y1=10, x2=100, y2=100, confidence=0.9, area=8100)]

        cache.update(frame_idx=0, rois=rois)

        assert not cache.is_expired(frame_idx=0, current_frame=10, interval=10)

        assert not cache.is_expired(frame_idx=0, current_frame=20, interval=10)

        assert cache.is_expired(frame_idx=0, current_frame=25, interval=10)

    def test_clear_empties_cache(self):
        """Test clear() empties cache"""
        from src.roi_cache import ROICache
        from src.roi import ROI

        cache = ROICache(ttl_multiplier=2)

        rois = [ROI(x1=10, y1=10, x2=100, y2=100, confidence=0.9, area=8100)]

        cache.update(frame_idx=0, rois=rois)
        cache.update(frame_idx=10, rois=rois)
        cache.update(frame_idx=20, rois=rois)

        cache.clear()

        assert cache.get(frame_idx=0, interval=10, current_frame=0) is None
        assert cache.get(frame_idx=10, interval=10, current_frame=10) is None
        assert cache.get(frame_idx=20, interval=10, current_frame=20) is None

    def test_get_stats_returns_metrics(self):
        """Test get_stats() returns hit_rate, total_hits, total_misses"""
        from src.roi_cache import ROICache
        from src.roi import ROI

        cache = ROICache(ttl_multiplier=2)

        rois = [ROI(x1=10, y1=10, x2=100, y2=100, confidence=0.9, area=8100)]

        cache.update(frame_idx=0, rois=rois)

        cache.get(frame_idx=0, interval=10, current_frame=5)
        cache.get(frame_idx=0, interval=10, current_frame=10)

        cache.get(frame_idx=999, interval=10, current_frame=999)

        stats = cache.get_stats()

        assert "total_hits" in stats
        assert "total_misses" in stats
        assert "hit_rate" in stats
        assert stats["total_hits"] == 2
        assert stats["total_misses"] == 1
        assert abs(stats["hit_rate"] - 0.666) < 0.01
