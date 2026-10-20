# Migration plan — Void (Cloudflare Workers) with a remote admin

Status: **proposal**, nothing built. Supersedes the local-only admin assumption in
`CONTEXT.md` §Admin and ADR 0003 — both need an update before Phase 4 starts.

---

## 0. What actually changes

Two decisions drive this migration, and only the second is the risky one.

1. **Runtime**: the hand-rolled worker (`worker/src/index.ts`, ~1000 lines, embedded
   assets, custom router) becomes a Void project — file routes, typed fetch, provisioned
   resources, `void deploy`.
2. **Admin becomes remote**: the back office stops being a localhost-only app and is
   served from the same deployment, behind authentication. Every write that today goes to
   `local_api.py` on `127.0.0.1:8000` has to become an authenticated server route with a
   real datastore.

The viewer is unaffected in behaviour: same routes, same JSON shapes, same SPA.

### What is broken today and must be fixed by the migration, not after it

The worker reads KV keys that **no script in the repo writes**:

| Worker reads | `scripts/upload-metadata.js` writes |
| --- | --- |
| `metadata_dense_<id>` | `video_metadata_<id>` |
| `processed_videos_list` | `videos_list` |
| `contestants_structured` | `contestants` |
| `videos_list_optimized` | — |
| `video_metadata_collection` | — |

A deploy today serves hardcoded fallback videos and mock metadata. The migration's Phase 2
is therefore not "port the reader", it is "build the writer that never existed" — one
typed publish step that is the only thing allowed to write the read model.

---

## 1. Target architecture

```text
Void project (repo root or apps/api)
├── routes/api/
│   ├── videos/processed/list.ts        GET   read model: reels
│   ├── videos/metadata/dense/[id].ts   GET   dense per-frame metadata (+ ?from=&to=)
│   ├── videos/[id]/stream.ts           GET   R2 object, HTTP Range
│   ├── contestants/index.ts            GET   cast (96 rows)
│   ├── contestants/[id]/photo.ts       GET   reference photo (R2)
│   ├── recognition/results.ts          GET   appearances by contestant
│   ├── system/status.ts                GET   health for the admin lamp
│   ├── faces/flagged/index.ts          GET   flag queue        (auth)
│   ├── faces/flagged/[id].ts           PATCH accept / void     (auth)
│   ├── faces/flag/update.ts            POST  reassign          (auth)
│   ├── flags/index.ts                  POST  create flag       (auth)
│   ├── processing/jobs.ts              GET/POST trigger + poll (auth)
│   └── embeddings/*.ts                 GET/POST workbench      (auth)
├── pages/           (optional) or: keep apps/viewer as a Vite SPA, served as static + API
└── resources: kv (index), storage/R2 (videos, photos, metadata bodies), d1 (flags, cast)
```

`apps/viewer` keeps React Router and calls these routes through an `apiBase` — the only
app change is that `apiBase` stops being `''` plus a dev proxy and becomes an env value.

`apps/admin` keeps its pages, but every `fetch('/api/...')` gains the Access cookie/JWT
automatically (same origin) and the write routes enforce it.

---

## 2. Where the data lives

**Uploaded 2026-10-20** to `yellowcandle/mv-face-recognition` — 14,962 files, 1.92 GB.
Verified: one photo downloaded and re-hashed (sha256 match), one video's bucket size equals the
local file (344,074,255 bytes), and the manifests parse to 6 videos / 964 reference photos /
160 curated photos.

| Prefix | Files | What |
| --- | --- | --- |
| `videos/source/{id}/{sha256}.mp4` | 6 | Source reels, 1.36 GB |
| `photos/reference/{id}/{sha256}.{ext}` | 964 | Reference photos for 95 of 96 contestants, 305 MB |
| `photos/curated/{id}/{sha256}.{ext}` | 160 | Curated reference set, 81 MB — **recovered** (see below) |
| `photos/historical/…` | 293 | Historical per-contestant set materialised out of old refs, 113 MB |
| `manifest/videos.json`, `manifest/photos.json`, `manifest/photos-curated.json` | 3 | sha256 manifests, uploaded last |
| `unmatched_faces/`, `chroma_db/`, `*.json` | 13,536 | `./data/` synced unchanged to the bucket root |

