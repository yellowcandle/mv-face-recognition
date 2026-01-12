# TODO

## Pending

### Priority 1: Production Modal Integration (January 2026)

#### Worker Backend - Modal API Integration
- [ ] Add `MODAL_JOBS` KV namespace binding to wrangler.toml
- [ ] Add `MODAL_TOKEN` secret for Modal API authentication
- [ ] Integrate Worker Modal routes into main index.ts router
- [ ] Replace simulated Modal execution with actual Modal API calls
- [ ] Add job result persistence to R2 bucket

#### Modal Script Enhancements
- [ ] Add HTTP webhook endpoint to modal_hf_processor.py for job status callbacks
- [ ] Implement job progress reporting via Modal's `modal.web_endpoint`
- [ ] Add structured JSON output for job results parsing

**Context**: Frontend Modal integration UI is complete. Backend needs actual Modal API integration to replace simulated job execution.

### Priority 2: System Improvements

#### Automatic Reprocessing Pipeline
- [ ] Implement Cloudflare Queue for embedding update triggers
- [ ] Create scheduled Cron job for batch reprocessing
- [ ] Add webhook endpoint for HuggingFace dataset updates
- [ ] Implement video reprocessing after embedding changes

#### Error Handling & Monitoring
- [ ] Add Sentry/error tracking integration
- [ ] Implement job failure retry logic with exponential backoff
- [ ] Add alerting for failed processing jobs
- [ ] Create admin dashboard for job monitoring

#### Performance Optimization
- [ ] Implement video chunking for files >2GB to prevent OOM errors during processing
- [ ] Add GPU utilization monitoring and auto-scaling thresholds in Modal containers
- [ ] Implement Redis-based caching for face recognition results (reduce ChromaDB queries by 60%)
- [ ] Optimize ChromaDB queries with proper indexing on contestant IDs and timestamps
- [ ] Add parallel video processing pipeline with configurable worker counts

#### Security & Compliance
- [ ] Conduct comprehensive security audit using OWASP ZAP on all 21 API endpoints
- [ ] Implement API rate limiting using Cloudflare Workers rate limiting features
- [ ] Create data retention and privacy compliance framework (GDPR-like policies)
- [ ] Enhance access control with role-based permissions (admin, operator, viewer)
- [ ] Audit and strengthen input validation across all API endpoints

### Priority 3: Modal Video Processing Enhancements

#### Batch Processing
- [ ] Frontend: Multi-file upload component with drag-and-drop
- [ ] Backend: Batch job creation endpoint
- [ ] Modal: Parallel video processing with `starmap()`
- [ ] Progress tracking for batch jobs (individual + overall)

#### Result Notifications
- [ ] Email notification service (SendGrid/Resend integration)
- [ ] Webhook callback system for external integrations
- [ ] In-app notification system with bell icon
- [ ] Slack/Discord integration (optional)

#### User Experience & Accessibility
- [ ] Optimize video player for mobile devices with touch controls and responsive design
- [ ] Achieve WCAG 2.1 AA accessibility compliance across all components
- [ ] Implement internationalization (i18n) framework for multi-language support
- [ ] Add offline functionality with service workers for cached video metadata
- [ ] Convert to Progressive Web App (PWA) with offline capabilities

#### Monitoring & Observability
- [ ] Integrate Application Performance Monitoring (DataDog/New Relic) for production metrics
- [ ] Implement real-time error tracking with Sentry for both frontend and backend
- [ ] Create usage analytics dashboard for processing jobs, API usage, and system performance
- [ ] Add comprehensive health checks with dependency monitoring (ChromaDB, R2, KV)
- [ ] Implement log aggregation pipeline with structured logging and analysis

### Priority 4: Testing & Quality Assurance

#### Modal Integration Tests
- [ ] Unit tests for job management API endpoints
- [ ] Integration tests for Modal job lifecycle
- [ ] E2E tests for processing page UI
- [ ] Load testing for concurrent job handling

#### CI/CD Pipeline Updates
- [ ] Add Modal deployment to GitHub Actions
- [ ] Automated KV namespace setup for preview deployments
- [ ] Staging environment with separate Modal app

