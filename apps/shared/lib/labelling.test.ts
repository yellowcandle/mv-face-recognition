import { describe, expect, it } from 'vite-plus/test';
import { slipTime, sheetPosition } from './labelling';

describe('slipTime', () => {
  it('reads a local timestamp as MM-DD HH:mm', () => {
    expect(slipTime('2026-11-01T00:31:42')).toBe('11-01 00:31');
  });

  it('takes a Date too', () => {
    expect(slipTime(new Date(2026, 0, 5, 9, 7))).toBe('01-05 09:07');
  });

  it('shows an unparseable value as it came rather than NaN', () => {
    expect(slipTime('not-a-date')).toBe('not-a-date');
  });
});

describe('sheetPosition', () => {
  it('counts from one', () => {
    expect(sheetPosition(10, 186)).toBe('在列第 11 / 186 張');
  });

  it('says so when a filter has taken the open track out of view', () => {
    expect(sheetPosition(-1, 186)).toBe('不在目前篩選內');
  });
});