### Recovering `source/photo/contestants/photos` (2026-10-20)

All 160 files in that folder were 131-byte LFS pointer stubs, and `git lfs pull` correctly did
nothing: the folder is **gitignored** (`.gitignore:18`), untracked, has no history, and
`git lfs ls-files --all` (6,122 entries across 134 branches) contains **none** of them. The
Hugging Face dataset repo held the same 131-byte stubs, uploaded as content.

They were recovered by asking GitHub's LFS batch API directly for the 160 `oid`/`size` pairs
from the pointer files — the server still held all 160 objects (81 MB) even though no ref
pointed at them. Each was downloaded and verified against its sha256 before replacing the stub.
The recovery is now archived at `photos/curated/` precisely because pointers with no ref are
one garbage collection away from gone.

Still outstanding: the 94 `.npy` in `.../contestants/embeddings/` were not uploaded (the plan
puts them in the dataset repo), and contestant 52's 4 screenshot PNGs are local only.

### Retention rule for LFS history (decided 2026-10-20)

**`source/photo` is kept.** It is input, not a derived artifact, so it stays in git history and
in the bucket. **Do not prune it**, and do not prune `source/videos` either.

The only later pruning candidates are the derived sets: `processed_videos/` (7.37 GB of annotated
reels) and `output_frames/` (5,146 extracted jpgs, 3.35 GB). Both regenerate from `source/` plus
the pipeline. Not during the Void migration — different risk, different day.

What "keeping" it actually means for `source/photo`, measured:

| | |
| --- | --- |
| LFS blobs under `source/photo` | **386** (112.8 MB) |
| Paths, not blobs | per-contestant dirs `contestants/{id}/` — a *third* set, distinct from `photos/` and `ig_photos/` |
| Refs that still carry them | **138 branches** (`dev-chromadb` alone has 302 files) |
| Checked out at HEAD | **13 files** |
| Blobs in the local cache | **95 of 386** — the other 291 exist only on the server |

So this set survives **only because those 138 branches exist**. Deleting the branches, or a
history rewrite that drops them, loses 291 blobs that nothing else holds — the bucket has
`photos/reference` (964, from `ig_photos`) and `photos/curated` (160, recovered), but not this
historical `contestants/{id}` set.

If you want it durable independent of branch history, materialise `dev-chromadb`'s 302 files
and stage them to `photos/historical/` in the bucket. That is a 10-minute job and does not
require touching any branch. Until then, treat those 138 branches as load-bearing.

**Done 2026-10-20.** `scripts/hf/materialize_source_photo.py` copied **292 files (112.6 MB)**
from the LFS object cache into `source/photo/historical/`, each verified against its sha256,
with a `MANIFEST.json` of `{path, oid, bytes}`. Zero failures. (292, not 302: the dev-chromadb
count includes non-LFS files such as the contestant CSV.)

- Local copy: `source/photo/historical/` — plain files, **gitignored** (`.gitignore:24`) so they
  can never be committed by accident.
- Archived: `photos/historical/` in the bucket (293 objects including the manifest).
- The 138 branches are no longer load-bearing for this set; they can be cleaned up freely.

### Cleanup executed (2026-10-20)

With the archive in place, the branches and derived artifacts were dropped to reclaim disk:

| Action | Before | After |
| --- | --- | --- |
| Local branches | 47 | **3** (`deploy-ui-rewrite`, `main`, `worktree-buzzing-swinging-summit`) |
| Remote-tracking refs | 85 | **0** |
| `git lfs prune` | 6,361 objects, 13.6 GB | **3,855 objects, 7.4 GB** — 2,506 objects / **10 GB** reclaimed |
| Worktree derived video | `processed_videos/` 708 MB + `local_output/processed_videos/` 1.3 GB | removed (regenerable; both archived in the bucket) |
| Free disk | 6.5 GiB (99 % used) | **18 GiB** |

