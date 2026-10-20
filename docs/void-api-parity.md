# Void API parity — Phase 0 inventory

Every HTTP call the two apps make, the server route that answers it today, and where that
route lands on Void. Nothing is ported until each row is ✅.

Sources: `apps/*/src`, `apps/shared`, `worker/src/index.ts` (edge), `mvp-processor/src/local_api.py`
(admin dev server), `apps/*/public` (static payloads).

Legend — **Origin**: `edge` = Cloudflare Worker, `local` = `local_api.py` on
`127.0.0.1:8000`, `static` = a file in `public/`, `none` = no implementation exists.
**Void**: read = public GET, auth = authenticated write, static = shipped asset.

---

## 1. Read endpoints — viewer needs all of these

| Endpoint | Origin | Callers | Response shape | Void route |
| --- | --- | --- | --- | --- |
| `GET /api/videos/processed/list` | edge + local | `useVideos` (viewer Home, Player, Analytics; admin Dashboard) | `Video[]` — `{id, name, stream_url, filename?, duration?, width?, height?}` | `routes/api/videos/processed/list.ts` |
| `GET /api/videos/metadata/dense/{id}` | edge + local | `useViewerMetadata`, `Analytics`, admin `Labelling` | `VideoMetadata` — `video_info`, `processing_summary`, `contestant_timeline`, `frame_data[]` (2–3 MB) | `routes/api/videos/metadata/dense/[id].ts` — §5.1 of the migration plan |
| `GET /api/contestants` | edge + local | `useContestants` | `Contestant[]` — `{id, name, nickname, age, has_embedding, reference_count, quality, portrait_url?, …}` — **`portrait_url` is new**, needed by the thumbnail gallery | `routes/api/contestants/index.ts` (D1) |
| `GET /api/contestants/{id}/thumb/{size}` | none | public portrait route, used by the public cast sheet (`apps/viewer`) | webp bytes (sizes `320`, `640`, `face`) | `routes/api/contestants/[id]/thumb/[size].ts` (served from R2, immutable + long cache) |
| `GET /api/contestants/{id}/photo` | local only | admin only (admin `Contestants` `<img src>`); raw originals, must not be called by `apps/viewer` | image bytes | `routes/api/contestants/[id]/photo.ts` (R2 thumb) |
| `GET /api/system/status` | edge + local | admin `AdminLayout` lamp | `{status, mode}` / `{chromadb_connected, …}` | `routes/api/system/status.ts` |
| `GET /api/faces/flagged?details=true` | local only | `useFlaggedFaces` (admin; viewer passes `enabled: canFlag`) | `{flagged_faces: FlaggedFace[]}` | `routes/api/faces/flagged/index.ts` (**auth**, D1) |
| `GET /api/faces/detect?video_id&timestamp` | edge + local | `Player` admin polling | `{faces: FaceDetection[]}` | `routes/api/faces/detect.ts` (derived from dense metadata) |
| `GET /api/recognition/results?contestant_id` | edge + local | admin `Contestants` filing card | `{results: [{video_id, timestamp, match_score}]}` | `routes/api/recognition/results.ts` (D1) |
| `GET /api/labels/{video_id}` | local only | admin `Labelling` | `{video_id, labels, schema, source, labelled_at}` | `routes/api/labels/[videoId].ts` (**auth**, D1) |
| `GET /api/labels` | local only | admin `Labelling` (index) | `[{video_id, count, labelled_at}]` | `routes/api/labels/index.ts` (**auth**) |
| `GET /api/videos/stream/{id}` | local (Range) | `VideoCanvas` `<video src>` | video bytes, **206 + Range** | `routes/api/videos/[id]/stream.ts` — §5.2 |
| `GET /api/faces/crop?video_id&frame_number&width` | local only | admin (face crop) | image bytes | `routes/api/faces/crop.ts` (**auth**, R2) |
| `GET /api/videos` | edge only | *unused by both apps* | hardcoded list | drop |
| `GET /api/videos/local` | local only | *unused by both apps* | local file inventory | drop |
| `GET /data/coverage.json` | static (`admin/public`) | `useCoverage` | JSON | static asset |
| `GET /data/similarity_matrix.json`, `/data/top_pairs.json` | static (`admin/public`) | `useSimilarity` | JSON | static asset |

## 2. Write endpoints — all become authenticated

