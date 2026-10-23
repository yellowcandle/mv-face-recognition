/**
 * The unauthenticated Worker is read-only, and this is what keeps it that way.
 *
 * ADR 0003 settled that the Worker serves and never writes without an identity; ticket 015
 * deleted every write route. The admin writes that came back (face flags, ground-truth labels)
 * sit behind Cloudflare Access, so the invariant is narrower but unchanged in spirit:
 * **without an Access JWT, no route has any effect**. This test drives every route in the
 * switch, with every method, using both an empty body and a body full of plausible field
 * names, and asserts the request had no effect: no KV write, no R2 write, no outbound fetch.
 * It enumerates routes from the source, so the next route someone adds is covered without
 * anyone updating a list.
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

// The Access application every authenticated test signs for.
const TEAM_DOMAIN = 'test-team.cloudflareaccess.com';
const AUD = 'test-aud';
const KID = 'k1';
const EMAIL = 'admin@example.com';

const { publicKey, privateKey } = await crypto.subtle.generateKey(
  {
    name: 'RSASSA-PKCS1-v1_5',
    modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]),
    hash: 'SHA-256',
  },
  true,
  ['sign', 'verify'],
);
const publicJwk = { ...(await crypto.subtle.exportKey('jwk', publicKey)), kid: KID };

const b64url = (bytes) => Buffer.from(bytes).toString('base64url');
const encodePart = (value) => b64url(new TextEncoder().encode(JSON.stringify(value)));

/** A token Cloudflare Access would issue for the test team. */
async function signAccessToken(claims = {}) {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: `https://${TEAM_DOMAIN}`,
    aud: [AUD],
    email: EMAIL,
    iat: now,
    nbf: now,
    exp: now + 600,
    ...claims,
  };
  const input = `${encodePart({ alg: 'RS256', kid: KID, typ: 'JWT' })}.${encodePart(payload)}`;
  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    privateKey,
    new TextEncoder().encode(input),
  );
  return `${input}.${b64url(new Uint8Array(signature))}`;
}

/** An in-memory KV with the same surface the Worker uses, paginated two keys at a time. */
function memoryKv(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    store,
    async get(key) {
      return store.has(key) ? store.get(key) : null;
    },
    async put(key, value) {
      store.set(key, value);
    },
    async delete(key) {
      store.delete(key);
    },
    async list({ prefix = '', cursor } = {}) {
      const keys = [...store.keys()].filter((key) => key.startsWith(prefix)).sort();
      const start = cursor ? Number(cursor) : 0;
      const page = keys.slice(start, start + 2).map((name) => ({ name }));
      const done = start + 2 >= keys.length;
      return { keys: page, list_complete: done, cursor: done ? undefined : String(start + 2) };
    },
  };
}

function memoryR2(objects = {}) {
  return {
    async get(key) {
      return key in objects ? { body: objects[key], size: objects[key].length } : null;
    },
    async head() {
      return null;
    },
    async list() {
      return { objects: [], truncated: false };
    },
    async put() {},
    async delete() {},
  };
}

async function callWorker(worker, env, ctx, method, path, { token, cookie, body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token !== undefined) headers['Cf-Access-Jwt-Assertion'] = token;
  if (cookie !== undefined) headers.Cookie = `CF_Authorization=${cookie}`;
  return worker.fetch(
    new Request(`https://worker.test${path}`, {
      method,
      headers,
      body: method === 'GET' || method === 'DELETE' ? undefined : JSON.stringify(body ?? {}),
    }),
    env,
    ctx,
  );
}

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
    JOB_STORE: kv('JOB_STORE'),
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
    // Set, so the gate is live rather than bypassed — the production shape. Without a token,
    // though, no route may reach the KV/R2 stubs above.
    CF_ACCESS_AUD: AUD,
    CF_ACCESS_TEAM_DOMAIN: TEAM_DOMAIN,
  };
}

