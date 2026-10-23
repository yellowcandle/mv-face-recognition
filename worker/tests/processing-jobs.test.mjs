/**
 * Contract tests for the processing-job store and the HF Jobs payload builder.
 *
 * These drive the modules directly, with an in-memory KV and no network: the route layer's auth
 * and cache behaviour is covered by `worker-is-read-only.test.mjs`, and the shapes here are what
 * the admin reads.
 */
import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKER_DIR = join(HERE, '..');

function bundle(relPath) {
  const out = join(mkdtempSync(join(tmpdir(), 'worker-lib-')), 'mod.mjs');
  execFileSync(
    join(WORKER_DIR, 'node_modules/.bin/esbuild'),
    [
      join(WORKER_DIR, relPath),
      '--bundle',
      '--format=esm',
      '--platform=neutral',
      '--outfile=' + out,
    ],
    { cwd: WORKER_DIR, stdio: 'pipe' },
  );
  return out;
}

const jobs = await import(pathToFileURL(bundle('src/lib/jobs.ts')).href);
const hf = await import(pathToFileURL(bundle('src/lib/hfJobs.ts')).href);

/** KV-shaped store: paginated two keys per page, so the list loop is actually exercised. */
function memoryStore() {
  const data = new Map();
  const puts = [];
  return {
    puts,
    async get(key) {
      return data.has(key) ? data.get(key) : null;
    },
    async put(key, value, options) {
      data.set(key, value);
      puts.push({ key, options });
    },
    async delete(key) {
      data.delete(key);
    },
    async list({ prefix = '', cursor } = {}) {
      const names = [...data.keys()].filter((name) => name.startsWith(prefix)).sort();
      const start = cursor ? Number(cursor) : 0;
      const slice = names.slice(start, start + 2);
      const nextCursor = start + 2 < names.length ? String(start + 2) : undefined;
      const page = {
        keys: slice.map((name) => ({ name })),
        list_complete: nextCursor === undefined,
      };
      if (nextCursor !== undefined) page.cursor = nextCursor;
      return page;
    },
  };
}

function seedJob(store, overrides) {
  const job = {
    id: jobs.newJobId(),
    status: 'queued',
    progress: 0,
    mode: 'initial',
    total_videos: 1,
    videos_processed: 0,
    current_video: '4-《全民造星IV》極限拍MV.mp4',
    created_at: '2026-10-22T00:00:00.000Z',
    started_at: null,
    completed_at: null,
    video_files: ['4-《全民造星IV》極限拍MV.mp4'],
    hf_job_id: null,
    error: null,
    ...overrides,
  };
  return job;
}

test('job records keep the local API shape and hide internals', async () => {
  const store = memoryStore();
  const job = seedJob(store);
  await jobs.putJob(store, job);

  const stored = await jobs.readJob(store, job.id);
  assert.deepEqual(stored, job, 'the record round-trips unchanged');

  const wire = jobs.toWire(stored);
  assert.equal('video_files' in wire, false, 'video_files must not cross the wire');
  assert.equal('hf_job_id' in wire, false, 'hf_job_id must not cross the wire');
  assert.deepEqual(Object.keys(wire).sort(), [
    'completed_at',
    'created_at',
    'current_video',
    'error',
    'id',
    'mode',
    'progress',
    'started_at',
    'status',
    'total_videos',
    'videos_processed',
  ]);

  assert.equal(store.puts[0].options.expirationTtl, jobs.JOB_TTL_SECONDS);
});

test('listJobs reads every KV page and returns newest first', async () => {
  const store = memoryStore();
  const older = seedJob(store, { created_at: '2026-10-20T00:00:00.000Z' });
  const newer = seedJob(store, { created_at: '2026-10-22T00:00:00.000Z' });
  const middle = seedJob(store, { created_at: '2026-10-21T00:00:00.000Z' });
  for (const job of [older, newer, middle]) await jobs.putJob(store, job);

  const listed = await jobs.listJobs(store);
  assert.deepEqual(
    listed.map((job) => job.id),
    [newer.id, middle.id, older.id],
    'three records span two KV pages and must all survive',
  );
});

test('only terminal records are cleared; cancellation flips exactly once', async () => {
  const store = memoryStore();
  const done = seedJob(store, { status: 'completed', progress: 100 });
  const failed = seedJob(store, { status: 'failed', progress: 100, error: 'boom' });
  const running = seedJob(store, { status: 'running', progress: 10 });
  for (const job of [done, failed, running]) await jobs.putJob(store, job);

  assert.equal(await jobs.countActiveJobs(store), 1);

  const cancelled = await jobs.cancelJob(store, running.id);
  assert.equal(cancelled.status, 'cancelled');
  assert.equal(cancelled.progress, 100);
  assert.equal(typeof cancelled.completed_at, 'number');

  assert.equal(await jobs.clearCompleted(store), 3, 'completed, failed and cancelled all clear');
  assert.equal(await jobs.readJob(store, done.id), null);
  assert.equal(await jobs.cancelJob(store, 'missing'), null);
});

