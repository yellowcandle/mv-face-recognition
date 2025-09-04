Project: mv-face-recognition
Purpose: Production-ready video processing and face recognition system for MV videos with SvelteKit frontend, Cloudflare Workers backend, and an optimized Python processing pipeline.
Tech stack: Python 3.9+, SvelteKit 2.x (TypeScript), Cloudflare Workers, R2 + KV, InsightFace/ChromaDB/OpenCV, FFmpeg, Modal for GPU jobs, Node.js for frontend and scripts.
Code style: Python with type hints, docstrings, tests via pytest; frontend TypeScript + Svelte; linting via ruff, eslint, formatting via prettier.
Key commands:
- Frontend: `cd frontend && npm install && npm run dev` / `npm run build` / `npm run test:coverage`
- Processor: `cd mvp-processor && pip install -r requirements.txt && python src/process_video.py --input ../source/videos/video.mp4`
- Worker: `cd worker && npm install && wrangler dev` / `wrangler deploy`
- Tests: `cd mvp-processor && pytest` ; `cd frontend && npm run test:coverage`
Repo structure: frontend/, worker/, mvp-processor/, scripts/, metadata/, source/ (photos/videos), processed_videos/, docs/.
Guidelines: Do not delete metadata/contestant_info.csv; prefer editing existing files; document work in DESIGN.md; avoid overwriting README.md.
