/**
 * Accepted flags are overlaid on detections as they are served; stored metadata is untouched,
 * so rejecting or re-pending a flag undoes it. Both read paths must agree, through the fetch
 * handler: `/api/faces/detect` (Admin player) and dense metadata (Viewer, 紀錄, 標註).
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

let bundlePath = null;
async function loadWorker() {
  if (!bundlePath) {
    bundlePath = join(mkdtempSync(join(tmpdir(), 'worker-flags-')), 'worker.mjs');
    execFileSync(
      join(WORKER_DIR, 'node_modules/.bin/esbuild'),
      [
        join(WORKER_DIR, 'src/index.ts'),
        '--bundle',
        '--format=esm',
        '--platform=neutral',
        '--outfile=' + bundlePath,
      ],
      { cwd: WORKER_DIR, stdio: 'pipe' },
    );
  }
  return (await import(pathToFileURL(bundlePath).href)).default;
}

const VIDEO = 'reel-1';
const BOX_A = [0.1, 0.2, 0.3, 0.4];
const BOX_B = [0.5, 0.6, 0.7, 0.8];
const ROSTER = [
  { id: '1', number: 1, name: '蘇雅琳', nickname: 'Ivy So' },
  { id: '2', number: 2, name: '黃雅慧', nickname: '咖喱' },
];

const unmatched = (bbox, tracker_id = 7) => ({
  tracker_id,
  match_source: null,
  contestant_id: null,
  contestant_name: null,
  contestant_nickname: null,
  match_score: null,
  det_score: 0.81,
  bbox,
});
const recognised = (bbox, contestant_id, match_score) => ({
  ...unmatched(bbox, 8),
  match_source: 'frame',
  contestant_id,
  contestant_name: `名${contestant_id}`,
  contestant_nickname: `Nick${contestant_id}`,
  match_score,
});
const STORED = {
  video_info: { processing_date: '2026-01-02T03:04:05' },
  processing_summary: {
    frames_processed: 3,
    total_faces_detected: 5,
    total_recognitions: 3,
    unique_contestants: 2,
    recognition_rate: 0.6,
  },
  contestant_timeline: {
    2: {
      contestant_info: { id: '2', name: '名2', nickname: 'Nick2' },
      appearances: [{ timestamp: 10.32, frame_number: 62, match_score: 0.6, bbox: BOX_A }],
      total_appearances: 1,
      average_match_score: 0.6,
      max_match_score: 0.6,
      first_appearance: 10.32,
      last_appearance: 10.32,
    },
    5: {
      contestant_info: { id: '5', name: '名5', nickname: 'Nick5' },
      appearances: [
        { timestamp: 10, frame_number: 60, match_score: 0.5, bbox: BOX_B },
        { timestamp: 10.32, frame_number: 62, match_score: 0.7, bbox: BOX_B },
      ],
      total_appearances: 2,
      average_match_score: 0.6,
      max_match_score: 0.7,
      first_appearance: 10,
      last_appearance: 10.32,
    },
  },
  frame_data: [
    {
      frame_number: 60,
      timestamp: 10,
      detections_count: 2,
      recognitions_count: 1,
      detections: [unmatched(BOX_A), recognised(BOX_B, '5', 0.5)],
    },
    // Same track, same box a frame later: a flag covers one detection, never the track.
    {
      frame_number: 61,
      timestamp: 10.16,
      detections_count: 1,
      recognitions_count: 0,
      detections: [unmatched(BOX_A)],
    },
    {
      frame_number: 62,
      timestamp: 10.32,
      detections_count: 2,
      recognitions_count: 2,
      detections: [recognised(BOX_B, '5', 0.7), recognised(BOX_A, '2', 0.6)],
    },
  ],
};

const flag = (overrides = {}) => ({
  id: 'f1',
  contestant_id: 1,
  video_id: VIDEO,
  timestamp: 10.03,
  confidence: 0,
  bbox: BOX_A,
  status: 'accepted',
  user_label: 'SECRET-LABEL',
  thumbnail: 'SECRET-THUMB',
  created_at: '2026-10-01T00:00:00.000Z',
  flagged_by: 'SECRET-USER',
  ...overrides,
});

const metadataOf = ({ video_id, status }) => ({ video_id, status });

/**
 * KV as workerd behaves (checked against Miniflare): `put` replaces metadata, and without any
 * clears it; `list` returns it, with no `metadata` key when there is none; 1000 keys a page, with a
 * cursor only when more remain; over 1024 bytes of JSON the put throws and nothing is stored.
 *
 * Stored text keeps odd spacing so a verbatim read can be told from a re-serialised one.
 * Flags have no metadata, like every flag written before it existed, unless `keyMetadata` is set.
 */