test('HF stages map onto the five states, and unknowns fail closed', () => {
  assert.deepEqual(hf.mapStage('SCHEDULING'), { status: 'queued', progress: 0 });
  assert.deepEqual(hf.mapStage('RUNNING'), { status: 'running', progress: 10 });
  assert.deepEqual(hf.mapStage('UPDATING'), { status: 'running', progress: 10 });
  assert.deepEqual(hf.mapStage('COMPLETED'), { status: 'completed', progress: 100 });
  assert.deepEqual(hf.mapStage('CANCELED'), { status: 'cancelled', progress: 100 });
  assert.deepEqual(hf.mapStage('DELETED'), { status: 'cancelled', progress: 100 });

  const errored = hf.mapStage('ERROR', 'CUDA out of memory');
  assert.equal(errored.status, 'failed');
  assert.equal(errored.detail, 'CUDA out of memory');

  const unknown = hf.mapStage('SOMETHING_NEW');
  assert.equal(unknown.status, 'failed', 'an unknown stage must never read as completed');
  assert.match(unknown.detail, /SOMETHING_NEW/);
});

test('a reel filename yields the manifest id, and nothing else does', () => {
  assert.equal(hf.videoIdFromFilename('4-《全民造星IV》極限拍MV.mp4'), '4');
  assert.equal(hf.videoIdFromFilename('12_reel.mp4'), '12');
  assert.equal(hf.videoIdFromFilename('test-video-mv2.mp4'), null);
  assert.equal(hf.videoIdFromFilename(' 3.mp4 '), '3');
});

test('the job spec matches submit.py: command, timeout, label and volume', () => {
  const video = hf.buildJobSpec({
    mode: 'initial',
    videoId: '4',
    ref: 'main',
    bucket: 'yellowcandle/mv-face-recognition',
    cacheFlavor: 'cpu-upgrade',
    videoFlavor: 'cpu-upgrade',
  });
  assert.deepEqual(video.command.slice(0, 2), ['bash', '-lc']);
  assert.doesNotMatch(video.command[2], /build-essential|pip install/);
  assert.match(video.command[2], /hf_pipeline\.py/);
  assert.match(video.command[2], /python \/tmp\/j\.py video --video-id 4$/);
  assert.equal(video.flavor, 'cpu-upgrade');
  assert.equal(video.dockerImage, hf.HF_JOBS_DEFAULTS.image);
  assert.deepEqual(video.environment, { REPO_REF: 'main' });
  assert.equal(video.timeoutSeconds, 10800);
  assert.deepEqual(video.labels, { name: 'mv-video-4' });
  assert.deepEqual(video.volumes, [
    { type: 'bucket', source: 'yellowcandle/mv-face-recognition', mountPath: '/mnt/data' },
  ]);

  // A GPU flavor is the whole switch: image, provider env and setup follow the name.
  const gpu = hf.buildJobSpec({
    mode: 'initial',
    videoId: '4',
    ref: 'main',
    bucket: 'yellowcandle/mv-face-recognition',
    cacheFlavor: 'cpu-upgrade',
    videoFlavor: 'a10g-small',
  });
  assert.match(gpu.command[2], /build-essential/);
  assert.match(gpu.command[2], /pip install -q uv/);
  assert.equal(gpu.flavor, 'a10g-small');
  assert.equal(gpu.dockerImage, hf.HF_JOBS_DEFAULTS.gpuImage);
  assert.deepEqual(gpu.environment, {
    REPO_REF: 'main',
    ONNXRUNTIME_GPU: '1',
    INSIGHTFACE_PROVIDERS: 'CUDAExecutionProvider',
  });

  const cache = hf.buildJobSpec({
    mode: 'embedding-update',
    videoId: null,
    ref: 'main',
    bucket: 'yellowcandle/mv-face-recognition',
    cacheFlavor: 'cpu-upgrade',
    videoFlavor: 'a10g-small',
  });
  assert.match(cache.command[2], /python \/tmp\/j\.py cache$/);
  assert.doesNotMatch(cache.command[2], /build-essential|pip install/);
  assert.equal(cache.flavor, 'cpu-upgrade');
  assert.equal(cache.dockerImage, hf.HF_JOBS_DEFAULTS.image);
  assert.deepEqual(cache.environment, { REPO_REF: 'main' });
  assert.equal(cache.timeoutSeconds, 2700);
  assert.deepEqual(cache.labels, { name: 'mv-cache' });
});
