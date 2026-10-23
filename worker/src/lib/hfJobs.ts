/**
 * HF Jobs dispatch for processing jobs (ADR 0006).
 *
 * The Hub exposes create / inspect / cancel over plain JSON; none of it needs a CLI step, which is
 * why the Worker can drive it directly. Two facts shape this module:
 *
 * - The Hub's stage vocabulary is wider than ours (`UPDATING` appears in the API even though the
 *   SDK's enum omits it). Anything we do not recognise maps to `failed`: mapping it to
 *   `completed` would claim a pipeline run that may never have happened.
 * - There is no delete for regular jobs, so `clear-completed` clears local records only.
 */

import type { JobMode, JobStatus } from './jobs';

const REPO_SLUG = 'yellowcandle/mv-face-recognition';
const APT = 'apt-get update -qq && apt-get install -y -qq libgl1 libglib2.0-0';

/** Defaults mirror `scripts/hf/jobs/submit.py`, which is the authority for what a run needs. */
export const HF_JOBS_DEFAULTS = {
  namespace: 'yellowcandle',
  bucket: 'yellowcandle/mv-face-recognition',
  ref: 'main',
  // A cache rebuild is CPU work over reference portraits; a reel run is detection over every
  // frame, which at ~5s/frame on `cpu-upgrade` outlives the 3h budget. Hence GPU for video.
  cacheFlavor: 'cpu-upgrade',
  videoFlavor: 'a10g-small',
  // The CUDA image ships the driver stack but no uv; the uv image cannot see a GPU.
  image: 'ghcr.io/astral-sh/uv:python3.12-bookworm',
  gpuImage: 'pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime',
} as const;

export interface HfJobsEnv {
  HF_TOKEN?: string;
  HF_JOBS_NAMESPACE?: string;
  HF_JOBS_BUCKET?: string;
  HF_JOBS_REF?: string;
  HF_JOBS_FLAVOR?: string;
  HF_JOBS_VIDEO_FLAVOR?: string;
}

export interface JobSpecInput {
  mode: JobMode;
  /** Numeric id from the source filename, e.g. `4`. Required for `initial` runs. */
  videoId?: string | null;
  ref: string;
  bucket: string;
  cacheFlavor: string;
  videoFlavor: string;
}

export interface JobSpec {
  command: string[];
  arguments: string[];
  environment: Record<string, string>;
  flavor: string;
  timeoutSeconds: number;
  labels: Record<string, string>;
  volumes: Array<{ type: string; source: string; mountPath: string }>;
  dockerImage: string;
}

/**
 * `4-《全民造星IV》極限拍MV.mp4` → `4`. The pipeline takes `--video-id` as the manifest number, so
 * the leading digits are the only portable part of a filename.
 */
export function videoIdFromFilename(filename: string): string | null {
  const match = filename.trim().match(/^(\d+)(?=[-_ .]|$)/);
  return match ? match[1] : null;
}

/**
 * The payload `run_job` would POST. `command` downloads the pipeline script from GitHub at
 * runtime, which is what lets a token with `job.write` but no bucket write submit a run.
 */
export function buildJobSpec(input: JobSpecInput): JobSpec {
  const script = `https://raw.githubusercontent.com/${REPO_SLUG}/${input.ref}/scripts/hf/jobs/hf_pipeline.py`;
  const download = `python -c "import urllib.request; urllib.request.urlretrieve('${script}','/tmp/j.py')"`;
  const gpu = input.mode === 'initial';
  const stage = gpu ? `video --video-id ${input.videoId ?? ''}` : 'cache';
  const setup = gpu ? `${APT} build-essential && pip install -q uv` : APT;
  return {
    command: ['bash', '-lc', `${setup} && ${download} && python /tmp/j.py ${stage}`],
    arguments: [],
    environment: gpu
      ? {
          REPO_REF: input.ref,
          ONNXRUNTIME_GPU: '1',
          INSIGHTFACE_PROVIDERS: 'CUDAExecutionProvider',
        }
      : { REPO_REF: input.ref },
    flavor: gpu ? input.videoFlavor : input.cacheFlavor,
    // A cache rebuild reads every reference photo; a reel run also encodes. Neither finishes in
    // the Hub's default window.
    timeoutSeconds: gpu ? 10800 : 2700,
    labels: { name: gpu ? `mv-video-${input.videoId ?? ''}` : 'mv-cache' },
    volumes: [{ type: 'bucket', source: input.bucket, mountPath: '/mnt/data' }],
    dockerImage: gpu ? HF_JOBS_DEFAULTS.gpuImage : HF_JOBS_DEFAULTS.image,
  };
}

