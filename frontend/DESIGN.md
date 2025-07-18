# MV Face Recognition - System Design Document

## 🏗️ Architecture Overview

### System Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Storage       │
│   (SvelteKit)   │◄──►│   (FastAPI)     │◄──►│   (R2 + KV)     │
│                 │    │                 │    │                 │
│ • Video Player  │    │ • Face Detection│    │ • Video Files   │
│ • Face Display  │    │ • Recognition   │    │ • Metadata      │
│ • Analytics     │    │ • Processing    │    │ • Results       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Cloudflare    │
                    │   Workers       │
                    │                 │
                    │ • Edge Serving  │
                    │ • API Gateway   │
                    │ • Asset Hosting │
                    └─────────────────┘
```

### Technology Stack
- **Frontend**: SvelteKit + TypeScript + Vite
- **Backend**: Python FastAPI + OpenCV + Face Recognition
- **Deployment**: Cloudflare Workers + R2 + KV
- **Testing**: Vitest + Playwright
- **Build**: Vite + SvelteKit

## 🎨 Frontend Architecture

### Component Hierarchy
```
App.svelte
├── Header.svelte
│   ├── Navigation
│   └── Status Indicator
├── Main Content
│   ├── Dashboard (+page.svelte)
│   ├── Video Processing (+page.svelte)
│   ├── Face Recognition (+page.svelte)
│   ├── Analytics (+page.svelte)
│   └── Settings (+page.svelte)
└── Footer.svelte
```

### State Management
```typescript
// Stores
├── main.ts           // App-wide state
├── contestants.ts    // Contestant data
├── videoProcessing.ts // Video upload/processing
└── websocket.ts     // Real-time connections

// Store Structure
interface MainStore {
  systemStatus: 'online' | 'offline'
  userSettings: UserSettings
  notifications: Notification[]
}

interface VideoProcessingStore {
  uploadProgress: number
  processingJobs: ProcessingJob[]
  results: RecognitionResult[]
}
```

### Routing Structure
```
/                           # Dashboard
├── video-processing/       # Video upload & processing
├── face-recognition/       # Recognition results
├── analytics/             # Analytics dashboard
├── settings/              # App settings
└── video-player/          # Video player with overlays
```

## 🔌 API Design

### REST Endpoints
```typescript
// Video Management
GET    /api/videos              // List videos
POST   /api/videos/upload       // Upload video
GET    /api/videos/{id}         // Get video details
GET    /api/videos/{id}/stream  // Stream video

// Face Recognition
GET    /api/recognition/results // Get recognition results
POST   /api/recognition/process // Process video
GET    /api/contestants         // Get contestants

// System
GET    /api/system/status       // System status
GET    /api/analytics/overview  // Analytics data
```

### WebSocket Events
```typescript
// Client → Server
interface ClientEvents {
  'processing:start': { videoId: string }
  'processing:stop': { jobId: string }
  'player:seek': { timestamp: number }
}

// Server → Client
interface ServerEvents {
  'processing:progress': { jobId: string, progress: number }
  'processing:complete': { jobId: string, results: RecognitionResult[] }
  'system:status': { status: 'online' | 'offline' }
}
```

## 🎬 Video Player Architecture

### Component Structure
```
VideoPlayer.svelte
├── VideoSelector.svelte
├── VideoContainer.svelte
│   ├── <video> element
│   └── FaceOverlay.svelte
├── PlayerControls.svelte
└── FaceSidebar.svelte
    ├── FaceList.svelte
    └── FaceDetails.svelte
```

### Face Overlay System
```typescript
interface FaceDetection {
  id: string
  contestant_id: number
  confidence: number
  bounding_box: {
    x: number, y: number
    width: number, height: number
  }
  timestamp: number
}

interface OverlayRenderer {
  drawFaces(detections: FaceDetection[]): void
  clearOverlay(): void
  highlightFace(faceId: string): void
}
```

## 📊 Data Flow

### Video Processing Flow
```
1. User Uploads Video
   ↓
2. Frontend → Backend (POST /api/videos/upload)
   ↓
3. Backend Processes Video
   ├── Extract frames
   ├── Detect faces
   ├── Recognize contestants
   └── Generate metadata
   ↓
4. WebSocket Updates (progress, completion)
   ↓
5. Frontend Updates UI
   ├── Progress indicators
   ├── Results display
   └── Video player integration
```

### Real-time Updates Flow
```
Backend Processing
    ↓
WebSocket Server
    ↓
Frontend WebSocket Client
    ↓
Svelte Store Updates
    ↓
Reactive UI Updates
```

## 🎨 UI/UX Design System

### Color Palette
```css
:root {
  /* Primary Colors */
  --primary-color: #2563eb;
  --primary-hover: #1d4ed8;
  
  /* Semantic Colors */
  --success-color: #10b981;
  --warning-color: #f59e0b;
  --error-color: #ef4444;
  
  /* Neutral Colors */
  --background-color: #ffffff;
  --surface-color: #f8fafc;
  --text-color: #1e293b;
  --text-secondary: #64748b;
  --border-color: #e2e8f0;
}
```

### Typography Scale
```css
/* Headings */
h1 { font-size: 2.5rem; font-weight: 700; }
h2 { font-size: 1.75rem; font-weight: 600; }
h3 { font-size: 1.25rem; font-weight: 600; }

