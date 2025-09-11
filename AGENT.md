# MV Face Recognition - Agent Instructions

## Build/Test Commands
- **Frontend**: `cd frontend && npm run build/test:coverage/test:e2e/lint/format`
- **Python**: `cd mvp-processor && pytest tests/unit/ -v --cov=src` (80%+ coverage required)
- **Scripts**: `cd scripts && npm test` (75%+ coverage required)
- **Worker**: `cd worker && npm run test:coverage/deploy` (90%+ coverage required)
- **Single test**: `pytest tests/unit/test_video_processor.py::TestVideoProcessor::test_extract_frames -v`

## Architecture
- **Frontend**: SvelteKit 2.x with TypeScript, Vite build, static adapter
- **Backend**: Python video processing with OpenCV, face-recognition, ChromaDB
- **Worker**: Cloudflare Worker API with 21 endpoints, R2 storage, KV store
- **Database**: ChromaDB for face embeddings, contestant_info.csv (96 records)
- **Deployment**: Cloudflare Workers, R2 buckets, automated pipeline scripts

## Code Style
- **TypeScript**: Use TypeScript strict mode, prefer interfaces over types
- **Python**: Follow PEP 8, use type hints, pytest fixtures for testing
- **Imports**: Use absolute imports, group by external/internal/relative
- **Error handling**: Use try/catch in TS, proper exception handling in Python
- **Naming**: kebab-case for files, camelCase for variables, PascalCase for classes

## Critical Rules from CLAUDE.md
- NEVER delete metadata/contestant_info.csv (required for system to function)
- NEVER restore .backup files (src/main.js.backup, src/App.svelte.backup)
- Use SvelteKit build system, NOT legacy Vite setup
- Always run comprehensive tests before deployment
- Document work in DESIGN.md, maintain coverage thresholds
