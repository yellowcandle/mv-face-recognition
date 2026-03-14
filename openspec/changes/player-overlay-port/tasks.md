# Tasks: Player Overlay Port

## T1: Fix bbox format bug ✅
- **File**: `mvp-processor/src/routes/player/+page.svelte`
- Changed `getBboxStyle()` from `[x, y, w, h]` to `[x1, y1, x2, y2]`
- Fixed `extractFaceThumbnail()` to use same format
- Added letterbox offset via `getVideoRenderRect()`

## T2: Add canvas annotation overlay ✅
- **File**: `mvp-processor/src/routes/player/+page.svelte`
- Added `annotationCanvas` binding + `<canvas>` element
- Ported `getVideoRenderRect()` (letterbox offset calculation)
- Ported `drawAnnotations()` with 10-color palette + HiDPI scaling
- Added reactive redraw + window resize listener
- Added `.annotation-canvas` CSS (z-index: 1, above video, below hit targets)

## T3: Add original vs annotated video toggle ✅
- **File**: `mvp-processor/src/routes/player/+page.svelte`
- Added `showOriginalVideo` state
- Ported `getVideoSource()` + `toggleVideoSource()` (preserves playback position)
- Changed video `src` from hardcoded to `{getVideoSource()}`
- Added toggle button in detection bar

## T4: Add show/hide annotations button ✅
- **File**: `mvp-processor/src/routes/player/+page.svelte`
- Added "Boxes ON/OFF" toggle in detection bar
- Calls `drawAnnotations()` on toggle

## T5: Unify navigation ✅
- **File**: `mvp-processor/src/routes/+layout.svelte`
- Updated from 5 items to 8: Dashboard, Player, Contestants, Ingestion, Analytics, Flagging, ---separator---, Processing, Admin
- Fixed `NavigationLink` usage to pass individual props instead of `{item}` object
- Added `.nav-separator` divider between user and operational routes