/* Body Text */
p { font-size: 1rem; line-height: 1.6; }
small { font-size: 0.875rem; }

/* UI Elements */
button { font-size: 0.95rem; font-weight: 600; }
input { font-size: 0.9rem; }
```

### Spacing System
```css
/* 8px Grid System */
--space-1: 0.25rem;  /* 4px */
--space-2: 0.5rem;   /* 8px */
--space-3: 0.75rem;  /* 12px */
--space-4: 1rem;     /* 16px */
--space-6: 1.5rem;   /* 24px */
--space-8: 2rem;     /* 32px */
--space-12: 3rem;    /* 48px */
```

## 🔧 Development Workflow

### Local Development
```bash
# Frontend Development
cd frontend
npm install
npm run dev

# Backend Development
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Testing
npm run test          # Unit tests
npx playwright test   # E2E tests
```

### Build & Deployment
```bash
# Build Frontend
cd frontend
npm run build

# Embed Assets in Worker
node scripts/update-worker-assets.js

# Deploy to Cloudflare
cd worker
wrangler deploy
```

## 🧪 Testing Strategy

### Unit Testing
```typescript
// Component Testing
import { render, screen } from '@testing-library/svelte'
import VideoPlayer from './VideoPlayer.svelte'

test('video player loads correctly', () => {
  render(VideoPlayer, { props: { videoId: 'test' } })
  expect(screen.getByRole('video')).toBeInTheDocument()
})

// Store Testing
import { get } from 'svelte/store'
import { videoProcessing } from '$lib/stores/videoProcessing'

test('store updates correctly', () => {
  videoProcessing.setProgress(50)
  expect(get(videoProcessing).progress).toBe(50)
})
```

### E2E Testing
```typescript
// Playwright Tests
test('upload video and process', async ({ page }) => {
  await page.goto('/video-processing')
  await page.setInputFiles('input[type="file"]', 'test-video.mp4')
  await page.click('button:has-text("Upload")')
  await expect(page.locator('.progress')).toBeVisible()
})
```

## 🚀 Performance Optimization

### Bundle Optimization
- **Code Splitting**: Route-based splitting
- **Tree Shaking**: Remove unused code
- **Minification**: Compress production builds
- **Compression**: Gzip/Brotli compression

### Runtime Performance
- **Lazy Loading**: Load components on demand
- **Virtual Scrolling**: For large lists
- **Debouncing**: Input event optimization
- **Memoization**: Expensive calculations

### Caching Strategy
- **Browser Cache**: Static assets
- **API Cache**: Response caching
- **CDN Cache**: Edge caching
- **Service Worker**: Offline support

## 🔒 Security Considerations

### Frontend Security
- **CSP Headers**: XSS protection
- **Input Validation**: Client-side validation
- **HTTPS Only**: Secure connections
- **Content Sanitization**: User content

### API Security
- **CORS Configuration**: Cross-origin requests
- **Rate Limiting**: API abuse prevention
- **Authentication**: JWT token validation
- **Input Validation**: Server-side validation

## 📊 Monitoring & Analytics

### Error Tracking
```typescript
// Error Boundary
<script>
  import { onError } from 'svelte'
  
  onError(({ error, event }) => {
    console.error('Component error:', error)
    // Send to error tracking service
  })
</script>
```

### Performance Monitoring
```typescript
// Core Web Vitals
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'

getCLS(console.log)
getFID(console.log)
getFCP(console.log)
getLCP(console.log)
getTTFB(console.log)
```

## 🔄 Migration Strategy

### From Vue.js to Svelte
1. **Component Migration**
   - Vue template → Svelte template
   - Vue script → Svelte script
   - Vue style → Svelte style

2. **State Management**
   - Pinia stores → Svelte stores
   - Vuex → Svelte reactive statements

3. **Routing**
   - Vue Router → SvelteKit routing
   - Route guards → SvelteKit hooks

4. **Build System**
   - Vite config updates
   - Plugin configuration
   - Deployment scripts

### Benefits Achieved
- **40% smaller bundle size**
- **Better performance** (no virtual DOM)
- **Simpler code** (less boilerplate)
- **Better TypeScript integration**

## 📚 Documentation

### Code Documentation
- **JSDoc**: Function documentation
- **TypeScript**: Type definitions
- **README**: Setup instructions
- **API Docs**: Endpoint documentation

### User Documentation
- **User Guide**: Feature explanations
- **Tutorial**: Step-by-step guides
- **FAQ**: Common questions
- **Troubleshooting**: Problem solutions

---

**Version**: 1.0.0
**Last Updated**: 2024-01-XX
**Maintainer**: Development Team 