import { useQuery } from '@tanstack/react-query';
import { isTestClip } from '../lib/reels';
import type { Video } from '../types';

/**
 * `test-*` clips are fixtures, not reels: the Viewer never lists them. The Admin passes
 * `includeTests` where it counts them (儀表, 管理), looks one up (待核) or opens them (標註, 播放).
 */
export function useVideos(apiBase = '', { includeTests = false }: { includeTests?: boolean } = {}) {
  return useQuery<Video[]>({
    queryKey: ['videos', includeTests],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/api/videos/processed/list`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      return includeTests ? list : list.filter((v) => !isTestClip(v.id));
    },
    staleTime: 5 * 60 * 1000,
  });
}