| Endpoint | Origin | Callers | Body | Void route |
| --- | --- | --- | --- | --- |
| `POST /api/faces/flag` | edge + local | `Player` (admin flagging) | `{video_id, timestamp, contestant_id, bbox, confidence, user_label}` | `routes/api/faces/flag.ts` (**auth**, D1 + audit) |
| `PATCH /api/faces/flagged/{id}` | local only | admin `Flagging` accept/void | `{status: 'accepted' \| 'rejected'}` | `routes/api/faces/flagged/[id].ts` (**auth**, D1 + audit) |
| `POST /api/faces/flag/update` | local only | admin `Flagging` reassign | `{face_id, contestant_id}` | `routes/api/faces/flag/update.ts` (**auth**, D1 + audit) |
| `DELETE /api/faces/flagged/{id}` | local only | *unused by both apps* | — | drop |
| `PUT /api/labels/{video_id}` | local only | admin `Labelling` save | `{labels, schema, source}` | `routes/api/labels/[videoId].ts` (**auth**, D1) |
| `POST /api/processing/trigger` | local only | admin `Processing` | `{mode, video_files}` | `routes/api/processing/trigger.ts` (**auth**, enqueues Modal job) |
| `POST /api/processing/cancel/{job_id}` | local only | admin `Processing` | — | `routes/api/processing/cancel/[jobId].ts` (**auth**) |
| `POST /api/processing/clear-completed` | local only | admin `Processing` | — | `routes/api/processing/clear-completed.ts` (**auth**) |

## 3. Endpoints that do not exist

| Endpoint | Called by | Reality |
| --- | --- | --- |
| `GET /api/ingestion/jobs` | admin `Ingestion` | **No implementation** in `worker/src/index.ts` or `local_api.py`. The page is already commented out of `main.tsx`. |
| `POST /api/ingestion/submit` | admin `Ingestion` | Same. The disabled page is honest; do not port. |
| `GET /api/processing/jobs` | admin `Processing` | **local only.** The Worker has no processing routes at all. `GET /api/processing/jobs/{id}` exists locally and is unused. |

## 4. Divergences between the two origins

These are the traps; the port must pick one behaviour per row.

| Behaviour | edge (`worker/src/index.ts`) | local (`local_api.py`) | Pick |
| --- | --- | --- | --- |
| `contestants` | reads KV `contestants_structured`, falls back to a hardcoded 96-entry `allContestants` | reads `contestant_info.csv` + embeddings | **D1 seed from CSV**; delete the hardcoded fallback |
| `processed/list` | reads KV `processed_videos_list` (no writer) → falls back to **mock videos** | lists `local_output/metadata/*` | **KV read model written by publish** |
| dense metadata | KV `metadata_dense_<id>` (no writer) | reads `local_output/metadata/*.json` | **publish writes it** (Phase 2) |
| `system/status` | static `{chromadb_connected: true, …}` | `{status: 'online', mode: 'local'}` | one shape, real checks (D1/R2 reachable) |
| video stream | R2 + Range (correct) | disk + Range | **R2 + Range** |
| flag storage | *no write routes at all* (ADR 0003 removed them) | JSON file `local_output/flagged_faces.json` | **D1 + audit rows** |
| `recognition/results` | KV/hardcoded | scans metadata | **D1 index** |

## 5. Calls that are not HTTP

- `Player.tsx` also opens a **WebSocket** to `/ws/…` for realtime processing
  (`worker/src/index.ts:98`, `case '/realtime-processing'`). The viewer never uses it; the admin
  uses polling instead. **Port nothing here**; if realtime is wanted later it is a Void
  WebSocket route, not part of this migration.
- Video and photo `src` attributes go through `apiBase` (`''` in dev, proxied by Vite). On
  Void, `apiBase` becomes the deployment origin; the routes stay identical.

## 6. Exit criteria

- [x] Every `fetch(` in `apps/*/src` and `apps/shared` appears above — 33 call sites resolving to
      **23 distinct literal endpoints**, plus the video stream URL that arrives inside the
      `processed/list` payload (`video.stream_url`) and is loaded by `<video src>`, so 24
      endpoints are reached at runtime. Verified by grepping URL literals, not only `fetch(`
      call sites, because several calls are multi-line.
- [x] Every route in `worker/src/index.ts` and `mvp-processor/src/local_api.py` is classified
      as read / write / unused / missing.
- [ ] Each row gets a ✅ when the Void route returns the same shape (filled in during Phase 1–4).
