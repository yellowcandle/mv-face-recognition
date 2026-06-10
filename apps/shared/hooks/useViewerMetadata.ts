import { useState, useEffect, useMemo, useCallback } from 'react';
import type { FrameData, VideoMetadata } from '../types';

export function useViewerMetadata(apiBase: string, videoId: string | null) {
  const [metadata, setMetadata] = useState<VideoMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load metadata when videoId changes
  useEffect(() => {
    if (!videoId) return;
    setLoading(true);
    setError(null);

    fetch(`${apiBase}/api/videos/metadata/dense/${videoId}`)
      .then(r => {
        if (!r.ok) throw new Error(`Failed to load metadata: ${r.status}`);
        return r.json();
      })
      .then(data => {
        setMetadata(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiBase, videoId]);

  // Sort frame_data by timestamp for binary search
  const sortedFrames = useMemo(() => {
    if (!metadata?.frame_data) return [];
    return [...metadata.frame_data].sort((a, b) => a.timestamp - b.timestamp);
  }, [metadata]);

  const timestamps = useMemo(() => sortedFrames.map(f => f.timestamp), [sortedFrames]);

  // Get frame data at a given time (floor match - most recent past detection)
  const getFrameAtTime = useCallback((time: number): FrameData | null => {
    if (sortedFrames.length === 0) return null;

    // Binary search for floor
    let lo = 0, hi = sortedFrames.length - 1;
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
  }, [sortedFrames, timestamps]);

  // Convert frame recognitions to FaceDetection format for FaceOverlay
  const getFacesAtTime = useCallback((time: number) => {
    const frame = getFrameAtTime(time);
    if (!frame || !frame.recognitions) return [];

    return frame.recognitions.map(r => {
      const [top, right, bottom, left] = r.face_location;
      return {
        bbox: [left, top, right, bottom] as [number, number, number, number],
        confidence: r.confidence,
        contestant_name: r.contestant_nickname || r.contestant_name,
        contestant_id: r.contestant_id,
        contestant_nickname: r.contestant_nickname,
        detection_confidence: r.confidence,
        recognition_confidence: r.confidence,
        matched: true,
      };
    });
  }, [getFrameAtTime]);

  // Stable identity so consumers can safely use the result in effect deps
  return useMemo(
    () => ({ metadata, loading, error, getFrameAtTime, getFacesAtTime }),
    [metadata, loading, error, getFrameAtTime, getFacesAtTime],
  );
}
