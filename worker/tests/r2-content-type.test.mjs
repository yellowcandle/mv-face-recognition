/**
 * `/videos/` serves stills, not only reels.
 *
 * The route used to answer every R2 object with `Content-Type: video/mp4`, so a report image
 * arrived as a video and no browser would draw it. The type now comes from the object's stored
 * metadata, falling back to the key's extension — including when `put` recorded the useless
 * `application/octet-stream`. Nothing enforced that, so a future "simplification" back to a
 * constant would pass every other test.
 *
 * Run: node --test tests/*.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKER_DIR = join(HERE, '..');
const ENTRY = join(WORKER_DIR, 'src/index.ts');

let bundlePath = null;
function loadWorker() {
  if (!bundlePath) {
    bundlePath = join(mkdtempSync(join(tmpdir(), 'worker-types-')), 'worker.mjs');
    execFileSync(
      join(WORKER_DIR, 'node_modules/.bin/esbuild'),
      [ENTRY, '--bundle', '--format=esm', '--platform=neutral', '--outfile=' + bundlePath],
      { cwd: WORKER_DIR, stdio: 'pipe' },
    );
  }
  return import(pathToFileURL(bundlePath).href).then((mod) => mod.default);
}

/** A bucket holding one object, with the metadata a real `put` would have left. */
function bucketWith(key, contentType) {
  return {
    get: async () => ({
      key,
      body: new Uint8Array([0xff, 0xd8, 0xff]),
      size: 3,
      httpMetadata: contentType ? { contentType } : undefined,
      writeHttpMetadata() {},
    }),
  };
}

const contentTypeOf = async (key, stored) => {
  const worker = await loadWorker();
  const res = await worker.fetch(
    new Request(`https://mv.example/videos/${encodeURIComponent(key)}`),
    { METADATA_KV: { get: async () => null }, JOB_STORE: { get: async () => null }, VIDEOS_BUCKET: bucketWith(key, stored) },
  );
  return { status: res.status, type: res.headers.get('content-type') };
};

test('a still is served as an image even when the upload recorded octet-stream', async () => {
  const { status, type } = await contentTypeOf('reports/street/frame-1.jpg', 'application/octet-stream');
  assert.equal(status, 200);
  assert.equal(type, 'image/jpeg');
});

test('a stored image type wins over the key', async () => {
  const { type } = await contentTypeOf('reports/street/odd-name', 'image/webp');
  assert.equal(type, 'image/webp');
});

test('a reel keeps its video type', async () => {
  const { type } = await contentTypeOf('processed_videos/1-前傳_1080p.mp4', null);
  assert.equal(type, 'video/mp4');
});

test('an object with neither a stored type nor a known extension is not called a video', async () => {
  const { type } = await contentTypeOf('reports/street/blob', null);
  assert.equal(type, 'application/octet-stream');
});
