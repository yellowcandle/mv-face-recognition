/**
 * A shared link has to arrive with the head that link promised.
 *
 * The bundle ships one SPA shell, so every route would otherwise serve the 點唱單 title with no
 * Open Graph tags — which is what a Threads unfurl reads. `/street` is the page handed out as a
 * reply to a public post, so its title, description and card image are asserted here; a route the
 * map does not list must stay untouched, or every page would claim to be the street report.
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
    bundlePath = join(mkdtempSync(join(tmpdir(), 'worker-heads-')), 'worker.mjs');
    execFileSync(
      join(WORKER_DIR, 'node_modules/.bin/esbuild'),
      [ENTRY, '--bundle', '--format=esm', '--platform=neutral', '--outfile=' + bundlePath],
      { cwd: WORKER_DIR, stdio: 'pipe' },
    );
  }
  return import(pathToFileURL(bundlePath).href).then((mod) => mod.default);
}

/** Only the static routes are exercised, so KV and R2 are never touched. */
const env = {
  METADATA_KV: { get: async () => null, put: async () => {}, delete: async () => {} },
  JOB_STORE: { get: async () => null, put: async () => {}, delete: async () => {} },
  VIDEOS_BUCKET: { get: async () => null, head: async () => null },
  ENVIRONMENT: 'test',
};

const fetchHtml = async (worker, path) => {
  const res = await worker.fetch(new Request(`https://mv.example${path}`), env);
  return { status: res.status, type: res.headers.get('content-type'), body: await res.text() };
};

test('/street serves the street report head', async () => {
  const worker = await loadWorker();
  const { status, type, body } = await fetchHtml(worker, '/street');

  assert.equal(status, 200);
  assert.match(type ?? '', /text\/html/);
  assert.match(body, /<title>[^<]*街拍判讀[^<]*<\/title>/);
  assert.match(body, /<meta property="og:title" content="[^"]*街拍判讀/);
  assert.match(body, /<meta property="og:description"/);
  assert.match(
    body,
    /<meta property="og:image" content="https:\/\/mv\.example\/videos\/reports\/street-photos-2026-11-15\/frame-1\.jpg"/,
  );
  // One title, one description: a duplicated pair means the injector appended instead of replacing.
  assert.equal(body.match(/<title>/g).length, 1);
  assert.equal(body.match(/name="description"/g).length, 1);
});

test('routes the map does not list keep the shell head', async () => {
  const worker = await loadWorker();
  const { status, body } = await fetchHtml(worker, '/cast');

  assert.equal(status, 200);
  assert.match(body, /<title>點唱單 · MV Face Recognition<\/title>/);
  assert.doesNotMatch(body, /og:title/);
  assert.doesNotMatch(body, /name="description"/);
});

test('/street/ gets the same head as /street', async () => {
  const worker = await loadWorker();
  const { status, body } = await fetchHtml(worker, '/street/');

  assert.equal(status, 200);
  assert.match(body, /<title>[^<]*街拍判讀[^<]*<\/title>/);
});

test('a still recorded as octet-stream is served by its extension', async () => {
  const worker = await loadWorker();
  const envWithStill = {
    ...env,
    VIDEOS_BUCKET: {
      get: async (key) => ({
        key,
        size: 3,
        body: 'jpg',
        httpMetadata: { contentType: 'application/octet-stream' },
      }),
      head: async () => null,
    },
  };

  const res = await worker.fetch(
    new Request('https://mv.example/videos/reports/street-photos-2026-11-15/frame-1.jpg'),
    envWithStill,
  );

  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'image/jpeg');
});