function makeEnv(flags, { roster = ROSTER, extra = {}, keyMetadata = false } = {}) {
  const store = new Map(
    Object.entries({
      [`metadata_${VIDEO}`]: JSON.stringify(STORED, null, 1),
      ...(roster ? { contestants_structured: JSON.stringify(roster) } : {}),
      ...extra,
    }),
  );
  const keyMeta = new Map();
  for (const record of flags) {
    store.set(`flag_${record.id}`, JSON.stringify(record));
    if (keyMetadata) keyMeta.set(`flag_${record.id}`, metadataOf(record));
  }
  const log = { gets: [], puts: [], lists: 0 };
  return {
    log,
    store,
    keyMeta,
    METADATA_KV: {
      get: async (key) => {
        log.gets.push(key);
        return store.get(key) ?? null;
      },
      put: async (key, value, options = {}) => {
        log.puts.push(key);
        const length = new TextEncoder().encode(JSON.stringify(options.metadata) ?? '').length;
        if (length > 1024) {
          throw new Error(`KV PUT failed: 413 Metadata length of ${length} exceeds limit of 1024.`);
        }
        store.set(key, value);
        if (options.metadata === undefined) keyMeta.delete(key);
        else keyMeta.set(key, options.metadata);
      },
      delete: async (key) => {
        log.puts.push(key);
        store.delete(key);
        keyMeta.delete(key);
      },
      list: async ({ prefix = '', cursor } = {}) => {
        log.lists += 1;
        const names = [...store.keys()].filter((name) => name.startsWith(prefix)).sort();
        const start = cursor ? Number(cursor) : 0;
        const done = start + 1000 >= names.length;
        return {
          keys: names
            .slice(start, start + 1000)
            .map((name) => (keyMeta.has(name) ? { name, metadata: keyMeta.get(name) } : { name })),
          list_complete: done,
          ...(done ? {} : { cursor: String(start + 1000) }),
        };
      },
    },
  };
}

const CONTEXT = { waitUntil() {}, passThroughOnException() {} };

async function get(env, path) {
  const worker = await loadWorker();
  return worker.fetch(new Request(`https://worker.test${path}`), env, CONTEXT);
}

const denseResponse = (env) => get(env, `/api/videos/metadata/dense/${VIDEO}`);
const dense = async (env) => (await denseResponse(env)).json();
const facesAt = async (env, timestamp) =>
  (await (await get(env, `/api/faces/detect?video_id=${VIDEO}&timestamp=${timestamp}`)).json())
    .faces;
const denseFace = (metadata, frame = 0, detection = 0) =>
  metadata.frame_data[frame].detections[detection];

/** The stored document must come back byte for byte, and no roster read be spent on it. */
async function assertNothingChanged(flags) {
  const env = makeEnv(flags);
  const response = await denseResponse(env);
  assert.equal(await response.text(), env.store.get(`metadata_${VIDEO}`));

  const [face] = await facesAt(env, 10.03);
  assert.equal(face.contestant_id, null);
  assert.equal(face.match_source, null);
  assert.equal(face.matched, false);
}

test('an accepted flag turns an unmatched detection into the flagged contestant, in both reads', async () => {
  const env = makeEnv([flag()]);
  const expected = {
    contestant_id: '1',
    contestant_name: '蘇雅琳',
    contestant_nickname: 'Ivy So',
    matched: true,
    match_source: 'flag',
    match_score: null,
    det_score: 0.81,
    tracker_id: 7,
    bbox: BOX_A,
  };

  assert.deepEqual(denseFace(await dense(env)), expected);

  const faces = await facesAt(env, 10.03);
  assert.deepEqual(faces[0], expected);
  assert.equal(faces[1].contestant_id, '5', 'the other face in the frame is left alone');
  assert.equal(faces[1].match_score, 0.5);
});

