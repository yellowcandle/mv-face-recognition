# Port Annotation Overlay to /player

## Problem

The canonical video player route `/player` is missing 6 features that exist in the legacy `/video-player` route (which now 308-redirects to `/player`). These features were built as part of the Stage 6 annotation overlay work but never ported when `/player` became the primary route.

Additionally, `/player` has a **bbox format bug** — it interprets face coordinates as `[x, y, w, h]` when the backend stores `[top, right, bottom, left]` (i.e. `[x1, y1, x2, y2]`). This causes mispositioned face hit targets.

## Solution

Port the 6 missing features from `/video-player` into `/player` and fix the bbox bug. After porting, `/video-player` can be reduced to just its redirect.

## Scope

### In Scope
1. **Canvas annotation overlay** — `<canvas>` element + `drawAnnotations()` function (~70 lines)
2. **HiDPI canvas rendering** — `devicePixelRatio` scaling for Retina displays
3. **Per-contestant color coding** — 10-color palette assigned by first appearance
4. **Letterbox offset calculation** — `getVideoRenderRect()` for `object-fit: contain` alignment
5. **Original vs Annotated video toggle** — `getVideoSource()` + `toggleVideoSource()` with playback position preservation
6. **Show/hide annotations button** — `showAnnotations` toggle
7. **Window resize handler** — Redraw canvas on resize
8. **Fix bbox format** — Change `getBboxStyle()` from `[x, y, w, h]` to `[x1, y1, x2, y2]`
9. **Unify nav** — Update `+layout.svelte` nav to include all 8 routes

### Out of Scope
- Rewriting `/player` from scratch
- Design system migration for the player page
- New features not in `/video-player`

## Architecture

No architectural changes. This is a pure feature port from one Svelte component to another. Both files are ~1700 lines with identical structure (state → functions → markup → styles).

### Lines to Port
- ~20 lines: state variables (`annotationCanvas`, `showAnnotations`, `showOriginalVideo`)
- ~30 lines: `getVideoRenderRect()` function
- ~70 lines: `drawAnnotations()` function with color palette
- ~20 lines: `getVideoSource()` + `toggleVideoSource()`
- ~5 lines: reactive statement + resize listener
- ~15 lines: `<canvas>` element + toggle buttons in markup
- ~15 lines: CSS for `.annotation-canvas`
- ~5 lines: `getBboxStyle()` fix

Total: ~180 lines of additions/changes to `/player`

## Priority

**High** — the bbox bug means face flagging targets are misaligned in production, and the annotation overlay is the primary way users see face recognition results.
