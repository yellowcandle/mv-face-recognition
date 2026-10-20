---
id: 016
title: Decide the fate of the remaining ungated admin routes
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: closed
assignee: claude
---

## Question

`verifyCloudflareAccess` is a no-op in production. After ticket 015 removes the flagging
routes, what happens to the other eight call sites?

Surfaced by *Remove flagging from the public viewer*. **Ruling this out of scope is a live
option** — but it should be ruled, not assumed.

## Context

- `worker/src/index.ts:119` returns `{ verified: true }` whenever `CF_ACCESS_AUD` is unset, and
  it is unset: `wrangler.toml:23-26` carries it only as a commented-out setup recipe. Every
  route that "checks Access" is therefore open to the public internet today.
- Remaining sites after 015: `/admin/youtube/submit`, `/admin/youtube/queue`,
  `/admin/youtube/status`, `/admin/embeddings/compare`, `/admin/embeddings/trigger-sync`,
  `/embeddings/sync`, and the handlers at `:1178`, `:1262`, `:1309`.
- **The map already ruled the Ingestion page out of scope** ("Restoring
  `scripts/modal_youtube_processor.py` … reviving the disabled Ingestion page. Separate
  effort"). But the *page* being disabled did not remove the *routes*: they are live and
  writable. The precedent from 015 is that a deployed route with no deployed caller gets
  deleted, not gated.
- The user called the equivalent flagging hole **blocking for publish**, which is why this is
  a ticket rather than fog.
- Options to put: delete the routes as 015 did; provision Cloudflare Access for real (a Task —
  only the user can create the Access app and `wrangler secret put` both values); or accept
  them and record why.
- Note `verifyCloudflareAccess` never verifies the JWT signature (`:157-158`, "we trust
  Cloudflare's edge validation"). If the answer is "provision Access", that comment needs
  checking against how the worker is actually fronted.

## Resolution

**Closed 2026-09-20, with the user: delete them all.** The 015 precedent applied to the whole
surface, and the deployed Worker is now read-only without exception — ADR 0003 stops having
asterisks, and `verifyCloudflareAccess` itself is gone because nothing calls it any more.

### The inventory the ticket did not have

The ticket named eight call sites. Walking every handler for side effects found **twelve routes
with no deployed caller, four of them ungated writers**:

| route | ungated effect |
|---|---|
| `/admin/upload-video` (POST) | **uploads the posted file to HuggingFace with the Worker's `HF_TOKEN`** |
| `/settings` (PUT) | writes `app_settings` to KV |
| `/embeddings/sync` (POST) | writes `embedding_sync_*` |
| `/admin/trigger-modal` (POST) | writes `modal_job_*` |

plus eight routes whose gate was decorative: the five `/admin/youtube/*`, `/admin/embeddings/compare`,
`/admin/embeddings/trigger-sync`, and `/settings`' GET half.

The upload route is the one that mattered: an anonymous stranger could push arbitrary files to
HuggingFace with the project's token. The other three only litter KV — and every key they write
(`app_settings`, `embedding_sync_*`, `modal_job_*`) is read by nothing (ticket 007's inventory).

Nothing in the repo calls any of the twelve. The only remaining caller anywhere is
`scripts/process-youtube-queue.js`, part of the Modal ingestion revival the map already ruled out
of scope — it will 404 if anyone runs it, which is correct and recorded here.

### Deleted

Twelve route blocks (with their trailing-slash twins), twelve handlers, `verifyCloudflareAccess`,
`AccessVerificationResult`, and the now-unread fields of the `Env` interface (`MODAL_JOBS`,
`HF_TOKEN`, `MODAL_TOKEN`, `CF_ACCESS_AUD`, `CF_ACCESS_TEAM`). The switch went from 39 routes to
8, all of them reads: `/system/status`, `/contestants`, `/videos`, `/videos/processed/list`,
`/faces/detect`, `/recognition/results`, and the two metadata routes. `wrangler.toml` still binds
`MODAL_JOBS` and the Modal secrets — an unused binding is harmless, and removing one is a deploy
change, not a source change.

**`HF_TOKEN` needs deleting by you: `wrangler secret delete HF_TOKEN`.** Flagged, not run — it is
a Cloudflare-side change and the map keeps one confirmation point, at the end.

### What the answer to "provision Access" would have been

Recorded for whoever wants admin routes back: Access **can** front a `workers.dev` hostname
(hostname-based self-hosted application; Zero Trust must be enabled on the account), but a
*Worker-level* policy **breaks WebSockets** and this Worker has a live one at
`/ws/realtime-processing`. And the hand-rolled verifier was the wrong tool regardless: today's
runtime exposes `ctx.access` with `getIdentity()`, verified by the platform, whereas this code
decoded the JWT payload and trusted it — its comment "we trust Cloudflare's edge validation" was
true of a deployment that never had Access in front of it.

### The check, strengthened

`worker/tests/worker-is-read-only.test.mjs` (renamed from the 015 guard, which is superseded and
deleted) drives **every route from the source, every method, with an empty body and a body full of
plausible field names**, and asserts no KV write, no R2 write and **no outbound fetch**. That
depth is the point: the first version sent only GET and POST with `{}` and therefore **missed the
upload route** (which validates its input before uploading) and **`/settings`** (which writes on
PUT). Proven by planting both shapes — a PUT-only KV writer and an external uploader — watching it
fail, and restoring.

Three tests: no route has an effect; every deleted route 404s (17 paths, flag routes included);
the read surface still answers.

### Verification

- Live `wrangler dev`: all **twelve** deleted routes 404; `/system/status`, `/contestants`,
  `/videos`, `/videos/processed/list`, `/recognition/results`, `/faces/detect` and `/` all 200.
- The viewer (fresh build, served by the worker) makes **three** API calls, all on the read
  surface, and renders — no flag affordances, no requests to anything deleted.
- `npx tsc --noEmit` clean in `worker`, `apps/shared`, `apps/viewer`, `apps/admin`;
  `wrangler deploy --dry-run` bundles at **364 KiB** (was 390). **No deploy was run.**
- `npm test` in `worker/`: 3/3.

