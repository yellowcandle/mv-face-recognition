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
const STORED = {
  video_info: { processing_date: '2026-01-02T03:04:05' },
  contestant_timeline: { 5: { total_appearances: 1, average_match_score: 0.5 } },
  frame_data: [
    {
      frame_number: 60,
      timestamp: 10,
      detections: [
        unmatched(BOX_A),
        {
          ...unmatched(BOX_B, 8),
          match_source: 'frame',
          contestant_id: '5',
          contestant_name: '錯的',
          contestant_nickname: 'Wrong',
          match_score: 0.5,
        },
      ],
    },
    // Same track, same box a frame later: a flag covers one detection, never the track.
    { frame_number: 61, timestamp: 10.16, detections: [unmatched(BOX_A)] },
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

/** Stored text keeps odd spacing so a verbatim read can be told from a re-serialised one. */
function makeEnv(flags, { roster = ROSTER, extra = {} } = {}) {
  const store = new Map(
    Object.entries({
      [`metadata_${VIDEO}`]: JSON.stringify(STORED, null, 1),
      ...(roster ? { contestants_structured: JSON.stringify(roster) } : {}),
      ...extra,
    }),
  );
  for (const record of flags) store.set(`flag_${record.id}`, JSON.stringify(record));
  const log = { gets: [], puts: [] };
  return {
    log,
    store,
    METADATA_KV: {
      get: async (key) => {
        log.gets.push(key);
        return store.get(key) ?? null;
      },
      put: async (key) => log.puts.push(key),
      delete: async (key) => log.puts.push(key),
      list: async ({ prefix = '' } = {}) => ({
        keys: [...store.keys()]
          .filter((name) => name.startsWith(prefix))
          .sort()
          .map((name) => ({ name })),
        list_complete: true,
      }),
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

test('a read writes nothing, and stored metadata and the timeline stay as they were', async () => {
  const env = makeEnv([flag()]);
  const before = env.store.get(`metadata_${VIDEO}`);
  const metadata = await dense(env);
  await facesAt(env, 10.03);
  assert.deepEqual(env.log.puts, []);
  assert.equal(env.store.get(`metadata_${VIDEO}`), before);
  assert.deepEqual(metadata.contestant_timeline, STORED.contestant_timeline);
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
