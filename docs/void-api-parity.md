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
| `GET /api/contestants/{id}/thumb/{size}` | edge + local | public portrait route, used by the public cast sheet (`apps/viewer`) and admin `Contestants` via `portrait_url` | webp bytes (sizes `320`, `640`, `face`) — edge serves `portraits/{id}.webp` from R2, local scans `source/photo/historical/contestants/{id}` then `contestant_{id}` | `routes/api/contestants/[id]/thumb/[size].ts` (served from R2, immutable + long cache) |
| `GET /api/contestants/{id}/photo` | edge + local | same resource as `thumb/face` — kept as an alias for older payloads; raw originals, must not be called by `apps/viewer` | image bytes | `routes/api/contestants/[id]/photo.ts` (alias of the thumb route) |
| `GET /api/system/status` | edge + local | admin `AdminLayout` lamp, `SystemAdmin` counters | one shape on both: `{status, mode, chromadb_connected, model_loaded, services_running, contestant_count, video_count, processing_jobs}` — `mode` is `'edge'` or `'local'` | `routes/api/system/status.ts` |
| `GET /api/faces/flagged?details=true` | edge + local | `useFlaggedFaces` (admin; viewer passes `enabled: canFlag`) | `{flagged_faces: FlaggedFace[]}`; `thumbnail` omitted unless `details=true` | `routes/api/faces/flagged/index.ts` (**auth**, D1) |
| `GET /api/embedding/coverage` | edge + local | `useCoverage` (admin Dashboard, `EmbeddingWorkbench`, viewer ledger) | `{contestants[], summary{total, good, weak, missing, avg_match_score, recognition_rate, total_faces_detected, total_faces_recognized}}` — edge reads KV `embedding_coverage`, local reads `data/coverage.json` and regenerates when absent | `routes/api/embedding/coverage.ts` |
| `GET /api/embedding/similarity` | edge + local | `useSimilarity` (admin `EmbeddingWorkbench` Confusion) | `{labels[], matrix[][], stats{…}}` — KV `embedding_similarity_matrix` / `data/similarity_matrix.json` | `routes/api/embedding/similarity.ts` |
| `GET /api/embedding/top-pairs` | edge + local | `useSimilarity` | `{pairs[], total_pairs}` — KV `embedding_top_pairs` / `data/top_pairs.json` | `routes/api/embedding/top-pairs.ts` |
| `GET /api/faces/detect?video_id&timestamp` | edge + local | `Player` admin polling | `{faces: FaceDetection[]}` | `routes/api/faces/detect.ts` (derived from dense metadata) |
| `GET /api/recognition/results?contestant_id` | edge + local | admin `Contestants` filing card, `EmbeddingWorkbench` detail grid | `{results: [{video_id, timestamp, match_score, frame_number?, bbox?, detection_index?}]}` — `detection_index` is recovered by matching the box back to the frame's detection list (both origins), which is what makes `/api/faces/crop` addressable; absent when no detection matches, and the client then crops the reel | `routes/api/recognition/results.ts` (D1) |
| `GET /api/labels/{video_id}` | edge + local | admin `Labelling` | `{schema: 'labels/v2', video_id, labelled_at, labelled_by?, source{processing_date, detections}, labels[], legacy_ignored}`; `409` when the stored `source` no longer matches the current metadata run | `routes/api/labels/[videoId].ts` (**auth**, KV on edge / D1) |
| `GET /api/labels` | edge + local | admin `Labelling` (index), `SystemAdmin` | `{labels: [{video_id, schema, count, labelled_at, legacy_ignored}]}` | `routes/api/labels/index.ts` (**auth**) |
| `GET /api/videos/stream/{id}` | local (Range) | `VideoCanvas` `<video src>` | video bytes, **206 + Range** | `routes/api/videos/[id]/stream.ts` — §5.2 |
| `GET /api/faces/crop?video_id&frame_number&detection_index&width` | edge + local | `<FaceCrop>` in admin `Labelling` / `EmbeddingWorkbench` | image bytes — edge serves R2 `crops/{video}/{frame}_{index}.jpg`; `404` means the client falls back to seeking the reel and cropping `bbox` on a canvas | `routes/api/faces/crop.ts` (R2) |
| `GET /api/videos` | edge only | *unused by both apps* | hardcoded list | drop |
| `GET /api/videos/local` | local only | admin `Processing` source-reel selector (probe failure disables the pipeline buttons) | local file inventory `{filename, size_mb}[]` | drop on Void |


