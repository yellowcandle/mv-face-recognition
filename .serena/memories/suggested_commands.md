Development & common commands for mv-face-recognition

Project setup:
- `git clone <repo>`
- `cd mv-face-recognition`

Frontend (SvelteKit):
- `cd frontend && npm install`
- `npm run dev` — start dev server
- `npm run build` — build production
- `npm run preview` — preview build
- `npm run test:coverage` — run tests with coverage
- `npm run lint` — run eslint
- `npm run format` — run prettier

Processor (Python):
- `cd mvp-processor && python -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt` (or optional groups: `pip install -r requirements.txt; pip install .[acceleration,cloud]`)
- `python src/process_video.py --input ../source/videos/<file>.mp4 --output processed/`
- `pytest tests/` — run Python tests

Worker (Cloudflare):
- `cd worker && npm install`
- `wrangler dev` — local worker dev
- `wrangler deploy` — deploy to Cloudflare

Utilities & verification:
- `node scripts/update-worker-assets.js` — embed frontend build into worker
- `node scripts/upload-to-r2.js --dir processed_videos/` — upload processed videos to R2
- `python mvp-processor/src/check_embeddings.py` — validate embeddings
- `python mvp-processor/src/validate_contestants.py` — validate contestant CSV mapping

Performance & debugging:
- `python mvp-processor/src/enable_optimization.py --input <video>` — enable optimized pipeline
- `python analyze_embeddings.py` — analyze embedding distributions
- `ffprobe <file>` — inspect video properties
- `wrangler whoami` — verify Cloudflare auth

Notes:
- NEVER delete `metadata/contestant_info.csv`.
- Always run tests before deployment.
