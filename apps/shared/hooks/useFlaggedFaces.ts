import { useQuery } from '@tanstack/react-query';
import type { FlaggedFace } from '../types';

export function useFlaggedFaces(apiBase = '') {
  return useQuery<FlaggedFace[]>({
    queryKey: ['flaggedFaces'],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/api/faces/flagged?details=true`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return data.flagged_faces || [];
    },
    staleTime: 60 * 1000,
  });
}