**Second pass — the tooling refs.** 49 `refs/conductor-checkpoints/*` refs were deleted, but they
held **no unique LFS objects**: the first prune had already reclaimed their share, and a prune
immediately after deleting them removed nothing. The actual holder of the derived sets was a
single **tag**: `pre-merge-20250812-043000` carried **1,471 derived paths** while all three
branches carried zero. Deleting that tag and pruning again removed **3,533 objects (3.8 GB)**,
leaving 322 objects (3.8 GB) — the reference photos in `source/photo` plus small metadata.

| | Final |
| --- | --- |
| Free disk | **21 GiB** (95 % used), from 6.5 GiB at the start |
| Local LFS objects | **322** (3.8 GB) from 6,361 (13.6 GB) |
| Refs | 3 branches, no tags, no checkpoints |

**Committed:** `daf24608` removes `local_output/processed_videos/*.mp4` (the two rendition
pointers) from the tree. Note the root `processed_videos/` (8 paths, 3.89 GB) was **never
tracked at HEAD** — it only existed on the deleted tag, which is why pruning could drop it.
Nothing else was swept in: three unrelated pre-existing deletions
(`mvp-processor/src/supervision_annotator.py`, its test, a tracked `.DS_Store`) remain
uncommitted.

Safety net: `/tmp/refs-backup.txt` holds `objectname refname` for all 184 refs before deletion, so
any branch is recoverable from its SHA while the objects exist. Nothing was pushed — **the
branches still exist on GitHub**; only local and remote-tracking refs were removed. A later
`git fetch` will re-create the remote-tracking refs, and any LFS object a re-created branch needs
will be re-downloaded on demand.

`source/videos/` was **not** touched — inputs stay.

### Gallery source of truth