## 2. Write endpoints — all become authenticated

| Endpoint | Origin | Callers | Body | Void route |
| --- | --- | --- | --- | --- |
| `POST /api/faces/flag` | edge + local | `Player` (admin flagging) | `{video_id, timestamp, contestant_id, bbox, confidence, user_label, thumbnail?}` — edge stamps `id`, `created_at`, `status: 'pending'`, `flagged_by` from the Access JWT email | `routes/api/faces/flag.ts` (**auth**, D1 + audit) |
| `PATCH /api/faces/flagged/{id}` | edge + local | admin `Flagging` accept/void | `{status: 'pending' \| 'accepted' \| 'rejected'}` | `routes/api/faces/flagged/[id].ts` (**auth**, D1 + audit) |
| `POST /api/faces/flag/update` | edge + local | admin `Flagging` reassign | `{face_id, contestant_id}` — resets `status` to `pending` | `routes/api/faces/flag/update.ts` (**auth**, D1 + audit) |
| `DELETE /api/faces/flagged/{id}` | edge + local | *unused by both apps* | — | drop |
| `PUT /api/labels/{video_id}` | edge + local | admin `Labelling` save | `{labels[{tracker_id, verdict, contestant_id?, note?}], source{processing_date, detections}}` — `400` on duplicate/unknown/negative `tracker_id` or unknown verdict, `409` on stale `source` | `routes/api/labels/[videoId].ts` (**auth**, KV on edge / D1) |
| `POST /api/processing/trigger` | local only | admin `Processing`, `EmbeddingWorkbench` | `{mode: 'initial' \| 'embedding-update' \| 'coverage-refresh', video?}` — `400` on any other mode; embedding/coverage modes rebuild `reference_embeddings.npz` and re-derive the coverage/similarity payloads the `/api/embedding/*` reads serve | `routes/api/processing/trigger.ts` (**auth**, enqueues Modal job) |
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
| `processed/list` | reads KV `processed_videos_list` → falls back to **mock videos** | lists `local_output/metadata/*` | **KV read model written by publish** |
| dense metadata | KV `metadata_${id}` (written by publish) | reads `local_output/metadata/*.json` | **publish writes it** (Phase 2) |
| `system/status` | `{status:'online', mode:'edge', …}` | `{status:'online', mode:'local', …}` | unified shape; `mode` is the one intended difference — don't fork the rest of it |
| video stream | R2 + Range (correct) | disk + Range | **R2 + Range** |
| flag storage | KV `flagged_faces` (single JSON array, last-write-wins) | JSON file `local_output/flagged_faces.json` | **D1 + audit rows** |
| label storage | KV `labels_${video_id}`, `labels/v2`, `409` on stale `source` | JSON file per video, same schema + `409` | **D1 + audit rows**; keep the `source` guard — it is what stops labels landing on a re-run |
| coverage / similarity | KV `embedding_coverage` / `embedding_similarity_matrix` / `embedding_top_pairs` (published) | `data/*.json`, regenerated on demand by `coverage-refresh` | **published documents, never bundle assets** — the static copies cost ~190 KiB of the 1 MiB Worker limit |
| `recognition/results` | aggregation over KV `metadata_*` `contestant_timeline`; includes `frame_number` + `bbox` | same aggregation over `local_output/metadata/*` | **D1 index** |
| writes that need a human | any `/api/faces/flag*` or `/api/labels*` request runs Cloudflare Access RS256 verification first: `503` when `CF_ACCESS_AUD`/`CF_ACCESS_TEAM_DOMAIN` are unset, `401` on a missing/invalid token, and the token shape is rejected **before** any JWKS fetch so anonymous traffic never causes an outbound request | no auth (loopback only) | **verify before touching storage**; keep the fail-closed ordering — the read-only test asserts zero KV/R2 writes and zero outbound fetches for every unauthenticated route × method |

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
