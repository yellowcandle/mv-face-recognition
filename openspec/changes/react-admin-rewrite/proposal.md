# React Admin Rewrite

## Problem

The frontend is a single SvelteKit app (`mvp-processor/src/routes/`) that conflates two audiences: a local admin tool (7 pages for processing/curating videos) and a public viewer (3 pages deployed to Cloudflare Workers). The Svelte codebase has accumulated pain:

- 45 pre-existing type errors from Svelte 4→5 migration
- Monolithic 1700-line single-file pages with no component reuse
- Svelte 5 but still using Svelte 4 reactivity patterns (no runes)
- Thin ecosystem for charting, data tables, and canvas tooling
- TanStack Query less mature on Svelte than React
- Developer wants to focus on React

## Solution

Rewrite the frontend as a **pnpm monorepo** with two React + Vite + Tailwind apps sharing a common package:

- **apps/admin** — 7 admin pages, runs locally (`localhost:5173`), reads local JSON/API
- **apps/viewer** — 3 public pages, built and deployed to Cloudflare Workers (Phase 2)
- **apps/shared** — shared components (Player, Button, Badge, Card), TypeScript types, data hooks

## Scope

### Phase 1: Admin App (this change)

**In Scope:**
- pnpm workspace setup with `apps/admin`, `apps/shared`
- React 19 + Vite 6 + Tailwind CSS 4 + React Router 7
- TanStack Query 5 + TanStack Table (for data tables)
- Port all 7 admin pages from Svelte → React:
  - Dashboard (`/`)
  - Player (`/player`) — full-featured with canvas annotations, flagging, batch mode
  - Embedding Workbench (`/embedding-workbench`) — coverage grid, detail, confusion heatmap
  - Contestants (`/contestants`)
  - Flagging (`/flagging`)
  - Ingestion (`/ingestion`)
  - Processing (`/processing`)
- Shared components in `apps/shared`: Player, Button, Badge, Card, NavigationLink, Layout
- Shared types: Contestant, Video, Metadata, FaceDetection, CoverageSummary
- Shared hooks: useContestants, useVideos, useFaces, useCoverage
- Dark theme via Tailwind config mapping existing design tokens

**Out of Scope (Phase 2):**
- `apps/viewer` (public-facing app)
- Worker deployment changes
- Deleting old Svelte code (keep until viewer is ported)

### Non-goals
- SSR / server components (not needed — client-rendered admin tool)
- Next.js / Remix (unnecessary complexity for this use case)
- Mobile-first design (admin is desktop-only)

## Architecture

### Monorepo Layout

```
mv-face-recognition/
├── apps/
│   ├── admin/
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Player.tsx        (imports shared Player)
│   │   │   │   ├── EmbeddingWorkbench.tsx
│   │   │   │   ├── Contestants.tsx
│   │   │   │   ├── Flagging.tsx
│   │   │   │   ├── Ingestion.tsx
│   │   │   │   └── Processing.tsx
│   │   │   ├── layouts/
│   │   │   │   └── AdminLayout.tsx   (sidebar nav + header)
│   │   │   └── main.tsx
│   │   ├── package.json
│   │   ├── tailwind.config.ts
│   │   └── vite.config.ts
│   │
│   └── shared/
│       ├── components/
│       │   ├── Player.tsx            (canvas overlays, face boxes, video toggle)
│       │   ├── Button.tsx
│       │   ├── Badge.tsx
│       │   ├── Card.tsx
│       │   └── index.ts
│       ├── hooks/
│       │   ├── useContestants.ts
│       │   ├── useVideos.ts
│       │   ├── useFaces.ts
│       │   └── useCoverage.ts
│       ├── types/
│       │   └── index.ts
│       └── package.json
│
├── pnpm-workspace.yaml
├── mvp-processor/            (Python — unchanged)
├── worker/                   (Cloudflare Worker — unchanged for now)
└── data/                     (generated JSONs)
```

### Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | React 19 | Largest ecosystem, developer preference |
| Build | Vite 6 | Already using, fast, no SSR needed |
| Routing | React Router 7 | Standard, file-based optional |
| Styling | Tailwind CSS 4 | Utility-first, dark theme, fast iteration |
| Data fetching | TanStack Query 5 | Already using (better React support than Svelte) |
| Data tables | TanStack Table | For analytics, contestants, flagging pages |
| Monorepo | pnpm workspaces | Lightweight, no Turborepo overhead needed |
| Types | TypeScript 5.x | Same as now |

### Shared Player Component

The Player is the most complex component (~1700 lines in Svelte). In React it becomes:

```
shared/components/Player.tsx
├── Props:
│   ├── mode: 'admin' | 'viewer'    (controls flagging UI visibility)
│   ├── apiBase: string              (localhost vs workers.dev)
│   ├── onFlag?: callback            (admin only)
│   └── showControls?: boolean       (playback speed, batch mode)
│
├── Sub-components:
│   ├── VideoCanvas.tsx              (video + annotation canvas overlay)
│   ├── FaceOverlay.tsx              (clickable hit targets)
│   ├── PlayerControls.tsx           (play/pause, seek, speed, volume)
│   ├── DetectionBar.tsx             (face count, toggles)
│   └── FlagDialog.tsx               (admin-only)
│
└── Hooks:
    ├── useVideoPlayer.ts            (playback state)
    ├── useAnnotations.ts            (canvas drawing, color palette)
    └── useFaceDetection.ts          (polling, face data)
```

Breaking the 1700-line monolith into ~6 focused components + 3 hooks.

## Migration Strategy

Port pages in dependency order (shared hooks/components first, then pages):

1. Scaffold monorepo (pnpm workspace, Vite configs, Tailwind)
2. Shared types + hooks
3. Shared components (Player sub-components, then Button/Badge/Card)
4. Admin layout (sidebar nav, header, dark theme)
5. Dashboard page (simplest — stat cards + links)
6. Contestants page (table + search)
7. Player page (most complex — imports shared Player)
8. Embedding Workbench (coverage grid + heatmap canvas)
9. Flagging page (filters + reassignment)
10. Ingestion page (upload + queue)
11. Processing page (job tracking)

## Priority

High — this unblocks all future frontend work on a stable, well-supported foundation.
