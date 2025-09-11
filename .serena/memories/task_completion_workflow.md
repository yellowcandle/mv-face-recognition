# MV Face Recognition - Task Completion Workflow

## When a Task is Completed

### 1. Code Quality Checks (MANDATORY)

#### Frontend Changes (mvp-processor/)
```bash
cd mvp-processor
npm run lint          # ESLint checking
npm run check         # TypeScript validation
npm run test:coverage # Unit tests (85%+ functions required)
npm run build         # Verify build succeeds
```

#### Python Changes
```bash
cd mvp-processor
flake8 src/ --count --select=E9,F63,F7,F82  # Critical errors
pytest tests/unit/ --cov=src --cov-report=term  # Unit tests (80%+ lines required)
python -m mypy src/   # Type checking (if mypy configured)
```

#### Scripts Changes
```bash
cd scripts
npm run lint          # ESLint for Node.js scripts
npm run test:coverage # Jest testing (75%+ coverage required)
```

#### Worker Changes
```bash
cd worker
npm run lint          # ESLint for Worker code
npm run test:coverage # Vitest + Miniflare testing (90%+ coverage required)
```

### 2. Integration Testing

#### Full Pipeline Test
```bash
# Test complete video processing pipeline
node scripts/run-full-pipeline.js --process-only

# Verify outputs exist
test -f processed_videos/*_720p.mp4
test -f metadata/*_metadata.json
test -f thumbnails/*_thumb.jpg
```

#### Frontend Build Verification
```bash
cd mvp-processor
npm run build
# Verify build/ directory contains _app/ structure

cd ../scripts
node update-worker-assets.js
# Verify 30+ assets embedded in worker
```

### 3. Deployment Testing (if applicable)

#### Worker Deployment
```bash
cd worker
wrangler deploy --dry-run  # Verify deployment config
```

#### Test API Endpoints
```bash
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/api/system/status"
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/api/videos"
```

### 4. Documentation Updates

#### Update DESIGN.md (MANDATORY)
- Document any architectural changes
- Update API specifications if endpoints changed
- Add new component documentation
- Keep within context window limits

#### Update README.md (if major changes)
- Only if explicitly requested by user
- Never overwrite without permission

### 5. Git Operations

#### Commit Guidelines
- Use conventional commit format
- Include descriptive messages
- Reference issue numbers if applicable

```bash
git add .
git commit -m "feat: add enhanced face recognition overlay"
git push origin feature/enhanced-recognition
```

### 6. Critical Warnings

#### NEVER Skip These Steps:
1. **Coverage thresholds** - All components have minimum requirements
2. **Build verification** - Must succeed before deployment
3. **DESIGN.md updates** - Required for all significant changes
4. **Integration tests** - Verify full system functionality

#### Files to NEVER Modify:
- **metadata/contestant_info.csv** - Critical system data
- **README.md** - Without explicit permission
- **Build configurations** - Unless fixing deployment issues

### 7. CI/CD Verification

#### GitHub Actions
- All 5 test jobs must pass:
  - frontend-tests
  - python-tests  
  - scripts-tests
  - worker-tests
  - integration-tests

#### Local CI Simulation
```bash
# Run subset of CI checks locally
cd mvp-processor && npm run test:coverage && pytest tests/unit/ --cov=src
cd ../scripts && npm run test:coverage
cd ../worker && npm run test:coverage
```

This workflow ensures production-ready code quality and system reliability.