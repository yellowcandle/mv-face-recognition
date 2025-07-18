# MV Face Recognition - Frontend Development Notes

## 🚀 Deployment & Production

### Cloudflare Workers Deployment
- **Frontend**: SvelteKit app deployed to Cloudflare Workers
- **Backend**: Python FastAPI backend (separate deployment)
- **Assets**: Static assets embedded in worker via `scripts/update-worker-assets.js`
- **Domain**: Production domain configured in Cloudflare

### Build Process
1. `cd frontend && npm run build` - Build SvelteKit app
2. `node scripts/update-worker-assets.js` - Embed assets in worker
3. `cd worker && wrangler deploy` - Deploy to Cloudflare

### Environment Configuration
- API proxy configured in `vite.config.js` for development
- Production API endpoints configured in worker
- WebSocket connections for real-time updates

## 🧪 Testing Strategy

### Unit Tests
- **Framework**: Vitest for fast unit testing
- **Coverage**: V8 coverage reporting
- **UI**: Vitest UI for visual test runner
- **Location**: `frontend/tests/` directory

### E2E Tests
- **Framework**: Playwright for browser testing
- **Configuration**: `playwright.config.ts`
- **Reports**: HTML reports in `playwright-report/`

### Test Commands
```bash
npm run test          # Run unit tests
npm run test:ui       # Run tests with UI
npm run test:coverage # Run with coverage
npx playwright test   # Run E2E tests
```

## 🔧 Development Setup

### Prerequisites
- Node.js 18+
- npm/yarn/pnpm
- Git

### Quick Start
```bash
cd frontend
npm install
npm run dev
```

### Development Workflow
1. **Start Development**: `npm run dev`
2. **Type Checking**: `npm run check`
3. **Linting**: `npm run lint`
4. **Formatting**: `npm run format`
5. **Testing**: `npm run test`

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app.css                 # Global styles
│   ├── app.html               # HTML template
│   ├── lib/
│   │   ├── services/          # API services
│   │   ├── stores/            # Svelte stores
│   │   └── types/             # TypeScript types
│   └── routes/                # SvelteKit pages
├── tests/                     # Test files
├── static/                    # Static assets
├── package.json
├── vite.config.js
├── svelte.config.js
└── tsconfig.json
```

## 🎨 UI/UX Features

### Design System
- **Theme**: Light/dark mode with CSS variables
- **Colors**: Primary blue (#2563eb), semantic colors
- **Typography**: System fonts with proper hierarchy
- **Spacing**: Consistent 8px grid system

### Components
- **Layout**: Responsive grid with mobile-first approach
- **Navigation**: Sticky header with mobile menu
- **Cards**: Consistent card design for content
- **Forms**: Accessible form controls
- **Loading**: Skeleton screens and spinners

### Responsive Design
- **Mobile**: 320px+ (mobile-first)
- **Tablet**: 768px+ (responsive breakpoints)
- **Desktop**: 1024px+ (full features)

## 🔌 API Integration

### API Service Layer
- **Base URL**: `/api` (proxied in development)
- **Error Handling**: Consistent error responses
- **Type Safety**: Full TypeScript integration
- **Caching**: Browser caching for static assets

### WebSocket Integration
- **Real-time Updates**: Processing status, live results
- **Reconnection**: Automatic reconnection logic
- **Error Handling**: Graceful connection failures

## 🚀 Performance Optimization

### Build Optimizations
- **Code Splitting**: Automatic route-based splitting
- **Tree Shaking**: Unused code elimination
- **Minification**: Production builds minified
- **Compression**: Gzip/Brotli compression

### Runtime Performance
- **Lazy Loading**: Route-based code splitting
- **Image Optimization**: WebP format support
- **Caching**: Aggressive browser caching
- **CDN**: Cloudflare edge caching

## 🔒 Security Considerations

### Content Security Policy
- **CSP Headers**: Configured for XSS protection
- **HTTPS**: Enforced in production
- **Input Validation**: Client-side validation

### API Security
- **CORS**: Properly configured for API calls
- **Authentication**: JWT token handling
- **Rate Limiting**: API rate limiting

## 📊 Monitoring & Analytics

### Error Tracking
- **Console Logging**: Development error logging
- **Error Boundaries**: Graceful error handling
- **Performance Monitoring**: Core Web Vitals

### User Analytics
- **Page Views**: Route change tracking
- **User Interactions**: Button clicks, form submissions
- **Performance Metrics**: Load times, render performance

## 🔄 Migration Notes

### From Vue.js to Svelte
- **State Management**: Pinia → Svelte stores
- **Routing**: Vue Router → SvelteKit routing
- **Components**: Vue components → Svelte components
- **Build System**: Vite (same, different config)

### Benefits Achieved
- **Smaller Bundle**: ~40% reduction in bundle size
- **Better Performance**: No virtual DOM overhead
- **Simpler Code**: Less boilerplate, more readable
- **Type Safety**: Better TypeScript integration

## 🐛 Common Issues & Solutions

### Build Issues
- **Missing Dependencies**: Run `npm install`
- **Type Errors**: Run `npm run check`
- **Lint Errors**: Run `npm run lint`

### Development Issues
- **Hot Reload**: Restart dev server
- **API Errors**: Check backend status
- **WebSocket Issues**: Check connection status

### Deployment Issues
- **Asset Embedding**: Run asset embedding script
- **Worker Errors**: Check worker logs
- **CORS Issues**: Verify API configuration

## 📚 Additional Resources

### Documentation
- [SvelteKit Docs](https://kit.svelte.dev/)
- [Svelte Docs](https://svelte.dev/docs)
- [Vite Docs](https://vitejs.dev/)

### Tools
- [Vitest](https://vitest.dev/) - Testing framework
- [Playwright](https://playwright.dev/) - E2E testing
- [ESLint](https://eslint.org/) - Code linting
- [Prettier](https://prettier.io/) - Code formatting

### Deployment
- [Cloudflare Workers](https://workers.cloudflare.com/)
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/)
- [Cloudflare R2](https://developers.cloudflare.com/r2/)

---

**Last Updated**: 2024-01-XX
**Version**: 1.0.0
**Maintainer**: Development Team 