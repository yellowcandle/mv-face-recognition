/**
 * The deployed Worker is read-only, and this is what keeps it that way.
 *
 * ADR 0003 settled that the Worker serves and never writes; tickets 015 and 016 deleted every
 * route that could. This test drives **every route in the switch, with every method, using both
 * an empty body and a body full of plausible field names**, and asserts the request had no
 * effect: no KV write, no R2 write, no outbound fetch. It enumerates routes from the source, so
 * the next route someone adds is covered without anyone updating a list.
 *
 * That last part matters: the first version of this check only sent GET and POST with `{}`, and
 * it missed `/admin/upload-video` (which validates its input before uploading to HuggingFace) and
 * `/settings` (which writes on PUT). Depth beats a hand-kept list.
 *
 * Run: node --test tests/*.test.mjs    (esbuild is already present as a wrangler dependency)
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKER_DIR = join(HERE, '..');
const ENTRY = join(WORKER_DIR, 'src/index.ts');
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

/** Field names a write-capable route might require before it does anything. */
const PLAUSIBLE_BODY = JSON.stringify({
  contestant_id: 33,
  video_id: 'test-video-mv2',
  timestamp: 1,
  flag_id: 'flag_1',
  action: 'approve',
  video_url: 'https://example.test/x.mp4',
  video_name: 'x',
  filename: 'x.mp4',
  url: 'https://example.test/x',
  contestantId: 33,
  id: '1',
  name: 'x',
  status: 'queued',
  theme: 'dark',
  settings: {},
  keys: [],
});

/** Every `case '<path>':` in the source — the routes the API switch answers. */
function routesFromSource() {
  const source = readFileSync(ENTRY, 'utf8');
  const paths = new Set();
  for (const [, path] of source.matchAll(/case\s+'(\/[^']*)'\s*:/g)) {
    paths.add(path.replace(/\/+$/, '')); // `/x` and `/x/` are one route; same handler
  }
  return [...paths].sort((a, b) => a.localeCompare(b));
}

let bundlePath = null;
function buildWorker() {
  if (bundlePath) return bundlePath;
  bundlePath = join(mkdtempSync(join(tmpdir(), 'worker-bundle-')), 'worker.mjs');
  execFileSync(
    join(WORKER_DIR, 'node_modules/.bin/esbuild'),
    [ENTRY, '--bundle', '--format=esm', '--platform=neutral', '--outfile=' + bundlePath],
    { cwd: WORKER_DIR, stdio: 'pipe' },
  );
  return bundlePath;
}

async function loadWorker() {
  return (await import(pathToFileURL(buildWorker()).href)).default;
}

/**
 * An env whose every mutation is recorded, plus a stubbed outbound `fetch` — the check is about
 * effects, and an upload endpoint's only effect is a request.
 */
function recordingEnv(effects) {
  const kv = (name) => ({
    get: async () => null,
    put: async (key) => {
      effects.push(`${name}.put ${key}`);
    },
    delete: async (key) => {
      effects.push(`${name}.delete ${key}`);
    },
    list: async () => ({ keys: [], list_complete: true }),
  });
  return {
    METADATA_KV: kv('METADATA_KV'),
    MODAL_JOBS: kv('MODAL_JOBS'),
    VIDEOS_BUCKET: {
      get: async () => null,
      head: async () => null,
      list: async () => ({ objects: [], truncated: false }),
      put: async (key) => {
        effects.push(`VIDEOS_BUCKET.put ${key}`);
      },
      delete: async (key) => {
        effects.push(`VIDEOS_BUCKET.delete ${key}`);
      },
    },
    // Set, so the gate is live rather than bypassed — the production shape.
    CF_ACCESS_AUD: 'test-aud',
    CF_ACCESS_TEAM: 'test-team',
  };
}

test('no route has an effect: the Worker is read-only', async () => {
  const worker = await loadWorker();
  const routes = routesFromSource();
  // 8 after tickets 015 and 016 stripped the write surface; the floor only guards against the
  // regex silently matching nothing and the test passing vacuously.
  assert.ok(routes.length >= 6, `expected the API switch to expose routes, found ${routes.length}`);

  const realFetch = globalThis.fetch;
  const offenders = [];

  try {
    for (const route of routes) {
      for (const method of METHODS) {
        for (const body of [undefined, PLAUSIBLE_BODY]) {
          const effects = [];
          globalThis.fetch = async (input) => {
            effects.push(`outbound fetch ${typeof input === 'string' ? input : input?.url}`);
            return new Response('{}', {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            });
          };
          const request = new Request(`https://worker.test/api${route}`, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: method === 'GET' || method === 'DELETE' ? undefined : body,
          });
          try {
            await worker.fetch(request, recordingEnv(effects), {
              waitUntil() {},
              passThroughOnException() {},
            });
          } catch {
            // Throwing on a stub env is fine — the assertion is about what it did before that.
          }
          globalThis.fetch = realFetch;
          if (effects.length > 0) offenders.push(`${method} ${route} -> ${effects.join(', ')}`);
        }
      }
    }
  } finally {
    globalThis.fetch = realFetch;
  }

  assert.deepEqual(
    offenders,
    [],
    `these requests had a side effect:\n${offenders.map((o) => `  ${o}`).join('\n')}\n` +
      `The deployed Worker reads and streams; it does not write. See ADR 0003.`,
  );
  console.log(
    `checked ${routes.length} routes × ${METHODS.length} methods: no writes, no outbound calls`,
  );
});

test('every admin and write route is gone, not gated', async () => {
  const worker = await loadWorker();
  const env = recordingEnv([]);
  const ctx = { waitUntil() {}, passThroughOnException() {} };

  // Deleted by ticket 015 (flagging) and ticket 016 (everything else that could write).
  const removed = [
    ['POST', '/api/faces/flag'],
    ['GET', '/api/faces/flagged'],
    ['GET', '/api/faces/thumbnail'],
    ['POST', '/api/admin/flagged/approve'],
    ['GET', '/api/settings'],
    ['PUT', '/api/settings'],
    ['POST', '/api/embeddings/sync'],
    ['POST', '/api/admin/trigger-modal'],
    ['POST', '/api/admin/upload-video'],
    ['POST', '/api/admin/youtube/submit'],
    ['GET', '/api/admin/youtube/queue'],
    ['POST', '/api/admin/youtube/status'],
    ['GET', '/api/admin/youtube/samples'],
    ['POST', '/api/admin/youtube/validate'],
    ['POST', '/api/admin/youtube/bootstrap'],
    ['GET', '/api/admin/embeddings/compare'],
    ['POST', '/api/admin/embeddings/trigger-sync'],
  ];

  for (const [method, path] of removed) {
    const response = await worker.fetch(
      new Request(`https://worker.test${path}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'GET' ? undefined : '{}',
      }),
      env,
      ctx,
    );
    assert.equal(response.status, 404, `${method} ${path} should be gone, got ${response.status}`);
  }
});

test('the read surface still answers', async () => {
  const worker = await loadWorker();
  const env = recordingEnv([]);
  const ctx = { waitUntil() {}, passThroughOnException() {} };

  // The routes the viewer actually depends on. A 200 is not the point; not-404 is.
  const kept = [
    '/api/system/status',
    '/api/contestants',
    '/api/videos',
    '/api/videos/processed/list',
    '/api/faces/detect?video_id=4-x&timestamp=0',
    '/api/recognition/results?contestant_id=17',
  ];
  for (const path of kept) {
    const response = await worker.fetch(new Request(`https://worker.test${path}`), env, ctx);
    assert.notEqual(response.status, 404, `${path} should still be served`);
  }
});
