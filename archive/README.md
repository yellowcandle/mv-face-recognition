# Archive Directory

This directory contains archived components and code from the MV Face Recognition project that are no longer actively used but preserved for reference.

## Contents

### `/frontend-vue/` - Legacy Vue.js Frontend
**Archived:** July 8, 2025  
**Reason:** Replaced by SvelteKit frontend for Cloudflare Workers deployment

**Original Features:**
- Vue 3 with Composition API and TypeScript
- Vuetify Material Design components
- Comprehensive component architecture
- API service layer with mock support
- Routing with Vue Router

**Architecture:**
- Designed for traditional server deployment
- Required proxy configuration for API routing
- Not optimized for static hosting or serverless deployment

**Migration Notes:**
- All functionality has been reimplemented in the SvelteKit frontend
- Component patterns and store logic were adapted for Svelte
- API service patterns were preserved in the new architecture

**Restoration:**
If you need to restore the Vue.js frontend:
1. Copy contents back to `/frontend/`
2. Install dependencies: `npm install`
3. Update API endpoints for current backend
4. Configure build process for deployment target

### Migration History
- **July 7, 2025**: SvelteKit frontend completed and deployed
- **July 8, 2025**: Vue.js frontend archived as legacy
- **Current**: SvelteKit is the active frontend at `/frontend-svelte/`

## Notes
- Node modules are excluded from archive (run `npm install` if restoring)
- All configuration files and source code are preserved
- Documentation and README files maintained for reference