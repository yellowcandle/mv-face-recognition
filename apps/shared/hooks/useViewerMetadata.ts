import { useState, useEffect, useMemo, useCallback } from 'react';
import type { FaceDetection, FrameData, VideoMetadata } from '../types';

export function useViewerMetadata(apiBase: string, videoId: string | null) {
  const [metadata, setMetadata] = useState<VideoMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load metadata when videoId changes
  useEffect(() => {
    if (!videoId) return;
    setLoading(true);
    setError(null);

    fetch(`${apiBase}/api/videos/metadata/dense/${encodeURIComponent(videoId)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load metadata: ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setMetadata(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiBase, videoId]);

  // Sort frame_data by timestamp for binary search
  const sortedFrames = useMemo(() => {
    if (!metadata?.frame_data) return [];
    return [...metadata.frame_data].sort((a, b) => a.timestamp - b.timestamp);
  }, [metadata]);

  const timestamps = useMemo(() => sortedFrames.map((f) => f.timestamp), [sortedFrames]);

  // Get frame data at a given time (floor match - most recent past detection)
  const getFrameAtTime = useCallback(
    (time: number): FrameData | null => {
      if (sortedFrames.length === 0) return null;

      // Binary search for floor
      let lo = 0,
        hi = sortedFrames.length - 1;
      let result = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (timestamps[mid] <= time) {
          result = mid;
          lo = mid + 1;
        } else {
          hi = mid - 1;
        }
      }

      return result >= 0 ? sortedFrames[result] : null;
    },
    [sortedFrames, timestamps],
  );

  // Stored detections already carry the served shape: frame-fraction bbox, raw cosine
  // match_score (null when unmatched), det_score, ids. Pass them through — no reorder,
  // no rescale, no duplication of one score under three names.
  const getFacesAtTime = useCallback(
    (time: number): FaceDetection[] => {
      const frame = getFrameAtTime(time);
      if (!frame?.detections) return [];

      return frame.detections.map((d) => ({
        bbox: d.bbox,
        tracker_id: d.tracker_id,
        match_source: d.match_source,
        match_score: d.match_score,
        det_score: d.det_score,
        contestant_id: d.contestant_id,
        contestant_name: d.contestant_name,
        contestant_nickname: d.contestant_nickname,
        matched: d.contestant_id != null,
      }));
    },
    [getFrameAtTime],
  );

  // Stable identity so consumers can safely use the result in effect deps
  return useMemo(
    () => ({ metadata, loading, error, getFrameAtTime, getFacesAtTime }),
    [metadata, loading, error, getFrameAtTime, getFacesAtTime],
  );
}