test('a flag covers one detection: the next frame of the same track stays as stored', async () => {
  const env = makeEnv([flag()]);
  assert.equal(denseFace(await dense(env), 1).contestant_id, null);
  assert.equal((await facesAt(env, 10.16))[0].contestant_id, null);
});

test('a recognition flagged as someone else loses its cosine', async () => {
  const env = makeEnv([flag({ contestant_id: 2, bbox: BOX_B })]);
  const face = denseFace(await dense(env), 0, 1);
  assert.equal(face.contestant_id, '2');
  assert.equal(face.contestant_nickname, '咖喱');
  assert.equal(face.match_score, null);
  assert.equal(face.match_source, 'flag');
});

test('pending and rejected flags change nothing and spend no roster read', async () => {
  for (const status of ['pending', 'rejected']) {
    await assertNothingChanged([flag({ status })]);
    const env = makeEnv([flag({ status })]);
    await denseResponse(env);
    assert.ok(!env.log.gets.includes('contestants_structured'));
  }
});

test("another reel's accepted flag is ignored", async () => {
  await assertNothingChanged([flag({ video_id: 'reel-2' })]);
});

test('flags with no bbox or no exact bbox are skipped, never matched by proximity', async () => {
  for (const bbox of [null, undefined, [0.1, 0.2, 0.3], [0.1, 0.2, 0.3, 0.401]]) {
    await assertNothingChanged([flag({ bbox })]);
  }
});

test('bbox equality has float slack', async () => {
  const env = makeEnv([flag({ bbox: [0.1 + 1e-7, 0.2, 0.3, 0.4 - 1e-7] })]);
  assert.equal(denseFace(await dense(env)).contestant_id, '1');
});

test('a flag lands on the floor frame, and only that frame', async () => {
  // Exactly on the frame.
  assert.equal(denseFace(await dense(makeEnv([flag({ timestamp: 10 })]))).contestant_id, '1');
  // After the second frame: the box matches there, not in the first frame.
  const later = await dense(makeEnv([flag({ timestamp: 10.2 })]));
  assert.equal(denseFace(later, 1).contestant_id, '1');
  assert.equal(denseFace(later, 0).contestant_id, null);
  // Before any frame: nothing to file against.
  await assertNothingChanged([flag({ timestamp: 9 })]);
  // BOX_B is only in the first frame, and the floor of 10.2 is the second.
  const missed = await dense(makeEnv([flag({ timestamp: 10.2, bbox: BOX_B })]));
  assert.equal(denseFace(missed, 0, 1).contestant_id, '5');
});

test('the newest accepted flag wins whichever order KV lists them in', async () => {
  const older = { contestant_id: 2, created_at: '2026-10-01T00:00:00.000Z' };
  const newer = { contestant_id: 1, created_at: '2026-10-02T00:00:00.000Z' };
  for (const [a, b] of [
    [older, newer],
    [newer, older],
  ]) {
    const env = makeEnv([flag({ id: 'a', ...a }), flag({ id: 'b', ...b })]);
    assert.equal(denseFace(await dense(env)).contestant_id, '1');
    assert.equal((await facesAt(env, 10.03))[0].contestant_id, '1');
  }
});

test('a newer pending flag does not outrank an accepted one', async () => {
  const env = makeEnv([
    flag({ id: 'a', contestant_id: 1, created_at: '2026-10-01T00:00:00.000Z' }),
    flag({ id: 'b', contestant_id: 2, status: 'pending', created_at: '2026-10-02T00:00:00.000Z' }),
  ]);
  assert.equal(denseFace(await dense(env)).contestant_id, '1');
});

test('contestant ids are normalised: integer flag and roster become a string detection id', async () => {
  const env = makeEnv([flag({ contestant_id: 1 })], {
    roster: [{ id: 1, name: '蘇雅琳', nickname: 'Ivy So' }],
  });
  assert.strictEqual(denseFace(await dense(env)).contestant_id, '1');
  assert.strictEqual((await facesAt(env, 10.03))[0].contestant_id, '1');
});

