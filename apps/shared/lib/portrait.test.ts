import { afterEach, expect, test, vi } from 'vite-plus/test';
import { portraitSrc } from './portrait';

const U = '/api/contestants/1/thumb/face';
const at = (hostname: string) => vi.stubGlobal('location', { hostname });
afterEach(() => vi.unstubAllGlobals());

test('on the deployed site it asks Cloudflare for 2x the display width, snapped to a size', () => {
  at('mv.herballemon.dev');
  expect(portraitSrc(U, 28)).toBe(`/cdn-cgi/image/width=64,format=auto${U}`);
  expect(portraitSrc(U, 60)).toBe(`/cdn-cgi/image/width=128,format=auto${U}`);
  expect(portraitSrc(U, 128)).toBe(`/cdn-cgi/image/width=256,format=auto${U}`);
  expect(portraitSrc(U, 204)).toBe(`/cdn-cgi/image/width=512,format=auto${U}`);
  expect(portraitSrc(U, 900)).toBe(`/cdn-cgi/image/width=512,format=auto${U}`);
});

test('anywhere else the url is untouched', () => {
  at('localhost');
  expect(portraitSrc(U, 64)).toBe(U);
});

test('null passes through and absolute urls are left alone', () => {
  at('mv.herballemon.dev');
  expect(portraitSrc(null, 64)).toBeNull();
  expect(portraitSrc(undefined, 64)).toBeNull();
  expect(portraitSrc('https://elsewhere.test/a.webp', 64)).toBe('https://elsewhere.test/a.webp');
});
