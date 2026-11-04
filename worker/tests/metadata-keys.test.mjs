/**
 * KV metadata is keyed by the full video id (ticket 007 Q1).
 *
 * The Worker used to strip a numeric prefix (`"5-《…》"` → `metadata_dense_5`), which could
 * silently serve another reel's metadata. These tests pin the key the handlers actually
 * read, for the three routes that touch it, without needing a KV.
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
    bundlePath = join(mkdtempSync(join(tmpdir(), 'worker-keys-')), 'worker.mjs');
    execFileSync(
      join(WORKER_DIR, 'node_modules/.bin/esbuild'),
      [ENTRY, '--bundle', '--format=esm', '--platform=neutral', '--outfile=' + bundlePath],
      { cwd: WORKER_DIR, stdio: 'pipe' },
    );
  }
  return import(pathToFileURL(bundlePath).href).then((mod) => mod.default);
}

/** Env that records every KV key read and returns nothing for all of them. */
function keyRecordingEnv(reads) {
  const kv = {
    get: async (key) => {
      reads.push(key);
      return null;
    },
    put: async () => {},
    delete: async () => {},
    list: async (options = {}) => {
      reads.push(`list:${options.prefix ?? ''}`);
      return { keys: [], list_complete: true };
    },
  };
  return {
    METADATA_KV: kv,
    MODAL_JOBS: {
      ...kv,
      get: async (key) => {
        reads.push(`MODAL_JOBS.get ${key}`);
        return null;
      },
    },
    VIDEOS_BUCKET: {
      get: async () => null,
      head: async () => null,
      list: async () => ({ objects: [], truncated: false }),
    },
    CF_ACCESS_AUD: 'test-aud',
    CF_ACCESS_TEAM: 'test-team',
  };
}

const VIDEO_ID = '4-《全民造星IV》極限拍MV';
const KV_KEY = `metadata_${VIDEO_ID}`;
const CONTEXT = { waitUntil() {}, passThroughOnException() {} };

test('dense metadata is read by the full video id', async () => {
  const worker = await loadWorker();
  const reads = [];
  const response = await worker.fetch(
    new Request(`https://worker.test/api/videos/metadata/dense/${encodeURIComponent(VIDEO_ID)}`),
    keyRecordingEnv(reads),
    CONTEXT,
  );

  assert.equal(response.status, 404, 'missing metadata must be loud, not mocked');
  assert.deepEqual(reads, [KV_KEY]);
  assert.equal((await response.json()).key, KV_KEY);
});

test('faces at a timestamp read the same full-id key', async () => {
  const worker = await loadWorker();
  const reads = [];
  await worker.fetch(
    new Request(
      `https://worker.test/api/faces/detect?video_id=${encodeURIComponent(VIDEO_ID)}&timestamp=12`,
    ),
    keyRecordingEnv(reads),
    CONTEXT,
  );

  assert.ok(reads.includes(KV_KEY), `expected ${KV_KEY}, read ${reads.join(', ')}`);
});

test('contestant appearances list and read full-id keys', async () => {
  const worker = await loadWorker();
  const reads = [];
  await worker.fetch(
    new Request(
      `https://worker.test/api/recognition/results?contestant_id=33&video_id=${encodeURIComponent(VIDEO_ID)}`,
    ),
    keyRecordingEnv(reads),
    CONTEXT,
  );

  assert.ok(reads.includes(KV_KEY), `expected ${KV_KEY}, read ${reads.join(', ')}`);

  const allReads = [];
  await worker.fetch(
    new Request('https://worker.test/api/recognition/results?contestant_id=33'),
    keyRecordingEnv(allReads),
    CONTEXT,
  );
  assert.ok(
    allReads.includes('list:metadata_'),
    `an unfiltered scan must use the metadata_ prefix, read ${allReads.join(', ')}`,
  );
});

test('/api/faces/detect drops a frame once the faces have left the shot', async () => {
  const worker = await loadWorker();
  const frame = (frame_number, timestamp) => ({
    frame_number,
    timestamp,
    detections: [{ bbox: [0.1, 0.2, 0.3, 0.4], contestant_id: '1' }],
  });
  // Sampled every 0.16s; frames with no faces aren't stored, so the next one is 10s away.
  const metadata = JSON.stringify({
    frame_data: [frame(90, 14.4), frame(91, 14.56), frame(92, 14.72), frame(150, 25)],
  });
  const env = { METADATA_KV: { get: async (key) => (key === 'metadata_x' ? metadata : null) } };
  const ctx = { waitUntil() {}, passThroughOnException() {} };
  const at = async (t) => {
    const url = `https://worker.test/api/faces/detect?video_id=x&timestamp=${t}`;
    return (await worker.fetch(new Request(url), env, ctx)).json();
  };

  assert.equal((await at(14.8)).frame, 92);
  assert.equal((await at(14.8)).faces.length, 1);
  for (const t of [15, 18, 24.9, 1]) {
    const body = await at(t);
    assert.equal(body.frame, null, `t=${t}`);
    assert.deepEqual(body.faces, [], `t=${t}`);
  }
  assert.equal((await at(25)).frame, 150);
});

test('HTML revalidates so a deploy shows at once; hashed bundles stay cached', async () => {
  const worker = await loadWorker();
  const get = (path) =>
    worker.fetch(new Request(`https://worker.test${path}`), keyRecordingEnv([]), {
      waitUntil() {},
    });

  for (const path of ['/', '/index.html', '/cast', '/admin', '/admin/', '/admin/flagging']) {
    const response = await get(path);
    assert.equal(response.status, 200, path);
    assert.match(response.headers.get('Content-Type'), /text\/html/, path);
    assert.equal(response.headers.get('Cache-Control'), 'no-cache', path);
  }

  for (const shell of ['/', '/admin/']) {
    const html = await (await get(shell)).text();
    const bundle = html.match(/src="([^"]*assets\/[^"]+\.js)"/)?.[1];
    assert.ok(bundle, `${shell} names a hashed bundle`);
    const response = await get(bundle);
    assert.equal(response.status, 200, bundle);
    assert.equal(response.headers.get('Cache-Control'), 'public, max-age=31536000', bundle);
  }
});