test('no route has an effect: the Worker is read-only', async () => {
  const worker = await loadWorker();
  const routes = routesFromSource();
  // Parameterised routes are not `case` labels, so sample each shape explicitly: the sweep must
  // cover them or the next write-with-an-id route could slip past the no-effect check.
  routes.push(
    '/faces/flagged/sample-face',
    '/labels/sample-video',
    '/processing/jobs/sample-job',
    '/processing/cancel/sample-job',
  );
  routes.sort((a, b) => a.localeCompare(b));
  // The floor only guards against the regex silently matching nothing and the test passing
  // vacuously.
  assert.ok(routes.length >= 6, `expected the API switch to expose routes, found ${routes.length}`);

  const realFetch = globalThis.fetch;
  const offenders = [];

  try {
    for (const route of routes) {
      // The admin calls the gated routes through the Access-protected prefix; it must map to
      // the same handlers and inherit the same no-write-before-auth guarantee.
      for (const prefix of ['/api', '/admin/api']) {
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
            const request = new Request(`https://worker.test${prefix}${route}`, {
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
            if (effects.length > 0)
              offenders.push(`${method} ${prefix}${route} -> ${effects.join(', ')}`);
          }
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

test('deleted routes are gone; Access-gated writes fail closed', async () => {
  const worker = await loadWorker();
  const env = recordingEnv([]);
  const ctx = { waitUntil() {}, passThroughOnException() {} };

  // Deleted by ticket 016: nothing here writes, gated or not.
  const removed = [
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

  // The writes that exist are gated, not public: every one refuses an unauthenticated caller.
  const gated = [
    ['GET', '/api/faces/flagged'],
    ['POST', '/api/faces/flag'],
    ['PATCH', '/api/faces/flagged/abc123'],
    ['DELETE', '/api/faces/flagged/abc123'],
    ['POST', '/api/faces/flag/update'],
    ['GET', '/api/labels'],
    ['GET', '/api/labels/4-x'],
    ['PUT', '/api/labels/4-x'],
    // Processing jobs are writes on the same terms (ADR 0006).
    ['POST', '/api/processing/trigger'],
    ['GET', '/api/processing/jobs'],
    ['GET', '/api/processing/jobs/abc123'],
    ['POST', '/api/processing/cancel/abc123'],
    ['POST', '/api/processing/clear-completed'],
    // The admin's Access-protected prefix must fail closed the same way.
    ['POST', '/admin/api/faces/flag'],
    ['GET', '/admin/api/faces/flagged'],
    ['PUT', '/admin/api/labels/4-x'],
  ];

  for (const [method, path] of gated) {
    const response = await worker.fetch(
      new Request(`https://worker.test${path}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'GET' || method === 'DELETE' ? undefined : '{}',
      }),
      env,
      ctx,
    );
    assert.equal(response.status, 401, `${method} ${path} should refuse anonymously`);
    assert.deepEqual(await response.json(), { error: 'Unauthorized' }, `${method} ${path}`);
    assert.equal(
      response.headers.get('cache-control'),
      'no-store',
      `${method} ${path} must not be cached — a cached queue hides accepted flags`,
    );
  }

  // Fail closed, not open: without the Access audience every gated route is 503.
  const unconfigured = recordingEnv([]);
  delete unconfigured.CF_ACCESS_AUD;
  for (const [method, path] of gated) {
    const response = await worker.fetch(
      new Request(`https://worker.test${path}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'GET' || method === 'DELETE' ? undefined : '{}',
      }),
      unconfigured,
      ctx,
    );
    assert.equal(response.status, 503, `${method} ${path} without CF_ACCESS_AUD should be 503`);
    assert.deepEqual(
      await response.json(),
      { error: 'Service not configured' },
      `${method} ${path}`,
    );
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

test('authenticated flagging and labelling routes round-trip in KV', async () => {
  const module = await import(pathToFileURL(buildWorker()).href);
  const worker = module.default;
  module.resetJwksCache();

  const ctx = { waitUntil() {}, passThroughOnException() {} };
  const metadata = {
    video_info: { processing_date: '2026-01-02T03:04:05' },
    frame_data: [
      {
        frame_number: 1,
        detections: [{ tracker_id: 0, bbox: [0.1, 0.2, 0.3, 0.4] }, { tracker_id: 1 }],
      },
      { frame_number: 2, detections: [{ tracker_id: 1 }] },
    ],
  };
  const env = {
    METADATA_KV: memoryKv({
      metadata_vid1: JSON.stringify(metadata),
      metadata_vidlegacy: JSON.stringify(metadata),
      labels_vidlegacy: JSON.stringify({
        schema: 'labels/v1',
        video_id: 'vidlegacy',
        labels: [{ frame_number: 1, detection_index: 0 }],
      }),
    }),
    VIDEOS_BUCKET: memoryR2(),
    CF_ACCESS_TEAM_DOMAIN: TEAM_DOMAIN,
    CF_ACCESS_AUD: AUD,
    LOG_LEVEL: 'none',
  };

  const jwksUrl = `https://${TEAM_DOMAIN}/cdn-cgi/access/certs`;
  const realFetch = globalThis.fetch;
  const fetches = [];
  globalThis.fetch = async (input) => {
    const url = typeof input === 'string' ? input : input.url;
    fetches.push(url);
    if (url === jwksUrl) return Response.json({ keys: [publicJwk] });
    return new Response('not found', { status: 404 });
  };

  try {
    const token = await signAccessToken();
    const source = { processing_date: '2026-01-02T03:04:05', detections: 3 };

    // ── flags, authenticated with the header Access injects ──
    const created = await callWorker(worker, env, ctx, 'POST', '/api/faces/flag', {
      token,
      body: {
        contestant_id: 33,
        video_id: 'vid1',
        timestamp: 12.5,
        confidence: 0.87,
        bbox: [0.1, 0.2, 0.3, 0.4],
        user_label: 'looks right',
        thumbnail: 'BASE64JPEG',
      },
    });
    assert.equal(created.status, 200);
    const flag = await created.json();
    assert.match(flag.id, /^[0-9a-f]{12}$/);
    assert.equal(flag.contestant_id, 33);
    assert.equal(flag.video_id, 'vid1');
    assert.equal(flag.timestamp, 12.5);
    assert.equal(flag.confidence, 0.87);
    assert.deepEqual(flag.bbox, [0.1, 0.2, 0.3, 0.4]);
    assert.equal(flag.status, 'pending');
    assert.equal(flag.user_label, 'looks right');
    assert.equal(flag.thumbnail, 'BASE64JPEG');
    assert.equal(flag.flagged_by, EMAIL);
    assert.ok(!Number.isNaN(Date.parse(flag.created_at)));

    // A rejected body never appends.
    const invalidFlag = await callWorker(worker, env, ctx, 'POST', '/api/faces/flag', {
      token,
      body: { video_id: '', timestamp: 'soon' },
    });
    assert.equal(invalidFlag.status, 400);
    assert.equal(
      [...env.METADATA_KV.store.keys()].filter((key) => key.startsWith('flag_')).length,
      1,
      'a rejected body stores nothing',
    );

    let response = await callWorker(worker, env, ctx, 'GET', '/api/faces/flagged', { token });
    assert.equal(response.status, 200);
    let body = await response.json();
    assert.equal(body.flagged_faces.length, 1);
    assert.equal('thumbnail' in body.flagged_faces[0], false);

    response = await callWorker(worker, env, ctx, 'GET', '/api/faces/flagged?details=true', {
      token,
    });
    body = await response.json();
    assert.equal(body.flagged_faces[0].thumbnail, 'BASE64JPEG');

    // PATCH/DELETE accept the Access cookie as well as the header.
    response = await callWorker(worker, env, ctx, 'PATCH', `/api/faces/flagged/${flag.id}`, {
      cookie: token,
      body: { status: 'accepted' },
    });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, 'accepted');

    response = await callWorker(worker, env, ctx, 'PATCH', `/api/faces/flagged/${flag.id}`, {
      token,
      body: { status: 'maybe' },
    });
    assert.equal(response.status, 400);
    assert.match((await response.json()).detail, /Invalid status/);

    response = await callWorker(worker, env, ctx, 'POST', '/api/faces/flag/update', {
      token,
      body: { face_id: flag.id, contestant_id: 44 },
    });
    assert.equal(response.status, 200);
    body = await response.json();
    assert.equal(body.contestant_id, 44);
    assert.equal(body.status, 'pending');

    // ── labels ──
    response = await callWorker(worker, env, ctx, 'GET', '/api/labels/vid1', { cookie: token });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      schema: 'labels/v2',
      video_id: 'vid1',
      labelled_at: null,
      source,
      labels: [],
      legacy_ignored: false,
    });

    response = await callWorker(worker, env, ctx, 'GET', '/api/labels', { token });
    assert.equal(response.status, 200);
    body = await response.json();
    assert.deepEqual(body.labels, [
      {
        video_id: 'vidlegacy',
        schema: 'labels/v1',
        count: 0,
        labelled_at: null,
        legacy_ignored: true,
      },
    ]);

    response = await callWorker(worker, env, ctx, 'GET', '/api/labels/vidlegacy', { token });
    assert.equal(response.status, 200);
    body = await response.json();
    assert.equal(body.legacy_ignored, true);
    assert.equal(typeof body.legacy_detail, 'string');
    assert.deepEqual(body.labels, []);
    assert.deepEqual(body.source, source);

    response = await callWorker(worker, env, ctx, 'PUT', '/api/labels/vid1', {
      cookie: token,
      body: {
        source,
        labels: [
          { tracker_id: 0, verdict: 'contestant', contestant_id: '33' },
          { tracker_id: 1, verdict: 'not_a_contestant' },
        ],
      },
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { saved: true, count: 2, path: 'kv:labels_vid1' });

    response = await callWorker(worker, env, ctx, 'GET', '/api/labels/vid1', { token });
    body = await response.json();
    assert.equal(body.schema, 'labels/v2');
    assert.equal(body.legacy_ignored, false);
    assert.equal(body.labelled_by, EMAIL);
    assert.deepEqual(body.labels, [
      { tracker_id: 0, verdict: 'contestant', contestant_id: '33' },
      { tracker_id: 1, verdict: 'not_a_contestant' },
    ]);

    response = await callWorker(worker, env, ctx, 'GET', '/api/labels', { token });
    body = await response.json();
    const saved = body.labels.find((entry) => entry.video_id === 'vid1');
    assert.equal(saved.schema, 'labels/v2');
    assert.equal(saved.count, 2);
    assert.equal(saved.legacy_ignored, false);

    // Anything that does not point at a real track is refused, not written.
    const invalidLabelSets = [
      [
        { tracker_id: 0, verdict: 'unsure' },
        { tracker_id: 0, verdict: 'unsure' },
      ],
      [{ tracker_id: 9, verdict: 'unsure' }],
      [{ tracker_id: 0, verdict: 'maybe' }],
      [{ tracker_id: 0, verdict: 'contestant' }],
      [{ tracker_id: 0, verdict: 'unsure', contestant_id: '33' }],
      [{ tracker_id: 0, verdict: 'contestant', contestant_id: '97' }],
    ];
    for (const labels of invalidLabelSets) {
      response = await callWorker(worker, env, ctx, 'PUT', '/api/labels/vid1', {
        token,
        body: { source, labels },
      });
      assert.equal(response.status, 400, JSON.stringify(labels));
      assert.equal(typeof (await response.json()).detail, 'string');
    }

    response = await callWorker(worker, env, ctx, 'PUT', '/api/labels/vid1', {
      token,
      body: { source: { processing_date: '2025-01-01T00:00:00', detections: 3 }, labels: [] },
    });
    assert.equal(response.status, 409);
    assert.deepEqual(await response.json(), { detail: 'Refusing labels for stale metadata run' });

    // Labels from another metadata run are refused on read too: a reprocess renumbers tracks.
    await env.METADATA_KV.put(
      'metadata_vid1',
      JSON.stringify({ ...metadata, video_info: { processing_date: '2026-02-02T00:00:00' } }),
    );
    response = await callWorker(worker, env, ctx, 'GET', '/api/labels/vid1', { token });
    assert.equal(response.status, 409);
    assert.match((await response.json()).detail, /different metadata run/);

    // ── delete ──
    response = await callWorker(worker, env, ctx, 'DELETE', `/api/faces/flagged/${flag.id}`, {
      token,
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { deleted: flag.id });

    response = await callWorker(worker, env, ctx, 'DELETE', `/api/faces/flagged/${flag.id}`, {
      token,
    });
    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { error: 'Flagged face not found' });

    // ── the Access-protected prefix reaches the same handlers, query and body intact ──
    response = await callWorker(worker, env, ctx, 'POST', '/admin/api/faces/flag', {
      cookie: token,
      body: { contestant_id: 44, video_id: 'vid1', timestamp: 2.5, thumbnail: 'ALIAS' },
    });
    assert.equal(response.status, 200);
    const aliased = await response.json();
    assert.equal(aliased.contestant_id, 44);
    assert.equal(aliased.flagged_by, EMAIL);

    response = await callWorker(worker, env, ctx, 'GET', '/admin/api/faces/flagged?details=true', {
      token,
    });
    assert.equal(response.status, 200);
    body = await response.json();
    assert.equal(body.flagged_faces.find((entry) => entry.id === aliased.id)?.thumbnail, 'ALIAS');

    // The same record is visible through the unprefixed read, so both prefixes share storage.
    response = await callWorker(worker, env, ctx, 'GET', '/api/faces/flagged', { token });
    assert.ok((await response.json()).flagged_faces.some((entry) => entry.id === aliased.id));

    // ── a legacy single array is readable, then claimed by the first write ──
    await env.METADATA_KV.put(
      'flagged_faces',
      JSON.stringify([
        {
          id: 'legacy000001',
          contestant_id: 7,
          video_id: 'vid1',
          timestamp: 1,
          confidence: 0,
          bbox: null,
          status: 'pending',
          user_label: null,
          thumbnail: null,
          created_at: '2026-01-01T00:00:00.000Z',
          flagged_by: 'old@example.com',
        },
      ]),
    );
    response = await callWorker(worker, env, ctx, 'GET', '/api/faces/flagged', { token });
    assert.ok((await response.json()).flagged_faces.some((entry) => entry.id === 'legacy000001'));

    response = await callWorker(
      worker,
      env,
      ctx,
      'PATCH',
      '/admin/api/faces/flagged/legacy000001',
      {
        cookie: token,
        body: { status: 'accepted' },
      },
    );
    assert.equal(response.status, 200);
    assert.equal(await env.METADATA_KV.get('flagged_faces'), null, 'the legacy key is claimed');
    assert.equal(
      JSON.parse(await env.METADATA_KV.get('flag_legacy000001')).status,
      'accepted',
      'the migrated record is updated in place',
    );

    assert.equal(
      fetches.filter((url) => url === jwksUrl).length,
      1,
      'the JWKS is fetched once and cached across requests',
    );
  } finally {
    globalThis.fetch = realFetch;
  }
});

test('embedding documents, portraits, crops and recognition boxes are served', async () => {
  const worker = await loadWorker();
  const ctx = { waitUntil() {}, passThroughOnException() {} };
  const env = {
    METADATA_KV: memoryKv({
      embedding_coverage: JSON.stringify({ summary: { total: 96 } }),
      embedding_similarity_matrix: JSON.stringify({ contestants: [] }),
      embedding_top_pairs: JSON.stringify({ pairs: [] }),
    }),
    VIDEOS_BUCKET: memoryR2({
      'portraits/33.webp': 'WEBPBYTES',
      'crops/vid1/32_2.jpg': 'JPEGBYTES',
    }),
    JOB_STORE: memoryKv(),
  };

  for (const [path, expected] of [
    ['/api/embedding/coverage', { summary: { total: 96 } }],
    ['/api/embedding/similarity', { contestants: [] }],
    ['/api/embedding/top-pairs', { pairs: [] }],
  ]) {
    const response = await worker.fetch(new Request(`https://worker.test${path}`), env, ctx);
    assert.equal(response.status, 200, path);
    assert.deepEqual(await response.json(), expected, path);
  }

  const emptyEnv = { METADATA_KV: memoryKv(), VIDEOS_BUCKET: memoryR2() };
  const missing = await worker.fetch(
    new Request('https://worker.test/api/embedding/coverage'),
    emptyEnv,
    ctx,
  );
  assert.equal(missing.status, 404);
  assert.deepEqual(await missing.json(), { error: 'embedding_coverage not found' });

  // `/photo`, `/thumb/face` and the sized variants are one published portrait.
  for (const path of [
    '/api/contestants/33/thumb/face',
    '/api/contestants/33/thumb/320',
    '/api/contestants/33/thumb/640',
    '/api/contestants/33/photo',
  ]) {
    const response = await worker.fetch(new Request(`https://worker.test${path}`), env, ctx);
    assert.equal(response.status, 200, path);
    assert.equal(response.headers.get('Content-Type'), 'image/webp', path);
    assert.equal(await response.text(), 'WEBPBYTES', path);
  }

  let response = await worker.fetch(
    new Request(
      'https://worker.test/api/faces/crop?video_id=vid1&frame_number=32&detection_index=2',
    ),
    env,
    ctx,
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Content-Type'), 'image/jpeg');
  assert.equal(response.headers.get('Cache-Control'), 'public, max-age=3600');
  assert.equal(await response.text(), 'JPEGBYTES');

  response = await worker.fetch(
    new Request('https://worker.test/api/faces/crop?video_id=vid1&frame_number=32'),
    env,
    ctx,
  );
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: 'crop not found' });

  // The status document names the environment so the admin chrome can label EDGE vs LOCAL.
  response = await worker.fetch(new Request('https://worker.test/api/system/status'), env, ctx);
  const status = await response.json();
  assert.equal(status.status, 'online');
  assert.equal(status.mode, 'edge');

  // Recognition results carry the box and the detection index the crop route keys on.
  env.METADATA_KV = memoryKv({
    metadata_vid1: JSON.stringify({
      frame_data: [
        {
          frame_number: 105,
          detections: [
            { tracker_id: 3, bbox: [0.5, 0.5, 0.6, 0.6] },
            { tracker_id: 4, bbox: [0.1, 0.2, 0.3, 0.4] },
          ],
        },
      ],
      contestant_timeline: {
        17: {
          appearances: [
            { timestamp: 3.5, match_score: 0.9, frame_number: 105, bbox: [0.1, 0.2, 0.3, 0.4] },
            { timestamp: 9.5, match_score: 0.4, frame_number: 999, bbox: [0.7, 0.7, 0.8, 0.8] },
          ],
        },
      },
    }),
  });
  response = await worker.fetch(
    new Request('https://worker.test/api/recognition/results?contestant_id=17&video_id=vid1'),
    env,
    ctx,
  );
  const recognition = await response.json();
  assert.equal(recognition.results.length, 2);
  assert.deepEqual(recognition.results[0].bbox, [0.1, 0.2, 0.3, 0.4]);
  assert.equal(recognition.results[0].detection_index, 1);
  // A box with no matching detection stays unindexed, so the client crops the reel instead.
  assert.equal('detection_index' in recognition.results[1], false);
});

test('processing jobs dispatch to HF Jobs and read back through the gated prefix', async () => {
  const module = await import(pathToFileURL(buildWorker()).href);
  const worker = module.default;
  module.resetJwksCache();

  const ctx = { waitUntil() {}, passThroughOnException() {} };
  const env = {
    METADATA_KV: memoryKv(),
    VIDEOS_BUCKET: memoryR2(),
    JOB_STORE: memoryKv(),
    CF_ACCESS_TEAM_DOMAIN: TEAM_DOMAIN,
    CF_ACCESS_AUD: AUD,
    HF_TOKEN: 'hf_test_token',
    LOG_LEVEL: 'none',
  };

  const jwksUrl = `https://${TEAM_DOMAIN}/cdn-cgi/access/certs`;
  const hub = 'https://huggingface.co/api/jobs/yellowcandle';
  const realFetch = globalThis.fetch;
  const calls = [];
  let stage = 'SCHEDULING';
  globalThis.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    calls.push(`${init?.method ?? 'GET'} ${url}`);
    if (url === jwksUrl) return Response.json({ keys: [publicJwk] });
    if (init?.method === 'POST' && url === hub) {
      return Response.json({ id: 'hub-job-1', status: { stage } });
    }
    if (init?.method === 'POST' && url === `${hub}/hub-job-1/cancel`) {
      stage = 'CANCELED';
      return new Response(null, { status: 200 });
    }
    if (url === `${hub}/hub-job-1`) {
      return Response.json({ id: 'hub-job-1', status: { stage } });
    }
    return new Response('not found', { status: 404 });
  };

  try {
    const token = await signAccessToken();

    // The edge cannot enumerate a source directory, so an initial run must name its reel.
    const nameless = await callWorker(worker, env, ctx, 'POST', '/admin/api/processing/trigger', {
      token,
      body: { mode: 'initial' },
    });
    assert.equal(nameless.status, 400);
    assert.match((await nameless.json()).detail, /video is required/);

    const badMode = await callWorker(worker, env, ctx, 'POST', '/admin/api/processing/trigger', {
      token,
      body: { mode: 'sideways' },
    });
    assert.equal(badMode.status, 400);

    const triggered = await callWorker(worker, env, ctx, 'POST', '/admin/api/processing/trigger', {
      token,
      body: { mode: 'initial', video: '4-《全民造星IV》極限拍MV.mp4' },
    });
    assert.equal(triggered.status, 200);
    assert.equal(triggered.headers.get('cache-control'), 'no-store');
    const start = await triggered.json();
    assert.match(start.job_id, /^[0-9a-f]{8}$/);
    assert.equal(start.status, 'queued');
    assert.equal(start.total_videos, 1);
    // Parity with local_api: the video branch carries no `mode`.
    assert.equal('mode' in start, false);

    assert.ok(
      calls.some((call) => call === `POST ${hub}`),
      'trigger must dispatch to HF Jobs',
    );

    // The list serves the wire shape, refreshed from the Hub, with internals stripped.
    stage = 'RUNNING';
    const listed = await callWorker(worker, env, ctx, 'GET', '/admin/api/processing/jobs', {
      token,
    });
    assert.equal(listed.status, 200);
    const { jobs } = await listed.json();
    assert.equal(jobs.length, 1);
    assert.equal(jobs[0].id, start.job_id);
    assert.equal(jobs[0].status, 'running');
    assert.equal('video_files' in jobs[0], false);
    assert.equal('hf_job_id' in jobs[0], false);
    assert.equal(jobs[0].error, null);

    stage = 'COMPLETED';
    const one = await callWorker(
      worker,
      env,
      ctx,
      'GET',
      `/admin/api/processing/jobs/${start.job_id}`,
      { token },
    );
    assert.equal(one.status, 200);
    const job = await one.json();
    assert.equal(job.status, 'completed');
    assert.equal(job.progress, 100);
    assert.equal(typeof job.completed_at, 'number');

    const missing = await callWorker(worker, env, ctx, 'GET', '/admin/api/processing/jobs/nope', {
      token,
    });
    assert.equal(missing.status, 404);
    assert.deepEqual(await missing.json(), { detail: 'Job not found' });

    const cleared = await callWorker(
      worker,
      env,
      ctx,
      'POST',
      '/admin/api/processing/clear-completed',
      { token },
    );
    assert.deepEqual(await cleared.json(), { cleared: 1 });
  } finally {
    globalThis.fetch = realFetch;
  }
});
