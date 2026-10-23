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
  // Detection and reference-embedding work use the GPU; work that only reads and rewrites JSON
  // does not. A GPU flavor costs ~20x more per hour, so the split is explicit, not heuristic.
  cpuFlavor: 'cpu-upgrade',
  gpuFlavor: 'a10g-small',
  // The CUDA image ships the driver stack but no uv; the uv image cannot see a GPU.
  image: 'ghcr.io/astral-sh/uv:python3.12-bookworm',
  gpuImage: 'pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime',
} as const;

/** Job kinds that need a GPU. `Record<JobMode, …>` so a new mode cannot skip the decision. */
export const GPU_MODES: Record<JobMode, boolean> = {
  initial: true,
  'embedding-update': true,
  'coverage-refresh': false,
};

export function flavorFor(mode: JobMode, env: HfJobsEnv): string {
  if (GPU_MODES[mode]) return env.HF_JOBS_GPU_FLAVOR ?? HF_JOBS_DEFAULTS.gpuFlavor;
  return env.HF_JOBS_CPU_FLAVOR ?? HF_JOBS_DEFAULTS.cpuFlavor;
}

export interface HfJobsEnv {
  HF_TOKEN?: string;
  HF_JOBS_NAMESPACE?: string;
  HF_JOBS_BUCKET?: string;
  HF_JOBS_REF?: string;
  /** Flavor for jobs that do not need a GPU (`cpu-upgrade` by default). */
  HF_JOBS_CPU_FLAVOR?: string;
  /** Flavor for `GPU_MODES` jobs (`a10g-small` by default). */
  HF_JOBS_GPU_FLAVOR?: string;
}

export interface JobSpecInput {
  mode: JobMode;
  /** Numeric id from the source filename, e.g. `4`. Required for `initial` runs. */
  videoId?: string | null;
  ref: string;
  bucket: string;
  /** Resolved by `flavorFor`: the flavor name also selects the image and provider env. */
  flavor: string;
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
 * The flavor decides the image, not the mode: a GPU flavor needs the CUDA stack and the GPU
 * provider, a CPU flavor must not pay for either. Names are the Hub's own (`hf jobs run --flavor`).
 */
const GPU_FLAVORS: Record<string, true> = {
  't4-small': true,
  't4-medium': true,
  l4x1: true,
  l4x4: true,
  l40sx1: true,
  l40sx4: true,
  l40sx8: true,
  'a10g-small': true,
  'a10g-large': true,
  'a10g-largex2': true,
  'a10g-largex4': true,
  'a100-large': true,
  a100x4: true,
  a100x8: true,
  'rtx-pro-6000': true,
  'rtx-pro-6000x2': true,
  'rtx-pro-6000x4': true,
  'rtx-pro-6000x8': true,
  h200: true,
  h200x2: true,
  h200x4: true,
  h200x8: true,
};

export function isGpuFlavor(flavor: string): boolean {
  return GPU_FLAVORS[flavor] === true;
}

/**
 * The payload `run_job` would POST. `command` downloads the pipeline script from GitHub at
 * runtime, which is what lets a token with `job.write` but no bucket write submit a run.
 */
export function buildJobSpec(input: JobSpecInput): JobSpec {
  const script = `https://raw.githubusercontent.com/${REPO_SLUG}/${input.ref}/scripts/hf/jobs/hf_pipeline.py`;
  const download = `python -c "import urllib.request; urllib.request.urlretrieve('${script}','/tmp/j.py')"`;
  const video = input.mode === 'initial';
  const flavor = input.flavor;
  const gpu = isGpuFlavor(flavor);
  const stage = video ? `video --video-id ${input.videoId ?? ''}` : 'cache';
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
    flavor,
    // A cache rebuild reads every reference photo; a reel run also encodes. Neither finishes in
    // the Hub's default window.
    timeoutSeconds: video ? 10800 : 2700,
    labels: { name: video ? `mv-video-${input.videoId ?? ''}` : 'mv-cache' },
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
