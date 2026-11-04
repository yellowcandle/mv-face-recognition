import type { Contestant } from '../types';

/**
 * `/api/contestants` has no detection counts, and its quality only looks at references. Coverage
 * has both, so it wins where it has an entry; the roster itself stays the plain list's.
 */
export function withCoverage(
  contestants: Contestant[],
  coverage: Contestant[] | undefined,
): Contestant[] {
  const byId = new Map(coverage?.map((c) => [c.id, c]));
  return contestants.map((c) => ({ ...c, ...byId.get(c.id) }));
}
