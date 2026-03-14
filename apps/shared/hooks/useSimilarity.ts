import { useQuery } from '@tanstack/react-query';
import type { SimilarityData, ConfusionPair } from '../types';

export function useSimilarity() {
  const matrix = useQuery<SimilarityData>({
    queryKey: ['similarity-matrix'],
    queryFn: async () => {
      const res = await fetch('/data/similarity_matrix.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 10 * 60 * 1000,
    enabled: false, // load on demand
  });

  const pairs = useQuery<ConfusionPair[]>({
    queryKey: ['top-pairs'],
    queryFn: async () => {
      const res = await fetch('/data/top_pairs.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return data.pairs || [];
    },
    staleTime: 10 * 60 * 1000,
    enabled: false,
  });

  function load() {
    matrix.refetch();
    pairs.refetch();
  }

  return { matrix, pairs, load };
}
