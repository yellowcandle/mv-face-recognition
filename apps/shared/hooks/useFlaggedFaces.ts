import { useQuery } from '@tanstack/react-query';
import { adminFetch } from '../lib/adminApi';
import type { FlaggedFace } from '../types';

/**
 * Flags are collected by whichever origin serves the admin: `local_api.py`, or the Worker's KV
 * behind Cloudflare Access. `enabled` keeps the viewer from asking for them at all — it is
 * read-only and anonymous, so the call would only ever return 401.
 */
export function useFlaggedFaces(apiBase = '', enabled = true) {
  return useQuery<FlaggedFace[]>({
    queryKey: ['flaggedFaces'],
    enabled,
    queryFn: async () => {
      const res = await adminFetch(`${apiBase}/admin/api/faces/flagged?details=true`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return data.flagged_faces || [];
    },
    staleTime: 60 * 1000,
  });
}
