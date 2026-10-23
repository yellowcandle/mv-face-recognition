#!/usr/bin/env node
// Mobbin MCP OAuth (Supabase authorization server) — one-time login, token refresh, and
// end-to-end verification for the OMP `mobbin` MCP server.
//
//   node scripts/mobbin/oauth.mjs           # browser sign-in → cache tokens → verify MCP
//   node scripts/mobbin/oauth.mjs --verify  # re-run tools/list + sample search with cached token
//   node scripts/mobbin/oauth.mjs --token   # print a fresh access token (refreshes if expired)
//
// Credentials are cached in ~/.config/mobbin/oauth.json (0600). Nothing secret touches the repo.
// The MCP endpoint takes the Supabase access token as a Bearer credential; see
// https://mobbin.com/mcp.md and https://docs.mobbin.com/mcp/build-an-integration

import { createServer } from 'node:http';
import { createHash, randomBytes } from 'node:crypto';
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { spawn } from 'node:child_process';

const MCP_URL = 'https://api.mobbin.com/mcp';
const AUTH_SERVER = 'https://ujasntkfphywizsdaapi.supabase.co/auth/v1';
const SCOPE = 'openid offline_access';
const CALLBACK_PORT = Number(process.env.MOBBIN_CALLBACK_PORT ?? 3939);
const REDIRECT_URI = `http://127.0.0.1:${CALLBACK_PORT}/callback`;
const STORE = join(
  process.env.XDG_CONFIG_HOME || join(homedir(), '.config'),
  'mobbin',
  'oauth.json',
);
const PROTOCOL_VERSION = '2025-06-18';
const EXPIRY_SKEW_MS = 120_000;

const b64url = (buf) => buf.toString('base64url');
const now = () => Date.now();

function readStore() {
  if (!existsSync(STORE)) return null;
  try {
    return JSON.parse(readFileSync(STORE, 'utf8'));
  } catch {
    return null;
  }
}

function writeStore(store) {
  mkdirSync(dirname(STORE), { recursive: true });
  writeFileSync(STORE, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });
  chmodSync(STORE, 0o600);
}

async function readJson(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`);
  }
}

async function registerClient(existing) {
  const body = {
    client_name: 'omp-mobbin',
    redirect_uris: [REDIRECT_URI],
    grant_types: ['authorization_code', 'refresh_token'],
    response_types: ['code'],
    token_endpoint_auth_method: 'none',
    scope: SCOPE,
  };
  const res = await fetch(`${AUTH_SERVER}/oauth/clients/register`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`client registration failed (${res.status}): ${detail.slice(0, 300)}`);
  }
  const client = await readJson(res);
  if (!client.client_id) throw new Error('client registration returned no client_id');
  return {
    ...existing,
    client_id: client.client_id,
    client_secret: client.client_secret,
    redirect_uri: REDIRECT_URI,
  };
}

function tokenRequest(store, params) {
  const form = new URLSearchParams({
    ...params,
    client_id: store.client_id,
    ...(store.client_secret ? { client_secret: store.client_secret } : {}),
  });
  return fetch(`${AUTH_SERVER}/oauth/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
}

function mergeTokens(store, tokens) {
  return {
    ...store,
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token ?? store.refresh_token,
    token_type: tokens.token_type,
    scope: tokens.scope ?? store.scope,
    expires_at: now() + Number(tokens.expires_in ?? 3600) * 1000,
  };
}

async function freshToken(store) {
  if (!store?.access_token) throw new Error('not signed in: run `node scripts/mobbin/oauth.mjs`');
  if (store.expires_at && store.expires_at - EXPIRY_SKEW_MS > now()) return store.access_token;
  if (!store.refresh_token) throw new Error('access token expired and no refresh token; sign in again');

  let res = await tokenRequest(store, {
    grant_type: 'refresh_token',
    refresh_token: store.refresh_token,
  });
  if (res.status === 400 || res.status === 401) {
    // Client may have been pruned server-side; re-register once and retry the refresh.
    const retryStore = await registerClient(store);
    res = await tokenRequest(retryStore, {
      grant_type: 'refresh_token',
      refresh_token: store.refresh_token,
    });
    if (!res.ok) throw new Error(`refresh failed (${res.status}): ${(await res.text()).slice(0, 300)}`);
    store = { ...retryStore, ...mergeTokens(retryStore, await readJson(res)) };
    writeStore(store);
    return store.access_token;
  }
  if (!res.ok) throw new Error(`refresh failed (${res.status}): ${(await res.text()).slice(0, 300)}`);
  const updated = mergeTokens(store, await readJson(res));
  writeStore(updated);
  return updated.access_token;
}