export interface StageMapping {
  status: JobStatus;
  progress: number;
  detail?: string;
}

/**
 * Hub stage → the five states the console reads. `SCHEDULING` is still `queued` because no
 * pipeline work has started; `UPDATING` is running work; unknown stages fail closed.
 */
export function mapStage(stage: string, message?: string | null): StageMapping {
  switch (stage) {
    case 'SCHEDULING':
      return { status: 'queued', progress: 0 };
    case 'RUNNING':
    case 'UPDATING':
      return { status: 'running', progress: 10 };
    case 'COMPLETED':
      return { status: 'completed', progress: 100 };
    case 'CANCELED':
    case 'DELETED':
      return { status: 'cancelled', progress: 100 };
    case 'ERROR':
      return { status: 'failed', progress: 100, detail: message ?? 'Upstream job failed' };
    default:
      return {
        status: 'failed',
        progress: 100,
        detail: `Unrecognised HF job stage: ${stage}`,
      };
  }
}

type HubResult<T> = { ok: true; value: T } | { ok: false; detail: string };

function baseUrl(env: HfJobsEnv): string {
  return 'https://huggingface.co/api/jobs/' + (env.HF_JOBS_NAMESPACE ?? HF_JOBS_DEFAULTS.namespace);
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === 'object' && body !== null) {
      const record = body as Record<string, unknown>;
      if (typeof record.error === 'string') return record.error;
      if (Array.isArray(record.errors)) {
        const first = record.errors[0] as Record<string, unknown> | undefined;
        if (first && typeof first.message === 'string') return first.message;
      }
      if (typeof record.detail === 'string') return record.detail;
    }
  } catch {
    // Non-JSON error body: fall through to the status line.
  }
  return `HF Jobs responded ${response.status}`;
}

export async function submitHfJob(
  env: HfJobsEnv,
  spec: JobSpec,
): Promise<HubResult<{ id: string; stage: string }>> {
  if (!env.HF_TOKEN) return { ok: false, detail: 'HF_TOKEN is not configured' };
  let response: Response;
  try {
    response = await fetch(baseUrl(env), {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.HF_TOKEN}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify(spec),
    });
  } catch (error) {
    return { ok: false, detail: `HF Jobs unreachable: ${(error as Error).message}` };
  }
  if (!response.ok) return { ok: false, detail: await readDetail(response) };
  const body = (await response.json()) as { id?: unknown; status?: { stage?: unknown } };
  if (typeof body.id !== 'string' || body.id === '') {
    return { ok: false, detail: 'HF Jobs returned no job id' };
  }
  const stage = typeof body.status?.stage === 'string' ? body.status.stage : 'SCHEDULING';
  return { ok: true, value: { id: body.id, stage } };
}

export async function fetchHfStage(
  env: HfJobsEnv,
  hubJobId: string,
): Promise<HubResult<{ stage: string; message: string | null }>> {
  if (!env.HF_TOKEN) return { ok: false, detail: 'HF_TOKEN is not configured' };
  let response: Response;
  try {
    response = await fetch(`${baseUrl(env)}/${encodeURIComponent(hubJobId)}`, {
      headers: { authorization: `Bearer ${env.HF_TOKEN}` },
    });
  } catch (error) {
    return { ok: false, detail: `HF Jobs unreachable: ${(error as Error).message}` };
  }
  if (!response.ok) return { ok: false, detail: await readDetail(response) };
  const body = (await response.json()) as { status?: { stage?: unknown; message?: unknown } };
  const stage = typeof body.status?.stage === 'string' ? body.status.stage : 'UNKNOWN';
  const message = typeof body.status?.message === 'string' ? body.status.message : null;
  return { ok: true, value: { stage, message } };
}

export async function cancelHfJob(env: HfJobsEnv, hubJobId: string): Promise<HubResult<null>> {
  if (!env.HF_TOKEN) return { ok: false, detail: 'HF_TOKEN is not configured' };
  let response: Response;
  try {
    response = await fetch(`${baseUrl(env)}/${encodeURIComponent(hubJobId)}/cancel`, {
      method: 'POST',
      headers: { authorization: `Bearer ${env.HF_TOKEN}` },
    });
  } catch (error) {
    return { ok: false, detail: `HF Jobs unreachable: ${(error as Error).message}` };
  }
  if (!response.ok) return { ok: false, detail: await readDetail(response) };
  return { ok: true, value: null };
}
