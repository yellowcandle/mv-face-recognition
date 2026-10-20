/**
 * Labelling Worker — the one deployed thing that WRITES, and only labels.
 *
 * It is a separate Worker from worker/ on purpose: ADR 0003 keeps the public viewer read-only.
 * Everything here sits behind Cloudflare Access and FAILS CLOSED: no Access config means 503 for
 * every request, and any token that does not verify (signature, iss, aud, exp, nbf) means 401.
 *
 * Routes:
 *   GET    /api/labels/:video_id                                  -> labels/v1 listing
 *   PUT    /api/labels/:video_id/:frame_number/:detection_index   -> set a verdict
 *   DELETE /api/labels/:video_id/:frame_number/:detection_index   -> clear a verdict
 *   GET    /crops/:video_id/:file                                 -> crop JPEG from R2
 *
 * Written as plain erasable TypeScript (no enums, no imports) so `node --test` can load it
 * directly with Node's built-in type stripping.
 */

export interface Env {
  LABELS: KVNamespace;
  LABEL_CROPS: R2Bucket;
  CF_ACCESS_TEAM_DOMAIN?: string;
  CF_ACCESS_AUD?: string;
  LOG_LEVEL?: string;
}

// Same vocabulary as local_api.py VERDICTS and apps/admin/src/pages/Labelling.tsx.
const VERDICTS = ['contestant', 'not_a_contestant', 'unsure', 'box_wrong'] as const;
type Verdict = (typeof VERDICTS)[number];

const LABELS_SCHEMA = 'labels/v1';
// Letters, digits, CJK ideographs, space, 《》, -, _, . — nothing that can mean a path or a KV separator.
const VIDEO_ID_RE = /^[A-Za-z0-9\p{Script=Han} 《》_.-]{1,200}$/u;
const CROP_FILE_RE = /^\d+_\d+\.jpg$/;
const INDEX_RE = /^\d{1,9}$/;
const CONTESTANT_ID_RE = /^[1-9]\d{0,2}$/; // 編號 in metadata/contestant_info.csv: 1..96, unpadded

const JWKS_TTL_MS = 5 * 60 * 1000;
const CLOCK_SKEW_S = 60;

// ─── logging: one JSON line per event, never a token ───

const LEVELS: Record<string, number> = { debug: 0, info: 1, warn: 2, error: 3, none: 4 };

function log(env: Env, level: 'debug' | 'info' | 'warn' | 'error', message: string, meta: Record<string, unknown> = {}): void {
  if (LEVELS[level] < (LEVELS[env.LOG_LEVEL ?? 'info'] ?? 1)) return;
  console.log(JSON.stringify({ level, message, timestamp: new Date().toISOString(), ...meta }));
}

class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

// ─── Cloudflare Access JWT verification (RS256 via Web Crypto) ───

interface Jwk extends JsonWebKey {
  kid?: string;
}

let jwksCache: { url: string; keys: Jwk[]; fetchedAt: number } | null = null;

/** Test hook: forget cached keys so each test sees its own JWKS. */
export function resetJwksCache(): void {
  jwksCache = null;
}

async function getJwks(url: string): Promise<Jwk[]> {
  if (jwksCache && jwksCache.url === url && Date.now() - jwksCache.fetchedAt < JWKS_TTL_MS) {
    return jwksCache.keys;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`JWKS fetch failed: ${res.status}`);
  const body = (await res.json()) as { keys?: Jwk[] };
  if (!Array.isArray(body.keys)) throw new Error('JWKS has no keys');
  jwksCache = { url, keys: body.keys, fetchedAt: Date.now() };
  return body.keys;
}

function b64urlToBytes(s: string): Uint8Array<ArrayBuffer> {
  if (!/^[A-Za-z0-9_-]*$/.test(s)) throw new Error('bad base64url');
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function decodePart(s: string): Record<string, unknown> {
  const v: unknown = JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));
  if (typeof v !== 'object' || v === null || Array.isArray(v)) throw new Error('JWT part is not an object');
  return v as Record<string, unknown>;
}

/** Returns the verified email, or throws with a reason (the reason is logged, never returned). */
async function verifyAccessJwt(token: string, teamDomain: string, aud: string): Promise<string> {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('malformed token');
  const [h, p, s] = parts;
  const header = decodePart(h);
  const payload = decodePart(p);

  if (header.alg !== 'RS256') throw new Error('unexpected alg');
  if (typeof header.kid !== 'string') throw new Error('missing kid');

  const keys = await getJwks(`https://${teamDomain}/cdn-cgi/access/certs`);
  const jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) throw new Error('unknown kid');

  const key = await crypto.subtle.importKey(
    'jwk',
    { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: 'RS256', ext: true },
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  );
  const ok = await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5',
    key,
    b64urlToBytes(s),
    new TextEncoder().encode(`${h}.${p}`),
  );
  if (!ok) throw new Error('bad signature');

  const now = Math.floor(Date.now() / 1000);
  if (payload.iss !== `https://${teamDomain}`) throw new Error('wrong iss');
  const auds = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!auds.includes(aud)) throw new Error('wrong aud');
  if (typeof payload.exp !== 'number' || payload.exp + CLOCK_SKEW_S < now) throw new Error('expired');
  if (payload.nbf !== undefined && (typeof payload.nbf !== 'number' || payload.nbf - CLOCK_SKEW_S > now)) {
    throw new Error('not yet valid');
  }
  if (typeof payload.email !== 'string' || payload.email === '') throw new Error('no email claim');
  return payload.email;
}

// ─── path parsing ───

function decodeSegment(seg: string): string {
  try {
    return decodeURIComponent(seg);
  } catch {
    throw new HttpError(400, 'Bad path encoding');
  }
}