#### Developer Experience
- [ ] Auto-generate OpenAPI/Swagger documentation from TypeScript interfaces
- [ ] Develop SDK/Client library for external integrations with face recognition API
- [ ] Create improved local development setup with Docker Compose for all services
- [ ] Add advanced debugging tools with profiling for video processing pipeline
- [ ] Build component library documentation site with live examples

#### Infrastructure & DevOps
- [ ] Implement multi-region Cloudflare Workers deployment for global latency reduction
- [ ] Create automated backup and disaster recovery procedures for R2 and KV
- [ ] Add cost optimization monitoring and alerts for cloud resources
- [ ] Develop Infrastructure as Code using Terraform for reproducible deployments
- [ ] Implement blue-green deployment pipeline for zero-downtime updates

### Priority 5: Documentation & DevX

#### Developer Documentation
- [ ] Modal integration setup guide
- [ ] API documentation for job management endpoints
- [ ] Troubleshooting guide for common issues
- [ ] Architecture diagram updates

#### Data Management
- [ ] Implement automated data retention policies for processed videos and metadata
- [ ] Create database migration and versioning system for ChromaDB schemas
- [ ] Build data quality assurance pipelines for embedding consistency
- [ ] Add automated backup verification and integrity checking
- [ ] Develop data archiving strategies for long-term storage optimization

#### Advanced Testing & Quality Assurance
- [ ] Implement load testing for 100+ concurrent video processing jobs
- [ ] Conduct security penetration testing on Modal integration endpoints
- [ ] Add performance regression testing with automated alerts
- [ ] Implement automated accessibility testing with axe-core integration
- [ ] Create cross-browser compatibility testing suite for video player

---

## In Progress

### Modal-Frontend Integration (PR #29)
- [x] Frontend API routes for job management
- [x] Enhanced processing page with dual modes
- [x] Real-time job monitoring via WebSocket
- [x] Worker backend structure (pending actual Modal integration)
- [ ] **Pending merge and production testing**

---

## Completed

### Completed (December 2025 - Continued)
- [x] **Video Processing Pipeline Optimization** (Phase 1)
  - [x] Frame difference detection (3 methods: histogram, MSE, structural)
  - [x] Face tracking across frames (IoU-based matching)
  - [x] Batch face recognition module
  - [x] Metadata compression (delta encoding + gzip)
  - [x] Confidence-based filtering
  - [x] Frame optimizer utility

### Completed (December 2025 - Frontend)
- [x] Complete design system refactoring (7 components, 112 spacing tokens)
- [x] All TypeScript/svelte-check errors resolved (0 errors)
- [x] Reusable component library with design tokens

### Completed (December 2025 - Initial)
- [x] Implement Cloudflare Zero Trust for Admin UI
- [x] Admin UI: YouTube video ingestion
- [x] Batch flagging for multiple faces
- [x] Face thumbnail extraction for flagged faces
- [x] Embedding comparison visualization
- [x] Flagging approval workflow for admins
- [x] Face flagging system and HuggingFace XET integration
- [x] Modal cloud processing with HuggingFace sync
- [x] Pipeline documentation
- [x] Worker: migrate to TypeScript entrypoint (wrangler main=src/index.ts)
- [x] Backend: replace remaining print() usage with logging
- [x] Repo cleanup: archive/move legacy root scripts (gradio, debug, benchmarks, legacy video_processor)
- [x] Python: rename src/logging.py -> src/secure_logging.py (avoid shadowing stdlib logging; enable ty)

### Completed (January 2026)
- [x] **Modal-Frontend Integration** - Complete cloud processing control from web UI
  - [x] Frontend API routes for job management (trigger, status, cancel, list)
  - [x] Enhanced processing page with dual modes (Initial & Embedding Update)
  - [x] Real-time job monitoring via WebSocket
  - [x] Progress bars and visual status indicators
  - [x] Job cancellation support
  - [x] Worker backend with KV-based job persistence
  - [x] Integration with existing Modal scripts (modal_hf_processor.py)

### Completed (July 2025)
- [x] Comprehensive video player with face recognition overlays
- [x] SvelteKit migration with proper routing
- [x] Critical deployment fixes (SvelteKit vs legacy Vite conflicts)
- [x] All frontend routes working (/, /video-player, /face-recognition, /analytics, /settings)
- [x] 21 API endpoints functional