test('a contestant missing from the roster is skipped', async () => {
  await assertNothingChanged([flag({ contestant_id: 95 })]);
});

test('the built-in roster stands in when KV has none (local wrangler dev)', async () => {
  const env = makeEnv([flag()], { roster: null });
  assert.equal(denseFace(await dense(env)).contestant_name, '蘇雅琳');
});

test('private flag fields never reach a public read', async () => {
  const env = makeEnv([flag()]);
  for (const path of [
    `/api/videos/metadata/dense/${VIDEO}`,
    `/api/videos/metadata/${VIDEO}`,
    `/api/faces/detect?video_id=${VIDEO}&timestamp=10.03`,
  ]) {
    const text = await (await get(env, path)).text();
    assert.match(text, /"match_source":\s*"flag"/, path);
    assert.ok(!text.includes('SECRET'), `${path} leaked a flag field`);
  }
});

test('a read writes nothing, and stored metadata stays as it was', async () => {
  const env = makeEnv([flag()]);
  const before = env.store.get(`metadata_${VIDEO}`);
  await dense(env);
  await facesAt(env, 10.03);
  await get(env, `/api/recognition/results?contestant_id=1`);
  assert.deepEqual(env.log.puts, []);
  assert.equal(env.store.get(`metadata_${VIDEO}`), before);
});

test('a flag on an unrecognised face adds an appearance and removes none', async () => {
  const {
    contestant_timeline: timeline,
    processing_summary: summary,
    frame_data: frames,
  } = await dense(makeEnv([flag()]));

  assert.deepEqual(timeline['1'], {
    contestant_info: { id: '1', name: '蘇雅琳', nickname: 'Ivy So' },
    appearances: [
      { timestamp: 10, frame_number: 60, match_score: null, bbox: BOX_A, match_source: 'flag' },
    ],
    total_appearances: 1,
    average_match_score: null,
    max_match_score: null,
    first_appearance: 10,
    last_appearance: 10,
  });
  assert.deepEqual(timeline['5'], STORED.contestant_timeline['5']);
  assert.deepEqual(timeline['2'], STORED.contestant_timeline['2']);
  assert.equal(summary.total_recognitions, 4);
  assert.equal(summary.unique_contestants, 3);
  assert.equal(summary.recognition_rate, 0.8);
  assert.equal(summary.total_faces_detected, 5);
  assert.equal(frames[0].recognitions_count, 2);
  assert.equal(frames[1].recognitions_count, 0);
});

test('a flag on a recognition moves that appearance from the old contestant to the new', async () => {
  const {
    contestant_timeline: timeline,
    processing_summary: summary,
    frame_data: frames,
  } = await dense(makeEnv([flag({ contestant_id: 2, bbox: BOX_B })]));

  // The old contestant is recounted from what remains: only the 0.7 at 10.32.
  assert.equal(timeline['5'].total_appearances, 1);
  assert.equal(timeline['5'].average_match_score, 0.7);
  assert.equal(timeline['5'].max_match_score, 0.7);
  assert.equal(timeline['5'].first_appearance, 10.32);
  assert.equal(timeline['5'].appearances[0].match_score, 0.7);

  // The new one's average skips the null rather than counting it as 0, and stays time-ordered.
  assert.equal(timeline['2'].total_appearances, 2);
  assert.equal(timeline['2'].average_match_score, 0.6);
  assert.equal(timeline['2'].max_match_score, 0.6);
  assert.equal(timeline['2'].first_appearance, 10);
  assert.equal(timeline['2'].last_appearance, 10.32);
  assert.deepEqual(
    timeline['2'].appearances.map((a) => a.match_score),
    [null, 0.6],
  );

  // A recognition stayed a recognition.
  assert.equal(summary.total_recognitions, 3);
  assert.equal(summary.unique_contestants, 2);
  assert.equal(summary.recognition_rate, 0.6);
  assert.equal(frames[0].recognitions_count, 1);
});