The cast sheet's thumbnails come **exclusively** from `source/photo/historical/contestants/{id}/`
— the curated per-contestant set (2 photos each, all 96 present). The sources are ordered and the
first one that has photos wins outright; they are not merged, so a scraped `ig_photos` face can
never displace a curated one. `ig_photos` and the recovered `photos/` set remain as fallbacks for
any contestant the historical set is missing. Rescored after the switch: 96 portraits, 3.2 MB,
45 by embedding, 46 by clustering, 5 with no signal (#7, #21, #51, #72, #93).

**Decided 2026-10-20: Hugging Face holds inputs and run history; R2 holds only the served
state; D1 holds the index.** The viewer never reads from HF, and nothing is authored in R2.

Two HF products, split by whether git history is the point:

- **Storage Buckets** (`yellowcandle/mv-face-recognition`, private, created 2026-10-20) —
  S3-like object storage on the Xet backend, per-TB pricing, built-in CDN, **non-versioned and
  mutable**. Bulk binaries go here, addressed by content hash.
- **Dataset repo** `yellowcandle/mv-face-recognition-data` — small files whose history matters, pinned by commit.

Bucket access is available four ways, which is why it wins for compute: the `hf` CLI
(`hf buckets`), the Python API, an **S3-compatible endpoint** (AWS CLI, boto3, s5cmd), and
`hf://` paths / volume mounts inside Jobs and Spaces. The project pins `huggingface-hub>=0.33.1`,
and the installed 0.33.1 has no bucket API, so the upload needs a newer client (PyPI latest is
2.2.0; minimum version not yet verified).

### Bucket key layout

```text
videos/source/{video_id}/{sha256}.mp4           # video_id = numeric prefix; hash is the version
photos/reference/{contestant_id}/{sha256}.{ext} # content-addressed, like videos
manifest/videos.json                            # {video_id: {key, sha256, bytes, original_name, added_at}}
manifest/photos.json                            # {contestant_id: [{key, sha256, bytes, original_name}]}
chroma_db/, unmatched_faces/, *.json            # ./data/ synced unchanged to the bucket root
```

Buckets are **mutable and non-versioned** — an overwrite is silent and unrecoverable. So:
keys are content-addressed (the `{sha256}` segment), nothing overwrites in place, and
the publish step verifies the hash it reads against the manifest before promoting a run. A
re-ingested reel gets a new key; the old one is deleted only after the new run is published.

`./data/` goes to the bucket root unchanged, by owner decision on 2026-10-20. That overrides
the dataset-repo placement for those `.npy` files in the table below.

| Data | Size (measured unless marked est.) | Store | Why |
| --- | --- | --- | --- |
| Source videos (as ingested) | 170–330 MB per reel, 1.3 GB total | **HF Storage Bucket** | Too big for git; Jobs mount it; no git overhead |
| Reference photos (originals) | 305 MB | **HF Storage Bucket** | Bulk immutables; the served copy is a cropped 320/640 px derivative |
| Photo manifest (sha256 per file) | KB | **HF bucket** `manifest/photos.json` | The verifiable link between photos and embeddings |
| Embeddings `.npy` | 376 KB | **HF dataset repo** | Small; must sit at the same revision as the photo manifest |
| Run report + manifests | ~tens of KB per run (est.) | **HF dataset repo** `runs/<run_id>/` | Run history; records the input hashes |
| Dense per-frame metadata | **1.5–3.0 MB per video** | R2 (`metadata/{id}.json`), snapshot also in `runs/` | See §5.1 |
| Renditions 1080p/720p | 708 MB | R2 | Derived; cacheable at the edge |
| Photo thumbs (`photos/thumb/{id}/{sha}-{w}.webp`) | 2.7 MB measured for all 96 at 512 px | R2 | The **public thumbnail gallery** and the admin both read these, never the originals |
| Flag evidence crops | small | R2 | Served to the remote review sheet |
| Processed reels list, current-metadata pointer | < 5 KB | KV | Read on every page load |
| Contestants (96) | ~30 KB | **D1** | Relational: joins with flags |
| Flags + lifecycle + audit | grows unbounded | **D1** | Needs `WHERE status = 'pending'`, counts, ordering |

### Serving the contestant photos as a thumbnail gallery

The bucket copies are **archival inputs for embeddings**, not display assets. Measured: 3–20
photos per contestant (median 9), full Instagram resolution, mixed aspect (1440×1920 portrait,
1280×720 landscape, 640×1136, …). A 1440×1920 IG photo in a 160 px tile shows a room, not a
face — so the gallery cannot use the originals.

Derived set, written by the publish step (or an HF Job), content-addressed like everything else
in R2:

```text
photos/thumb/{contestant_id}/{sha256}-320.webp   # 2× a 160 px tile; ~40 KB each
photos/thumb/{contestant_id}/{sha256}-640.webp   # hover / detail; ~120 KB each
photos/thumb/{contestant_id}/{sha256}-face.webp  # square face crop, 512 px, for the tile
```

The **face crop** reuses the pipeline that already exists: InsightFace finds a frontal face in
the source photo, the box is padded to a square, and one **portrait per contestant** is chosen
and recorded explicitly — `contestants.portrait_key` in D1, `portrait` in
`manifest/photos.json` — so the gallery is stable across runs instead of reshuffling when a new
IG photo lands. The rest stay available as a secondary strip.

**Prototyped and measured (2026-10-20)** with `scripts/hf/make_portraits.py`: **96 of 96**
contestants after the curated set was recovered (2.7 MB total, 28 KB average at 512 px — the
whole gallery is smaller than a single source photo). Choosing the face needed two signals,
because "largest face" is a coin flip in a group shot:

| Signal | Count | Range | Meaning |
| --- | --- | --- | --- |
| reference embedding | 49 | 0.55–1.00 cosine (median 0.78) | trusted |
| repeated-person clustering | 39 | 0.36–0.78 agreement (median 0.56) | the person appearing across that contestant's own photos |
| largest face, no signal | 7 | — | **needs a human**: #21, #22, #40, #60, #72, #79, #83 |

Clustering exists because **36 of 96 contestants have no embedding under their CSV nickname**
(the 94 `.npy` files are keyed by alternate names), so the reference vector is unavailable for
more than a third of the cast. Fixing that naming is a data-hygiene task worth doing before the
real publish: it moves ~36 portraits from a heuristic to a trusted match.

Known source-quality limit: a few contestants' photos only contain small faces (under ~96 px),
which upscale to visible mush at 512 px — #60 Win Win is the clearest. No picker change fixes
that; those need better source photos, or a 低清 stamp on the tile.

Cost: 96 portraits × ~28 KB ≈ **2.7 MB** for the whole gallery, against 305 MB if the originals
were served; the 640 px version is only fetched on hover or detail.

Licensing note, because this gallery is public: these are third-party Instagram photos of real
people. Keeping the source URL and original filename (already in the manifest) is the minimum
provenance; a takedown path and an attribution line are product decisions, not technical
details. Recorded here so it is a decision rather than an oversight.

Provenance without git history: a bucket object is identified by its **sha256**, recorded in
`manifest/videos.json` and the run report in the dataset repo, and in the D1 row. A result is
reproducible when the hashes match — not when a commit matches. The dataset repo commit that
pins the manifests is the human-readable anchor. Because the bucket cannot tell you what an
object used to be, the manifest is the only history; it must be updated in the same publish
run that writes the object, never after.

**KV holds read-only projections. D1 holds anything a human can change.** That single rule
is what keeps eventual consistency from producing "I accepted that flag and it came back".

---

## 3. Phases

Each phase ends with a parity check against the current app; nothing is cut over until the
check passes.

### Phase 0 — Inventory (half a day)

- Grep every `fetch(` in `apps/viewer`, `apps/admin`, `apps/shared`; record path, method,
  request body, response shape. This is the contract.
- Record the response shape of each `local_api.py` handler the admin uses.
- Output: `docs/void-api-parity.md` — one row per endpoint, with a ✅ when the Void route
  returns the same shape.
- **Exit**: the list is complete; no route is discovered later during cutover.

### Phase 1 — Void scaffold + viewer read path (1–2 days)

- `void init` in a branch; keep `apps/viewer` as the SPA, deploy its `dist` and the API from
  the same project.
- Port the read routes: processed list, dense metadata, contestants, photos, system status.
- Point the viewer at the new origin via `VITE_API_BASE`; keep the Vite proxy for local dev.
- Import `db` (D1) and `kv` so the resources exist in local dev, even if unused yet.
- **Exit**: the viewer's three routes render against Void locally (`vite dev` + provisioned
  resources) and in a preview deploy, byte-identical JSON to the worker's.

