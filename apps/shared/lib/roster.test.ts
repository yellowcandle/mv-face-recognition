import { expect, test } from 'vite-plus/test';
import { withCoverage } from './roster';
import type { Contestant } from '../types';

const listed = { id: '25', nickname: 'Emiko', quality: 'good' } as Contestant;
const covered = {
  id: '25',
  nickname: 'Emiko',
  quality: 'weak',
  detection_count: 7,
  videos_seen_in: 2,
} as Contestant;

test('coverage supplies the counts and the quality the plain list lacks', () => {
  const [row] = withCoverage([listed], [covered]);
  expect(row.detection_count).toBe(7);
  expect(row.videos_seen_in).toBe(2);
  expect(row.quality).toBe('weak');
});

test('the roster still lists everyone while coverage is missing or partial', () => {
  expect(withCoverage([listed], undefined)).toEqual([listed]);
  expect(withCoverage([listed], [])).toEqual([listed]);
});
