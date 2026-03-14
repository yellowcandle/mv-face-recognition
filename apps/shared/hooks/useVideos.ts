import { useQuery } from '@tanstack/react-query';
import type { Video } from '../types';

export function useVideos(apiBase = '') {
  return useQuery<Video[]>({
    queryKey: ['videos'],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/api/videos/processed/list`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    },
    staleTime: 5 * 60 * 1000,
  });
}
