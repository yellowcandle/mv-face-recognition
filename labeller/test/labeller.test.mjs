/**
 * Labelling Worker tests. Run: node --test test/*.test.mjs
 * Node loads src/index.ts directly (built-in type stripping); KV and R2 are in-memory stubs and
 * the Access JWKS is served from a stubbed global fetch, signed by a keypair made here.
 */
import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import worker, { resetJwksCache } from '../src/index.ts';

const TEAM = 'test-team.cloudflareaccess.com';
const AUD = 'test-aud';
const KID = 'k1';

const { publicKey, privateKey } = await crypto.subtle.generateKey(
  { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
  true,
  ['sign', 'verify'],
);
const other = await crypto.subtle.generateKey(
  { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
  true,
  ['sign', 'verify'],
);
const jwk = { ...(await crypto.subtle.exportKey('jwk', publicKey)), kid: KID };

const b64url = (bytes) => Buffer.from(bytes).toString('base64url');
const enc = (obj) => b64url(new TextEncoder().encode(JSON.stringify(obj)));

async function sign(claims = {}, { key = privateKey, kid = KID, alg = 'RS256' } = {}) {
  const now = Math.floor(Date.now() / 1000);
  const payload = { iss: `https://${TEAM}`, aud: [AUD], email: 'labeller@example.com', iat: now, nbf: now, exp: now + 600, ...claims };
  const input = `${enc({ alg, kid, typ: 'JWT' })}.${enc(payload)}`;
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(input));
  return `${input}.${b64url(new Uint8Array(sig))}`;
}

function memKv() {
  const store = new Map();
  return {
    store,
    async get(k, type) { const v = store.get(k); return v === undefined ? null : type === 'json' ? JSON.parse(v) : v; },
    async put(k, v) { store.set(k, v); },
    async delete(k) { store.delete(k); },
    // Pages of 2 so pagination is exercised.
    async list({ prefix = '', cursor } = {}) {
      const all = [...store.keys()].filter((k) => k.startsWith(prefix)).sort();
      const start = cursor ? Number(cursor) : 0;
      const keys = all.slice(start, start + 2).map((name) => ({ name }));
      const done = start + 2 >= all.length;
      return { keys, list_complete: done, cursor: done ? undefined : String(start + 2) };
    },
  };
}

function memR2(objects = {}) {
  const gets = [];
  return {
    gets,
    async get(k) { gets.push(k); return k in objects ? { body: objects[k], httpEtag: '"e"' } : null; },
  };
}

let env;
let fetches;
const realFetch = globalThis.fetch;

beforeEach(() => {
  resetJwksCache();
  fetches = [];
  globalThis.fetch = async (url) => {
    fetches.push(String(url));
    if (String(url) === `https://${TEAM}/cdn-cgi/access/certs`) return Response.json({ keys: [jwk] });
    return new Response('no', { status: 404 });
  };
  env = { LABELS: memKv(), LABEL_CROPS: memR2({ 'crops/test-video-mv2/32_2.jpg': 'JPEGBYTES' }), CF_ACCESS_TEAM_DOMAIN: TEAM, CF_ACCESS_AUD: AUD, LOG_LEVEL: 'none' };
});
afterEach(() => { globalThis.fetch = realFetch; });

async function call(method, path, { token, body } = {}) {
  const headers = {};
  if (token !== undefined) headers['Cf-Access-Jwt-Assertion'] = token;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  return worker.fetch(new Request(`https://labeller.test${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) }), env);
}

test('fails closed with 503 when CF_ACCESS_AUD or team domain is unset, even with a valid token', async () => {
  const token = await sign();
  for (const unset of ['CF_ACCESS_AUD', 'CF_ACCESS_TEAM_DOMAIN']) {
    env[unset] = '';
    assert.equal((await call('GET', '/api/labels/test-video-mv2', { token })).status, 503);
    env[unset] = unset === 'CF_ACCESS_AUD' ? AUD : TEAM;
  }
  delete env.CF_ACCESS_AUD;
  assert.equal((await call('GET', '/nope', { token })).status, 503);
});

test('401 for missing, malformed, wrong-signature, expired, not-yet-valid, wrong-aud, wrong-iss, unknown-kid, alg none', async () => {
  const now = Math.floor(Date.now() / 1000);
  const good = await sign();
  const [h, p] = good.split('.');
  const cases = {
    missing: undefined,
    malformed: 'not.a.jwt',
    wrongSignature: await sign({}, { key: other.privateKey }),
    tamperedPayload: `${h}.${enc({ ...JSON.parse(Buffer.from(p, 'base64url')), email: 'evil@example.com' })}.${good.split('.')[2]}`,
    expired: await sign({ exp: now - 3600 }),
    notYetValid: await sign({ nbf: now + 3600 }),
    wrongAud: await sign({ aud: ['someone-else'] }),
    wrongIss: await sign({ iss: 'https://evil.cloudflareaccess.com' }),
    unknownKid: await sign({}, { kid: 'k2' }),
    algNone: `${enc({ alg: 'none', kid: KID })}.${p}.`,
    noEmail: await sign({ email: undefined }),
  };
  for (const [name, token] of Object.entries(cases)) {
    const res = await call('GET', '/api/labels/test-video-mv2', { token });
    assert.equal(res.status, 401, name);
    assert.deepEqual(await res.json(), { error: 'Unauthorized' }, name);
  }
});

test('a correctly signed token is accepted; aud may be a string; JWKS is cached', async () => {
  assert.equal((await call('GET', '/api/labels/test-video-mv2', { token: await sign() })).status, 200);
  assert.equal((await call('GET', '/api/labels/test-video-mv2', { token: await sign({ aud: AUD }) })).status, 200);
  assert.equal(fetches.length, 1);
});

test('PUT stores the verdict with the verified email; GET lists all labels across pages', async () => {
  const token = await sign();
  const puts = [[32, 2, { verdict: 'not_a_contestant' }], [32, 3, { verdict: 'unsure' }], [33, 0, { verdict: 'box_wrong' }], [5, 1, { verdict: 'contestant', contestant_id: '42' }]];
  for (const [f, i, body] of puts) {
    const res = await call('PUT', `/api/labels/test-video-mv2/${f}/${i}`, { token, body });
    assert.equal(res.status, 200);
  }
  const stored = JSON.parse(env.LABELS.store.get('label:test-video-mv2:32:2'));
  assert.equal(stored.labeller, 'labeller@example.com');
  assert.equal(stored.verdict, 'not_a_contestant');
  assert.ok(!Number.isNaN(Date.parse(stored.labelled_at)));

  // A different video sharing the prefix stem must not leak in.
  env.LABELS.store.set('label:test-video-mv2b:1:1', JSON.stringify({ verdict: 'unsure' }));

  const body = await (await call('GET', '/api/labels/test-video-mv2', { token })).json();
  assert.equal(body.schema, 'labels/v1');
  assert.equal(body.video_id, 'test-video-mv2');
  assert.deepEqual(body.labels.map((l) => [l.frame_number, l.detection_index, l.verdict]), [[5, 1, 'contestant'], [32, 2, 'not_a_contestant'], [32, 3, 'unsure'], [33, 0, 'box_wrong']]);
  assert.equal(body.labels[0].contestant_id, '42');
  assert.equal(body.labels[0].labeller, 'labeller@example.com');
});

test('PUT validates verdict, contestant_id, body and indices', async () => {
  const token = await sign();
  const bad = [
    ['/api/labels/test-video-mv2/1/0', { verdict: 'maybe' }],
    ['/api/labels/test-video-mv2/1/0', { verdict: 'Contestant' }],
    ['/api/labels/test-video-mv2/1/0', {}],
    ['/api/labels/test-video-mv2/1/0', { verdict: 'contestant' }],
    ['/api/labels/test-video-mv2/1/0', { verdict: 'contestant', contestant_id: '../1' }],
    ['/api/labels/test-video-mv2/1/0', { verdict: 'unsure', contestant_id: '3' }],
    ['/api/labels/test-video-mv2/-1/0', { verdict: 'unsure' }],
    ['/api/labels/test-video-mv2/1/-1', { verdict: 'unsure' }],
    ['/api/labels/test-video-mv2/1.5/0', { verdict: 'unsure' }],
    ['/api/labels/test-video-mv2/abc/0', { verdict: 'unsure' }],
    ['/api/labels/test-video-mv2/1/1e3', { verdict: 'unsure' }],
    ['/api/labels/bad%3Aid/1/0', { verdict: 'unsure' }],
  ];
  for (const [path, body] of bad) {
    assert.equal((await call('PUT', path, { token, body })).status, 400, `${path} ${JSON.stringify(body)}`);
  }
  const notJson = await worker.fetch(new Request('https://labeller.test/api/labels/test-video-mv2/1/0', { method: 'PUT', headers: { 'Cf-Access-Jwt-Assertion': token }, body: '{' }), env);
  assert.equal(notJson.status, 400);
  assert.equal(env.LABELS.store.size, 0);
});

test('CJK video ids are accepted', async () => {
  const token = await sign();
  const id = '《測試》 MV-1_a.b';
  assert.equal((await call('PUT', `/api/labels/${encodeURIComponent(id)}/0/0`, { token, body: { verdict: 'unsure' } })).status, 200);
  assert.ok(env.LABELS.store.has(`label:${id}:0:0`));
});

test('DELETE removes the key', async () => {
  const token = await sign();
  await call('PUT', '/api/labels/test-video-mv2/7/1', { token, body: { verdict: 'unsure' } });
  assert.ok(env.LABELS.store.has('label:test-video-mv2:7:1'));
  assert.equal((await call('DELETE', '/api/labels/test-video-mv2/7/1', { token })).status, 204);
  assert.ok(!env.LABELS.store.has('label:test-video-mv2:7:1'));
  assert.equal((await call('DELETE', '/api/labels/test-video-mv2/7/1', { token: await sign({ exp: 1 }) })).status, 401);
});

test('crop route serves the R2 object and rejects traversal and bad names', async () => {
  const token = await sign();
  const ok = await call('GET', '/crops/test-video-mv2/32_2.jpg', { token });
  assert.equal(ok.status, 200);
  assert.equal(ok.headers.get('Content-Type'), 'image/jpeg');
  assert.equal(await ok.text(), 'JPEGBYTES');
  assert.equal((await call('GET', '/crops/test-video-mv2/99_9.jpg', { token })).status, 404);

  for (const path of [
    '/crops/test-video-mv2/..%2F..%2Fsecret.jpg',
    '/crops/..%2Fother/32_2.jpg',
    '/crops/test-video-mv2/32_2.png',
    '/crops/test-video-mv2/32_2.jpg%00',
    '/crops/..%2E/32_2.jpg',
  ]) {
    assert.equal((await call('GET', path, { token })).status, 400, path);
  }
  // URL parsing resolves an encoded dot-dot segment before routing; it lands on no route.
  assert.equal((await call('GET', '/crops/test-video-mv2/%2e%2e', { token })).status, 404);
  assert.equal((await call('GET', '/crops/test-video-mv2/32_2.jpg')).status, 401);
  assert.deepEqual(env.LABEL_CROPS.gets, ['crops/test-video-mv2/32_2.jpg', 'crops/test-video-mv2/99_9.jpg']);
});

test('unknown routes and methods are 404 (after auth)', async () => {
  const token = await sign();
  for (const [m, p] of [['GET', '/'], ['POST', '/api/labels/test-video-mv2'], ['GET', '/api/labels/test-video-mv2/1/0'], ['PUT', '/crops/test-video-mv2/32_2.jpg'], ['GET', '/api/labels/test-video-mv2/1/0/extra']]) {
    assert.equal((await call(m, p, { token })).status, 404, `${m} ${p}`);
  }
  assert.equal((await call('GET', '/')).status, 401);
});

test('importer prints one wrangler kv command per label and keeps source_processing_date', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const out = execFileSync(process.execPath, [join(here, '..', 'import_labels.mjs')], { encoding: 'utf8' });
  const cmds = out.split('\n').filter((l) => l.startsWith('npx wrangler kv key put'));
  assert.ok(cmds.length > 0);
  assert.match(cmds[0], /--binding=LABELS --remote 'label:test-video-mv2:\d+:\d+' '\{"verdict":"[a-z_]+".*"labeller":"import","labelled_at":"[^"]+","source_processing_date":"2026-09-21T01:40:44.883847"\}'$/);
});