async function login() {
  let store = readStore();
  store = await registerClient(store);

  const verifier = b64url(randomBytes(32));
  const challenge = b64url(createHash('sha256').update(verifier).digest());
  const state = b64url(randomBytes(16));

  const authorizeUrl = new URL(`${AUTH_SERVER}/oauth/authorize`);
  authorizeUrl.search = new URLSearchParams({
    response_type: 'code',
    client_id: store.client_id,
    redirect_uri: REDIRECT_URI,
    scope: SCOPE,
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    resource: MCP_URL,
  }).toString();

  console.log(`\nAuthorize omp to read Mobbin design references (Pro/Team/Enterprise plan required).`);
  console.log(`Redirect target: ${REDIRECT_URI}`);
  console.log(`\nOpening browser. If it does not open, visit:\n\n${authorizeUrl.toString()}\n`);
  openBrowser(authorizeUrl.toString());

  const code = await waitForCode(state);
  const res = await tokenRequest(store, {
    grant_type: 'authorization_code',
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: verifier,
  });
  if (!res.ok) throw new Error(`token exchange failed (${res.status}): ${(await res.text()).slice(0, 300)}`);
  store = mergeTokens(store, await readJson(res));
  writeStore(store);
  console.log(`Signed in. Tokens cached at ${STORE}`);
  return store;
}

function openBrowser(url) {
  const [cmd, args] =
    process.platform === 'darwin'
      ? ['open', [url]]
      : process.platform === 'win32'
        ? ['cmd', ['/c', 'start', '', url]]
        : ['xdg-open', [url]];
  try {
    spawn(cmd, args, { stdio: 'ignore', detached: true }).unref();
  } catch {
    /* URL is printed anyway */
  }
}

function waitForCode(expectedState) {
  return new Promise((resolve, reject) => {
    const server = createServer((req, res) => {
      const url = new URL(req.url, `http://127.0.0.1:${CALLBACK_PORT}`);
      if (url.pathname !== '/callback') {
        res.writeHead(404).end('not found');
        return;
      }
      const error = url.searchParams.get('error');
      const code = url.searchParams.get('code');
      const state = url.searchParams.get('state');
      const finish = (status, message) => {
        res.writeHead(status, { 'content-type': 'text/plain' }).end(message);
        server.close();
      };
      if (error) {
        finish(400, `authorization denied: ${error}`);
        reject(new Error(`authorization denied: ${error} ${url.searchParams.get('error_description') ?? ''}`.trim()));
        return;
      }
      if (state !== expectedState) {
        finish(400, 'state mismatch');
        reject(new Error('state mismatch on OAuth callback'));
        return;
      }
      if (!code) {
        finish(400, 'missing code');
        reject(new Error('OAuth callback carried no code'));
        return;
      }
      finish(200, 'Mobbin authorized. You can close this tab.');
      resolve(code);
    });
    server.on('error', reject);
    server.listen(CALLBACK_PORT, '127.0.0.1');
    console.log(`Waiting for the browser callback on port ${CALLBACK_PORT}…`);
  });
}

// --- minimal Streamable HTTP MCP client -------------------------------------

class McpClient {
  constructor(token) {
    this.token = token;
    this.sessionId = null;
    this.id = 0;
  }