test('a contestant left with no appearances leaves the timeline', async () => {
  const flags = [
    flag({ id: 'a', contestant_id: 1, bbox: BOX_B }),
    flag({ id: 'b', contestant_id: 1, bbox: BOX_B, timestamp: 10.33 }),
  ];
  const { contestant_timeline: timeline, processing_summary: summary } = await dense(
    makeEnv(flags),
  );
  assert.equal(timeline['5'], undefined);
  assert.equal(timeline['1'].total_appearances, 2);
  assert.equal(summary.unique_contestants, 2);
  assert.equal(summary.total_recognitions, 3);
});

test('a flag confirming the same contestant keeps the count and drops the cosine', async () => {
  const roster = [...ROSTER, { id: '5', name: '名5', nickname: 'Nick5' }];
  const { contestant_timeline: timeline, processing_summary: summary } = await dense(
    makeEnv([flag({ contestant_id: 5, bbox: BOX_B })], { roster }),
  );
  assert.equal(timeline['5'].total_appearances, 2);
  assert.equal(timeline['5'].average_match_score, 0.7);
  assert.equal(summary.total_recognitions, 3);
});

test('re-pending a flag restores the stored timeline and summary', async () => {
  const env = makeEnv([flag({ contestant_id: 2, bbox: BOX_B })]);
  await dense(env);
  env.store.set(
    'flag_f1',
    JSON.stringify(flag({ contestant_id: 2, bbox: BOX_B, status: 'pending' })),
  );
  const metadata = await dense(env);
  assert.deepEqual(metadata.contestant_timeline, STORED.contestant_timeline);
  assert.deepEqual(metadata.processing_summary, STORED.processing_summary);
});

const results = async (env, contestant, video = VIDEO) =>
  (
    await (
      await get(env, `/api/recognition/results?contestant_id=${contestant}&video_id=${video}`)
    ).json()
  ).results;

test('/api/recognition/results follows the moved appearance', async () => {
  const env = makeEnv([flag({ contestant_id: 2, bbox: BOX_B })]);

  assert.deepEqual(
    (await results(env, 5)).map((r) => r.timestamp),
    [10.32],
  );
  const [moved, own] = await results(env, 2);
  assert.deepEqual(moved, {
    video_id: VIDEO,
    timestamp: 10,
    match_score: null,
    match_source: 'flag',
    frame_number: 60,
    bbox: BOX_B,
    detection_index: 1,
  });
  assert.equal(own.match_score, 0.6);
  assert.equal(own.match_source, undefined);
});

test('/api/recognition/results finds a contestant only a flag names', async () => {
  const env = makeEnv([flag()]);
  const [only] = await results(env, 1);
  assert.equal(only.match_score, null, 'a flag has no cosine, and null must not become 0');
  assert.equal(only.detection_index, 0);
});

test('/api/recognition/results reads flags once across reels, leaks nothing, is not reused', async () => {
  const env = makeEnv([flag()], {
    extra: { 'metadata_reel-2': JSON.stringify(STORED) },
  });
  const response = await get(env, '/api/recognition/results?contestant_id=1');
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  const text = await response.text();
  assert.ok(!text.includes('SECRET'));
  // Only reel-1's flag applies, so reel-2 gains nothing.
  assert.deepEqual(
    JSON.parse(text).results.map((r) => r.video_id),
    [VIDEO],
  );
  assert.equal(env.log.gets.filter((key) => key === 'flag_f1').length, 1);
  assert.equal(env.log.gets.filter((key) => key === 'contestants_structured').length, 1);
});

test('re-pending a flag undoes it on the next read', async () => {
  const env = makeEnv([flag()]);
  assert.equal(denseFace(await dense(env)).contestant_id, '1');
  env.store.set('flag_f1', JSON.stringify(flag({ status: 'pending' })));
  assert.equal(denseFace(await dense(env)).contestant_id, null);
  assert.equal((await facesAt(env, 10.03))[0].contestant_id, null);
});

test('the staleness limit on /api/faces/detect still holds for a flagged frame', async () => {
  const env = makeEnv([flag({ timestamp: 10.2 })]);
  assert.equal((await facesAt(env, 10.2)).length, 1);
  assert.equal((await facesAt(env, 12)).length, 0);
});

test('both reads tell the browser not to reuse them, so a decision shows on the next load', async () => {
  const env = makeEnv([]);
  assert.equal((await denseResponse(env)).headers.get('Cache-Control'), 'no-store');
  const detect = await get(env, `/api/faces/detect?video_id=${VIDEO}&timestamp=10`);
  assert.equal(detect.headers.get('Cache-Control'), 'no-store');
});

