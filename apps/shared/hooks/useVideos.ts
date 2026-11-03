import { useQuery } from '@tanstack/react-query';
import type { Video } from '../types';

/**
 * `test-*` clips are fixtures, not reels: the Viewer never lists them. The Admin
 * labeller passes `includeTests` because it still has to open them.
 */
export function useVideos(
  apiBase = '',
  { includeTests = false }: { includeTests?: boolean } = {},
) {
  return useQuery<Video[]>({
    queryKey: ['videos', includeTests],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/api/videos/processed/list`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      return includeTests ? list : list.filter((v) => !v.id.startsWith('test-'));
    },
    staleTime: 5 * 60 * 1000,
  });
}
