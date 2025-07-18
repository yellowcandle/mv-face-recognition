---
inclusion: always
---

# Technical Guidelines

## Code Style & Conventions

### TypeScript/JavaScript
- Use TypeScript for all frontend code with strict type checking
- Prefer `const` over `let`, avoid `var` entirely
- Use async/await over Promise chains
- Export types and interfaces explicitly
- Follow SvelteKit file-based routing conventions

### Python
- Use Python 3.11+ with `uv` for dependency management
- Follow PEP 8 style guidelines with 88-character line limit
- Use type hints for all function parameters and return values
- Prefer pathlib over os.path for file operations
- Use dataclasses or Pydantic models for structured data

### Error Handling
- Always handle errors gracefully with try/catch blocks
- Log errors with context using structured logging
- Return meaningful error messages to users
- Use proper HTTP status codes in API responses

## Architecture Patterns

### Frontend (SvelteKit)
- Use stores for shared state management
- Keep components small and focused on single responsibilities
- Implement proper loading states and error boundaries
- Use TypeScript interfaces for API response types
- Test components with Vitest, E2E scenarios with Playwright

### Backend Processing (Python)
- Separate concerns: video processing, face detection, metadata generation
- Use configuration files (YAML) for processing parameters
- Implement proper logging with different levels (DEBUG, INFO, ERROR)
- Process videos in chunks to manage memory usage
- Always preserve original audio tracks during processing

### API Layer (Cloudflare Workers)
- Keep worker functions lightweight and stateless
- Use proper CORS headers for frontend integration
- Implement rate limiting and error handling
- Cache responses appropriately using Cloudflare KV
- Return consistent JSON response formats

## Development Workflow

### Essential Commands
```bash
# Frontend development
cd frontend && npm run dev

# Python processing
cd mvp-processor && python src/process_video.py --input ../source/videos/video.mp4

# Full deployment pipeline
node scripts/run-full-pipeline.js

# Run tests before commits
cd frontend && npm run test && npm run test:e2e
cd mvp-processor && pytest tests/unit/ -v
```

### Testing Requirements
- Write unit tests for all utility functions
- Test API endpoints with mock data
- Include E2E tests for critical user flows
- Maintain >80% code coverage for core modules
- Test video processing with sample files before production

## Critical Dependencies

### Face Recognition Pipeline
- **InsightFace buffalo_l model**: Use for face detection with GPU acceleration
- **ChromaDB**: Store and query 95 contestant face embeddings
- **OpenCV**: Frame extraction and video processing
- **FFmpeg**: Audio preservation during video encoding

### Deployment Stack
- **Cloudflare Workers**: Edge computing with global distribution
- **Cloudflare R2**: Video storage with CDN integration
- **Cloudflare KV**: Metadata storage with edge caching
- **Wrangler CLI**: Deployment and local development

## Common Pitfalls to Avoid

- Never process entire videos in memory - use streaming/chunking
- Always validate file paths and handle missing files gracefully
- Don't hardcode API endpoints - use environment variables
- Avoid blocking operations in Cloudflare Workers (use async patterns)
- Don't commit large files to git - use Git LFS for videos/models
- Always test with actual video files, not just mock data

## Performance Guidelines

- Process every 5th frame for dense metadata (6x performance improvement)
- Use GPU acceleration when available (Apple Silicon/NVIDIA CUDA)
- Implement proper caching strategies for face embeddings
- Optimize video encoding settings for web delivery
- Use Cloudflare's edge network for global content delivery