### Phase 2 — Publish path (the missing writer) (1–2 days)

- A single script, `scripts/publish/` (Node, typed), whose **input is an HF snapshot at a
  pinned revision**, not `local_output/` on the operator's disk. It reads
  `runs/<run_id>/…` from the dataset repo and writes the KV read model and the D1 rows in one
  run, with a manifest and a checksum per video.
- It also promotes the run to R2 (renditions, `metadata/{id}.json`, 512px photo thumbs) with
  immutable keys, and stamps `source_revision` + `run_id` into the D1 row.
- Fail loudly when a video exists in the list but not in storage, or when a run's
  `source_revision` does not match the manifest.
- Run it in CI on a schedule, and from the admin as "重新發佈".
- **Exit**: `processed_videos_list` and `metadata_dense_*` are written by a script that is
  in the repo, from a reproducible snapshot, and a fresh deploy serves real reels — the
  current bug is closed.

### Phase 3 — Storage and streaming (1 day)

- Port the R2 video route *including* Range handling (the worker already has the correct
  approach; see §5.2). Videos re-uploaded to the Void-provisioned bucket, or bound to the
  existing `mv-face-recognition-videos` bucket via config so nothing re-uploads.
- Reference photos to R2; `/api/contestants/:id/photo` reads from R2 with a `Cache-Control`.
- **Exit**: seeking works in Safari, Chrome and Firefox; `curl -r` returns 206 with the
  right `Content-Range`; no full-object buffering in any path.

### Phase 4 — Remote admin (2–3 days) — the risky one

Order inside this phase matters; do not parallelise it.

1. **Auth first, routes second.** Cloudflare Access application for `/admin*` and for every
   `POST`/`PATCH` API route; verify the Access JWT in the route (the repo already reserves
   `CF_ACCESS_AUD` / `CF_ACCESS_TEAM` secrets). Reject unauthenticated writes with 401 *and
   log the attempt*; do not fall back to open.
