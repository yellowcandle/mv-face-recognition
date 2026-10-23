/**
 * Processing-job records for the admin console.
 *
 * One KV document per job (`job:<8 hex>`), with the shapes `local_api.py` served when the console
 * was local-only (ADR 0006). The record — not the HF Jobs run — is what the admin reads: a
 * pipeline can outlive the request that started it, and a job whose upstream run vanished must
 * still be visible as failed rather than silently disappear.
 *
 * The record carries two fields that never cross the wire: `video_files` (what was asked for) and
 * `hf_job_id` (how to reach the upstream run). Both are internal bookkeeping.
 */

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
export type JobMode = 'initial' | 'embedding-update' | 'coverage-refresh';

export const JOB_MODES: readonly JobMode[] = ['initial', 'embedding-update', 'coverage-refresh'];

export interface ProcessingJob {
  id: string;
  status: JobStatus;
  /** 0–100. A single-reel job reports 0 queued, 10 running, 100 terminal. */
  progress: number;
  mode: JobMode;
  total_videos: number;
  videos_processed: number;
  /** Reel being processed; the edge runs one reel per job, so this is informational. */
  current_video: string | null;
  /** ISO-8601 string, matching the local API's `created_at`. */
  created_at: string;
  /** Epoch milliseconds, matching the local API's numbers. */
  started_at: number | null;
  completed_at: number | null;
  /** Internal: reels the job was asked to process. Never served. */
  video_files: string[];
  /** Internal: upstream HF Jobs id. Never served. */
  hf_job_id: string | null;
  /** Upstream failure message, served exactly where the local API served it. */
  error: string | null;
}

/** What the admin reads: the record minus its internal fields. */
export type WireJob = Omit<ProcessingJob, 'video_files' | 'hf_job_id'>;

/**
 * The subset of `KVNamespace` these functions need. Declared structurally so the tests can drive
 * an in-memory store without a Miniflare runtime.
 */
export interface JobStore {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
  delete(key: string): Promise<void>;
  list(options?: { prefix?: string; cursor?: string }): Promise<JobKeyPage>;
}

export interface JobKeyPage {
  keys: Array<{ name: string }>;
  list_complete: boolean;
  cursor?: string;
}

const JOB_PREFIX = 'job:';
/** Records outlive a week only if something is badly wrong; the Hub keeps the real history. */
export const JOB_TTL_SECONDS = 60 * 60 * 24 * 7;

/** Terminal states, keyed statically so a new status cannot be forgotten in a `Set`. */
const TERMINAL_STATUS: Record<JobStatus, boolean> = {
  queued: false,
  running: false,
  completed: true,
  failed: true,
  cancelled: true,
};

export function jobKey(id: string): string {
  return `${JOB_PREFIX}${id}`;
}

export function newJobId(): string {
  return crypto.randomUUID().replace(/-/g, '').slice(0, 8);
}

export function isTerminal(status: JobStatus): boolean {
  return TERMINAL_STATUS[status];
}

export function isJobMode(value: unknown): value is JobMode {
  return typeof value === 'string' && (JOB_MODES as readonly string[]).includes(value);
}

export function toWire(job: ProcessingJob): WireJob {
  const { video_files: _videoFiles, hf_job_id: _hfJobId, ...wire } = job;
  return wire;
}

export async function putJob(store: JobStore, job: ProcessingJob): Promise<void> {
  await store.put(jobKey(job.id), JSON.stringify(job), { expirationTtl: JOB_TTL_SECONDS });
}

export async function readJob(store: JobStore, id: string): Promise<ProcessingJob | null> {
  const raw = await store.get(jobKey(id));
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return null;
    return parsed as ProcessingJob;
  } catch {
    return null;
  }
}

/** Every page of `job:` keys. KV list is paginated; a single call silently truncates. */
async function jobKeys(store: JobStore): Promise<string[]> {
  const names: string[] = [];
  let cursor: string | undefined;
  do {
    const page = await store.list(cursor ? { prefix: JOB_PREFIX, cursor } : { prefix: JOB_PREFIX });
    for (const key of page.keys) names.push(key.name.slice(JOB_PREFIX.length));
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return names;
}

export async function listJobs(store: JobStore): Promise<ProcessingJob[]> {
  const ids = await jobKeys(store);
  const jobs = await Promise.all(ids.map((id) => readJob(store, id)));
  // Insertion order is not preserved by KV; newest first matches how the console reads them.
  return jobs
    .filter((job): job is ProcessingJob => job !== null)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export async function countActiveJobs(store: JobStore): Promise<number> {
  const jobs = await listJobs(store);
  return jobs.filter((job) => !isTerminal(job.status)).length;
}

export async function cancelJob(store: JobStore, id: string): Promise<ProcessingJob | null> {
  const job = await readJob(store, id);
  if (!job) return null;
  if (!isTerminal(job.status)) {
    job.status = 'cancelled';
    job.completed_at = Date.now();
    job.progress = 100;
    await putJob(store, job);
  }
  return job;
}

export async function clearCompleted(store: JobStore): Promise<number> {
  const ids = await jobKeys(store);
  const jobs = await Promise.all(ids.map((id) => readJob(store, id)));
  let cleared = 0;
  for (const job of jobs) {
    if (job && isTerminal(job.status)) {
      await store.delete(jobKey(job.id));
      cleared += 1;
    }
  }
  return cleared;
}
