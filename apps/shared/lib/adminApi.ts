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