2. **CSRF and origin**: writes require `Origin` in an allow-list plus a custom header, so a
   third-party page cannot drive the admin with a borrowed cookie.
3. **Move the writes**: flags create/accept/void/reassign → D1 with an audit row per change
   (who, when, before, after). The flag lifecycle stays exactly as `CONTEXT.md` defines it —
   pending / accepted / rejected — but now it has an owner.
4. **Move the heavy operations**: processing and embedding regeneration stay in Modal. The
   admin route only enqueues and polls; it never computes.
5. **Retire the local assumption**: `CONTEXT.md` §Admin, `PRODUCT.md` (operating context and
   the "writes stay home" principle), and ADR 0003 get rewritten in the same commit that
   makes the admin reachable. A stale rule that contradicts the code is worse than no rule.
6. **Operator surface**: the admin's 唯讀/存根 language changes — 存根 means "the office copy
   you may write on", which still holds, but the "LOCAL ONLY · 127.0.0.1" line in every
   masthead becomes false and must be replaced with the real environment name.

- **Exit**: an authenticated operator can clear a flag queue from a laptop that has never
  run `local_api.py`; an unauthenticated request gets 401 and no write lands.

### Phase 5 — Parallel run and cutover (1 day)

- Run Void on a preview hostname alongside `mv-face-recognition-api.herballemon.workers.dev`
  for a week of real use; both read the same R2 bucket.
- Cut over by DNS/route swap, keeping the wrangler worker deployable for one release as
  rollback.
- **Exit**: 7 days with no parity bug; rollback rehearsed once (re-point the domain).

### Phase 6 — Cleanup (half a day)

- Delete `worker/embedded-assets.js`, `scripts/update-worker-assets.js`, the old router.
- Delete `wrangler.toml` or reduce it to the R2 binding if the bucket is still bound by name.
- Update `DESIGN.md`, `README`, deployment docs; add an ADR recording the move and why the
  admin is no longer local.

Total: roughly **7–10 working days**, with Phase 4 the only phase that can invalidate the
plan if the auth model is wrong.

---

## 4. Security model for the remote admin

| Concern | Decision |
| --- | --- |
| Who can reach the admin | Cloudflare Access policy (email OTP or SSO), one operator identity |
| Who can write | Same identity, verified as a JWT in the route — Access protecting the page is not enough, an attacker can POST directly |
| Replay / CSRF | Origin allow-list + custom header + short-lived JWT |
| Blast radius | Writes touch D1 only; videos and embeddings are read-only from the edge |
| Audit | Every flag change is a row: actor, timestamp, before, after |
| Fallback | If Access is misconfigured, writes fail closed (401), never open |

Known sharp edge: Access protects paths, not methods. Every write route re-verifies the JWT
itself; a page-level policy alone would leave the API open.

---

## 5. The two mechanisms to get right

### 5.1 Metadata size

Measured: `…_annotated_dense_metadata.json` is **1.5–3.0 MB** per video; five videos ≈ 10 MB.
Measured on reel 1: 859 frame records spanning 245 s (one every ~0.29 s), in a 1.5 MB file, so ~1.7 KB per record.

Why it matters: `useViewerMetadata` currently fetches **the whole document** on load, before
playback starts. On a phone that is 2–3 MB of JSON to parse before the first frame, and KV
charges per read while an edge cache only helps after the first miss.

Three placements, in order of effort:

| Option | How | Cost | Ceiling |
| --- | --- | --- | --- |
| **A. Whole-doc KV** (parity) | one `metadata_dense_<id>` value, gzip + `Cache-Control` | least code, matches today exactly | 25 MiB per value; whole doc per client |
| **B. KV index + time-sliced chunks** | index of `[{t, frame, chunk}]` (a few KB), plus 30 s chunks in KV or R2 | one extra request per 30 s of playback | chunk size × count, no hard ceiling |
| **C. R2 object + index, Range-served** | index in KV/D1, frames in R2 read by byte range | most code, cheapest reads, best on long videos | none |

