- NO NEED TO IMPLEMENT WEBCAM face recognition
- Only process files in /source/videos directory, no webcam processing required
- pls! do not! overwrite my README.md !!!
- you MUST document your work in DESIGN.md, the DESIGN.md MUST fit in your context window.
- document your TODOs in DESIGN.md

# CRITICAL FILES - DO NOT DELETE
## ⚠️ ABSOLUTELY CRITICAL - DO NOT DELETE THESE FILES ⚠️

- **metadata/contestant_info.csv** - ESSENTIAL contestant database mapping (編號,姓名,暱稱,年齡)
  - **LOCATION: /metadata/contestant_info.csv** 
  - Maps contestant numbers (1-96) to names and nicknames
  - Used by face recognition system to identify contestants
  - Contains 96 contestant records with Chinese names and nicknames
  - Previously deleted in commit 8348e0b3, restored from git history
  - **THIS FILE IS REQUIRED FOR THE ENTIRE SYSTEM TO FUNCTION**
  - **DO NOT DELETE, MOVE, OR MODIFY WITHOUT EXPLICIT USER PERMISSION**
  - **VIDEO PLAYER AND FACE RECOGNITION DEPEND ON THIS FILE**

# CRITICAL DEPLOYMENT CONFIGURATION - DO NOT BREAK
## ⚠️ SVELTEKIT vs LEGACY APP CONFLICTS - RESOLVED ⚠️

**CRITICAL ISSUE RESOLVED (July 10, 2025):**
The deployment was serving the WRONG APPLICATION due to build configuration conflicts.

### ✅ CORRECT CONFIGURATION (Current Working State):
- **Frontend Framework**: SvelteKit 2.x with TypeScript
- **Build Command**: `npm run build` (uses SvelteKit via `vite build --mode production`)
- **Entry Point**: `src/app.html` + SvelteKit routes (NOT `src/main.js`)
- **Asset Structure**: `build/_app/` directory with 36 embedded assets
- **Worker Deployment**: Uses `scripts/update-worker-assets.js` for SvelteKit structure

### ❌ LEGACY CONFIGURATION (Backed Up, Do Not Restore):
- **Old Files**: `src/main.js.backup`, `src/App.svelte.backup`
- **Old Structure**: Vite + Svelte with `assets/` directory (only 3 assets)
- **Problem**: Showed demo VideoPlayer with placeholder text instead of functional video player

### 🚨 CRITICAL WARNINGS FOR FUTURE AI ASSISTANTS:

1. **NEVER RESTORE BACKUP FILES**: 
   - `src/main.js.backup` and `src/App.svelte.backup` are legacy files
   - Restoring them will break the working SvelteKit deployment
   - The working app uses SvelteKit routes, not the old App.svelte

2. **BUILD CONFIGURATION IS CRITICAL**:
   - `vite.config.js` MUST use `sveltekit()` plugin, NOT `svelte()` plugin
   - `package.json` build script MUST work with SvelteKit structure
   - Asset embedding script MUST handle `_app/` directory, not just `assets/`

3. **DEPLOYMENT VERIFICATION**:
   - Cloudflare Workers should serve 36 assets (SvelteKit), not 3 (legacy Vite)
   - Root URL should serve functional video player, not demo placeholder
   - All routes (/, /video-player, /settings, etc.) should work

4. **IF DEPLOYMENT BREAKS**:
   - Check that SvelteKit is being built (not legacy Vite app)
   - Verify asset embedding includes `_app/` directory
   - Ensure no conflicts between old and new app files
   - Test that video player shows actual videos, not "[object Object]"

### 📋 WORKING DEPLOYMENT CHECKLIST:
- ✅ `vite.config.js` uses `sveltekit()` plugin
- ✅ `frontend/build/` contains `_app/` directory with 30+ files
- ✅ `scripts/update-worker-assets.js` embeds 36+ assets
- ✅ Video player route shows functional interface, not placeholder
- ✅ Video dropdown shows video names, not "[object Object]"
- ✅ All API endpoints return proper JSON responses
- ✅ WebSocket connections work for real-time features

### 🔧 RECOVERY COMMANDS (If Deployment Breaks):
```bash
# 1. Ensure correct SvelteKit build
cd frontend && npm run build

# 2. Verify _app directory exists
ls -la build/_app/

# 3. Update worker assets (should show 30+ assets)
cd .. && node scripts/update-worker-assets.js

# 4. Deploy to Cloudflare Workers
cd worker && wrangler deploy

# 5. Test deployment
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/" | head -10
```

## ⚠️ WARNING TO FUTURE AI ASSISTANTS ⚠️
- **NEVER DELETE metadata/contestant_info.csv**
- **NEVER RESTORE src/main.js.backup or src/App.svelte.backup**
- **ALWAYS CHECK CLAUDE.md BEFORE MAKING BUILD CONFIGURATION CHANGES**
- **VERIFY SVELTEKIT DEPLOYMENT AFTER ANY FRONTEND CHANGES**
- **THIS DEPLOYMENT WAS BROKEN ONCE - DO NOT REPEAT CONFIGURATION MISTAKES**
- **THE USER EXPECTS A WORKING VIDEO PLAYER, NOT DEMO PLACEHOLDERS**