# Tasks: React Admin Rewrite

## Phase 1A: Scaffold

### T1: Monorepo setup
- Create `pnpm-workspace.yaml` at project root
- Create `apps/admin/package.json` (React 19, Vite 6, React Router 7, TanStack Query 5)
- Create `apps/shared/package.json` (React 19 as peer dep)
- Vite configs for both packages
- TypeScript configs with path aliases
- Verify `pnpm install` and `pnpm -F admin dev` works

### T2: Tailwind + dark theme
- Install Tailwind CSS 4 in admin app
- Map existing design tokens to Tailwind theme:
  - `--surface-primary` → `bg-surface-primary`
  - `--text-primary` → `text-primary`
  - `--color-primary-600` → `text-accent` / `bg-accent`
  - etc.
- Create `tailwind.config.ts` with dark-mode-by-default
- Verify: dark background renders on `localhost:5173`

### T3: Admin layout + routing
- Create `AdminLayout.tsx`: sidebar nav (9 items with separator) + header + status indicator
- Create React Router config with all 7 routes
- Create `main.tsx` with QueryClientProvider + RouterProvider
- Verify: clicking nav links renders placeholder pages

## Phase 1B: Shared Package

### T4: Shared types
- `apps/shared/types/index.ts`:
  - `Contestant` (id, name, nickname, age, quality, confidence, etc.)
  - `Video` (id, name, stream_url, filename, etc.)
  - `VideoMetadata` (video_info, recognition_summary, contestant_timeline, frame_data)
  - `FaceDetection` (bbox, confidence, contestant_name, matched)
  - `CoverageSummary`, `ConfusionPair`, `SimilarityData`
- Export from `@mv/shared`

### T5: Shared data hooks
- `useContestants()` — fetches from `/api/contestants`
- `useVideos()` — fetches from `/api/videos/processed/list`
- `useFaces(videoId, timestamp)` — fetches from `/api/faces/detect`
- `useCoverage()` — fetches from `/data/coverage.json`
- `useSimilarity()` — fetches from `/data/similarity_matrix.json` + `/data/top_pairs.json`
- `useFlaggedFaces()` — fetches from `/api/faces/flagged`
- All using TanStack Query with appropriate stale times

### T6: Shared base components
- `Button.tsx` — variants: primary, secondary, ghost, destructive (Tailwind)
- `Badge.tsx` — variants: success, warning, error, neutral
- `Card.tsx` — dark surface with border
- `Input.tsx`, `Select.tsx` — form controls
- All with Tailwind, dark theme defaults

## Phase 1C: Shared Player

### T7: Player sub-components
- `VideoCanvas.tsx` — `<video>` + `<canvas>` annotation overlay, HiDPI rendering
- `useAnnotations.ts` hook — `drawAnnotations()`, color palette, letterbox offset (`getVideoRenderRect`)
- `FaceOverlay.tsx` — transparent click targets for face bboxes (correct `[x1,y1,x2,y2]` format)
- `PlayerControls.tsx` — play/pause, seek bar, speed selector, volume, skip buttons
- `DetectionBar.tsx` — face count, frame number, video source toggle, annotations toggle
- `FlagDialog.tsx` — single face flag + batch flag dialogs (admin-only, conditional render)

### T8: Player composition
- `Player.tsx` — composes sub-components, accepts `mode: 'admin' | 'viewer'` prop
- `useVideoPlayer.ts` hook — playback state, time update, metadata loading
- `useFaceDetection.ts` hook — polling, face data at current time
- Wire face thumbnail extraction (`extractFaceThumbnail`) using canvas
- Test: video plays, annotations draw, face click opens flag dialog

## Phase 1D: Admin Pages

### T9: Dashboard page
- Port from Svelte `+page.svelte` (simplest page)
- Stat cards (total videos, contestants, faces, pending flags)
- Quick links grid to other pages
- Uses `useVideos()`, `useContestants()`, `useFlaggedFaces()`

### T10: Contestants page
- Port from Svelte: search, contestant cards grid, detail modal
- Uses `useContestants()`, appearance stats
- Click contestant → modal with video appearances

### T11: Player page (admin)
- Thin wrapper: `<Player mode="admin" apiBase="" />`
- Video selector, flagged faces panel
- Timeline contestant filter (admin-specific feature)
- This is the integration test for T7+T8

### T12: Embedding Workbench page
- Port from Svelte: 4-tab layout
- Coverage tab: stat cards + contestant grid (from `useCoverage()`)
- Detail tab: contestant stats panel + placeholder for face crops
- Confusion tab: canvas heatmap + top pairs sidebar (from `useSimilarity()`)
- Unmatched tab: placeholder

### T13: Flagging page
- Port from Svelte: filter by status/video/contestant, confidence threshold
- Face comparison interface, reassignment modal
- Uses `useFlaggedFaces()`, `useContestants()`

### T14: Ingestion page
- Port from Svelte: YouTube URL input, processing queue, video library
- Uses `useVideos()`

### T15: Processing page
- Port from Svelte: WebSocket job tracking, job queue display
- Cancel/clear job actions