function parseVideoId(seg: string): string {
  const id = decodeSegment(seg);
  if (!VIDEO_ID_RE.test(id) || id.includes('..') || id.startsWith('.')) throw new HttpError(400, 'Invalid video_id');
  return id;
}

function parseIndex(seg: string, name: string): number {
  const raw = decodeSegment(seg);
  if (!INDEX_RE.test(raw)) throw new HttpError(400, `${name} must be a non-negative integer`);
  return Number(raw);
}

// ─── handlers ───

interface StoredLabel {
  verdict: Verdict;
  contestant_id?: string;
  labeller: string;
  labelled_at: string;
  source_processing_date?: string;
}

async function listLabels(env: Env, videoId: string): Promise<Response> {
  const prefix = `label:${videoId}:`;
  const names: string[] = [];
  let cursor: string | undefined;
  do {
    const page = await env.LABELS.list({ prefix, cursor });
    for (const k of page.keys) names.push(k.name);
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);

  // ponytail: one KV get per label; fine for hundreds of detections. Store the value as list
  // metadata too if a video ever has thousands.
  const labels = [];
  for (const name of names) {
    const value = await env.LABELS.get<StoredLabel>(name, 'json');
    if (!value) continue; // deleted between list and get
    const [frame, idx] = name.slice(prefix.length).split(':');
    labels.push({ frame_number: Number(frame), detection_index: Number(idx), ...value });
  }
  labels.sort((a, b) => a.frame_number - b.frame_number || a.detection_index - b.detection_index);
  return json({ schema: LABELS_SCHEMA, video_id: videoId, labels });
}

async function putLabel(request: Request, env: Env, key: string, labeller: string): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw new HttpError(400, 'Body must be JSON');
  }
  if (typeof body !== 'object' || body === null) throw new HttpError(400, 'Body must be a JSON object');
  const { verdict, contestant_id } = body as { verdict?: unknown; contestant_id?: unknown };

  if (typeof verdict !== 'string' || !(VERDICTS as readonly string[]).includes(verdict)) {
    throw new HttpError(400, `verdict must be one of ${VERDICTS.join(', ')}`);
  }
  // Same rule as local_api.py _validate_labels: a 'contestant' verdict names who; no other does.
  if (verdict === 'contestant') {
    if (typeof contestant_id !== 'string' || !CONTESTANT_ID_RE.test(contestant_id)) {
      throw new HttpError(400, "verdict 'contestant' needs a contestant_id like \"42\"");
    }
  } else if (contestant_id !== undefined && contestant_id !== null) {
    throw new HttpError(400, `verdict '${verdict}' must not carry a contestant_id`);
  }

  const value: StoredLabel = {
    verdict: verdict as Verdict,
    ...(verdict === 'contestant' ? { contestant_id: contestant_id as string } : {}),
    labeller,
    labelled_at: new Date().toISOString(),
  };
  await env.LABELS.put(key, JSON.stringify(value));
  return json(value);
}

async function getCrop(env: Env, videoId: string, file: string): Promise<Response> {
  const object = await env.LABEL_CROPS.get(`crops/${videoId}/${file}`);
  if (!object) throw new HttpError(404, 'Crop not found');
  return new Response(object.body, {
    headers: {
      'Content-Type': 'image/jpeg',
      'Cache-Control': 'private, max-age=3600',
      ETag: object.httpEtag,
    },
  });
}

async function route(request: Request, env: Env, labeller: string): Promise<Response> {
  const segs = new URL(request.url).pathname.split('/').slice(1);
  const method = request.method;

  if (segs[0] === 'api' && segs[1] === 'labels') {
    if (segs.length === 3 && method === 'GET') {
      return listLabels(env, parseVideoId(segs[2]));
    }
    if (segs.length === 5 && (method === 'PUT' || method === 'DELETE')) {
      const videoId = parseVideoId(segs[2]);
      const frame = parseIndex(segs[3], 'frame_number');
      const idx = parseIndex(segs[4], 'detection_index');
      const key = `label:${videoId}:${frame}:${idx}`;
      if (method === 'PUT') return putLabel(request, env, key, labeller);
      await env.LABELS.delete(key);
      return new Response(null, { status: 204 });
    }
  }

  if (segs[0] === 'crops' && segs.length === 3 && method === 'GET') {
    const videoId = parseVideoId(segs[1]);
    const file = decodeSegment(segs[2]);
    if (!CROP_FILE_RE.test(file)) throw new HttpError(400, 'Invalid crop file name');
    return getCrop(env, videoId, file);
  }

  throw new HttpError(404, 'Not found');
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const path = new URL(request.url).pathname;

    if (!env.CF_ACCESS_AUD || !env.CF_ACCESS_TEAM_DOMAIN) {
      log(env, 'error', 'Access not configured; refusing all requests', { path });
      return json({ error: 'Service not configured' }, 503);
    }

    const token = request.headers.get('Cf-Access-Jwt-Assertion');
    let labeller: string;
    try {
      if (!token) throw new Error('missing Cf-Access-Jwt-Assertion');
      labeller = await verifyAccessJwt(token, env.CF_ACCESS_TEAM_DOMAIN, env.CF_ACCESS_AUD);
    } catch (err) {
      log(env, 'warn', 'Auth failed', { path, method: request.method, reason: (err as Error).message });
      return json({ error: 'Unauthorized' }, 401);
    }

    try {
      const res = await route(request, env, labeller);
      log(env, 'info', `${request.method} ${path}`, { status: res.status, labeller });
      return res;
    } catch (err) {
      if (err instanceof HttpError) return json({ error: err.message }, err.status);
      log(env, 'error', 'Unhandled error', { path, message: (err as Error).message });
      return json({ error: 'Internal error' }, 500);
    }
  },
};
