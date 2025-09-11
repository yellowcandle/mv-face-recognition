# MV Face Recognition - Deployment Guidelines

## Critical Deployment Warnings

### ⚠️ NEVER BREAK THESE CONFIGURATIONS ⚠️

#### 1. Frontend Structure (RESOLVED - January 2025)
- **Working State**: SvelteKit 2.x in mvp-processor/ directory
- **Build Command**: `cd mvp-processor && npm run build`
- **Asset Structure**: `mvp-processor/build/_app/` directory
- **Entry Point**: SvelteKit routes, NOT legacy App.svelte
- **NEVER RESTORE**: `src/main.js.backup` or `src/App.svelte.backup`

#### 2. Critical File Protection
- **metadata/contestant_info.csv**: ESSENTIAL - 95 contestant database
  - Maps contestant numbers (1-96) to names and nicknames
  - Required for entire system to function
  - Previously deleted in commit 8348e0b3, restored from git history
  - DO NOT DELETE, MOVE, OR MODIFY without explicit permission

#### 3. Build Configuration Integrity
- **mvp-processor/vite.config.js**: MUST use `sveltekit()` plugin
- **package.json**: Build script MUST work with SvelteKit
- **scripts/update-worker-assets.js**: MUST handle `_app/` directory

## Deployment Workflow

### 1. Pre-Deployment Verification
```bash
# Verify SvelteKit build configuration
cd mvp-processor
grep -q "sveltekit" vite.config.js  # Must return success

# Test build process
npm run build
ls -la build/_app/  # Must contain SvelteKit assets

# Verify critical files exist
test -f ../metadata/contestant_info.csv  # Must exist
```

### 2. Full Deployment Pipeline
```bash
# Complete automated deployment
node scripts/run-full-pipeline.js

# OR manual step-by-step:
cd mvp-processor && npm run build
cd ../scripts && node update-worker-assets.js
cd ../worker && wrangler deploy
```

### 3. Asset Embedding Verification
```bash
# Update worker assets (should show 30+ assets)
node scripts/update-worker-assets.js

# Verify embedding successful
grep -c "STATIC_ASSETS" worker/embedded-assets.js  # Should be > 30
```

### 4. Post-Deployment Testing
```bash
# Test main endpoints
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/" | head -10
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/api/system/status"
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/api/videos"

# Verify routes work
curl -s -o /dev/null -w "%{http_code}" "https://mv-face-recognition-api.herballemon.workers.dev/video-player"  # Should be 200
curl -s -o /dev/null -w "%{http_code}" "https://mv-face-recognition-api.herballemon.workers.dev/analytics"  # Should be 200
```

## Recovery Procedures

### If Deployment Breaks
1. **Check SvelteKit Build**:
   ```bash
   cd mvp-processor && npm run build
   ls -la build/_app/  # Verify _app directory exists
   ```

2. **Verify Asset Embedding**:
   ```bash
   cd scripts && node update-worker-assets.js
   # Should show 30+ assets being embedded
   ```

3. **Test Asset Loading**:
   ```bash
   curl -s -w "HTTP: %{http_code}" "https://mv-face-recognition-api.herballemon.workers.dev/_app/immutable/entry/start.C8A6qoEF.js"
   ```

4. **Redeploy Worker**:
   ```bash
   cd worker && wrangler deploy
   ```

### If Wrong App Deployed
**Symptoms**: Demo VideoPlayer with "[object Object]" instead of functional dashboard

**Fix**:
1. Verify no legacy files restored:
   ```bash
   # These should NOT exist in src/
   test ! -f src/main.js
   test ! -f src/App.svelte
   ```

2. Check SvelteKit configuration:
   ```bash
   cd mvp-processor
   grep -q "@sveltejs/kit" package.json  # Must exist
   grep -q "sveltekit()" vite.config.js  # Must exist
   ```

3. Rebuild and redeploy:
   ```bash
   npm run build
   cd ../scripts && node update-worker-assets.js
   cd ../worker && wrangler deploy
   ```

## Quality Gates

### Pre-Deploy Checklist
- ✅ All tests pass (500+ test cases)
- ✅ Coverage thresholds met (75-90% per component)
- ✅ SvelteKit build successful
- ✅ Asset embedding shows 30+ files
- ✅ Critical files protected (contestant_info.csv)
- ✅ No legacy backup files restored

### Post-Deploy Validation
- ✅ Root URL serves functional dashboard (not demo)
- ✅ All routes accessible (/, /video-player, /analytics)
- ✅ API endpoints return JSON (not HTML)
- ✅ Video player shows actual videos
- ✅ Face recognition data loads correctly

## Emergency Contacts & Resources
- **GitHub Repository**: https://github.com/yellowcandle/mv-face-recognition
- **Cloudflare Dashboard**: Workers & R2 management
- **Deployment URL**: https://mv-face-recognition-api.herballemon.workers.dev
- **CI/CD Pipeline**: GitHub Actions with 5 parallel jobs

This deployment process ensures a production-ready system with comprehensive validation and recovery procedures.