test('a flag still in the legacy array applies', async () => {
  const env = makeEnv([], { extra: { flagged_faces: JSON.stringify([flag()]) } });
  assert.equal(denseFace(await dense(env)).contestant_id, '1');
});

test('flag reads are bounded per request', async () => {
  const many = Array.from({ length: 400 }, (_, i) =>
    flag({ id: `n${String(i).padStart(3, '0')}`, status: 'pending' }),
  );
  const env = makeEnv(many);
  await denseResponse(env);
  assert.equal(env.log.gets.filter((key) => key.startsWith('flag_')).length, 200);
});

test('malformed flag records and a failing flag read leave the stored metadata served', async () => {
  await assertNothingChanged([{ id: 'broken' }, flag({ id: 'bad-time', timestamp: 'soon' })]);

  const garbage = makeEnv([], { extra: { flag_garbage: 'not json' } });
  assert.equal((await denseResponse(garbage)).status, 200);

  const failing = makeEnv([flag()]);
  failing.METADATA_KV.list = async () => {
    throw new Error('KV down');
  };
  const degraded = await denseResponse(failing);
  assert.equal(degraded.status, 200);
  assert.equal((await degraded.json()).frame_data[0].detections[0].contestant_id, null);
  assert.equal((await facesAt(failing, 10.03))[0].contestant_id, null);
});

// ─── Which flags a public read fetches: KV key metadata ───

const flagGets = (env) => env.log.gets.filter((key) => key.startsWith('flag'));

// The Access application the admin routes check, as in worker-is-read-only.test.mjs.
const TEAM_DOMAIN = 'test-team.cloudflareaccess.com';
const AUD = 'test-aud';
const KID = 'k1';
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
const encodePart = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');

async function signAccessToken() {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: `https://${TEAM_DOMAIN}`,
    aud: [AUD],
    email: 'admin@example.com',
    iat: now,
    nbf: now,
    exp: now + 600,
  };
  const input = `${encodePart({ alg: 'RS256', kid: KID, typ: 'JWT' })}.${encodePart(payload)}`;
  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    privateKey,
    new TextEncoder().encode(input),
  );
  return `${input}.${Buffer.from(signature).toString('base64url')}`;
}

/** An authenticated admin request through the fetch handler; only the JWKS is fetched. */
async function admin(env, method, path, body) {
  const worker = await loadWorker();
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ keys: [publicJwk] });
  try {
    const response = await worker.fetch(
      new Request(`https://worker.test${path}`, {
        method,
        headers: { 'Cf-Access-Jwt-Assertion': await signAccessToken() },
        ...(body ? { body: JSON.stringify(body) } : {}),
      }),
      { ...env, CF_ACCESS_TEAM_DOMAIN: TEAM_DOMAIN, CF_ACCESS_AUD: AUD },
      CONTEXT,
    );
    assert.equal(response.status, 200, `${method} ${path}`);
    return await response.json();
  } finally {
    globalThis.fetch = realFetch;
  }
}

const NEW_FLAG = { contestant_id: 1, video_id: VIDEO, timestamp: 10.03, bbox: BOX_A };

test('a read gets only the accepted flags of its reel, and applies them', async () => {
  const env = makeEnv(
    [
      flag({ id: 'pending', status: 'pending' }),
      flag({ id: 'rejected', status: 'rejected' }),
      flag({ id: 'other-reel', video_id: 'reel-2' }),
      flag({ id: 'mine' }),
    ],
    { keyMetadata: true },
  );
  assert.equal(denseFace(await dense(env)).contestant_id, '1');
  assert.deepEqual(flagGets(env), ['flag_mine']);
  assert.equal(env.log.lists, 1);
});

test('a read with no reel gets accepted flags of every reel, and nothing else', async () => {
  const env = makeEnv(
    [flag({ id: 'pending', status: 'pending' }), flag(), flag({ id: 'b', video_id: 'reel-2' })],
    { keyMetadata: true },
  );
  await get(env, '/api/recognition/results?contestant_id=1');
  assert.deepEqual(flagGets(env).sort(), ['flag_b', 'flag_f1']);
});

