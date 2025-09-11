# MV Face Recognition - Suggested Commands

## Development Commands

### Frontend Development (mvp-processor/)
```bash
cd mvp-processor
npm run dev           # Start development server (SvelteKit)
npm run build         # Production build
npm run check         # TypeScript checking
npm run lint          # ESLint
npm run format        # Prettier formatting
npm run test          # Run unit tests
npm run test:coverage # Run tests with coverage
npm run test:e2e      # Playwright E2E tests
```

### Python Processing
```bash
cd mvp-processor
python main.py        # Main video processing script
pytest tests/         # Run Python tests
pytest tests/unit/ --cov=src  # Unit tests with coverage
flake8 src/           # Python linting
```

### Scripts & Automation
```bash
cd scripts
npm test              # Run script tests
npm run lint          # ESLint for scripts
npm run test:coverage # Coverage reporting
node run-full-pipeline.js  # Full processing pipeline
node setup-environment.js  # Environment setup
```

### Worker API
```bash
cd worker
wrangler dev          # Local development
wrangler deploy       # Deploy to Cloudflare
npm run test:coverage # API tests with Miniflare
```

### System Startup
```bash
./start_all.sh        # Start both backend and frontend
./start_backend.sh    # Backend only
./start_frontend.sh   # Frontend only
```

### Testing & Quality Assurance
```bash
# Frontend tests (85%+ function coverage required)
cd mvp-processor && npm run test:coverage

# Python tests (80%+ line coverage required)
cd mvp-processor && pytest tests/unit/ --cov=src

# Scripts tests (75%+ coverage required)
cd scripts && npm run test:coverage

# Worker tests (90%+ coverage required)
cd worker && npm run test:coverage

# Integration tests
node scripts/run-full-pipeline.js --process-only
```

### Deployment
```bash
# Full deployment pipeline
cd mvp-processor && npm run build
cd ../scripts && node update-worker-assets.js
cd ../worker && wrangler deploy

# Upload assets
node scripts/upload-to-r2.js
node scripts/upload-metadata.js
```

## System Commands (Darwin/macOS)
```bash
# Standard Unix commands work on Darwin
ls -la                # List files
find . -name "*.py"   # Find files
grep -r "pattern" .   # Search in files
git status            # Git operations
```