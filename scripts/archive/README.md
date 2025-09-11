# Archived Scripts

This directory contains scripts from the previous Docker/Fly.io deployment architecture. These scripts are preserved for reference but are no longer used in the current Cloudflare Workers + Modal.com architecture.

## Archived Files

### Local Processing Scripts
- **`batch_process_videos.py`** - Original local batch processing script
- **`process_videos_local.sh`** - Shell wrapper for local video processing

### Application Startup Scripts  
- **`start_app.sh`** - Combined application startup (backend + frontend)
- **`start_backend.sh`** - FastAPI backend server startup
- **`start_frontend.sh`** - SvelteKit frontend development server

## Migration Notes

These scripts were replaced by the new architecture:

- **Local processing** → **Modal.com cloud processing** (`modal_batch_processor.py`, `modal_rich_parallel.py`)
- **FastAPI backend** → **Cloudflare Workers** (serverless functions)
- **SvelteKit dev server** → **Static build deployment** to Cloudflare Pages
- **Local file storage** → **Cloudflare R2** for videos and **KV** for metadata

## If You Need to Restore

If you need to temporarily revert to the old architecture:

1. Copy the required scripts back to the parent directory
2. Ensure your local environment has the required dependencies
3. Update any path references that may have changed
4. Note that some features may not work without additional configuration

## Removal Timeline

These scripts may be permanently removed in a future cleanup once the new architecture is fully stable and tested.