test('a reel with only pending flags costs the list and no get at all', async () => {
  const env = makeEnv(
    [flag({ status: 'pending' }), flag({ id: 'g', status: 'pending', video_id: 'reel-2' })],
    { keyMetadata: true },
  );
  await dense(env);
  assert.deepEqual(flagGets(env), [], 'no flag read and no legacy read');
  assert.ok(!env.log.gets.includes('contestants_structured'), 'no roster read');
  assert.equal(env.log.lists, 1);
});

test('a key with no or malformed metadata is still read and applied', async () => {
  const malformed = [
    undefined,
    null,
    'pending',
    7,
    [],
    {},
    { status: 'pending' },
    { video_id: 'reel-2' },
    { status: 'PENDING', video_id: 'reel-2' },
    { status: 'pending', video_id: 9 },
    { status: 9, video_id: 'reel-2' },
  ];
  for (const metadata of malformed) {
    const env = makeEnv([flag()]);
    if (metadata !== undefined) env.keyMeta.set('flag_f1', metadata);
    const label = JSON.stringify(metadata);
    assert.equal(denseFace(await dense(env)).contestant_id, '1', label);
    assert.deepEqual(flagGets(env), ['flag_f1'], label);
    assert.deepEqual(env.log.puts, [], `${label}: a read never backfills`);
  }
});

test('the value decides: metadata saying accepted over a rejected value does not apply', async () => {
  for (const actual of [{ status: 'rejected' }, { video_id: 'reel-2' }]) {
    const env = makeEnv([flag(actual)]);
    env.keyMeta.set('flag_f1', { video_id: VIDEO, status: 'accepted' });
    assert.equal(denseFace(await dense(env)).contestant_id, null);
    assert.deepEqual(flagGets(env), ['flag_f1']);
    assert.ok(!env.log.gets.includes('contestants_structured'));
  }
});

test('every write keeps the metadata true, and the overlay follows it', async () => {
  const env = makeEnv([]);
  const { id } = await admin(env, 'POST', '/api/faces/flag', NEW_FLAG);
  const key = `flag_${id}`;
  assert.deepEqual(env.keyMeta.get(key), { video_id: VIDEO, status: 'pending' });
  assert.equal(denseFace(await dense(env)).contestant_id, null);

  await admin(env, 'PATCH', `/api/faces/flagged/${id}`, { status: 'accepted' });
  assert.deepEqual(env.keyMeta.get(key), { video_id: VIDEO, status: 'accepted' });
  assert.equal(denseFace(await dense(env)).contestant_id, '1');

  await admin(env, 'PATCH', `/api/faces/flagged/${id}`, { status: 'rejected' });
  assert.deepEqual(env.keyMeta.get(key), { video_id: VIDEO, status: 'rejected' });
  env.log.gets.length = 0;
  assert.equal(denseFace(await dense(env)).contestant_id, null);
  assert.deepEqual(flagGets(env), [], 'a rejected flag is not read');

  await admin(env, 'PATCH', `/api/faces/flagged/${id}`, { status: 'accepted' });
  await admin(env, 'POST', '/api/faces/flag/update', { face_id: id, contestant_id: 2 });
  assert.deepEqual(env.keyMeta.get(key), { video_id: VIDEO, status: 'pending' }, 'reassign');
  assert.equal(denseFace(await dense(env)).contestant_id, null);

  await admin(env, 'DELETE', `/api/faces/flagged/${id}`);
  assert.equal(env.keyMeta.has(key), false);
});

test('a video id too long for key metadata loses neither the flag nor its overlay', async () => {
  const video = '好'.repeat(400);
  const env = makeEnv([], { extra: { [`metadata_${video}`]: JSON.stringify(STORED) } });
  const { id } = await admin(env, 'POST', '/api/faces/flag', { ...NEW_FLAG, video_id: video });
  assert.ok(env.store.has(`flag_${id}`), 'the flag is stored');
  assert.equal(env.keyMeta.has(`flag_${id}`), false, 'with no metadata');

  await admin(env, 'PATCH', `/api/faces/flagged/${id}`, { status: 'accepted' });
  const path = `/api/videos/metadata/dense/${encodeURIComponent(video)}`;
  assert.equal(denseFace(await (await get(env, path)).json()).contestant_id, '1');
});

