import { useQuery } from '@tanstack/react-query';

export function useContestants(apiBase = '') {
  return useQuery({
    queryKey: ['contestants'],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/api/contestants`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
  });
}