  async post(payload) {
    const headers = {
      'content-type': 'application/json',
      accept: 'application/json, text/event-stream',
      authorization: `Bearer ${this.token}`,
      'mcp-protocol-version': PROTOCOL_VERSION,
    };
    if (this.sessionId) headers['mcp-session-id'] = this.sessionId;
    const res = await fetch(MCP_URL, { method: 'POST', headers, body: JSON.stringify(payload) });
    const sid = res.headers.get('mcp-session-id');
    if (sid) this.sessionId = sid;
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`MCP ${payload.method} → ${res.status} ${res.statusText}: ${body.slice(0, 400)}`);
    }
    const text = await res.text();
    if (!text.trim()) return null;
    const ctype = res.headers.get('content-type') ?? '';
    if (ctype.includes('text/event-stream')) {
      const messages = text
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .filter(Boolean)
        .map((data) => JSON.parse(data));
      const match = messages.find((m) => m.id === payload.id);
      return match ?? messages.at(-1) ?? null;
    }
    return JSON.parse(text);
  }

  async initialize() {
    const res = await this.post({
      jsonrpc: '2.0',
      id: ++this.id,
      method: 'initialize',
      params: {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: 'mobbin-oauth', version: '1.0.0' },
      },
    });
    if (res?.error) throw new Error(`initialize failed: ${JSON.stringify(res.error)}`);
    await this.post({ jsonrpc: '2.0', method: 'notifications/initialized' });
    return res?.result;
  }

  async listTools() {
    const res = await this.post({ jsonrpc: '2.0', id: ++this.id, method: 'tools/list', params: {} });
    if (res?.error) throw new Error(`tools/list failed: ${JSON.stringify(res.error)}`);
    return res?.result?.tools ?? [];
  }

  async callTool(name, args) {
    const res = await this.post({
      jsonrpc: '2.0',
      id: ++this.id,
      method: 'tools/call',
      params: { name, arguments: args },
    });
    if (res?.error) throw new Error(`${name} failed: ${JSON.stringify(res.error)}`);
    return res?.result;
  }
}

// Pick a plausible argument for a search tool from its declared input schema.
function sampleArgs(schema) {
  const props = schema?.properties ?? {};
  const required = schema?.required ?? Object.keys(props);
  const stringKey = required.find((key) => props[key]?.type === 'string') ?? Object.keys(props).find((k) => props[k]?.type === 'string');
  if (!stringKey) return {};
  const args = { [stringKey]: 'mobile login screen' };
  for (const key of required) {
    if (key !== stringKey && props[key]?.type === 'number') args[key] = 5;
  }
  return args;
}

async function verify(token) {
  const client = new McpClient(token);
  const info = await client.initialize();
  console.log(`Connected: ${info?.serverInfo?.name ?? 'unknown'} ${info?.serverInfo?.version ?? ''}`.trim());
  const tools = await client.listTools();
  console.log(`Tools (${tools.length}): ${tools.map((t) => t.name).join(', ')}`);

  const search = tools.find((t) => t.name === 'search_screens') ?? tools.find((t) => t.name.startsWith('search_'));
  if (!search) throw new Error('no search tool exposed by Mobbin MCP');
  const args = sampleArgs(search.inputSchema);
  console.log(`Calling ${search.name} ${JSON.stringify(args)}…`);
  const result = await client.callTool(search.name, args);
  const contents = result?.content ?? [];
  const text = contents.filter((c) => c.type === 'text').map((c) => c.text).join('\n');
  const images = contents.filter((c) => c.type === 'image').length;
  if (result?.isError) throw new Error(`tool returned error: ${text.slice(0, 400)}`);
  console.log(`Result: ${text.length} chars of text, ${images} image(s), ${contents.length} content block(s)`);
  console.log(text.slice(0, 800));
  return { tools: tools.map((t) => t.name), images, textLength: text.length };
}

async function main() {
  const mode = process.argv[2];
  if (mode === '--token') {
    process.stdout.write(await freshToken(readStore()));
    return;
  }
  if (mode === '--verify') {
    await verify(await freshToken(readStore()));
    return;
  }
  const store = await login();
  await verify(store.access_token);
}

main().catch((error) => {
  console.error(`\n${error.message}`);
  process.exit(1);
});