test('a status that stops the metadata fitting clears it rather than leaving it stale', async () => {
  // {"video_id":"","status":"pending"} is 34 bytes and 330 CJK characters 990: exactly 1024.
  // "accepted" is one byte longer.
  const video = '好'.repeat(330);
  const env = makeEnv([], { extra: { [`metadata_${video}`]: JSON.stringify(STORED) } });
  const { id } = await admin(env, 'POST', '/api/faces/flag', { ...NEW_FLAG, video_id: video });
  assert.deepEqual(env.keyMeta.get(`flag_${id}`), { video_id: video, status: 'pending' });

  await admin(env, 'PATCH', `/api/faces/flagged/${id}`, { status: 'accepted' });
  assert.equal(env.keyMeta.has(`flag_${id}`), false);
  const path = `/api/videos/metadata/dense/${encodeURIComponent(video)}`;
  assert.equal(denseFace(await (await get(env, path)).json()).contestant_id, '1');
});

test('an old flag gains metadata when a decision rewrites it, and a read never writes it', async () => {
  const env = makeEnv([flag({ status: 'pending' })]);
  await dense(env);
  assert.equal(env.keyMeta.has('flag_f1'), false);
  await admin(env, 'PATCH', '/api/faces/flagged/f1', { status: 'accepted' });
  assert.deepEqual(env.keyMeta.get('flag_f1'), { video_id: VIDEO, status: 'accepted' });
});

test('the legacy array is read only when listed, and a ruled-out key beats its copy in it', async () => {
  const legacy = flag({ id: 'old' });
  const applies = makeEnv([], { extra: { flagged_faces: JSON.stringify([legacy]) } });
  assert.equal(denseFace(await dense(applies)).contestant_id, '1');
  assert.deepEqual(flagGets(applies), ['flagged_faces']);

  // A claim wrote the key, a reviewer rejected it, and the array's delete has yet to propagate.
  const claimed = makeEnv([flag({ id: 'old', status: 'rejected' })], {
    keyMetadata: true,
    extra: { flagged_faces: JSON.stringify([legacy]) },
  });
  assert.equal(denseFace(await dense(claimed)).contestant_id, null);
});

test('claiming the legacy array writes metadata for each flag', async () => {
  const env = makeEnv([], {
    extra: { flagged_faces: JSON.stringify([flag({ id: 'old', status: 'rejected' })]) },
  });
  await admin(env, 'POST', '/api/faces/flag', NEW_FLAG);
  assert.equal(env.store.has('flagged_faces'), false);
  assert.deepEqual(env.keyMeta.get('flag_old'), { video_id: VIDEO, status: 'rejected' });
});

test('ruled-out keys cost no get and no ceiling, past a list page too', async () => {
  const many = Array.from({ length: 1500 }, (_, i) =>
    flag({ id: `n${String(i).padStart(4, '0')}`, status: 'pending' }),
  );
  const env = makeEnv([...many, flag({ id: 'z-accepted' })], { keyMetadata: true });
  assert.equal(denseFace(await dense(env)).contestant_id, '1');
  assert.deepEqual(flagGets(env), ['flag_z-accepted']);
  assert.equal(env.log.lists, 2);
});

test('the ceiling bounds the flags that need a get, across list pages', async () => {
  const accepted = Array.from({ length: 1100 }, (_, i) =>
    flag({ id: `a${String(i).padStart(4, '0')}`, bbox: null }),
  );
  const env = makeEnv(accepted, { keyMetadata: true });
  await dense(env);
  assert.equal(flagGets(env).length, 200);
});

test('the admin listing still reads every flag, whatever its metadata says', async () => {
  const env = makeEnv(
    [flag({ status: 'pending' }), flag({ id: 'r', status: 'rejected', video_id: 'reel-2' })],
    { keyMetadata: true },
  );
  const { flagged_faces: listed } = await admin(env, 'GET', '/api/faces/flagged');
  assert.deepEqual(listed.map((entry) => entry.id).sort(), ['f1', 'r']);
});