Recommendation: **ship A to reach parity, instrument the payload size, then move to B** if
the measured time-to-first-frame on mobile exceeds ~1 s. B is a drop-in for the existing
`getFrameAtTime` binary search — the index keeps the timestamps, so the search stays local
and only the selected chunk is fetched. C is only worth it if videos get much longer.

Also true regardless of placement: the viewer must never request metadata for a video it
has not opened (lazy per reel), and the dense doc should stop carrying fields the player
never reads (`processing_info`, duplicate detection names) — trimming may halve it for free.

### 5.2 HTTP Range streaming

Why it is not optional: `<video>` seeking depends on it. Without `Accept-Ranges: bytes` and
206 responses the browser downloads sequentially from byte 0, so dragging the scrubber either
does nothing until the bytes arrive or silently re-downloads the file.

The current worker already does the right thing and the code ports almost verbatim:

```ts
const range = request.headers.get('Range');
if (range) {
  const [start, end] = parseRange(range, size);
  const obj = await env.VIDEOS_BUCKET.get(path, {
    range: { offset: start, length: end - start + 1 },
  });
  return new Response(obj.body, {
    status: 206,
    headers: {
      'Content-Range': `bytes ${start}-${end}/${size}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': String(end - start + 1),
      'Content-Type': 'video/mp4',
    },
  });
}
```

Details that decide whether it actually works:

- **`HEAD` first.** Get the size with `head()`; a Range parse needs the total. Return
  `Accept-Ranges: bytes` and `Content-Length` on the plain 200 too.
- **Suffix and open-ended ranges.** `bytes=500-` (to the end) and `bytes=-500` (last 500
  bytes). Browsers use the first constantly; the second occasionally.
- **Unsatisfiable ranges.** If `start >= size`, return `416` with
  `Content-Range: bytes */<size>`. Do not clamp silently — the player reads that as a broken
  file.
- **Single range only.** Multi-range (`bytes=0-99,200-299`) is not used by browsers; treat it
  as a normal request or 416, never `multipart/byteranges`.
- **Stream, don't buffer.** `R2ObjectBody.body` is a `ReadableStream`; a Worker has 128 MB of
  memory, so buffering a 200 MB file is a crash, not a slowdown.
- **CORS exposes the headers.** Cross-origin playback needs
  `Access-Control-Allow-Headers: Range` and
  `Access-Control-Expose-Headers: Content-Range, Accept-Ranges, Content-Length`. Missing the
  second one is the classic "video plays but the scrubber has no duration" bug.
- **Cache-Control + ETag.** Partial responses are cached by Range key; passing the R2 ETag
  through lets the browser revalidate instead of re-downloading.
- **Local dev must exercise it.** Void's local R2 emulation should answer Range too; test the
  seek path in `vite dev`, not only in the preview deploy.

---

## 6. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Admin exposed without a method-level check | medium | verify JWT in every write route; a test that POSTs unauthenticated and expects 401 |
| KV eventual consistency shows stale flags | high (if flags stay in KV) | flags live in D1 only |
| Publish script writes a different shape than the reader | medium | Phase 0 parity doc + a schema test that runs the writer and validates against the reader's types |
| Dense metadata too slow on mobile | medium | §5.1 B, measured not guessed |
| R2 bucket rebind breaks existing objects | low | bind by name, do not recreate |
| Access policy locks the operator out | medium | keep one bypass path documented (Access service token) and test it before cutover |
| Void is young; a breaking change lands mid-migration | medium | keep the wrangler worker deployable until Phase 6 |

---

## 7. Open decisions

1. **Admin auth**: Cloudflare Access only, or Access + an operator allow-list table in D1?
2. **Flag identity**: does a flag record who proposed it (needed for audit once remote)?
3. **Embedding workbench**: does it, or does only Modal, ever compute vectors?
4. **Judging data**: remote admin means labels can be contributed from anywhere — is that
   still "the operator", or does the product now have reviewers?
5. **Product truth**: PRODUCT.md currently states "Writes stay home" as a principle. A remote
   admin replaces it with "writes are authenticated and audited" — confirm the wording
   before Phase 4.
