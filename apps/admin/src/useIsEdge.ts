import { useQuery } from '@tanstack/react-query';
import { adminFetch } from '@mv/shared';

/**
 * Whether the Admin is served by the Worker ("edge") rather than the local API. `undefined`
 * until the probe answers; a failed probe counts as local, so nothing is hidden on a guess.
 */
export function useIsEdge(): boolean | undefined {
  return useQuery({
    queryKey: ['system-status-mode'],
    staleTime: Infinity,
    queryFn: async () => {
      try {
        const res = await adminFetch('/admin/api/system/status');
        const status: unknown = res.ok ? await res.json() : null;
        return !!status && typeof status === 'object' && 'mode' in status && status.mode === 'edge';
      } catch {
        return false;
      }
    },
  }).data;
}
