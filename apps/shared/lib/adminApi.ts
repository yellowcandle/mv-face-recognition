/**
 * Gated admin calls live under the Access-protected prefix, so Cloudflare Access — not the app —
 * decides whether the caller may proceed. When the session expires, Access answers with a
 * redirect to the login page. A plain `fetch` follows it cross-origin and fails as an opaque
 * network error, which the reviewer cannot act on.
 *
 * `redirect: 'manual'` turns that into an opaque redirect we can name.
 */
export class SessionExpiredError extends Error {
  constructor() {
    super('登入已過期，請重新載入頁面');
    this.name = 'SessionExpiredError';
  }
}

export async function adminFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(path, { ...init, redirect: 'manual' });
  if (response.type === 'opaqueredirect' || response.status === 0) {
    throw new SessionExpiredError();
  }
  return response;
}

/** An HTTP failure carrying the server's `detail`, so callers can show the reason. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail ? `HTTP ${status}：${detail}` : `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/** Throw on a non-2xx response, preserving a JSON `detail` when the server sends one. */
export async function assertOk(response: Response): Promise<Response> {
  if (response.ok) return response;
  let detail = '';
  try {
    const body = (await response.clone().json()) as { detail?: unknown };
    const raw = body?.detail;
    detail = typeof raw === 'string' ? raw : raw === undefined ? '' : JSON.stringify(raw);
  } catch {
    try {
      detail = (await response.clone().text()).slice(0, 200);
    } catch {
      /* body already consumed */
    }
  }
  throw new ApiError(response.status, detail);
}

export function isSessionExpired(error: unknown): error is SessionExpiredError {
  return error instanceof SessionExpiredError;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
