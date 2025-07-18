# Parallel Testing System

This directory contains the parallel testing system for the MV Face Recognition project, consisting of two specialized testing agents that run simultaneously to test the backend and frontend components.

## Overview

The parallel testing system provides:
- **Backend Testing Agent**: Tests the Cloudflare Worker API endpoints
- **Frontend Testing Agent**: Tests the SvelteKit frontend with real backend integration
- **Parallel Test Runner**: Orchestrates both agents to run simultaneously

## Usage

### Quick Start

Run all tests in parallel:
```bash
cd scripts
npm run test:parallel
```

### Individual Agents

Run backend tests only:
```bash
cd scripts
npm run test:backend
```

Run frontend tests only:
```bash
cd scripts
npm run test:frontend
```

### Direct Script Execution

```bash
# Run parallel tests
./scripts/test-parallel.js

# Run backend agent
./scripts/test-backend-agent.js

# Run frontend agent
./scripts/test-frontend-agent.js
```

## System Architecture

### Backend Testing Agent (`test-backend-agent.js`)
- Starts Cloudflare Worker in development mode
- Runs comprehensive API tests for all endpoints
- Performs load testing and performance monitoring
- Logs results to `logs/test-results/backend-*.json`

### Frontend Testing Agent (`test-frontend-agent.js`)
- Waits for backend to be ready
- Starts SvelteKit frontend development server
- Runs integration tests against real backend APIs
- Executes E2E tests with Playwright
- Logs results to `logs/test-results/frontend-*.json`

### Parallel Test Runner (`test-parallel.js`)
- Orchestrates both agents simultaneously
- Handles coordination and communication
- Generates unified test reports
- Updates backlog tasks with results
- Logs combined results to `logs/test-results/parallel-*.json`

## Test Results

All test results are stored in the `logs/test-results/` directory:

- `backend-summary.json` - Backend test summary
- `frontend-summary.json` - Frontend test summary
- `overall-summary.json` - Combined test summary
- `backend-{timestamp}.json` - Detailed backend test results
- `frontend-{timestamp}.json` - Detailed frontend test results
- `parallel-{timestamp}.json` - Detailed parallel runner results

## API Endpoints Tested

### Backend Agent Tests
- `GET /api/system/status` - System health check
- `GET /api/videos` - Video listing
- `GET /api/contestants` - Contestant data
- `GET /api/recognition/results` - Face recognition results
- `GET /api/analytics/overview` - Analytics data
- `GET /api/settings` - System settings

### Frontend Agent Tests
- Frontend-Backend connection validation
- Video data loading integration
- Contestant data integration
- Recognition results display
- Analytics data integration
- Complete E2E user workflows

## Configuration

### Environment Variables

Both agents support these environment variables:
- `NODE_ENV=test` - Set test environment
- `BACKEND_URL` - Backend URL (default: http://localhost:8787)
- `FRONTEND_URL` - Frontend URL (default: http://localhost:5173)

### Timeouts

- Backend startup: 30 seconds
- Frontend startup: 45 seconds
- Health check: 30 attempts with 1-second delays
- E2E tests: 5 minutes

## Monitoring

The system provides real-time monitoring:
- Process output from both agents
- Test progress updates
- Performance metrics
- Error tracking
- Status notifications

## Troubleshooting

### Common Issues

1. **Backend startup failure**: Check if port 8787 is available
2. **Frontend startup failure**: Check if port 5173 is available
3. **Backend health check timeout**: Verify Cloudflare Worker configuration
4. **E2E test failures**: Check Playwright configuration and browser setup

### Debugging

Enable verbose logging:
```bash
DEBUG=* npm run test:parallel
```

Check individual agent logs:
```bash
# Backend agent logs
tail -f logs/test-results/backend-*.json

# Frontend agent logs
tail -f logs/test-results/frontend-*.json
```

## Integration with Backlog

The parallel test runner automatically updates backlog tasks:
- Task 012: Backend Testing Agent
- Task 013: Frontend Integration Testing Agent  
- Task 014: Parallel Test Runner

Tasks are marked as "Done" when all tests pass successfully.

## Performance Monitoring

The system includes performance monitoring:
- Response time tracking
- Load testing capabilities
- Resource usage monitoring
- Success rate calculations

## Future Enhancements

Potential improvements:
- Docker containerization for isolated testing
- CI/CD pipeline integration
- Test result visualization dashboard
- Automated test report generation
- Slack/email notifications for test results
