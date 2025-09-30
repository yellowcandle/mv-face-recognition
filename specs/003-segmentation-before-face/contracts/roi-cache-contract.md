# ROICache Contract

## Purpose
Cache person ROIs between segmentation runs with adaptive TTL to optimize performance.

## Interface

### Constructor
```python
ROICache(ttl_multiplier: int = 2)
```

**Preconditions**:
- `ttl_multiplier` >= 1

**Postconditions**:
- Empty cache initialized
- TTL multiplier stored

---

### update(frame_idx: int, rois: List[ROI]) → None
```python
def update(self, frame_idx: int, rois: List[ROI]) -> None:
    """
    Store ROIs for given frame index.

    Args:
        frame_idx: Frame number (0-indexed)
        rois: List of ROI objects from segmentation

    Raises:
        ValueError: If frame_idx < 0
    """
```

**Preconditions**:
- `frame_idx >= 0`
- `rois` is valid list (may be empty)

**Postconditions**:
- ROIs stored at `frame_idx` in cache
- `last_updated[frame_idx]` set to `frame_idx`
- Previous ROIs at same index overwritten

**Side Effects**:
- Cache size increases by 1 entry (if new frame_idx)

---

### get(frame_idx: int, interval: int, current_frame: int) → Optional[List[ROI]]
```python
def get(self, frame_idx: int, interval: int, current_frame: int) -> Optional[List[ROI]]:
    """
    Retrieve cached ROIs if not expired.

    Args:
        frame_idx: Frame number to lookup
        interval: Segmentation interval from config
        current_frame: Current processing frame number

    Returns:
        List of ROIs if valid, None if miss or expired
    """
```

**Preconditions**:
- `frame_idx >= 0`
- `interval > 0`
- `current_frame >= 0`

**Postconditions**:
- Returns cached ROIs if entry exists and not expired
- Returns `None` if:
  - No entry at `frame_idx` (cache miss)
  - Entry expired: `(current_frame - last_updated[frame_idx]) > (interval * ttl_multiplier)`
- Expired entries automatically removed from cache

**Invariants**:
- Returned ROIs are same objects stored via `update()` (no copies)
- Cache does not modify ROI objects

---

### is_expired(frame_idx: int, current_frame: int, interval: int) → bool
```python
def is_expired(self, frame_idx: int, current_frame: int, interval: int) -> bool:
    """
    Check if cache entry is stale.

    Returns:
        True if entry expired or missing, False if valid
    """
```

**Logic**:
```
TTL = interval * ttl_multiplier
age = current_frame - last_updated[frame_idx]
expired = (age > TTL) OR (frame_idx not in cache)
```

---

### clear() → None
```python
def clear(self) -> None:
    """Clear all cache entries."""
```

**Postconditions**:
- Cache is empty
- All stored ROIs released from memory

---

### get_stats() → Dict[str, int]
```python
def get_stats(self) -> Dict[str, int]:
    """
    Get cache statistics for observability.

    Returns:
        Dict with keys: total_entries, total_hits, total_misses, hit_rate
    """
```

**Postconditions**:
- Returns current cache statistics
- `hit_rate = total_hits / (total_hits + total_misses)` if denominator > 0, else 0.0

---

## State Transitions

```
Empty
  ↓ update()
Populated
  ↓ get() [within TTL]
Hit (return ROIs)
  ↓ get() [expired]
Miss (return None, delete entry)
  ↓ clear()
Empty
```

---

## Error Handling

| Error Condition | Exception | Expected Behavior |
|----------------|-----------|-------------------|
| Negative frame_idx | `ValueError` | Raise immediately |
| Invalid interval (<=0) | `ValueError` | Raise immediately |
| Empty ROI list in update | N/A | Store empty list (valid state) |
| Cache full (>10k entries) | N/A | LRU eviction of oldest entries |

---

## Contract Tests

### test_roi_cache_initialization
- Given: Default ttl_multiplier
- When: ROICache() created
- Then: Cache empty, ttl_multiplier=2

### test_update_stores_rois
- Given: Empty cache
- When: update(frame_idx=0, rois=[roi1, roi2])
- Then: get(0, interval=10, current_frame=0) returns [roi1, roi2]

### test_get_cache_hit
- Given: ROIs stored at frame 0
- When: get(0, interval=10, current_frame=15)
- Then: Returns stored ROIs (within TTL=20)

### test_get_cache_miss_expired
- Given: ROIs stored at frame 0, ttl_multiplier=2, interval=10
- When: get(0, interval=10, current_frame=25)
- Then: Returns None (age=25 > TTL=20)

### test_get_cache_miss_not_found
- Given: Empty cache
- When: get(99, interval=10, current_frame=100)
- Then: Returns None

### test_clear_empties_cache
- Given: Cache with 10 entries
- When: clear()
- Then: Cache size = 0, get() returns None

### test_stats_tracks_hits_misses
- Given: Cache with entries
- When: Multiple get() calls with hits and misses
- Then: get_stats() returns correct counts

### test_ttl_adaptive_to_interval
- Given: ttl_multiplier=2, interval=20
- When: ROIs stored at frame 0
- Then: Expires after 40 frames (2 * 20)

---

## Performance Requirements

- `update()`: O(1) time complexity
- `get()`: O(1) average time complexity
- Memory: O(N) where N = number of cached frames (max ~1000 at 30fps)
- Memory per entry: ~200 bytes (frame_idx + 5 ROIs * 32 bytes)

---

## Thread Safety

**Not thread-safe**: Designed for single-threaded video processing pipeline. If multi-threaded processing is added, use locks or concurrent data structures.

---

## Dependencies

- `typing` (List, Optional, Dict)
- `dataclasses` or plain Python classes for ROI