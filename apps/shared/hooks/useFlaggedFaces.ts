import { useQuery } from '@tanstack/react-query';
import type { FlaggedFace } from '../types';

/**
 * Flagged faces are only collected by the local admin API; the deployed Worker is read-only
 * (ADR 0003). `enabled` keeps the viewer from requesting a route that no longer exists there.
 */
export function useFlaggedFaces(apiBase = '', enabled = true) {
  return useQuery<FlaggedFace[]>({
    queryKey: ['flaggedFaces'],
    enabled,
    queryFn: async () => {
      const res = await fetch(`${apiBase}/api/faces/flagged?details=true`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return data.flagged_faces || [];
    },
    staleTime: 60 * 1000,
  });
}
