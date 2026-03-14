import { useQuery } from '@tanstack/react-query';
import type { CoverageData } from '../types';

export function useCoverage() {
  return useQuery<CoverageData>({
    queryKey: ['coverage'],
    queryFn: async () => {
      const res = await fetch('/data/coverage.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 10 * 60 * 1000,
  });
}
